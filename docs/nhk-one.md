# NHK 日语新闻接入（2026-10-21）

已删除未启用的 nhk-one 官方 RSS 配置，改为启用 nhk-japanese。

- 接入：Google News 日语 RSS 聚合（hl=ja、gl=JP、ceid=JP:ja），查询 site:news.web.nhk when:2d。
- 本机实测：返回 RSS 2.0，100 条候选；有当天日语标题、pubDate、NHK 来源标签和 Google News 跳转链接。采集器最多接收 10 条有效条目。
- 来源过滤：RSS source.href 的域名必须是 news.web.nhk 或其子域，拒绝混入其他媒体、相似恶意域名和缺失来源标签的条目。
- 语种过滤：标题至少含一个日文平假名或片假名，拒绝英文 NHK WORLD-JAPAN；可能排除少量仅含汉字的日语标题。
- 显示：仅标题，不保存或显示聚合摘要；经 Google News 跳转。聚合发布时间不保证等同于 NHK 原站首次发布时间。
- 免费、无需 API Key；不是 NHK 官方 RSS，也不是 RSSHub 社区转发。
- RSSHub /nhk/news_web_easy 本次读取返回 HTTP 错误，未配置为可用源。未引入未经验证的公共镜像。
- 删除旧官方源并不代表其技术上无法读取：此前实测可读，但未启用。此次按用户要求直接移除配置。

本接入只验证技术可用性，聚合不授予额外内容权利。原标题归 NHK，不抓取正文，不绕过登录或付费访问。
