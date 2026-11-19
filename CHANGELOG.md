# Changelog

## [Unreleased]

## [0.1.0] - 2026-11-19

### Added

- `scripts/price1688.py` with five entry points: `find` / `image` / `keyword` / `category` / `offer`
- Five-step flow: read title facts (twice) → cost tier → image + text search → per-listing check with a three-state verdict decided in code → purchase cost from the first-order tier price, pack conversion and a cost-tier band check
- `scripts/feedback.py` negative-feedback ledger (`add` / `report` / `to-eval`)
- `evals/run_eval.py` with a 20-case frozen set and an optional rolling set; baseline false-pass 0/11, false-reject 2/9
- `install.sh` for Claude Code (default), Codex, OpenClaw or a custom directory

### 中文

- 首个公开版本：五种入口、五步查价（读标题记事实 → 定成本档 → 双路找货 → 逐条核货 → 定采购成本）、负反馈台账、核对器评测、一键安装
