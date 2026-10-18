# 罗马尼亚、法国财经新闻推送

开盘指标新增节点与当前数据缺口见 [OPENING_INDICATORS.md](OPENING_INDICATORS.md)。开盘指标专报与原半点新闻分别去重；免费延迟报价不等于实时行情。

免费运行的 GitHub Actions + 官方 RSS/Atom 新闻机器人。按用户最新要求，**新闻标题和摘要免费翻译为简体中文**，标注机译并保留官方原文链接、来源和时间；中文市场影响仍为条件性关注提示，不是行情验证或投资结论。不调用收费模型或付费翻译 API，不需要 API Key。

使用 Google 公共网页翻译接口自动识别英语、法语、罗马尼亚语等原文，目标为 `zh-CN`；这不是付费 Cloud Translation API。该公开接口无可用性保证，失败时明确标注「免费翻译暂不可用」并保留原文，避免漏报或将错误响应冒充译文。机译不等于事实核验，以官方原文为准。

只向翻译服务传递公开 RSS 标题和摘要。按原文内容缓存译文，法国和罗马尼亚复用同一条译文，GitHub Actions Cache 跨运行复用；失败不缓存、当次运行不反复请求失效服务。原定推送节点、选稿数量、去重和发送账本逻辑不变。

## 两国配套美股新闻与事件影响

- 两国选稿均纳入 Nasdaq Markets（含署名转载）、WSJ Markets 公开 RSS 摘要及 SEC 公告；美联储与 BLS 继续提供美国宏观背景。只读取公开摘要，不绕过付费全文或访问限制。
- 在原定晨报最多6条、小时快报最多3条内，有合格新消息时优先各保留一条本国新闻、一条美股事件；美股暂缺时可配美国宏观事件。时效窗口、各国独立去重和推送时间不变，不用旧闻补数量。
- 按原文及来源识别美国利率、通胀、就业、增长、贸易、财报、科技、能源、银行、证券监管和指数事件。只把存在美国事件依据的文章算作美股配稿；明显股票对比、荐股问句及部分预测标题不占事件名额。
- 每条美国事件标明事件类型、原文关键词依据和分析性质。法国关注 CAC 40、EUR/USD、法国国债、出口及行业链；罗马尼亚关注 BET、RON、BNR、国债、能源和欧盟供应链。影响为条件性传导分析，不冒称已验证的涨跌因果或企业实际损失。
- 发布机构报道与官方机构公告区别标记；保留 RSS 作者/供稿及来源原文链接，中文仍由免费机译生成。没有符合条件的美国新事件时明确说明缺口。
- `news_coverage.py` 另列两国晨报、小时快报选中的美股事件数，区分美股与美国宏观覆盖；这些数字不代表实际发送回执。

## 运行方式

- `finance-news.yml`：抓取、测试和预览，始终 `DRY_RUN=true`、只读权限、无 Telegram 密钥。
- `finance-news-live.yml`：正式发送入口，每小时UTC第8、18、28、38、48、58分钟唤醒，无额外启用变量。只允许 main 分支；也可手动运行。
- 两国分别按当地时间 07:30 晨报，此后 08:30、09:30……每小时筛选快报，允许在当小时后半小时内延迟启动；正式入口每10分钟错峰唤醒，晨报与小时快报的发布窗口仍由两国当地时间判断。周一晨报回看 72 小时，其他晨报 18 小时，快报 6 小时。GitHub 调度可能延迟，不保证准点送达。
- 无合格新闻不发送。法国与罗马尼亚独立选稿、去重，同一新闻可以分别向两国发布。

### 备用定时触发方案（待审批，未上线）

GitHub 原生 cron 暂未产生运行记录，拟增加 ChatGPT「新闻备用触发」任务，按每小时半点更新 `ops/news-dispatch.json`，由 `news-dispatch-bridge.yml` 调用同一个 `finance-news-live.yml`。原 cron、两国当地时间窗口、内容和接收群不变，账本和串行锁继续防重复。备用任务在两国均不处于发送窗口时不写请求；若已有本时段正常正式运行，也不重复请求。

请求只包含公开时间戳和请求编号，30 分钟后失效；桥接入口没有 Telegram 密钥，也不能改目标工作流、分支或群。只有正式工作流处理选稿和发送。GitHub Actions 中的 `workflow_dispatch` 是正式备用触发，不应冒称原生 `schedule` 已恢复。停用正式工作流会同时阻止桥接发送；如要停止备用检查，也需暂停 ChatGPT 对应任务。

