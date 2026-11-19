## 🚀 Way to AIC | 通往 AI 电商之路
---
### 🌐 官网 Website
- https://waytoaic.com
- https://www.waytoaic.com
---

### 👥 社群招募 Community
`Way to AIC 社群招募 | WaytoAIC.com`

<p align="center">
  <img src="https://github.com/user-attachments/assets/d9f8bbf4-2056-4780-975d-86c885b52bab" width="70%">
</p>

---

### 📣 公众号 WeChat Official Account
`维正 WaytoAIC`

<p align="center">
  <img src="https://github.com/user-attachments/assets/71c71a5c-e68a-4f30-9afb-f2b056619991" width="300">
</p>

---

### 🧠 知识星球 Xiaozhixing
`AI电商之路 WaytoAIC`

<p align="center">
  <img src="https://github.com/user-attachments/assets/9eccef07-0e84-45a7-a415-affcb18c928d" width="200">
  <img src="https://github.com/user-attachments/assets/4e99fbc3-1981-4fee-b113-c9821141102d" width="400">
</p>

---

### 🧩 About Way to AIC

**AIC = AI Commerce**

在 AI 重塑商业的时代，我们希望和每一个拥抱 AI 的卖家：

- 找到场景
- 定义问题
- 积累能力
- 设计系统

共同通往 AI 电商之路。

> Way to AIC 不是教学，不是工具，
> 而是一条所有电商人共同走的进化之路。

### WaytoAIC 理念 | Principles

| 中文 | English |
|---|---|
| 场景先于方法 | Context before method |
| AI 的价值来自真实业务场景，而不是技术本身。 | AI creates value through real business contexts, not through technology alone. |
| 问题先于答案 | Problem before answer |
| 定义问题，比拥有工具更重要。 | Defining the problem matters more than collecting tools. |
| 系统胜过技巧 | System over tricks |
| 技巧是术，系统才是道，决定卖家的上限。 | Tricks are tactical; systems define long-term leverage and ceiling. |
| 共创优于独行 | Co-creation over solo progress |
| 我们相信，真正的进化发生在共同探索的过程中。 | Real evolution happens through shared exploration. |

---

# 1688 查价 1688 Price Finder（Claude Code Skill）

给跨境卖家用的 1688 查价工具：从竞品标题或一句需求描述出发，双路找货、AI 核对是不是同款、拉阶梯价和 SKU 价，最后按成本档和件数定出采购成本。到询盘之前为止。

```
竞品标题 ─①读标题记事实─②定成本档──────────────────────────┐
                                                             ▼
需求/图片/品名/品类/链接 ─③双路找货─④逐条核货─详情阶梯价/SKU─⑤定采购成本
```

## 为什么做成这样

我们在自己的选品流程里体检过：AI 直接用 1688 图搜「相似度最高」的那家写进表，115 条里只有 24% 货对，50% 完全是另一种东西（防水床单搜成信封、纸巾搜成地毯）。原因有三个：

1. **相似度是整次搜索共用的分数**，不是逐条打分，越高反而越容易错
2. **没有一步核对「1688 标题 = 我们要的货」**
3. **用了缩略图搜**，1688 认错了图里的主体

这个工具的做法：高清图 + 文字双路找货 → AI 只做逐项比对（款/规格/型号/件数），结论由代码按固定规则定 → 只用核对通过的货盘取价 → 价格再用成本档区间兜底。

## 安装

一键安装（默认装进 Claude Code 的 `~/.claude/skills/1688-price-finder`）：

```bash
curl -fsSL https://raw.githubusercontent.com/WaytoAIC/1688-price-finder/main/install.sh | bash
```

固定版本：

```bash
curl -fsSL https://raw.githubusercontent.com/WaytoAIC/1688-price-finder/v0.1.0/install.sh | bash -s -- --ref v0.1.0
```

其他位置：`--target codex` / `--target openclaw` / `--dest <目录>`。注意核对和读标题固定调用 `claude -p`，所以不管装在哪，机器上都要有已登录的 Claude Code。

依赖：

