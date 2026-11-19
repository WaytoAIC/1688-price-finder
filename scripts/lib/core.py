"""五步里的判定逻辑:读标题记事实、定成本档、合并候选、逐条核货、定采购成本。

原则:**AI 只记事实、只逐项比对;结论和算钱由代码定**——同一个输入永远得到同一个结论,规则改了一处全改。
"""
import json
import os

from . import llm

HERE = os.path.dirname(os.path.abspath(__file__))
TIERS_PATH = os.path.join(HERE, '..', 'config', 'cost_tiers.json')
MATERIALS = {'纺织布料', '玻璃陶瓷', '金属', '塑料硅胶橡胶', '木竹', '纸', '皮革', '混合', '未知'}
SIZES = {'轻小', '中大件', '大件重货', '未知'}
HOME_CATS = ('Home & Kitchen', 'Tools', 'Office', '家居', '收纳', '五金')


def tiers():
    with open(TIERS_PATH) as fp:
        return json.load(fp)['tiers']


# ---------- ① 读标题记事实 ----------

def _valid(f):
    errs = []
    if f.get('material') not in MATERIALS:
        errs.append(f"material={f.get('material')}")
    if f.get('size_class') not in SIZES:
        errs.append(f"size_class={f.get('size_class')}")
    for k in ('powered', 'fragile', 'kit'):
        if not isinstance(f.get(k), bool):
            errs.append(f'{k} 不是 true/false')
    if not isinstance(f.get('pack_count'), int) or f['pack_count'] < 1:
        errs.append(f"pack_count={f.get('pack_count')}")
    if not str(f.get('evidence') or '').strip():
        errs.append('evidence 为空')
    return errs


def title_facts(title, category=''):
    """AI 读标题两遍。返回 (事实, 成本档, 件数, 先验区间, 人核提示[])。
    两遍定出的成本档或件数不一致 → 标人核(成本档错了,第⑤步的区间校验就会放错)。"""
    rounds = []
    for _ in (1, 2):
        res = llm.align(llm.ask_json('facts.md', {'X': {'title': title, 'category': category}},
                                     model=llm.FACTS_MODEL), ['X'])
        f = res.get('X') or {}
        errs = _valid(f)
        if errs:
            raise llm.LLMError('标题事实不合格:' + '; '.join(errs))
        rounds.append(f)
    a, b = rounds
    ta, tb = tier_from_facts(a, category), tier_from_facts(b, category)
    review = []
    if ta != tb or a['pack_count'] != b['pack_count']:
        review.append(f'两遍不一致:成本档 {ta}/{tb},件数 {a["pack_count"]}/{b["pack_count"]}')
    if a['size_class'] in ('中大件', '大件重货') and (a['powered'] or a['fragile']):
        review.append(f'{a["size_class"]}且{"带电" if a["powered"] else "易碎"}:认证/破损包装另判')
    if '品牌常识' in a['evidence']:
        review.append(f'材质按品牌常识判({a["evidence"]})')
    return a, ta, max(a['pack_count'], 1), tiers()[ta]['band'], review


# ---------- ② 定成本档 ----------

def tier_from_facts(f, category=''):
    """事实 → 成本档。优先级:体积重量 > 纺织 > 带电 > 易碎 > 多件套 > 家居类目 > 默认。
    体积重量最先:大件的成本驱动是体积重量本身,区间上限也最高,取它才是保守端。"""
    if f.get('size_class') in ('中大件', '大件重货'):
        return f['size_class']
    if f['material'] == '纺织布料':
        return '纺织布料床品'
    if f['powered']:
        return '带电小电子'
    if f['fragile'] or f['material'] == '玻璃陶瓷':
        return '玻璃陶瓷易碎'
    if int(f['pack_count'] or 1) > 1 or f.get('kit'):
        return '多件套批量包'
    if any(c in (category or '') for c in HOME_CATS):
        return '小件家居收纳五金'
    return '轻小低客单配件'


# ---------- ③ 双路找货:合并 ----------