## 首次启用

1. 在仓库 Secrets 配置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，不要在聊天或代码中粘贴。
2. 手动运行现有 `Telegram one-time connectivity test`，填写 `SEND_ONE_TEST`，核对目标群收到测试消息。
3. 在新闻时段手动运行 `Telegram finance news (scheduled delivery)`，核对分国消息及 `state/live_ledger.json` 的回执。无新新闻或不在时段不会强行发送。
4. 定时发送随工作流生效；如需暂停，在 GitHub Actions 中禁用该发送工作流，正在运行的任务需另行取消。

正式工作流使用内置 `github.token` 写账本，无需长期 GitHub PAT。若分支保护禁止 Actions 更新账本，程序会在发送前停止，需调整账本存储方案。

## 中断与人工对账

正式账本是 `state/live_ledger.json`；预览的 `state/sent.json` 不代表实际送达。发请求前登记 `sending`，收到 Telegram `message_id` 才标记 `sent`。同一时段重启只续发尚未尝试的 `pending` 分段。超时未知结果不自动重试，旧时段消息不自动补发；一个国家受阻时仍可处理另一个国家。

Telegram 没有发送幂等键，因此不承诺 exactly-once；结果不明可能需要人工核对或接受漏发。

设置环境变量 `GITHUB_REPOSITORY`、`DELIVERY_GITHUB_TOKEN`（仅该仓库 contents 读写）后运行：

```bash
# 只显示账本 SHA、分段状态和回执，不显示密钥或正文
python reconcile_delivery.py

# 已核实送达：登记真实回执，part 从 0 开始
python reconcile_delivery.py --confirm-receipt --slot RO:2026-10-19-morning \
  --part 0 --expected-sha INSPECTED_SHA --message-id 123 --note '已人工核对目标群回执'

# 无法核实或消息已过期：取消剩余分段，接受可能漏发，保留文章占用防重发
python reconcile_delivery.py --abandon-slot --slot RO:2026-10-19-morning \
  --expected-sha INSPECTED_SHA --note '消息已过期，接受可能漏发'
```

对账前暂停定时发送并等待在途任务结束；SHA 不匹配时重新查看，不要盲目重试。

## 验证与边界

```bash
python -m pip install -r requirements.txt
python preflight.py
python -m unittest discover -s tests -v
RSS_CACHE_DIR=.rss-cache python check_sources.py
RSS_CACHE_DIR=.rss-cache python news_coverage.py
DRY_RUN=true PREVIEW_ALL=true RSS_CACHE_DIR=.rss-cache python news_bot.py
```

法国财政总司官方新闻源入口：<https://www.tresor.economie.gouv.fr/Flux>。该源是经济研究及政策发布，INSEE BDM 仍为统计数据更新源。Atom 仅有更新时间时显示「源更新时间」，不冒称首次发布时间。

市场开市提示仍为独立预览，未随新闻发送；尚未接入节假日及实时开市验证。程序处理官方 RSS 摘要，不声称逐篇完成全文事实核查。历史验收见 `RELEASE_CHECKLIST.md`，当前运行说明以本文件为准。

## 调度修复（2026-10-18）

只有正式finance-news-live.yml保留定时，预览工作流仅提交或手动触发。正式任务在UTC第8、18、28、38、48、58分钟唤醒，避开整点负载；当地07:30晨报及08:30起每小时快报的窗口不变。每窗口有多个唤醒机会，已发送由持久账本去重；没有新闻不发送，未知发送结果仍要求人工对账。GitHub Actions不保证准点执行；cron更新不等于自然定时已经恢复，须查event=schedule运行证据。

每次正式运行的Summary及news-delivery-status运行附件包含分国状态：OUTSIDE_WINDOW、NO_ELIGIBLE_NEWS、ALREADY_RECORDED、BLOCKED_PRIOR_UNFINISHED_SLOT、DELIVERY_UNCERTAIN、SENT/SENT_RESUMED。来源错误单独记录；工作流成功不代表已经送达。启动依赖或测试失败也会显示尚未开始投递。非时段不抓RSS、不写账本、不访问Telegram。

## 调度兜底

