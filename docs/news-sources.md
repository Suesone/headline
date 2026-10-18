# 大新闻源接入研究

核查日期：2026-10-18（北京时间）。这是接口与开源实现的研究，不是对新闻内容的重新授权。本轮没有启用收费服务或改变现有采集来源。

## 实测结论

测试通过本机网络执行，云端或不同 IP 的结果可能不同。HTTP 401/403 只说明这次请求被拒绝，不证明接口永久失效。测试没有使用反检测代理、付费墙绕过、浏览器登录凭据或全文抓取。

| 获取路径 | 本次结果 | 对当前网站的意义 |
| --- | --- | --- |
| BBC World 官方 RSS | HTTP 200，28 条，均有日期 | 最容易技术接入；个人 RSS 展示与 AI/统计分析应分别处理 |
| BBC Business 官方 RSS | HTTP 200，49 条，均有日期 | 同上；两个频道属于同一媒体，不算两个独立来源 |
| Reuters 网页内部列表 JSON | HTTP 401 | 有社区实现，但不是对开发者承诺稳定的官方开放 API |
| RSSHub Reuters 公开实例 | HTTP 403 | 当前网络不能直接依赖；自建也不能保证源站允许访问 |
| AP 旧 `index.rss` / World 网页 | HTTP 403 | 本次不能验证其条目、发布时间或持续可用性 |
| RSSHub AP topics / mobile 公开实例 | HTTP 403 | 存在源码，但当前实例未能返回订阅 |
| Google News 搜索 Reuters | HTTP 200，100 条，均带 RSS 发布日期；出版方 Reuters | 可以作为标题＋链接的发现入口候选，不能当作 Reuters 正式内容 API |
| Google News 搜索 AP | HTTP 200，100 条，均带 RSS 发布日期；出版方 AP News | 同上 |
| Guardian World 官方 RSS | HTTP 200，45 条，均有日期 | 技术可取，但当前聚合/AI 用途受使用条件限制 |

原始诊断见 [news-source-probes.json](news-source-probes.json)。这些条数是测试时的单次返回值，不是每日限额或完整新闻数量。

重跑方法（不启用来源、不写入网页新闻数据）：

```sh
.venv/bin/python -m scripts.probe_sources
```

## BBC：优先区分“原始 RSS 阅读”和“分析型产品”

官方入口：