def merge(*lists, top=10):
    """各路候选各取前 top 条,按 offerId 去重,配 id。"""
    out, seen = [], set()
    for lst in lists:
        for o in (lst or [])[:top]:
            oid = str(o.get('offerId') or '')
            if oid and oid in seen:
                continue
            seen.add(oid)
            out.append(dict(o, id=f'c{len(out) + 1}'))
    return out


def gen_query(need):
    """需求描述 → 1688 中文搜索词(带款式关键词、不带件数)。"""
    res = llm.align(llm.ask_json('query.md', {'q': need}), ['q'])
    return str(res.get('q') or '').strip() or need


# ---------- ④ 逐条核货 ----------

def verdict_of(v):
    """四项比对 → 通过 / 待人核 / 不通过。任一项矛盾=不通过;款看不出或要求型号却没写=待人核;
    规格/件数「缺失」放行(标题常不写尺寸和装数)。「把握」只留档不进规则——模型一见缺失就填"低",
    按它分流会把一半对的货打成待人核。"""
    if not isinstance(v, dict):
        return '不通过'
    four = [v.get(x) for x in ('款', '规格', '型号', '件数')]
    if '矛盾' in four:
        return '不通过'
    if v.get('款') != '一致' or v.get('型号') == '缺失':
        return '待人核'
    return '通过'


def judge(need, cands, batch=20):
    """给每个候选写「核对」「核对理由」「核对四项」。调用失败抛错——不许把"没核对"当成"没现货"。"""
    for i in range(0, len(cands), batch):
        part = cands[i:i + batch]
        payload = {'q': {'需求': {'细分需求': need},
                         '候选': [{'id': c['id'], '标题': c.get('标题'), '价格': c.get('价格'),
                                   '起订量': c.get('起订量')} for c in part]}}
        res = llm.align(llm.ask_json('judge.md', payload), ['q'])
        got = {str(v.get('id')): v for v in (res.get('q') or []) if isinstance(v, dict)}
        if not got:
            raise llm.LLMError('核对结果为空(模型没按格式返回),本次不可用')
        for c in part:
            v = got.get(c['id'])
            c['核对'] = verdict_of(v)
            c['核对理由'] = (v or {}).get('理由') or ('模型漏判,按不通过' if not v else '')
            c['核对四项'] = {x: (v or {}).get(x) for x in ('款', '规格', '型号', '件数', '把握')}
    return cands


def state_of(cands):
    if any(c.get('核对') == '通过' for c in cands):
        return '通过'
    return '待人核' if any(c.get('核对') == '待人核' for c in cands) else '未找到现货'


# ---------- ⑤ 定采购成本 ----------

def purchase_cost(pick_price, price_usd, tier, pack, fx):
    """首选那家首单档价 → 套装换算 → 先验区间校验。返回 (成本元, 来源, 说明[])。
      套装:单件价×件数 ≤ 售价×0.8 → 按"单件×N 件装"(悲观);否则认为货盘价已是整套价
      区间:成本/售价 落在 [下限×0.5, 上限×1.5] 之外 → 多半搜错规格或件数,弃实测用上限(来源=推算)
      没有核对通过的价 → 直接用上限(来源=推算)"""
    rev = price_usd * fx
    lo, hi = tiers()[tier]['band']
    notes = []
    if pick_price:
        cost, src = pick_price, '1688实价'
        if pack > 1:
            whole = pick_price * pack
            cost, src = (whole, f'1688单件×{pack}件装') if whole <= rev * 0.8 else (pick_price, '1688按整套价')
        share = cost / rev if rev else 0
        if lo * 0.5 <= share <= hi * 1.5:
            return round(cost, 2), src, notes
        notes.append(f'1688 价占售价 {share:.0%},出「{tier}」区间 [{lo:.0%}-{hi:.0%}]±50%:多半搜错规格/件数,弃实测用区间上限')
    else:
        notes.append('没有核对通过的 1688 价,用区间上限估')
    return round(rev * hi, 2), f'推算(区间上限·{tier})', notes
