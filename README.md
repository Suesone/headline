# Headline · 国际新闻榜

[打开网页](https://headline.infinitas.top/) · [源码仓库](https://github.com/Suesone/headline)

每四小时整理主流英文 RSS，先展示“榜中榜”，再按来源阅读。公开网站无需登录、无常驻服务器、零服务费。**翻译按需执行，译文仅留当前页面内存，不写入项目文件或 GitHub。Chrome / Ollama 为本地推理；跨设备 Gemini 通过 Google 登录保护的 Cloudflare 接口发送原文到 Google，密钥保存在 Worker Secret；另保留本机 Gemini 阅读器。**

## 当前功能

- 北京时间 00、04、08、12、16、20 点由 GitHub Actions 更新，允许调度延迟；关闭电脑后英文新闻仍可更新。
- 首页优先“榜中榜”：从各源前五条候选中，按 RSS 顺序与新鲜度推荐；完全相同标题合并，同一媒体多个频道不重复加分。不进行热词或语义分析，也没有虚构的阅读量。
- 默认看最近 24 小时已完成时段；可以切换四小时时段、最近 30 天和单一来源。
- 各源前两条使用大标题与 RSS 简短摘要，后列只展示标题和阅读操作。RSS 摘要并非原文首段；没有摘要时明确提示，不额外抓取正文。
- 每源默认显示十条，按需再显示十条；未展示的内容不送入翻译。
- 单条翻译、翻译当前屏幕、勾选报道后翻译；相同文字复用本页内存缓存。滚动后不会自动翻译。
- 个别报道可进入“全文”阅读器，粘贴可正常访问的原文或导入 .txt，在本机按段翻译，支持停止后续段落。不会声称从 RSS 得到全文，不绕过付费墙。
- 英语查词提供 Cambridge 与 Merriam-Webster 链接，点击后访问词典，不抓取释义。

**实时热词、今日热词与 Cloudflare AI 已归档**。当前工作流不安装 NLP 模型、不提取热词、不读取 Cloudflare 密钥、不调用云端 AI。旧实现保留在 `archive/` 和 Git 历史，未发布到网站。

## 来源

当前保留五个订阅流：Reuters（Feedseek 社区转发）、BBC World、BBC Business、NPR News、CNBC International。VOA 两个频道因缺少实际可展示内容已移除。BBC、CNBC 优先采用 Plenary 社区目录收录的官方 RSS；NPR 参考 Semantic News 的 1001 频道并采用当前官方 HTTPS 地址。官方地址可用时不额外依赖公共转发服务器。

AFP 的 Fact Check 候选复测仍返回 403，且并非综合新闻流，已从当前配置删除。没有找到可核验、稳定、长期零费用的 AFP 英文综合新闻社区 RSS；没有将 France 24 当作 AFP。NASA、Global Voices、Wikinews 测试源此前已移除。

本次实测记录在 [docs/major-rss-probes.json](docs/major-rss-probes.json)，含检查时间、条目数与日期，不保存文章全文。配置可用的来源临时失败时保留旧新闻并提示；不因一次短暂故障立即删除来源。

社区整理或转发不改变内容权利。**本地翻译不等于获得所有媒体条款的豁免或公开传播译文的许可。** 本项目实现私人辅助阅读；原始内容保留来源与链接，不训练模型。

## 按需翻译：面向入门者

完整说明也在网页的 [本地翻译使用说明](https://headline.infinitas.top/local-guide.html)。

### Gemini API 本机接口（已加入）

Gemini 是 Google 云端推理，不是本地模型。用户已明确接受发送原文；项目不会将译文上传 GitHub。Google 免费档可能处理输入与输出用于服务改进，不能保证服务商不留存内容。密钥仅由本机进程持有，认证时发送 Google，不进入浏览器或仓库。[官方数据条款](https://ai.google.dev/gemini-api/terms)

1. 在 [Google AI Studio](https://aistudio.google.com/api-keys)取得 **Free Tier、未关联计费账户**项目的 API Key。不要启用计费或充值。
2. 在项目目录运行：

```sh
python3 -m scripts.local_reader --provider gemini --allow-google-upload --free-tier-confirmed
```

3. 终端会提示输入密钥，输入不回显，只存于进程内存。不要把密钥发到聊天或写入命令历史。也支持本机已有的 `GEMINI_API_KEY` 环境变量，程序不会打印它。
4. 打开 **http://127.0.0.1:8765/**，选择 **Gemini API · 原文发送 Google**，再按需翻译。无需安装 Ollama。

默认模型 `gemini-2.5-flash-lite`，当前官方列有免费档；每次启动最多 20 个推理请求。只翻译显示/选中的文字，重复文字使用本页缓存。额度或速率限制（429）会暂停本次启动后续请求，不自动重试、切换模型或付费升级。全文按段发送 Google，可用 `--max-gemini-requests 40` 调整会话上限（最多 100）。

**零费用的前提是你的项目实际处于未关联计费的免费档。程序不能仅凭 API Key 核实账单状态；会话上限也不能为付费项目保证零费用。** 请在 AI Studio 核实 Billing Tier；免费政策、模型或地区不可用时暂停使用。[价格](https://ai.google.dev/gemini-api/docs/pricing) · [计费状态说明](https://ai.google.dev/gemini-api/docs/billing)

关闭阅读器后清空进程密钥，刷新页面清除译文缓存。公开网页不直接调用 Gemini；本机接口也不会接收浏览器传来的密钥、任意模型名或远程 API 地址。没有后台批量翻译、文件上传、Google Search grounding 或持久化云缓存。自动化测试使用模拟响应，不需要真实密钥。

### 方式一：桌面 Chrome

使用支持 Translator API 的桌面 Chrome 打开公开网页，点击报道的“翻译”或右下角“译 · 当前屏幕”。首次可能下载本地语言包，推理在设备上完成。

不支持的浏览器、设备或语言对会提示，**不会转用云端**。当前官方说明不支持移动设备；这与浏览器菜单里可能使用云服务的“翻译此页”不同。[Chrome 官方文档](https://developer.chrome.com/docs/ai/translator-api)

### 方式二：本地阅读器 + Ollama

1. 从 [Ollama 官网](https://ollama.com/download)安装 Ollama。
2. 下载本机模型（一次联网下载模型文件，默认约 2.5 GB）：

```sh
ollama pull qwen3:4b
```

3. 在终端进入本项目文件夹并启动阅读器：

```sh
cd /你的路径/Headline
python3 -m scripts.local_reader
```

本机项目当前位于桌面的 Headline 文件夹。阅读器只使用 Python 标准库，无需安装 NLP 或网页框架。打开终端显示的 **http://127.0.0.1:8765/**，选择“Ollama · 本地阅读器”，再点击翻译。

阅读器启动独立的 Ollama 实例，通过 `OLLAMA_NO_CLOUD=1` 关闭云功能，仅监听 `127.0.0.1:11435`。拒绝 cloud 模型、远程模型、非同源请求以及 HTTP 代理转发；不复用可能开启云功能的已有服务。浏览器只访问同源本机接口，公开网页不会直接访问你的模型。[Ollama 本地模式说明](https://docs.ollama.com/faq)

阅读器会下载最新公开英文新闻 JSON；失败时使用项目已有快照。下载新闻、模型文件和语言包不包含待翻译的私人文字。原文与译文只在浏览器内存和本机模型请求中处理，不记录文本日志、写入文件或上传服务器。刷新或关闭页面后，译文缓存不再保留。

较小模型可用以下方式（效果需要核对）：

```sh
ollama pull qwen3:1.7b
python3 -m scripts.local_reader --model qwen3:1.7b
```

端口占用时：

```sh
python3 -m scripts.local_reader --port 8766 --ollama-port 11436
```

按 Ctrl+C 关闭阅读器，同时关闭它启动的模型实例。较长全文最多 60,000 字符，每段约 1,800 字符；速度取决于电脑，分段可能影响上下文。停止功能阻止后续段落，当前已提交到本机模型的段落可能需要结束才停止。翻译可能有误，应对照原文。

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

日常英文采集只需要 feedparser；pytest 用于验证。旧 NLP 测试在没有 spaCy/YAKE/模型时跳过，恢复热词需另行安装 `archive/requirements-hotwords.txt` 的依赖。仅预览网页可运行 `python3 -m scripts.local_reader`；没有 Ollama 仍能阅读英文或使用支持的浏览器本地翻译。

- **手动更新**：仓库 → Actions → Update news and deploy → Run workflow。绿色勾表示流程结束，页面显示实际更新时间。
- **修改来源**：编辑 `config/sources.json` 的 RSS、名称、`publisher`、来源主页、条款与社区目录链接，再手动运行。不要提交需要私人令牌的 URL。
- **同媒体计数**：`publisher` 是媒体主体，BBC 多频道仍属于同一家媒体。
- **订阅陈旧**：Reuters 超过 36 小时、其他源超过 96 小时没有有效新条目时提示错误并保留旧数据。NPR 仅最近十条，四小时抓取不能保证完整收录。
- **自动更新暂停**：公开仓库长期无活动可能暂停定时任务，检查 Actions 并手动运行一次。
- **部署自己的副本**：Fork → Settings → Pages → GitHub Actions → 启用并手动运行。使用免费 github.io 地址，不买域名；修改本地阅读器 NEWS_URL 指向自己的英文数据地址。

每条新闻使用发布日期归档，迟到报道补入原窗口；零点前四小时属于昨天。GUID、规范化链接及同源相似标题去重，记录最近 30 天。Git 历史仍可能保留旧版本。

## 文件

- `public/`：发布的网页、排序与本地翻译客户端；`data/news.json` 只包含新闻快照。
- `scripts/collect.py`：RSS 获取、清洗、去重、归档。没有云端翻译入口。
- `scripts/local_reader.py`：本机阅读器、云功能关闭的 Ollama，以及明确启用后才调用的 Gemini 接口。
- `state/news.json`：滚动英文历史；`state/health.json`：免费定时流程的两天运行观察。
- `archive/`：旧热词页面和云端 AI 代码，仅保留、不发布、不执行。
- `tests/`：日期边界、去重、来源失败、排序、翻译分段/缓存/取消与本机隔离验证。

不保存个人资料、不设置分析追踪。当前没有 Cloudflare AI 调用，也无需配置或更换其 Secrets；若此前创建过密钥，可自行在 GitHub Secrets 中删除，工作流已不读取它们。

界面参考 [今日热榜](https://tophub.today/)的榜中榜、来源卡片与前列内容层级，采用本站独立文字标识。流程参考 NewsNow、RSSBox、TrendRadar 的开源经验，没有复制其实现。本站代码使用 MIT License；新闻内容和第三方模型保留原有权利及许可。

### 自有域名与跨设备翻译（可选）

`cloudflare/` 提供 `headline.infinitas.top` 的安全网关。公开新闻由 GitHub Pages 提供；翻译需获准的 Google 账号登录，Gemini Key 放 Worker Secret，译文仅留当前浏览器内存。默认每日 100 段，额度限制后暂停。配置缺失时拒绝调用；不会将 Key 放进前端。域名已启用 HTTPS，Gemini Secret 已保存，免费档已由账号主人确认；Google 整页登录回调已配置。使用步骤及维护方法详见 [Cloudflare 部署说明](docs/cloudflare-deployment.md)。

验证：`npm ci --prefix cloudflare --ignore-scripts` 后 `npm test --prefix cloudflare`。无需密钥，测试不会调用真实 Gemini。
