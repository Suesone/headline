# NHK 日语直达源验证（2026-10-21）

当前启用 nhk-hatena；已移除 nhk-one 官方配置及 nhk-japanese Google News 跳转源。

- RSS：https://b.hatena.ne.jp/entrylist?url=https%3A%2F%2Fnews.web.nhk%2F&mode=rss
- 提供者：Hatena Bookmark 社区，站点收录列表 https://b.hatena.ne.jp/site/news.web.nhk/ 。
- 本机实测 HTTP 200，RSS 1.0/RDF，30 条候选，含当天日语标题及 dc:date。采集器已验证最多接收 10 条有效条目。
- item.link 直接指向 https://news.web.nhk/newsweb/na/...，无需 Google News 或 Hatena 评论页中转；仅接受 news.web.nhk 域名并校验日语假名。
- dc:date 为社区收录时间，不保证等同于 NHK 原文首次发布时间。社区可能重新关注旧文，覆盖也并非完整新闻流。页面时间前标注“社区收录”。
- 只保存原标题和原文链接，不保存 RSS 摘要、社区评论、全文。原标题权利仍归 NHK，社区可访问不代表额外转载许可。
- 新源使用独立 id，旧 Google News 跳转条目不会进入当前 72 小时存档。
- RSSHub 官方公共实例 /nhk/news_web_easy 本次返回 403；rssforever 实例读取超时，未作为已验证来源或静默备用。

参考：https://b.hatena.ne.jp/help/entry/faq （域名/URL 新着书签 RSS）与 https://github.com/DIYgod/RSSHub/blob/master/lib/routes/nhk/news-web-easy.tsx （NHK Easy 社区实现）。
