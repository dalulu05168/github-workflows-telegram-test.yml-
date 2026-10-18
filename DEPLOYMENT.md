# 2026-10-18 接管更新：当前状态

`finance-news-live.yml` 已恢复原定 UTC 整点、半点调度，移除自行新增的启用变量和手动确认输入。正式工作流直接调用持久投递账本发送入口。晨报、小时快报时段与筛选规则不变；真实送达状态以运行回执为准。

用户明确要求不翻译：标题、摘要保留官方原文，无翻译或模型费用。已补充法国财政总司官方新闻源，实抓 HTTP 200、50 条记录；Atom 更新时间不冒称首次发布时间。本地 BVB 曾返回 HTTP 500，但随后 GitHub Actions #39095850766 中 7 个来源均解析成功（BVB 14 条、财政总司 50 条）；这不是长期可用性保证。

已修复同一时段 pending 分段的跨运行续发、增加 SHA 校验的人工回执登记及放弃旧消息工具；未知结果不自动重试，一个国家受阻仍可处理另一个国家。提交 `4ac927c` 的 [CI #39095850766](https://github.com/dalulu05168/github-workflows-telegram-test.yml-/actions/runs/39095850766) 通过 95 项测试、配置预检及全部预览步骤。随后统一覆盖率报告的本地来源识别并新增回归测试，本地固定依赖下 96 项测试通过。真实群接收、在线账本权限和实际多段消息仍需发送验收；开市提示不纳入正式发送。

当前配置与对账步骤见 [README.md](README.md)。下面保留接管前的历史说明，旧的「无 live 工作流」「必须中文翻译」状态已由本轮实现及用户新要求替代。

---


# Telegram 财经新闻 — 部署状态（尚未启用发送）

本仓库目前是 **GitHub Actions DRY_RUN 安全预览项目**，并非已上线的 Telegram Bot。

## 已有可信运行证据

- GitHub Actions #39090024514: 65 项单元测试通过；BVB 官方 RSS 14 条记录中 13 条通过筛选、INSEE 数据 RSS 43 条记录中 6 条进入 96 小时候选窗口。
- 新增的 `delivery_ledger.py` 和 `live_runner.py` 为**未连接到实际调度的独立代码**，需要从最新 Actions 验收。
- 当前工作流 `.github/workflows/finance-news.yml` 强制 `DRY_RUN: 'true'`，从不装载 Telegram Secrets，`contents: read` 且禁用持久发送步骤。
- 推送时间设计：罗马尼亚、法国当地 07:30 晨报及 08 点后的小时新闻筛选；实际 GitHub 运行时刻并非严格保证的发送 SLA。

## 已完成的可靠发送设计

`delivery_ledger.py` 引入保存在 GitHub `state/live_ledger.json`（**仅未来经批准的 live runner 创建，不是当前已存在的配置文件**）的投递账本，保留每国文章 ID、每个分片的 `pending` / `sending` / `sent` 状态及 Telegram 回执 message_id。

- Telegram API 并无可用的发送幂等键。为了避免断线后重复发送，程序**先在 GitHub 登记 sending，再发送**。如果 Telegram 请求超时/结果不明，后续运行**必须人工核对**，不会自动重试。
- 收到 Telegram message_id 后才标记 `sent`；完整消息多分段只发送仍为 pending 的分段。如果出现不明确分段，整个国家后续新消息暂停，避免叠加错误。
- 不保证“恰好一次（exactly-once）”；取舍是**不会冒险重发，但可能漏发并等待人工处理**。
- 通过 GitHub Contents API 的文件 SHA 乐观并发检测和 Actions 串行工作流减少并发覆盖风险，但真正上线还需要单独验证权限、原子性和冲突恢复。

## 尚未满足的上线条件

1. 完整中文事实翻译与引用来源、内容真实性和影响分析复核。
2. 真实 Telegram 群组接收测试、机器人群组权限及密钥安全设置。
3. 工作流中独立的经过批准的 live job / workflow（当前不存在），避免把 Secrets 暴露到公开 push 测试。
4. 实际的多段消息接收、超时后的人工恢复程序、保持 live token 最小权限。
5. 市场节假日与开市实时核验；现有市场提醒只是常规时钟提示。
6. 法国真正经济新闻稿 RSS 的覆盖，当前 INSEE 是官方统计数据更新源。
7. 用户明确同意后才能引入真正的 Telegram / GitHub write Secrets、部署独立 live workflow，并经单次试发确认后再开启定时模式。

任何时间不得通过聊天索取或粘贴明文 Token。当前没有启动 live runner 的自动入口。

## 本地 / Actions 预览验证

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python check_sources.py
python feed_diagnostics.py
python news_coverage.py
DRY_RUN=true PREVIEW_ALL=true python news_bot.py
```

`live_runner.py` 默认 **拒绝**发送，只有手动提供 `DRY_RUN=false`、`LIVE_APPROVED=true` 且所有 Telegram 和 GitHub 写权限凭据才能继续；**不要在当前工作流中启用**。
