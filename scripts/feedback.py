#!/usr/bin/env python3
"""负反馈闭环:人发现 AI 找错了 → 记一条 → 定期看错因 → 进评测集 → 改提示词/规则前后跑评测。

  python3 scripts/feedback.py add <run目录> --rank 1 --label 错款 --note "要硅胶,来的是塑料"
  python3 scripts/feedback.py add <run目录> --offer 736375408174 --label 货对
  python3 scripts/feedback.py report [--days 30]        # 按错因计数 + 抽检错放率
  python3 scripts/feedback.py to-eval                  # 人确认过的反馈 → evals/cases-rolling.json

标签:货对 / 规格不对 / 型号不对 / 错款 / 其实有现货 / 价格不对
节奏建议:每周抽 10 条 AI 判"通过"的结果人看一眼打标签(只有人工抽检能测出真实错放率——模型认不出自己错);
每月挑计数最多的一类错因改一处,改前改后跑 evals/run_eval.py,冻结集错放率不许升。
"""
import argparse
import csv
import json
import os
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
LEDGER = os.path.join(ROOT, 'feedback', 'ledger.csv')
ROLLING = os.path.join(ROOT, 'evals', 'cases-rolling.json')
LABELS = ('货对', '规格不对', '型号不对', '错款', '其实有现货', '价格不对')
COLS = ('时间', 'run', 'offerId', 'AI结论', '需求', '候选标题', '候选价', '标签', '备注', '已入评测')


def rows():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding='utf-8-sig') as fp:
        return list(csv.DictReader(fp))


def write(rs):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=COLS)
        w.writeheader()
        w.writerows(rs)


def add(a):
    res = json.load(open(os.path.join(a.run, 'result.json')))
    cands = json.load(open(os.path.join(a.run, 'candidates.json')))
    if a.offer:
        c = next((x for x in cands if str(x.get('offerId')) == str(a.offer)), None)
    else:
        r = (res.get('结果') or [None] * a.rank)[a.rank - 1] if res.get('结果') else None
        c = next((x for x in cands if r and str(x.get('offerId')) == str(r.get('offerId'))), None)
    if not c and a.label != '其实有现货':
        raise SystemExit('在这次结果里找不到这家货盘:用 --rank(结果里第几家)或 --offer <offerId>')
    q = res.get('查询') or {}
    rs = rows()
    rs.append({'时间': datetime.now().strftime('%Y-%m-%d %H:%M'), 'run': os.path.relpath(a.run, ROOT),
               'offerId': (c or {}).get('offerId', ''), 'AI结论': (c or {}).get('核对', res.get('寻源状态')),
               '需求': q.get('need') or q.get('title') or '', '候选标题': (c or {}).get('标题', ''),
               '候选价': (c or {}).get('价格', ''), '标签': a.label, '备注': a.note or '', '已入评测': ''})
    write(rs)
    print(f'已记 1 条反馈({a.label}),台账共 {len(rs)} 条 → feedback/ledger.csv')


def report(a):
    since = (datetime.now() - timedelta(days=a.days)).strftime('%Y-%m-%d')
    rs = [r for r in rows() if r['时间'] >= since]
    cnt = {}
    for r in rs:
        cnt[r['标签']] = cnt.get(r['标签'], 0) + 1
    passed = [r for r in rs if r['AI结论'] == '通过']
    bad = [r for r in passed if r['标签'] in ('规格不对', '型号不对', '错款', '价格不对')]
    print(f'近 {a.days} 天反馈 {len(rs)} 条:' + ('、'.join(f'{k} {v}' for k, v in sorted(cnt.items(), key=lambda x: -x[1])) or '无'))
    if passed:
        rate = len(bad) / len(passed)
        print(f'AI 判通过、人复核过 {len(passed)} 条,其中错 {len(bad)} 条 → 错放率 {rate:.0%}'
              + ('  ⚠ 超过 10%,建议立刻做一次错误分析' if rate > 0.10 else ''))
    top = max(cnt.items(), key=lambda x: x[1]) if cnt else None
    if top and top[0] != '货对':
        print(f'下次迭代先改这一类:{top[0]}({top[1]} 条)')


def to_eval(a):
    roll = json.load(open(ROLLING)) if os.path.exists(ROLLING) else {'说明': '人确认过的线上反馈,与冻结集分开计分', '用例': []}
    rs, n = rows(), 0
    for r in rs:
        if r['已入评测'] or not r['候选标题'] or r['标签'] not in LABELS[:4]:
            continue
        roll['用例'].append({'key': f"r{len(roll['用例']) + 1}", '需求': r['需求'],
                           '候选': {'标题': r['候选标题'], '价格': r['候选价']},
                           '标注': r['标签'], '应通过': r['标签'] == '货对', '来源': r['run']})
        r['已入评测'] = 'y'
        n += 1
    json.dump(roll, open(ROLLING, 'w'), ensure_ascii=False, indent=1)
    write(rs)
    print(f'滚动评测集新增 {n} 条,共 {len(roll["用例"])} 条 → evals/cases-rolling.json')


def main():
    ap = argparse.ArgumentParser(description='1688 查价负反馈台账')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add')
    p.add_argument('run', help='price1688-runs/ 下那次查询的目录')
    p.add_argument('--rank', type=int, default=1, help='结果里第几家(默认 1)')
    p.add_argument('--offer', help='或直接给 offerId(候选里任一家)')
    p.add_argument('--label', required=True, choices=LABELS)
    p.add_argument('--note')
    p.set_defaults(func=add)
    p = sub.add_parser('report')
    p.add_argument('--days', type=int, default=30)
    p.set_defaults(func=report)
    sub.add_parser('to-eval').set_defaults(func=to_eval)
    a = ap.parse_args()
    a.func(a)


if __name__ == '__main__':
    main()
