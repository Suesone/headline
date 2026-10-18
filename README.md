# Headline · 全球新闻手记

每四小时整理英文新闻，按话题连接报道，辅助英语阅读。原生 HTML/CSS/JavaScript + Python，无常驻服务器。目标是**零服务费**；免费服务限制变化时停止受影响功能，不自动付费。

- 网页：https://suesone.github.io/headline/
- 仓库：https://github.com/Suesone/headline
- 北京时间每日 00、04、08、12、16、20 点触发；GitHub Actions 和 Pages 可能延迟。
- 实时热词来自最近完成的四小时窗口；今日热词按北京时间自然日合并。可选择昨天或历史时段。
- 首次抓取只覆盖订阅源当前提供的记录，无法追溯它没有提供的旧报道。
- 页面默认显示最近完成的时段。如果没有新报道，点击「查看最近所有时段」。

## 当前来源与限制

首批候选 BBC World、BBC Business、Guardian World **都能读取 RSS**，但使用条件限制自动分析/AI，默认禁用。不要把 RSS 可访问当作转载或 AI 授权。

已启用 **Global Voices**（国际公民媒体，CC BY 3.0）和 **NASA**（官方科学资讯，遵循 NASA 使用指引）。它们不是 Reuters/AP 的替代通讯社，发布频率较低，部分四小时时段为空是正常情况。Wikinews 候选订阅实测 404，默认禁用。后续可在拿到合适许可后加入更多主流来源。

每条新闻保留作者（若订阅提供）、来源、原文链接与许可；只用 RSS 标题和短摘要。没有全文抓取、图片下载或付费墙绕过。

依据（实施时核查）：

- [BBC 使用条件](https://www.bbc.com/usingthebbc/terms-of-use/)
- [Guardian 条款第 3 节](https://www.theguardian.com/help/terms-of-service)
- [Global Voices 许可声明](https://globalvoices.org/about/)
- [NASA 使用指引](https://www.nasa.gov/nasa-brand-center/images-and-media/)

## 本地运行

需要 Python 3.12（不要用 Python 3.14 安装这组 spaCy 依赖）。在项目目录打开终端：

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
python -m scripts.collect
python -m pytest -q
python -m http.server 8765 --directory public
```

打开 http://localhost:8765/ 。不要直接双击 index.html，浏览器会限制本地 JSON 读取。

## 日常操作

### 手动更新

打开 GitHub 仓库 → **Actions** → **Update news and deploy** → **Run workflow** → 选择 `main` → 运行。绿色勾表示流程结束；点击运行可以查看摘要、失败步骤和两天观察状态。

自动任务运行在 GitHub，关闭电脑也能执行。公开仓库长期无活动可能暂停定时任务；若页面显示更新延迟，请检查 Actions 是否启用并手动运行一次。正文和数据文件存在不代表实时源始终可用。

### 修改新闻源

编辑 `config/sources.json`。新增一项，设置唯一 `id`、名称、媒体主体 `publisher`、RSS `url`、来源主页、许可链接、条款链接和说明；确认允许公开显示、分析、翻译后，再把 `enabled` 设为 `true`。不要提交需登录的订阅链接或带私人令牌的 URL。

`publisher` 应使用真实媒体主体：同一媒体多个频道只算一个独立来源。可用 `exclude_title_prefixes` 忽略固定前缀；NASA 默认过滤 APOD 页面索引噪声。

编辑 `config/aliases.json` 可以合并话题别名，例如 US、U.S. → United States。不确定的同名人物不要直接合并。热词由模型与统计工具提取，可能误判；点击查看原报道再判断。

### 可选 AI：默认未启用实际调用

没有密钥时，英文新闻、热词和词典入口照常使用；不会显示伪造的中文译文。

1. 注册/登录 Cloudflare，确认账户使用 **Workers Free**；不要启用付费或试用 Workers 订阅，也不要充值 AI Gateway。
2. 创建限定到该账户的 API Token，授权 **Workers AI: Read** 和读取账户订阅所需的 **Account Billing: Read**。实际权限以 Cloudflare 控制台为准。如果订阅查询被拒绝，程序会停止 AI，不绕过检查。
3. 在 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加 `CF_ACCOUNT_ID` 和 `CF_API_TOKEN`。
4. 在 `config/settings.json` 中，将 `ai.free_plan_confirmed` 改为 `true`。默认模型是 `@cf/qwen/qwen3-30b-a3b-fp8`，`ai.enabled` 可以随时关闭。
5. 手动运行更新。查看页面底部 AI 状态；额度不足、账户检查失败或模型失效时暂停新增 AI。

每次最多翻译 40 个当前时段标题，并解释前 10 个话题。页面的中英开关只显示已有缓存，不发起 API 调用。AI 只接收公开标题、短摘要和话题，不接收个人信息。

更换密钥：在 Secrets 中更新 `CF_API_TOKEN`，然后手动运行；不要把密钥写进源码、网页或公开 Issues。免费额度以账户为单位，其他项目也会消耗额度。程序在调用前核查 Workers 订阅并拒绝付费/试用计划；免费账户被升级或政策变化后，应先关闭 `ai.enabled`。AI 文字仍可能有误，引用链接不能自动证明每一句话正确。

[Cloudflare Workers AI 免费额度](https://developers.cloudflare.com/workers-ai/platform/pricing/)

### 发布自己的副本

Fork 本仓库 → Settings → Pages → Source 选择 **GitHub Actions** → Actions 启用工作流并手动运行。GitHub Free 的 Pages 来源仓库需公开。使用系统提供的 `github.io` 地址，无需购买域名。

此网页、源码、新闻数据和翻译缓存都是公开的；不收集个人资料，不设置分析追踪。中英对照偏好只保存在你的浏览器。词典查询需要点击链接后跳转官方词典。

## 数据与维护

- `public/`：实际发布目录；`public/data/news.json` 是浏览器唯一数据接口。
- `state/news.json`：去重身份与滚动历史，`state/ai-cache.json`：按内容缓存，`state/health.json`：两天运行观察。
- `scripts/collect.py`：抓取、清洗、去重、归档、统计；`scripts/ai.py`：免费账户检查、翻译和语境说明。
- `tests/`：时间边界、去重、迟到报道、来源故障、AI 降级与缓存测试。

统计时间使用发布时间，不以抓取时间替代。零点收集的前四小时属于昨天；尚未结束的时段下次再展示。没有日期、危险链接和明显未来日期的条目跳过，并显示跳过数量。重复报道不重复计数，跨媒体报道保留；不同标题的同一事件不保证自动精确合并。

数据保留最近 30 个北京时间自然日；Git 的历史提交仍可能保留过去版本。AI 内容缓存保留 30 天。单源最多重试三次；部分失败仍发布成功来源，全部失败保留先前新闻并标记失败。所有来源禁用后旧条目会移除。

前两天的观察由同一个免费定时工作流记录，不另外启动收费代理任务；需要实际经过两天才能完成，见 `state/health.json`。源码改动应先通过 `python -m pytest -q` 和 `node --check public/app.js`。

## 社区参考与许可

界面和流程借鉴 [NewsNow](https://github.com/newsnext/newsnow)、[RSSBox](https://github.com/versun/RSSBox)、[TrendRadar](https://github.com/sansan0/TrendRadar) 的公开设计与经验，没有复制其实现。依赖 feedparser、spaCy、YAKE；各自保留原许可。

本站代码使用 MIT License。新闻、摘要、许可声明及第三方模型不受本站代码许可重新授权。
