# 第二批来源与两小时更新（2026-10-18）

网页仅展示标题，前列字号略大。默认选中 Gemini；加载与滚动不自动调用。Chrome / Ollama 选项已移除，全文仍由用户自行粘贴或导入。

| 来源 | 优先路径 | 复测结果 | 备用 |
| --- | --- | --- | --- |
| The Guardian World | Plenary 社区目录收录的官方 `https://www.theguardian.com/world/rss` | 45 条有效、有日期的报道 | 无需备用 |
| The Washington Post | Plenary 社区目录收录的官方 `https://feeds.washingtonpost.com/rss/world` | World 与 Politics 均 502；替代 arcio 地址超时 | Google News RSS，仅接受 RSS source 域名为 washingtonpost.com 的条目；覆盖全报，非仅 World |
| NHK WORLD-JAPAN | RSSHub 社区 `/nhk/news/en` | rsshub.app 403；两个公共实例超时或 TLS 错误 | Google News RSS，仅接受 NHK 域名的英文标题，排除 TVGuide 等其他来源 |

NHK 旧官方英文 RSS 路径返回 404；Backstory RSS 最新日期 2026-08-31，不能作为当前新闻。RSSHub 源码使用的官方 `v7b/en/outline/list.json` 有 405 条，但全部缺少 public_at，检查到的条目已过期，因此未将其当作最新新闻。只依据成功 HTTP 状态启用来源会误判。

备用聚合链接经 Google News 跳转，日期属于订阅元数据。页面快捷入口和来源状态明确标注备用，不冒称官方 RSS。没有解码私有 Google 接口、抓取全文或绕过付费墙。每轮优先重试配置的官方/社区源，恢复后自动使用主源。

配置位于 `config/sources.json`；`fallbacks` 可修改备用 URL、允许的标题链接域名和 RSS source 域名。域名校验支持子域，拒绝 `nhk.or.jp.attacker.example` 等仿冒域名。采集每个条目后沿用原 GUID/规范化链接去重；保留历史按发布日期重新划入两小时窗口。

北京时间 00:00、02:00、04:00、06:00、08:00、10:00、12:00、14:00、16:00、18:00、20:00、22:00 触发；GitHub 可能延迟。变更频率后重新开始两天覆盖观察，旧四小时运行记录不作为两小时漏跑统计。

参考：[Plenary 目录](https://github.com/plenaryapp/awesome-rss-feeds/blob/master/recommended/with_category/News.opml)、[卫报 RSS 说明](https://www.theguardian.com/help/feeds)、[华盛顿邮报 RSS 目录](https://www.washingtonpost.com/information/2026/05/21/washington-post-rss-feeds/)、[RSSHub NHK 实现](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/nhk/news.tsx)。抓取结果是当时实测，不保证后续可用性。
