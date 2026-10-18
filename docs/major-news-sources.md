> 历史研究记录：当前版本已归档热词与云端 AI，AFP 候选已删除。最新行为和本地翻译见 [README](../README.md)。

# 主流英文新闻源调整（2026-10-18）

本次删除 Global Voices、NASA、Wikinews 配置与当前数据；历史 Git 提交仍可能包含旧记录。新增 BBC、NPR、CNBC，补充 VOA 原创英文新闻。AFP 保留明确禁用的候选位置，未用虚构新闻填充。

## 社区维护的两种形式

- [Plenary awesome-rss-feeds](https://github.com/plenaryapp/awesome-rss-feeds)：开源订阅目录，收录 BBC World、Business、CNBC International 等官方地址。本站直接读取官方 HTTPS RSS，并标注目录，不冒称社区转发。
- [Semantic News](https://github.com/semantic-news/rss-feeds/blob/master/en-general.md)：收录 NPR 1001 新闻频道。目录仍列旧 HTTP 地址，本站采用当前官方 `https://feeds.npr.org/1001/rss.xml`。
- [Feedseek](https://github.com/trvny/feedseek)：实际生成 Reuters Atom 并托管在 GitHub，继续保留为仅标题链接的阅读源。它的 feeds 目录未提供 BBC、NPR、CNBC、AFP，因此没有构造不存在的社区地址。
- VOA 采用[官方当前 RSS 目录](https://www.voanews.com/rssfeeds)。旧 USA / World 和 Learning English RSS 虽返回 200，最新报道停留在 2025 年，不能作为实时来源。此次使用目录中仍在更新的 China / Asia、Korean Peninsula **英文**频道，名称不表示抓取中文或韩文。

选择原则：社区提供可核验官方订阅时优先直连官方；没有官方源时再评估社区转发。公共 RSSHub / RSS-Bridge 先前探测失败，不作为必需基础设施。没有绕过 403、防爬机制或付费墙。

## 实测

可重跑 `.venv/bin/python -m scripts.probe_major`，结果保存在 [major-rss-probes.json](major-rss-probes.json)，含 UTC 检查时间、HTTP 状态、条目数、有效日期数和链接域名，无文章全文。首次本地探测：Reuters 100、BBC World 28、Business 49、NPR 10、CNBC 30、VOA 两频道 8/9，均为 200 且所有条目有发布日期；AFP Fact Check 为 403。数量会随运行变化，本地通过不能代替 GitHub Actions 验证。

只提供最近十条的 NPR RSS 在两次四小时抓取之间可能丢失被挤出的报道；本站不宣称完整收录。VOA 周末更新较少；96 小时没有有效新记录时将提示订阅陈旧。Reuters 社区订阅使用更严格的 36 小时阈值。

## 阅读、统计与 AI 分离

| 来源 | 配置 | 理由 |
| --- | --- | --- |
| Reuters | 标题链接；无热词、AI | 社区转发不改变原内容权利 |
| BBC | 阅读；无热词、AI | [BBC 条款第 8、15 节](https://www.bbc.com/usingthebbc/terms-of-use/)允许有条件个人 RSS 展示，但计算分析需要许可；保留 BBC News 署名与链接 |
| NPR | 阅读、标题实体/短语计数；无 AI | [NPR Content Feeds 条款](https://www.npr.org/about-npr/179876898/terms-of-use)允许有条件个人站点展示，明确限制翻译与修改。实体计数是本站对公开标题的统计判断，并非 NPR 提供的元数据或额外授权；不修改显示的英文标题和摘要，不训练模型 |
| CNBC | 阅读；无热词、AI | [当前官方 RSS](https://www.cnbc.com/rss-feeds/)可读；[Versant Prohibited Actions](https://www.versantmedia.com/terms/prohibited-actions)限制翻译、内容再利用及数据抽取，没有把可读 RSS 推断为 AI 授权 |
| VOA 原创 | 阅读、热词、可选 AI | [VOA 使用政策](https://www.voanews.com/p/5338.html)将独家制作文本列为 public domain，第三方内容除外。只收录已核验作者，拒绝未知署名和 RSS 标题、摘要、作者中带 Reuters/AP/AFP 信用标记的报道。政策依据仅适用于收录文字，不涵盖照片、音视频或正文中未提供的材料 |
| AFP | 禁用 | [AFP Stories](https://www.afp.com/en/our-offer/afp-stories)和[官方 API](https://www-pp.afp.com/en/our-offer/afp-api)提供订阅/试用入口，未验证到可长期零费用使用的英文综合新闻 RSS。Fact Check 候选 403，且不是综合新闻流；France 24 是另一家媒体，不能直接当作 AFP |

统计与翻译不等于训练模型，但来源可能分别限制翻译、计算分析或内容改编，需要逐项判断。以上是本项目的保守实现选择，不是对第三方内容作全面重新授权。

## 实现保障

- `topics_enabled` 与 `ai_enabled` 独立控制。`mode: read_only` 保留阅读摘要，默认关闭两个处理功能；`links_only` 还会清空摘要。
- NPR 的 `topics_title_only` 确保只分析标题。原始英文显示不变，统计链接回原文。
- AI 标题请求、缓存回填、话题语境输入和引用验证都过滤 `ai_allowed`。即使一个话题同时出现于 NPR 和 VOA，也只发送允许的 VOA 材料；不能通过话题关联间接传入受限来源。
- VOA 的 `allowed_authors` 是人工核验白名单；新署名需核验后更新，未知署名会增加“跳过”数量。仅凭文章 URL 在 VOA 域名不能自动判断其原创权利。
- 两个 BBC 频道在来源计数中算一个 BBC；两个 VOA 频道算一个 VOA。
- 采集时移除已删除来源的历史条目，并重建时段与每日统计；缓存不会向禁止 AI 的来源回填译文。
- 没有 Cloudflare 免费账户密钥时，AI 保持停用，新闻与热词正常；此轮未进行真实 AI 付费或免费调用。
