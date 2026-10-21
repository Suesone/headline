# 榜中榜配图核查

核查日期：2026-10-22，北京时间。用户要求所有当前新闻源均支持才添加配图，否则取消。因此本轮不启用新闻配图，保持纯标题榜单。

## 当前 RSS 实测

本机只读请求配置中的六个 RSS，全部返回 HTTP 200；逐一检查每源前 10 条。只读取图片地址与元数据，没有下载照片，没有将网页全文写入新闻数据。下表的图片数量表示候选地址存在，不保证图片响应、长期可用或站外展示许可。

| 来源 | 前 10 条的图片信息 | 结论 |
| --- | --- | --- |
| BBC World | 10 条有 `media:thumbnail`，240×135 | RSS 有缩略图，公开展示仍需符合适用条件 |
| BBC Business | 10 条有 `media:thumbnail`，240×135 | 同上 |
| NPR News | 8 条的 HTML 内容有非追踪图片候选；10 条均有追踪像素 | 不能把所有 `<img>` 当成配图，样本中并非每条都有新闻图片 |
| CNBC International | 0 条有新闻图片字段或 HTML 图片 | 当前 RSS 不支持直接取配图；额外抓取原文另涉访问与使用条件 |
| The Guardian World | 10 条有 `media:content` 图片地址、不同尺寸与署名字段 | 技术上有图片，不等于获得额外公开转载授权 |
| NHK 日语 / Hatena | 10 条有 `hatena:imageurl` 指向 NHK；HTML 还含社区缩略图、图标与计数图 | 可发现原图地址，但社区收录不等于 NHK 图片的再利用许可 |

原始计数：[news-image-probes.json](news-image-probes.json)。这些是单次样本，不是来源对以后每篇报道的图片保证。

## 额外验证与官方说明

- CNBC 样本原文页面 HTTP 200，含 `og:image`；说明网页上有图，而非 RSS 已提供图。未下载照片。对应官方 [Versant Prohibited Actions](https://www.versantmedia.com/terms/prohibited-actions) 第 6、10、12 项限制内容的复制、展示、嵌入和提取，未确认存在适用于本站的图片展示许可。因此不增加原文抓取兜底。
- [BBC 使用条件](https://www.bbc.com/usingthebbc/terms-of-use/)区分 RSS 与其他元数据用途；本次该网页对研究搜索工具拒绝访问，未据此声称已获得图片授权。[BBC 授权分发 API 文档](https://information-syndication.api.bbc.com/)要求有分发关系与 API Key，并区分图片权利和署名；它不是当前使用的免费公开 RSS。
- [卫报 RSS 说明](https://www.theguardian.com/help/feeds)将使用范围与[使用条件](https://www.theguardian.com/help/terms-of-service)关联；图片候选可读取不自动代表适合在本站再发布。
- [NPR 使用条件](https://www.npr.org/about-npr/179876898/terms-of-use)可通过本机请求读取，未取得额外图片展示授权。当前不将图片发现与授权混为一谈。
- [Hatena RSS 官方说明](https://developer.hatena.ne.jp/ja/documents/bookmark/misc/feed/)说明其社区订阅能力，不构成 NHK 原图的授权。

没有声称所有图片都被禁止使用；本轮结论仅为“尚不满足全部来源支持且可确认展示条件”的启用门槛。不添加部分来源配图、占位图、网页抓图或收费图片接口。
