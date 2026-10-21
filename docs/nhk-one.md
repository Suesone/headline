# NHK ONE 官方 RSS 验证（2026-10-21）

- 官方说明：https://www.nhk.or.jp/toppage/rss/index.html
- 官方现行综合源：https://news.web.nhk/n-data/conf/na/rss/cat0.xml
- 旧地址 https://www.nhk.or.jp/rss/news/cat0.xml 可跳转读取。
- 实测返回有效 RSS 2.0，频道名 NHKONEニュース；含日语标题、pubDate、GUID、链接。文章域名为 news.web.nhk。
- 官方说明明确：“RSSで提供する情報は個人の方の利用のためのみに使用することができます。”并说明不允许博客或程序再配信、再提供（包括商业使用）。
- 因本站公开发布，config/sources.json 中仅登记接入配置，enabled=false。不会发布其标题、摘要或其他 RSS 内容。未以社区镜像替代官方权限。

Reuters、The Washington Post、NHK WORLD-JAPAN 已按要求从当前配置和当前新闻数据删除；Git 历史不改写。