若GitHub自然schedule没有事件，`scheduler/windows/`提供免费的本机备用触发脚本（完整便携包双击 `install.cmd`，首次通过 GitHub 官方网页授权；`status.cmd` 查看状态，`uninstall.cmd` 移除）；只有用户安装后才会生效，电脑需开机、已登录且联网。它只调用现有正式工作流，不存Telegram密钥，不放宽选稿规则；已有运行或最近检查会跳过。`telegram-readonly-health.yml`仅核对机器人身份与目标权限，不发送任何消息，不能冒充真实送达验收。


### 采集与排版修正（2026-10-18）

正式流程新增 Economica、Romania Insider 和 CNBC 的公开 RSS；接入前已在 GitHub 运行机器实测可读取。官方来源仍保留，网站可达不等于每时段都有新闻。综合报纸需通过财经相关性和政治评论过滤，保留原有发布时间、6小时新闻窗口和去重限制，不用旧闻凑数。Nasdaq 超时不会阻止其他源的报道入选。

状态 `NO_ELIGIBLE_NEWS` 表示本时段没有符合条件的新闻；`NO_NEWS_WITH_SOURCE_FAILURES` 表示没有选出新闻且相关来源有采集故障，报告列出失败来源，两者不能混同。

正式推送与单次新闻验证共用同一个排版函数：资讯助理标识、当地易读时间、新闻标题和摘要、可能影响、值得关注，末尾保留来源与原文。不在读者正文输出内部关键词、分析类别、ISO时间串或测试执行说明。条件分析由已定义的主题规则生成，不冒充实时资金观测或个性化投资判断。免费翻译不可用时明确标注原文，不能谎称中文成稿。

单次验证不再读取仓库中的一次性采集快照；新闻必须在执行时由公开来源采集。实发成功只证明该次发送，不保证外部网站永久可用。


### 法国与美股覆盖（2026-10-18）

报道按明确的国家/发行人线索分流，不再仅按媒体语言或所在地归类：例如罗马尼亚媒体报道 LVMH、Hermès、Airbus，若没有罗马尼亚业务线索，则进入法国栏目；同时涉及罗马尼亚供应商则保留两国相关性。来源名称与链接始终保留实际出版方，不冒充法国或美国媒体。

新增在 GitHub 实测可读取的 BFM 经济、MarketWatch 公开 RSS 和 CNBC Finance，沿用时效及去重限制。美股公司/市场事件与媒体市场观察严格区分：媒体评论只作后台参考，不占正式推送的美国事件位置。两套推送固定为“罗马尼亚＋美国相关事件”和“法国＋美国相关事件”，没有独立美股栏目。美国事件必须分别说明对目标国家金融和股票市场的传导条件、观察板块与验证指标；无合格事件时明确说明，不拿旧闻或预测凑数。Franceinfo 的候选端点实测包含较多非财经社会新闻，未接入正式来源。

法国奢侈品与公共债务主题分别提供有条件的传导解释和后续核对项目，避免统一填充无针对性的“暂无法判断”。


### 两套目标市场推送（当前执行规则）

- 罗马尼亚＋美国相关事件：本地事件和美国事件都围绕 BET、RON、本地银行/能源/出口等已识别的传导关系编排。
- 法国＋美国相关事件：法国事件和美国事件都围绕 CAC 40、EUR/USD、法国银行/工业/奢侈品等实际相关渠道编排。
- 同一美国事件可以分别进入两套推送，但分析、观察板块和指标必须对应各自目标国家，不共用一段混写的影响。
- 不设置独立 US 推送入口。事件与标题新鲜度分别核对；新发表的预测或市场评论不能替代新的公司、经济或市场事件。


### 云端定时触发（不依赖电脑）

`scheduler/cloudflare/` 提供 Cloudflare Workers 定时器，按既有 RO/FR 本地窗口唤醒同一正式工作流。GitHub Actions 的 **Deploy Cloudflare news wakeup** 是部署入口；需先配置 Cloudflare 账户 ID、Worker/KV 编辑 token 和仅限本仓库的 GitHub Actions 触发 token。详细步骤见 [Cloudflare 定时器说明](scheduler/cloudflare/README.md)。

状态须分别验收：代码通过测试、Cloudflare 部署配置成功、自然 Cron 心跳、cloudflare 来源的 GitHub 运行、Telegram 实际回执。不能把其中一步当作全部完成。验证完成前保留 Windows 备用任务。
