# 上线验收清单（2026-10-18）

> **状态：未上线；DRY_RUN=true；不得将代码提交等同于测试通过。**

## 已有代码与可核查证据

- 工作流：`.github/workflows/finance-news.yml`，UTC 整点与半点调度；预览强制 `DRY_RUN: 'true'`，且不读取 Telegram secrets，GitHub token 为只读。
- 罗马尼亚、法国独立模板：`news_bot.py`，包含新闻标题、发生了什么、当地市场影响、后续关注、官方原文；未经核实的原图不显示。
- 条件性分析：`editorial.py`；不具备基于真实行情的因果验证。
- 来源：美联储、ECB、BLS，以及 BVB 官网 RSS 页面所列的市场操作与公告 RSS。BVB 入口来源：<https://www.bvb.ro/Services/DataVending/ForProfessionals>。**入口由官网确认，但本项目尚未证实 RSS 在 GitHub Actions 中能成功抓取并提供近期新闻。**
- INSEE 官方提供 RSS 订阅页：<https://www.insee.fr/fr/information/2381941>，但未核实可供本程序直接抓取的 RSS 终端地址，**故未配置**。
- BNR 和 Euronext Paris 尚无经验证可用的新闻 RSS 配置。\n- 已配置 INSEE 官方技术文档所列统计数据更新 RSS：`https://bdm.insee.fr/series/sdmx/rss/donnees`。**这是统计数据更新源，不是完整的 INSEE 新闻稿 RSS；实际抓取与文章内容仍未在 Actions 日志验证。**

## 本轮本地验证的严格范围

- 独立复现了 Telegram 拆分函数，并运行 4 项离线 Python 测试：新闻边界、超长单条新闻、普通长行、非法限制值，均通过。
- 独立复现关键词边界分类规则，并运行 4 项离线 Python 测试：通胀、利率、部分词误判、无关标题，均通过。以上均为**独立函数复现测试**，不能冒充完整仓库测试。
- **没有**在本地成功安装 `feedparser`，因为运行环境无法访问软件包索引；因此没有运行仓库完整测试套件。
- **没有**获取当前最新 GitHub Actions 运行日志，不能声称该提交的 CI 通过。
- **没有**进行真实 Telegram 发送，也没有验证官方 RSS 实际响应、发布时间或新闻覆盖率。

## 上线前必须满足（目前均未全部通过）

1. 最新 GitHub Actions `Run tests` 步骤成功，且保存可核查的运行链接。
2. `Check RSS source health` 输出各来源的有效性、最近一篇发布时间、是否超过 72 小时；周末和节假日应按真实发布频率判断，不可仅凭 72 小时判定故障。
3. BVB RSS 实际解析成功；法国本地 INSEE 数据更新 RSS 在 Actions 中实际解析成功，并继续补充真正的法国新闻稿来源；BNR/INSEE/Euronext 优先，但不能猜测 URL。
4. 按实际样本核对每国晨报、小时快报的数量、时效、来源、分析和图片，验证不虚构数据。当前 RSS 摘要仍是原文语言，已明确标记「未翻译」；**完整中文事实解读尚未实现**。
5. 在夏令时与冬令时分别测试 07:30 本地晨报和各交易所开盘窗口；节假日须有交易日历，不得把时钟提示当作真实开市。
6. 完成**跨次运行持久化**与**多段消息部分成功后重试**的幂等测试。当前工作流持久化步骤明确禁用，且没有 exactly-once 发送保证。已在代码中阻止真实多段发送，避免部分成功后重试重复发；这属于保护性限制，不是完成了可靠重试。
7. 在用户批准后，通过 GitHub Secrets 配置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，先测试群组接收、无 Topic、分国消息，再决定正式上线。**不要在聊天中提供 Token。**
8. 只有用户明确批准并且上述条件达标，才能把 `DRY_RUN` 改为 `false`；当前不允许启用。

