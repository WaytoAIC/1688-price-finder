# Changelog

## [Unreleased]

## [0.1.1] - 2026-11-25

### Changed

- Checker prompt (`scripts/prompts/judge.md`) v2 → v3, pack-count item only: it now checks whether the listing is the same combination and no longer compares quantities. An N-pack need against a single-piece listing (or another count, or no count stated) is consistent, and the minimum order quantity is not a pack count. It is a conflict only when the combination differs: the need is a kit of different items and the listing is just one of them, or the need is a single item and the listing bundles something else. A consistent pack count says nothing about style, spec or model fit, which are still judged on their own. The style / spec / model items, confidence, output format, `verdict_of` and the default model are unchanged
- Why: v2 said "single-piece listing = consistent", but its only counter-example ("a 27-piece bracelet set vs a single extension chain = conflict", which is also eval case p19) read as "N-pack vs single piece = conflict", so the model kept rejecting multi-pack needs against single-piece listings and sometimes took the MOQ for the pack count. v3's counter-example is a cocktail kit that is not in the eval set
- Frozen set, `claude-sonnet-4-6`, two v3 runs against a same-day v2 run: false-pass 0/11 → 0/11 and 0/11; false-reject 3/9 → 1/9 and 0/9 (both pack-count rejections gone; the case that flips is a style call). `evals/baseline.json` re-recorded on v3. Internal 115 labelled rows, same comparison: false-pass 1/87 → 1/87, false-reject 19/28 → 12/28

### 中文

- 核对提示词（`scripts/prompts/judge.md`）v2 → v3，只改第 4 项「件数」：只判是不是同一种组合、不比数量。需求 N 件装、货盘单件（或别的件数、没写几件）=一致，起订量和件数无关；组合不同才矛盾：需求是几样不同东西配成的套装、货盘只是其中一样，或需求是单样东西、货盘却搭了别的东西一起卖。件数一致只说明组合对得上，款/规格/型号照前三项单独判。款/规格/型号三项、把握、输出格式、`verdict_of`、默认模型都没动
- 起因：v2 写了「单件货盘=一致」，唯一的反例「要 27 件手链套装、来的是单条延长链=矛盾」（也就是评测用例 p19）读起来却像「N 件装 vs 单件=矛盾」，模型常把多件装需求配单件货盘判矛盾，有时还把起订量当件数。v3 的反例换成评测集里没有的调酒套装
- 评测（冻结集，`claude-sonnet-4-6`，v3 两遍对比同日 v2）：错放 0/11 → 0/11、0/11；错杀 3/9 → 1/9、0/9（两条件数误杀都救回，来回翻的那条是款的判断）。`evals/baseline.json` 已按 v3 重记。内部 115 条真实标注同样对比：错放 1/87 → 1/87，错杀 19/28 → 12/28

## [0.1.0] - 2026-11-19

### Added

- `scripts/price1688.py` with five entry points: `find` / `image` / `keyword` / `category` / `offer`
- Five-step flow: read title facts (twice) → cost tier → image + text search → per-listing check with a three-state verdict decided in code → purchase cost from the first-order tier price, pack conversion and a cost-tier band check
- `scripts/feedback.py` negative-feedback ledger (`add` / `report` / `to-eval`)
- `evals/run_eval.py` with a 20-case frozen set and an optional rolling set; baseline false-pass 0/11, false-reject 2/9
- `install.sh` for Claude Code (default), Codex, OpenClaw or a custom directory

### 中文

- 首个公开版本：五种入口、五步查价（读标题记事实 → 定成本档 → 双路找货 → 逐条核货 → 定采购成本）、负反馈台账、核对器评测、一键安装