- World：`https://feeds.bbci.co.uk/news/world/rss.xml`
- Business：`https://feeds.bbci.co.uk/news/business/rss.xml`
- [BBC 官方订阅说明](https://support.bbc.co.uk/platform/feeds/NewsFeeds.htm)
- [BBC 使用条件，特别是第 15 节](https://www.bbc.com/usingthebbc/terms-of-use/)

条款明确允许有条件地将 BBC News RSS 加到个人网站/社交账户：保留订阅，不去除其原有标识，并显著注明 BBC News、链接到 BBC。商业 RSS 使用另需许可；计算分析及 AI 相关用途也不能从个人展示条件直接推导。

因此，前一版将 BBC 整体禁用是针对本站“归档＋热词分析＋AI”的组合用途，并不等于 BBC 完全不能展示。可行的下一步是增加**独立的 BBC 只读 RSS 区域**，保留原始标题、摘要、日期、来源与原文链接，暂不接入热词统计或 AI。当前版本尚未实施这一模式，不建议只把 `enabled` 改为 `true` 后套用所有处理。

纯技术上可用现有 feedparser 读取；不需要浏览器抓取或 BBC 员工内部接口。缺日期的条目不应以抓取时间冒充发布时间。

## Reuters：官方授权渠道与网页内部接口不同

**正式渠道**是 [Reuters Connect](https://reutersagency.com/content-delivery-platforms/reuters-connect/)，支持 API、订阅等交付方式。[官方 RSS 技术说明](https://liaison.thomsonreuters.com/page/rss-feeds-tech-notes) 说明 RSS 交付客户会获得 Connect 账户。没有找到可承诺长期零成本生产使用的 Reuters 官方内容接口；不应采用网上旧 FeedBurner 地址作为已验证方案。

**开源路线**可参考 [RSSHub Reuters 源码](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/reuters/common.tsx)：

- 路由形如 `/reuters/world`、`/reuters/business`、`/reuters/world/us`。
- 默认从网页内部列表接口获取标题、简介、GUID、发布时间和更新时间。
- 内部路径是 `/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1`，查询包含 `section_id`、`offset`、`size`、`website`。
- `fulltext=true` 才会追加详情请求；本站应保持关闭。
- 本次直接列表请求 401，RSSHub 公开实例 403，不能把源码中存在的路由描述为已经可用的服务。

若未来获得正式账户，应该在 Python/Actions 中调用 API，密钥放 Secrets，保留文章 ID、原始发布时间与修订时间；公开网页只读取允许发布的数据。不要把账号专属 RSS URL 放进公开配置。

## AP：有官方样例，也有三种社区获取路线

**正式渠道**：[AP Media API 入门](https://api.ap.org/media/v/docs/Getting_Started_API.htm)、[Feed 文档](https://api.ap.org/media/v/docs/Feed.htm)、[AP 官方开源示例](https://github.com/TheAssociatedPress/APISamples)。

接口示意（需要自己的已授权账户；本研究没有发起此收费/授权接口调用）：

```http
GET https://api.ap.org/media/v/content/feed?in_my_plan=true&page_size=10
x-api-key: <在 GitHub Secrets 中配置的 AP_API_KEY>
```

`in_my_plan=true` 限制返回账户套餐内、下载不另收费的项目，**不意味着账户或套餐免费**。后续应跟随返回的 `next_page` 或按官方条件请求方法读取更新，保持原始文章 ID 去重。先获取元数据，不自动下载任何收费 rendition。官方要求通过安全中间层集成，不能把 API Key 放浏览器。

**社区路线**可参考 RSSHub：

1. [`topics.ts`](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/apnews/topics.ts)：解析公开分类页的标题与链接；默认映射未提供发布时间。仅接入本站现有采集器会被跳过，不能擅自补成抓取时刻。
2. [`mobile-api.ts`](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/apnews/mobile-api.ts)：使用网页移动客户端 GraphQL 数据；PagePromo 含 `publishDateStamp`，部分视频项没有日期；查询哈希或响应结构可能改变。
3. [`rss.ts`](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/apnews/rss.ts)：包装 AP 的 RSS 地址；本次 `index.rss` 请求被拒绝。

这些都是网站内部/公开页面适配，没有官方接口的稳定性承诺，也没有改变 AP 内容许可。公开实例的 403 不代表移动接口在所有部署环境都失效，但尚不能作为当前生产来源。

## Google News RSS：零费用发现入口候选

本次验证成功的搜索方式：

- Reuters：[打开 RSS](https://news.google.com/rss/search?q=site%3Areuters.com%20when%3A1d&hl=en-US&gl=US&ceid=US%3Aen)
- AP：[打开 RSS](https://news.google.com/rss/search?q=site%3Aapnews.com%20when%3A1d&hl=en-US&gl=US&ceid=US%3Aen)

这是非正式的 RSS 搜索入口，**不是 Google 承诺稳定的新闻开发者 API，也不是 Reuters/AP 的授权内容接口**。本次出版方字段分别匹配 Reuters、AP News；读取到的链接指向 Google News 中转页，不保证能从所有网络直接打开媒体原文。

如果接入，应只形成标题、出版方、链接的发现榜单，标明“经 Google News 收录”。不能把 RSS HTML 描述当作新闻正文；不能把聚合器的 pubDate 未经核对地称为源站精确发布时间。搜索排序、最多返回条数和缺漏也会影响“热度”，100 条不等于当天全部报道。

对当前零费用目标，建议顺序：**BBC 独立只读 RSS → Reuters/AP 链接发现榜单 → 取得许可后再合入统一热词与 AI 管线**。这次请求是接入研究，尚未将上述候选通道自动启用。
