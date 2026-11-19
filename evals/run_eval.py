#!/usr/bin/env python3
"""核对器评测:改提示词 / 换模型 / 改 verdict_of 规则前后各跑一次。

  python3 evals/run_eval.py                    # 默认模型(PRICE1688_MODEL)
  python3 evals/run_eval.py --model claude-sonnet-4-6
  python3 evals/run_eval.py --set-baseline     # 把这次结果记为基线

主指标 错放率 = 应不通过却判通过 / 应不通过总数(错放一条 = 一条点开是别的货的链接 + 一个错的成本)。
副指标 错杀率 = 应通过却没判通过 / 应通过总数(代价只是多问一次供应商)。
cases.json = 冻结集(只增不改);cases-rolling.json = 线上反馈攒的滚动集,单独计分。
"""
import argparse
import json
import os
import sys
from datetime import datetime

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, '..', 'scripts'))
from lib import core, llm  # noqa: E402


def load(name, tag):
    p = os.path.join(D, name)
    return [dict(c, 集=tag) for c in json.load(open(p))['用例']] if os.path.exists(p) else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model')
    ap.add_argument('--set-baseline', action='store_true')
    a = ap.parse_args()
    if a.model:
        llm.MODEL = a.model
    cases = load('cases.json', '冻结') + load('cases-rolling.json', '滚动')
    for c in cases:                                   # 一条用例 = 一个需求 + 一个候选,逐条判
        cand = [{'id': 'c1', '标题': c['候选']['标题'], '价格': c['候选'].get('价格'), '起订量': None}]
        core.judge(c['需求'], cand)
        c['判'], c['理由'] = cand[0]['核对'], cand[0]['核对理由']
    res = {'时间': datetime.now().isoformat(timespec='seconds'), '模型': llm.MODEL}
    for tag in ('冻结', '滚动'):
        cs = [c for c in cases if c['集'] == tag]
        if not cs:
            continue
        neg = [c for c in cs if not c['应通过']]
        pos = [c for c in cs if c['应通过']]
        fp = [c for c in neg if c['判'] == '通过']
        fn = [c for c in pos if c['判'] != '通过']
        res[tag] = {'条数': len(cs), '错放': len(fp), '错放率': round(len(fp) / len(neg), 3) if neg else None,
                    '错杀': len(fn), '错杀率': round(len(fn) / len(pos), 3) if pos else None}
        print(f"{tag}集 {len(cs)} 条:错放 {len(fp)}/{len(neg)}  错杀 {len(fn)}/{len(pos)}")
        for c in fp:
            print(f"  错放 [{c['标注']}] {c['需求'][:24]} ← {c['候选']['标题'][:30]}")
        for c in fn:
            print(f"  错杀 {c['需求'][:24]} ← {c['候选']['标题'][:30]}  理由:{c['理由']}")
    os.makedirs(os.path.join(D, 'outputs'), exist_ok=True)
    with open(os.path.join(D, 'outputs', res['时间'].replace(':', '') + '.json'), 'w') as fp:
        json.dump({**res, '明细': cases}, fp, ensure_ascii=False, indent=1)
    base = os.path.join(D, 'baseline.json')
    if a.set_baseline:
        json.dump(res, open(base, 'w'), ensure_ascii=False, indent=1)
        print('已记为基线')
    elif os.path.exists(base) and '冻结' in res:
        b = json.load(open(base))['冻结']
        worse = res['冻结']['错放率'] > b['错放率']
        print(f"基线错放率 {b['错放率']:.1%} → 本次 {res['冻结']['错放率']:.1%}  "
              + ('⚠ 变差了,别合这次改动' if worse else '✓ 没变差'))


if __name__ == '__main__':
    main()
