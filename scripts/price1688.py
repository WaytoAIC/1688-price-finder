#!/usr/bin/env python3
"""1688 查价:读标题记事实 → 定成本档 → 双路找货 → 逐条核货 → 定采购成本。到询盘之前为止。

手上有什么用什么:
  find      一句需求描述,或竞品标题(+可选主图 URL)→ 两路召回 + 核对 + 前几家拉详情     ← 最常用
  image     图片 URL(公网可访问,≤1MB)→ 以图搜款
  keyword   中文品名/搜索词 → 名称搜(自带阶梯价)
  category  只知道品类 → 本地类目树找节点 → 条件搜(按 30 天销量/价格筛)
  offer     1688 链接或 offerId → 详情阶梯价 + 每个 SKU 的价与包装尺寸重量

  python3 scripts/price1688.py find --need "Model Y 焕新版屏幕下方储物盒" --image <主图URL>
  python3 scripts/price1688.py find --title "<竞品英文标题>" --price 26.99      # 完整五步:含成本档与采购成本
  python3 scripts/price1688.py keyword "帆布 拉链 化妆包" --need "空白帆布拉链化妆包"
  python3 scripts/price1688.py category 收纳盒 --min-sales 100 --price-max 30 --need "..."
  python3 scripts/price1688.py offer https://detail.1688.com/offer/736375408174.html

结果写到 ./price1688-runs/<日期>/<编号>/:result.csv/json(前几家)、candidates.json(全部候选+核对理由)、
各接口原始响应。价格是 1688 面价:不含定制、打样、运费,不等于到手成本。
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import core, llm, sorftime as sf  # noqa: E402

CACHE = os.path.expanduser(os.environ.get('PRICE1688_CACHE', '~/.cache/price1688'))


def offer_id(s):
    s = str(s or '').strip()
    if s.isdigit():
        return s
    m = re.search(r'/offer/(\d+)', s) or re.search(r'offerId=(\d+)', s)
    return m.group(1) if m else None


def hires(url):
    """Amazon 缩略图(_AC_US600_ 等)换高清:缩略图上 1688 容易认错图里的主体。"""
    u = str(url or '')
    if 'media-amazon.com' in u or 'ssl-images-amazon.com' in u:
        return re.sub(r'\._[A-Za-z0-9_,+-]+_\.(jpg|jpeg|png)$', r'._AC_SL1000_.\1', u)
    return u


def estimate(args):
    q = sf.QUOTA
    n = {'find': (q['ProductSearchFromImage'] if getattr(args, 'image', None) else 0) + q['ProductSearchFromName'],
         'image': q['ProductSearchFromImage'], 'keyword': q['ProductSearchFromName'],
         'category': q['ProductSearch'], 'offer': 0}[args.cmd]
    n += (1 if args.cmd == 'offer' else args.detail) * (q['ProductRequest'] + q['ProductVariations'])
    return n


def run(args, cands, need, facts):
    out, qty = args.out, args.qty
    cands = [dict(c, id=c.get('id') or f'c{i + 1}') for i, c in enumerate(cands)]
    if need and cands:
        core.judge(need, cands)
        state = core.state_of(cands)
        picks = [c for c in cands if c['核对'] == '通过'][:args.detail]
    else:
        for c in cands:
            c['核对'] = '未核对'
        state, picks = ('未核对' if cands else '无候选'), cands[:args.detail]
    with open(os.path.join(out, 'candidates.json'), 'w') as fp:
        json.dump(cands, fp, ensure_ascii=False, indent=1)
    rows = []
    for c in picks:
        oid = offer_id(c.get('offerId')) or offer_id(c.get('链接'))
        if not oid:
            continue
        try:
            d = sf.detail(oid, out, qty)
        except sf.SorftimeError as e:
            print(f'  ⚠ {oid} 详情失败:{e}')
            d = {'offerId': oid, '链接': f'https://detail.1688.com/offer/{oid}.html'}
        # 部分货盘 sorftime 没收录报价(详情 Price=0、SKU 无数据)→ 回落搜索列表价,并标来源
        if d.get('首单档价'):
            d['价格来源'] = f'详情阶梯价(买{qty}件那一档)'
        elif c.get('价格'):
            d['首单档价'], d['价格来源'] = c['价格'], '列表价(详情无报价)'
        else:
            d['价格来源'] = '无报价'
        for k in ('标题', '供应商', '发货地', '起订量'):
            d[k] = d.get(k) or c.get(k)
        d.update({'召回来源': c.get('来源'), '列表价': c.get('价格'), '核对': c['核对'], '核对理由': c.get('核对理由')})
        rows.append(d)
    cost = None
    if facts and args.price:
        f, tier, pack, band, review = facts
        pick = rows[0]['首单档价'] if rows and rows[0]['核对'] == '通过' else None
        c, src, notes = core.purchase_cost(pick, args.price, tier, pack, args.fx)
        cost = {'采购成本(元)': c, '来源': src, '说明': notes, '占售价': round(c / (args.price * args.fx), 3),
                '成本档': tier, '件数': pack, '先验区间': band}
    res = {'时间': datetime.now().isoformat(timespec='seconds'),
           '查询': {k: v for k, v in vars(args).items() if k != 'out'}, '寻源状态': state,
           '标题事实': facts[0] if facts else None, '成本档': facts[1] if facts else None,
           '件数': facts[2] if facts else None, '人核提示': facts[4] if facts else [],
           '采购成本': cost, '候选数': len(cands), '结果': rows,
           '价格口径': f'首单档价=详情阶梯价按买 {qty} 件取档;1688 面价,不含定制/打样/运费'}
    with open(os.path.join(out, 'result.json'), 'w') as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1, default=str)
    cols = ['核对', '首单档价', '价格来源', '阶梯价', '起订量', 'SKU价区间', '包装cm', '重量kg', '供应商', '发货地',
            '近30天销量', '召回来源', '核对理由', '链接', '标题']
    with open(os.path.join(out, 'result.csv'), 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    n_ok = sum(c.get('核对') == '通过' for c in cands)
    n_pend = sum(c.get('核对') == '待人核' for c in cands)
    print(f'\n寻源状态:{state} | 候选 {len(cands)} 条,通过 {n_ok},待人核 {n_pend}')
    for i, r in enumerate(rows, 1):
        print(f"  {i}. [{r['核对']}] ¥{r.get('首单档价')}({r.get('价格来源')}) 起订{r.get('起订量')} "
              f"SKU价{r.get('SKU价区间')} {str(r.get('供应商') or '')[:16]} | {str(r.get('标题') or '')[:28]}\n"
              f"     {r['链接']}  {r.get('核对理由') or ''}")
    if facts:
        f = facts[0]
        print(f"① 标题事实:材质{f['material']} 体积{f['size_class']} 带电{f['powered']} 易碎{f['fragile']} "
              f"件数{facts[2]}({f['evidence']})")
        print(f"② 成本档:{facts[1]},先验区间(采购价/售价){facts[3][0]:.0%}~{facts[3][1]:.0%}"
              + (f";⚠ 人核:{'; '.join(facts[4])}" if facts[4] else ''))
    if cost:
        print(f"⑤ 采购成本:¥{cost['采购成本(元)']}({cost['来源']},占售价 {cost['占售价']:.0%})"
              + (f";{'; '.join(cost['说明'])}" if cost['说明'] else ''))
    if state in ('未找到现货', '待人核') and need:
        print('  → 没有一家完全对上:多半要定制或型号小众,下一步是询盘')
    print(f'结果:{os.path.relpath(out)}/result.csv')
    return res


def main():
    ap = argparse.ArgumentParser(description='1688 查价(到询盘之前)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, hlp in (('find', '需求描述或竞品标题:两路召回+核对+详情'), ('image', '图片 URL'),
                      ('keyword', '中文品名/搜索词'), ('category', '只知道品类'), ('offer', '1688 链接或 offerId')):
        p = sub.add_parser(name, help=hlp)
        if name != 'find':
            p.add_argument('target')
        if name == 'find':
            p.add_argument('--image', help='主图 URL(公网可访问)')
        if name == 'category':
            p.add_argument('--node', help='直接给 NodeId')
            p.add_argument('--min-sales', type=int)
            p.add_argument('--price-min', type=float)
            p.add_argument('--price-max', type=float)
        p.add_argument('--need', help='要找的货:款、关键规格、适配型号、件数。给了才做 AI 核对')
        p.add_argument('--title', help='竞品标题:做①读标题记事实 ②定成本档(没给 --need 时也当需求用)')
        p.add_argument('--category-path', help='竞品类目路径(定档参考,可空)')
        p.add_argument('--price', type=float, help='售价 USD:做⑤定采购成本(需同时给 --title)')
        p.add_argument('--fx', type=float, default=7.2, help='美元兑人民币汇率,默认 7.2')
        p.add_argument('--qty', type=int, default=100, help='首单量,决定取哪一档阶梯价,默认 100')
        p.add_argument('--detail', type=int, default=3, help='通过的前几家拉详情+SKU(每家 2 req),默认 3')
        p.add_argument('--out')
        p.add_argument('--dry-run', action='store_true', help='只报预计配额')
    args = ap.parse_args()
    if args.cmd == 'find' and not (args.need or args.title):
        ap.error('find 要给 --need(要找什么)或 --title(竞品标题)')
    print(f'预计 sorftime 配额 ≤{estimate(args)} req(核对与读标题调 Claude)')
    if args.dry_run:
        return
    slug = re.sub(r'[^\w一-龥-]+', '_', str(getattr(args, 'target', '') or args.need or args.title or ''))[:24]
    args.out = args.out or os.path.join('price1688-runs', date.today().isoformat(),
                                        f'{datetime.now():%H%M%S}-{args.cmd}-{slug}')
    os.makedirs(args.out, exist_ok=True)
    try:
        facts = core.title_facts(args.title, args.category_path or '') if args.title else None
        if args.price and not facts:
            print('  ⚠ 给了 --price 但没给 --title:成本档和件数要从竞品标题来,跳过⑤')
        need = args.need or args.title
        qty = args.qty
        if args.cmd == 'offer':
            oid = offer_id(args.target)
            if not oid:
                ap.error('认不出 offerId:给 detail.1688.com/offer/<数字>.html 或纯数字')
            cand = {'offerId': oid, '链接': f'https://detail.1688.com/offer/{oid}.html', '来源': '链接'}
            if need:
                d = sf.detail(oid, args.out, qty)
                cand.update({'标题': d['标题'], '价格': d['首单档价'], '起订量': d['起订量']})
            args.detail = 1
            return run(args, [cand], need, facts)
        if args.cmd == 'image':
            return run(args, sf.search_image(hires(args.target), args.out, qty)[:20], need, facts)
        if args.cmd == 'keyword':
            return run(args, sf.search_name(args.target, args.out, qty)[:20], need, facts)
        if args.cmd == 'category':
            node = args.node
            if not node:
                hits = sf.find_nodes(sf.category_tree(os.path.join(CACHE, 'cattree.json')), args.target)
                if not hits:
                    ap.error(f'类目树里没有含「{args.target}」的类目')
                for i, (nid, path) in enumerate(hits, 1):
                    print(f'  {i}. {nid}  {path}')
                node = hits[0][0]
                print(f'用第 1 个:{hits[0][1]}(不对就加 --node <NodeId>)')
            return run(args, sf.search_category(node, args.out, qty, args.min_sales, args.price_min,
                                                args.price_max)[:20], need, facts)
        img = sf.search_image(hires(args.image), args.out, qty) if args.image else []
        q = core.gen_query(need)
        print(f'搜索词:{q}')
        txt = sf.search_name(q, args.out, qty)
        return run(args, core.merge(img, txt), need, facts)
    except (llm.LLMError, sf.SorftimeError) as e:
        sys.exit(f'✗ {e}\n  原始响应已存 {args.out};核对或读标题失败时结果不可用,别把"没核对"当成"没现货"')


if __name__ == '__main__':
    main()
