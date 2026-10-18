# 调度恢复与正式验证记录

核查日期：2026-10-18。以下时间使用 Europe/Bucharest。

- 一次性恢复运行：https://github.com/dalulu05168/github-workflows-telegram-test.yml-/actions/runs/39098613236
- 07:52:47 读取正式工作流状态为 active，说明此前不是被禁用；定时未出现运行记录的根因尚未确认。
- 07:52:48 完成正式工作流调度注册的停用/启用复位，状态重新读回为 active；cron 0,30 * * * * 未改变。
- 随后通过 workflow_dispatch 启动正式流程：https://github.com/dalulu05168/github-workflows-telegram-test.yml-/actions/runs/39098621451
- 该正式运行成功，119 项测试通过；state/live_ledger.json 已由生产 token 实际创建并读回为 {"slots":{},"version":1}。空账本初始化用于验证持久化权限，不代表发送过任何新闻。
- 正式日志：罗马尼亚晨报没有合格新新闻，没有发送；法国当时06:52，尚未到时段，没有发送。Nasdaq 抓取超时，按规则跳过。
- 此记录不把手动触发当作自然 schedule 成功；仍须以随后 schedule 事件运行记录核实自动触发。
- 之前 Telegram 单次连通测试已取得 message_id=46，该回执不属于正式新闻。

此次未改动推送时间、选稿规则、接收群或已有 sending 状态。一次性恢复工作流执行完毕后移除。
