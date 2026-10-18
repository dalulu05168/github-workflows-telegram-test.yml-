# Cloudflare 云端定时触发器

只服务于 `dalulu05168/github-workflows-telegram-test.yml-` 的正式新闻工作流。电脑关机后，Cloudflare 仍可定时唤醒 GitHub；新闻采集、罗马尼亚＋美国／法国＋美国的编排、Telegram 凭据和发送去重仍由原项目负责。

## 一次性配置

把三项值填入本仓库 **Settings → Secrets and variables → Actions → New repository secret**。不要提交到代码或聊天。

| Secret 名称 | 填什么 |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 账户 ID；在 Workers & Pages 控制台可查看。不是邮箱，也不是 API token。 |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token。使用 **Edit Cloudflare Workers** 模板，仅包含目标账户。需允许 Worker Scripts 和 Workers KV Storage 的编辑操作。不要使用 Global API Key。 |
| `CLOUDFLARE_GITHUB_TOKEN` | GitHub fine-grained PAT。资源所有者为 `dalulu05168`，只选本仓库，Repository permissions 只需 **Actions: Read and write**（Metadata 只读为默认）。 |

GitHub 细粒度令牌到期前须在这个 Secret 中更新，否则云端唤醒会报告授权失败。Cloudflare 令牌如果设有到期日，同样需要维护。

首次使用 Cloudflare Workers 时，先在控制台启用 Workers 并确认已有 `workers.dev` 子域名。本方案不要求购买域名或服务器。

配置完成后，运行 GitHub Actions 中的 **Deploy Cloudflare news wakeup**（仅手动运行，使用 main 分支）。配置检查会明确列出缺失项，不会把未部署说成部署成功。

- 自动检查同名 Worker 的仓库标记；不覆盖其他项目的 Worker。
- 创建或复用本项目专用状态 KV：`dalulu05168-telegram-finance-news-wakeup-status`。
- 部署 Worker、Cron、状态存储，并把限定仓库的 GitHub 触发令牌保存为 Worker Secret `GITHUB_DISPATCH_TOKEN`。
- 不向 Cloudflare 复制 Telegram 机器人密钥。

## 时段与去重

Cloudflare Cron 使用 UTC，配置为每10分钟检查一次。Worker 用 IANA 时区自动换算罗马尼亚和法国本地时间，保持既有发布窗口：各地07:30–07:59，08点起每小时30–59分。窗口外不调用 GitHub。

正式工作流已有排队/运行，或最近10分钟已经检查过，便跳过本次唤醒。GitHub 并发控制与持久化发送账本继续防止重复发送。请求超时后不立即重试 POST；下一次检查先查询现有运行。

**Cron 不能承诺秒级准点。**Cloudflare 官方说明，新建或修改 Cron 最多可能需要15分钟在全球生效；控制台 Past Cron Events 显示也可能延后。不要靠反复重新部署或手动补发判断是否生效。

## 如何验收

部署完成的 Actions Summary 提供 Worker 的 `/health` 地址。

1. `configured: true`、正确 `revision`：只证明本次配置已部署。
2. `last_scheduled.checked_at` 与 `revision` 更新：证明当前版本自然 Cron 已执行；状态通过 KV 持久化，读取可能有短暂延迟。
3. `last_scheduled.outcome: DISPATCH_ACCEPTED`：只证明 GitHub 接受了唤醒；原工作流会显示 `trigger_origin: cloudflare`。
4. 正式工作流的 `SENT` 与账本里的 `telegram_message_id` 才是实际发送回执。没有合格新闻时仍不会凑数发送。

`RECENT_CHECK_EXISTS` 或 `RUN_ALREADY_PENDING` 表示其他定时器已经先执行，并非 Cloudflare 故障。**完成自然 Cron 和 cloudflare 来源的 GitHub 运行验收后，再停用 Windows 的 `TelegramFinanceNewsFallback`。**需要时可先暂停一个发布窗口观察云端接管，失败则重新启用。

根路径和 `/health` 均只读；公开 HTTP 请求不能触发新闻发送。日志和状态不包含密钥或新闻正文。

## 费用与验证范围

当前配置每日144次 Cron 检查、约144次 KV 状态写入。Cloudflare 官方 Workers Free 配额为每日100,000请求，KV Free 每日1,000写入；正常使用量远低于这些限额。以账户实际选择的计划与官方现行配额为准，脚本不启用付费计划。

测试：`npm ci && npm test && npm run check`。`check` 是本地 dry-run 打包，不能证明账号部署、真实 Cron 或 Telegram 送达。

官方参考：
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/
