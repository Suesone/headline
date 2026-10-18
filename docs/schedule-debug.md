# 2026-10-18 22:00 调度缺失排查

截至北京时间 22:51，GitHub API 没有 22:00 的 schedule 运行记录，也无排队运行；最后成功发布的数据是 21:49。默认分支 main、工作流 active、Actions 权限 enabled、cron `0 */2 * * *` 均正确；这不是 RSS 步骤执行失败。工作流最近一次 schedule 记录是 16:25，其推送冲突已经修复。`[skip ci]` 根据官方说明只影响 push/PR，不阻止 schedule。

GitHub 状态页当时没有未解决事故；不能从这些信息断言本次缺失的内部原因。官方指出整点负载可能导致延迟或事件丢弃，故采取避开整点的恢复检查，不把推测当作已证明的故障原因。

已通过 workflow_dispatch 手动补跑：[39137866331](https://github.com/Suesone/headline/actions/runs/39137866331)，采集、推送和 Pages 发布全部成功；公开数据 generated_at 为 2026-10-18T14:51:46.823656Z（北京时间 22:51），8/8 来源正常。

整点主调度保留，增加偶数小时 17 分与 37 分的恢复检查。只根据已发布站点本时段的成功数据跳过重复采集；读取失败、数据过期或来源失败时允许补抓。所有运行串行，不强推 Git、不调用 AI。

网页显示触发类型和具体 GitHub 运行链接。本时段过去 45 分钟仍无新数据时提示调度延迟。程序无法替 GitHub 生成真正的 schedule 事件；手动运行和 push 运行只能验证数据链路，不能证明下一个自动事件必达。备用检查仍依赖同一个 GitHub 调度服务。

参考：[调度限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[skip 说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)、[GitHub 状态](https://www.githubstatus.com/)。
