# 备用触发代码：仅上传，未启用

本分支用于保存和审阅备用触发实现，不创建定时任务、不修改 main，也不触发 Telegram 发送。

- `news-dispatch-bridge.yml.example` 是未启用的工作流模板，存放在 proposals 下，GitHub Actions 不会执行。
- `news-dispatch.example.json` 是公开请求示例，不在 ops 的实际触发路径。
- 仓库根目录 `dispatch_news_request.py` 是桥接实现，`tests/test_dispatch_news_request.py` 是配套离线测试。
- 已有正式推送、原时间节点、内容和接收群均不因本次上传改变。

本次只上传代码；部署工作流、提交有效触发请求和创建常驻备用任务是另外的动作，尚未执行。

本地完整套件已通过123项测试。