- [sorftime](https://www.sorftime.com) CLI 与 API Key（1688 数据来源，按请求计费）：`sorftime add <名字> <API Key>`
- [Claude Code](https://claude.com/claude-code) 已登录（核对和读标题调用 `claude -p`）
- Python 3.9+（只用标准库）

装好后在 Claude Code 里说「查一下这个品 1688 多少钱」即可触发，也可以直接跑命令，用法见 [SKILL.md](SKILL.md)。

## 快速试一下

```bash
cd ~/.claude/skills/1688-price-finder
python3 scripts/price1688.py offer https://detail.1688.com/offer/736375408174.html          # 2 req
python3 scripts/price1688.py find --need "空白帆布拉链化妆包" --detail 2                     # 约 6 req
python3 scripts/price1688.py find --title "<竞品英文标题>" --price 19.99                     # 完整五步
```

## 目录

| 路径 | 内容 |
|---|---|
| `scripts/price1688.py` | 主命令：find / image / keyword / category / offer |
| `scripts/lib/` | sorftime 接口、Claude 调用、五步判定逻辑 |
| `scripts/prompts/` | 读标题、写搜索词、逐条核对三份提示词 |
| `scripts/config/cost_tiers.json` | 8 个成本档的「采购价占售价」先验区间——**按你自己的品类校准** |
| `scripts/feedback.py` | 负反馈台账：记错 → 按错因统计 → 进评测集 |
| `evals/` | 核对器评测：20 条自拟示例 + 你自己的滚动集 |

## 准确率与局限

- 我们内部 115 条真实标注上：核对器错放率（错货判成对）约 2%，错杀率（对货没判通过）30–45%。错杀多是标题信息不够被判"待人核"，代价是多看一眼
- 结果只能当初筛，**下单前必须人看**；「未找到现货」不等于 1688 真没有，可能只是标题写法不同
- 价格是 1688 面价，不含定制、打样、运费；包装尺寸重量多为商家自填
- 自带的评测集是自拟的通用商品，用来跑通流程；真实效果请用你自己的反馈攒滚动集来测

---

## English

A Claude Code skill for cross-border sellers to check 1688.com sourcing prices. Start from a competitor's Amazon title or a one-line need, search 1688 by image and by text, let the AI check whether each listing is really the same product, pull tier prices and SKU prices, and set a purchase cost from a cost tier and pack count. It stops before contacting suppliers.

### Why it works this way

In our own product-selection pipeline, writing in the 1688 image-search result with the highest "similarity" gave the right product in only 24% of 115 rows; 50% were a different item entirely. Three causes:

1. **The similarity score is shared by the whole search**, not scored per listing — the higher it was, the more often it was wrong
2. **Nothing checked that the 1688 title matched the product we wanted**
3. **Thumbnails were used for image search**, so 1688 recognised the wrong subject

This tool: high-res image + text search → the AI only compares item by item (style / spec / model fit / pack count) and fixed code rules decide the verdict → only verified listings are priced → the price is sanity-checked against the cost-tier band.

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/WaytoAIC/1688-price-finder/main/install.sh | bash
```

Pin a version with `--ref v0.1.0`; install elsewhere with `--target codex`, `--target openclaw` or `--dest <dir>`. The checker always calls `claude -p`, so a logged-in Claude Code CLI is required wherever it is installed.

Requirements: [sorftime](https://www.sorftime.com) CLI with an API key (the 1688 data source, billed per request), a logged-in [Claude Code](https://claude.com/claude-code), Python 3.9+ (standard library only).

### Entry points

| You have | Command |
|---|---|
| Competitor title + price (all five steps) | `python3 scripts/price1688.py find --title "<title>" --price 26.99` |
| A one-line need | `python3 scripts/price1688.py find --need "..."` |
| An image URL | `python3 scripts/price1688.py image <URL> --need "..."` |
| A Chinese keyword | `python3 scripts/price1688.py keyword "..." --need "..."` |
| Only a category | `python3 scripts/price1688.py category <name> --need "..."` |
| A 1688 link or offerId | `python3 scripts/price1688.py offer <link>` |

Results go to `price1688-runs/<date>/<id>/` (`result.csv`, `result.json`, `candidates.json`, raw API responses). Prompts and the checker's output are in Chinese, because 1688 listings are.

### Accuracy and limits

- On our internal 115 labelled rows the checker's false-pass rate (wrong item judged right) is about 2%; its false-reject rate is 30–45%, mostly titles too vague to decide, which only costs a second look
- Treat results as a first screen — **a person must look before ordering**. "No stock found" does not prove 1688 has none
- Prices are 1688 list prices, excluding customisation, samples and freight; package size/weight is seller-entered
- The bundled eval set (20 self-written generic cases) only proves the pipeline runs; build your own rolling set from feedback (`scripts/feedback.py`) to measure real accuracy

## License

MIT