## 复现测试

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python check_sources.py
python news_coverage.py
DRY_RUN=true PREVIEW_ALL=true python news_bot.py
```

所有命令均可在 GitHub Actions 日志中单独查看。注意：命令被写入文档**不代表它们已经成功执行**。

## 2026-10-18 新增诊断与周一晨报逻辑

- 依据 GitHub Actions 用户提供的真实日志，2026-10-18 周日 RO、FR 最近 6h/18h 均无可选新闻；BVB RSS 可抓取 14 条、最近一条约 38.9h，BLS 原链接返回 404。
- 解析层保留最近 96h 的候选；**只有当地周一晨报**才允许回看最近 72h，普通晨报仍为 18h，每小时快报仍为 6h。旧文章仍受已发送 ID 去重限制（跨运行持久化仍未实现）。
- `Report country news coverage` 新增 `feed_diagnostics`：各来源抓取条数、接收条数、无日期、超过 96h、官方链接/标题不合格、请求错误。需要下一次 Actions 日志确认这些计数及新逻辑是否通过。
- **本轮 GitHub 提交成功，但最新 Actions 运行尚未验证**；本地无法安装 feedparser，不能声称全套测试已通过。

## 2026-10-18 本地优先与运行摘要（本轮）

- 按官方来源域名对 RO 的 BVB/BNR/INSSE、FR 的 INSEE/Euronext 加分，仍保留国际重大信息；仅改变候选排序，不凭空增加新闻。
- 对新闻 URL 规范化并去除 `utm_*`、`fbclid` 等追踪参数，在同一次筛选中去重；**跨次运行去重依旧需持久化状态**。
- 07:30–07:59 的晨报时段可容忍 GitHub Actions 启动晚于 07:50，避免漏报；仍不能保证平台延迟超过 08:00 时不错过。
- `Report country news coverage` 现在写入 GitHub Actions 运行摘要：RO/FR 选中数量、周一晨报窗口及各 RSS 的拒绝原因。用户无需靠猜测绿色勾号。
- 本地仅使用从核心函数重建的离线测试文件执行 4 项测试（全部通过）；**没有运行完整仓库依赖测试或新提交的全部单元测试**，需要后续 GitHub Actions 验证。
- `DRY_RUN=true`、无密钥、跨次持久化 disabled 的边界保持不变。

## 2026-10-18T02:25Z 实际 CI 验收（可复核）

- [GitHub Actions #39090024514](https://github.com/dalulu05168/github-workflows-telegram-test.yml-/actions/runs/39090024514) 在提交 `c603c8768add24fbde82f4d15d63dbd6898121e2` 上**成功**。日志明确记录 `Ran 65 tests ... OK`；RSS 健康、排除原因、覆盖率、新闻预览步骤均成功；真实发送状态持久化步骤为 skipped。
- 同次运行启用了仅限运行环境的 RSS 缓存，在新闻预览日志中没有 `Unavailable feed` 或连接超时。健康检查会缓存通过基本 RSS/日期校验的响应，后续诊断与预览复用缓存，避免重复请求得到不同结果。
- [GitHub Actions #39089710955](https://github.com/dalulu05168/github-workflows-telegram-test.yml-/actions/runs/39089710955) 通过 60 项测试，其 BVB 排除诊断显示 14 条、96h 内可用 13 条、其中 72h 内 5 条；此计数是筛选窗口信息，**不能被理解为周日小时快报可以推送 5 条**。
- 工作流已启用 push(main) 自动运行完整 DRY_RUN 测试；此后修改不再需要手动点 Run workflow。
- **仍未交付**：法国真正财经新闻稿来源和完整中文事实核查、跨次运行持久化去重、多段发送可靠重试、节假日交易日历、真实 Telegram 群组验收。未获得用户明确授权，不打开 LIVE_APPROVED/DRY_RUN 或 GitHub Secrets。
