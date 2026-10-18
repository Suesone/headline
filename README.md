# Headline · 国际新闻榜

[打开网页](https://headline.infinitas.top/) · [源码仓库](https://github.com/Suesone/headline)

每两小时整理主流英文 RSS，先展示“榜中榜”，再按来源阅读。公开网站无需登录、无常驻服务器、零服务费。**翻译按需执行，译文仅留当前页面内存，不写入项目文件或 GitHub。网页默认选中 Gemini，已移除 Chrome / Ollama 翻译选项；跨设备 Gemini 通过 Google 登录保护的 Cloudflare 接口发送原文到 Google，密钥保存在 Worker Secret。**

## 当前功能

- 北京时间 00:00 起每隔 2 小时（每天十二次）由 GitHub Actions 更新，允许调度延迟；关闭电脑后英文新闻仍可更新。
- 首页优先“榜中榜”：从各源前五条候选中，按 RSS 顺序与新鲜度推荐；完全相同标题合并，同一媒体多个频道不重复加分。不进行热词或语义分析，也没有虚构的阅读量。
- 默认看最近 24 小时已完成时段；可以切换两小时时段、最近 30 天和单一来源。
- 仅展示标题，榜中榜最多 10 条、全部大号黑体，各源前 3 条大号黑体；不展示或翻译 RSS 摘要，不额外抓取正文。
- 每源默认显示十条，按需再显示十条；未展示的内容不送入翻译。
- 单条翻译、翻译当前屏幕、勾选报道后翻译；相同文字复用本页内存缓存。可用“隐藏译文／显示译文”切换，不清除缓存、不额外调用 AI；刷新页面或“清除译文”才清除缓存。滚动后不会自动翻译。
- 个别报道可进入“全文”阅读器，粘贴可正常访问的原文或导入 .txt，在本机按段翻译，支持停止后续段落。不会声称从 RSS 得到全文，不绕过付费墙。
- 英语查词提供 Cambridge 与 Merriam-Webster 链接，点击后访问词典，不抓取释义。

**实时热词、今日热词与 Cloudflare AI 已归档**。当前工作流不安装 NLP 模型、不提取热词、不读取 Cloudflare 密钥、不调用云端 AI。旧实现保留在 `archive/` 和 Git 历史，未发布到网站。

## 来源

当前配置八个订阅流：Reuters（Feedseek 社区转发）、BBC World、BBC Business、NPR News、CNBC International，以及 The Guardian World、The Washington Post、NHK WORLD-JAPAN。新增来源及备用聚合实测见 [第二批来源记录](docs/second-batch-sources.md)。VOA 两个频道因缺少实际可展示内容已移除。BBC、CNBC 优先采用 Plenary 社区目录收录的官方 RSS；NPR 参考 Semantic News 的 1001 频道并采用当前官方 HTTPS 地址。官方地址可用时不额外依赖公共转发服务器。

AFP 的 Fact Check 候选复测仍返回 403，且并非综合新闻流，已从当前配置删除。没有找到可核验、稳定、长期零费用的 AFP 英文综合新闻社区 RSS；没有将 France 24 当作 AFP。NASA、Global Voices、Wikinews 测试源此前已移除。

首批实测记录在 [docs/major-rss-probes.json](docs/major-rss-probes.json)，含检查时间、条目数与日期，不保存文章全文。配置可用的来源临时失败时保留旧新闻并提示；不因一次短暂故障立即删除来源。

社区整理或转发不改变内容权利。**本地翻译不等于获得所有媒体条款的豁免或公开传播译文的许可。** 本项目实现私人辅助阅读；原始内容保留来源与链接，不训练模型。

## 按需翻译：面向入门者

完整说明也在网页的 [本地翻译使用说明](https://headline.infinitas.top/local-guide.html)。

### Gemini 跨设备翻译

1. 打开 [登录页](https://headline.infinitas.top/login.html)，使用获准的 Google 账号登录。
2. 网页默认选中 Gemini。点击报道的“翻译”、勾选报道后批量翻译，或点击“译 · 当前屏幕”。默认选中引擎不代表自动调用；加载、滚动、切换来源均不发送标题给 AI。
3. 感兴趣的全文可自行复制到“全文”对话框，或导入 .txt（最多 60,000 字符），按段翻译。本站不会抓取付费正文。

Gemini 密钥只保存在 Cloudflare Secret；原文经受保护接口发送 Google，译文只在当前页面内存中，刷新后清空。相同标题复用本页缓存，不重复调用。默认模型 `gemini-3.5-flash-lite`，每日最多 100 段，429 后暂停当天调用，不自动升级或切换付费服务。零费用以未关联付费计费的免费项目为前提。

Chrome / Ollama 本地翻译选项已从网页移除。`scripts/local_reader.py` 保留作历史开发工具，不影响线上部署。密钥维护见 [Cloudflare 部署说明](docs/cloudflare-deployment.md)。

## 新闻采集与维护

需要 Python 3.12+：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.collect
python -m pytest -q
node --test tests/*.test.cjs
```

日常英文采集只需要 feedparser；pytest 用于验证。旧 NLP 测试在没有 spaCy/YAKE/模型时跳过，恢复热词需另行安装 `archive/requirements-hotwords.txt` 的依赖。仅预览网页可运行 `python3 -m scripts.local_reader`；可阅读英文，线上翻译请使用自有域名。

- **手动更新**：仓库 → Actions → Update news and deploy → Run workflow。绿色勾表示流程结束，页面显示实际更新时间。
- **修改来源**：编辑 `config/sources.json` 的 RSS、名称、`publisher`、来源主页、条款与社区目录链接，再手动运行。不要提交需要私人令牌的 URL。
- **同媒体计数**：`publisher` 是媒体主体，BBC 多频道仍属于同一家媒体。
- **订阅陈旧**：Reuters 超过 36 小时、其他源超过 96 小时没有有效新条目时提示错误并保留旧数据。NPR 仅最近十条，两小时抓取不能保证完整收录。
- **自动更新暂停**：公开仓库长期无活动可能暂停定时任务，检查 Actions 并手动运行一次。
- **部署自己的副本**：Fork → Settings → Pages → GitHub Actions → 启用并手动运行。使用免费 github.io 地址，不买域名；修改本地阅读器 NEWS_URL 指向自己的英文数据地址。

每条新闻使用发布日期归档，迟到报道补入原窗口；零点前两小时属于昨天。GUID、规范化链接及同源相似标题去重，记录最近 30 天。Git 历史仍可能保留旧版本。

## 文件

- `public/`：发布的网页、排序与本地翻译客户端；`data/news.json` 只包含新闻快照。
- `scripts/collect.py`：RSS 获取、清洗、去重、归档。没有定时云端翻译入口。
- `scripts/local_reader.py`：本机阅读器、云功能关闭的 Ollama，以及明确启用后才调用的 Gemini 接口。
- `state/news.json`：滚动英文历史；`state/health.json`：免费定时流程的两天运行观察。
- `archive/`：旧热词页面和云端 AI 代码，仅保留、不发布、不执行。
- `tests/`：日期边界、去重、来源失败、排序、翻译分段/缓存/取消与本机隔离验证。

不保存个人资料、不设置分析追踪。当前没有 Cloudflare AI 调用，也无需配置或更换其 Secrets；若此前创建过密钥，可自行在 GitHub Secrets 中删除，工作流已不读取它们。

界面参考 [今日热榜](https://tophub.today/)的榜中榜、来源卡片与前列内容层级，采用本站独立文字标识。流程参考 NewsNow、RSSBox、TrendRadar 的开源经验，没有复制其实现。本站代码使用 MIT License；新闻内容和第三方模型保留原有权利及许可。

### 自有域名与跨设备翻译（可选）

`cloudflare/` 提供 `headline.infinitas.top` 的安全网关。公开新闻由 GitHub Pages 提供；翻译需获准的 Google 账号登录，Gemini Key 放 Worker Secret，译文仅留当前浏览器内存。默认每日 100 段，额度限制后暂停。配置缺失时拒绝调用；不会将 Key 放进前端。域名已启用 HTTPS，Gemini Secret 已保存，免费档已由账号主人确认；Google 整页登录回调已配置。使用步骤及维护方法详见 [Cloudflare 部署说明](docs/cloudflare-deployment.md)。

验证：`npm ci --prefix cloudflare --ignore-scripts` 后 `npm test --prefix cloudflare`。无需密钥，测试不会调用真实 Gemini。

### 抓取推送并发修复

2026-10-18 失败运行 `39111391279` 的 RSS 步骤成功；失败发生在 `git push`，原因是抓取期间维护者向 main 推送了新提交。工作流现在从最新 main 检出完整历史；推送被拒时重新读取远端最新代码、配置与历史，运行检查并重新抓取后再推送（最多三次）。不强推、不覆盖远端改动，失败时停止部署，避免发布旧代码。
