# 独立调度兜底

新闻仍由 GitHub Actions 的 Python 流程采集、去重、保存 30 天历史、发布 Pages。保留北京时间偶数小时整点、17 分、37 分的 GitHub 检查。

新增 `headline-schedule-watchdog`：Cloudflare 在每个偶数小时的 02、12、32、52 分独立检查。它只读取很小的 `public/data/status.json` 发布回执，不读取新闻正文、不调用 Gemini。如果本时段已成功发布，或者 GitHub 最近 20 分钟已有执行/排队任务，就不重复触发。否则调用固定的 `Suesone/headline` / `update.yml` / `main`。GitHub 接到请求后再次检查回执，防止检查与派发间发生重复。

D1 中独立的 `watchdog_attempts` 表原子限制两次补跑至少间隔 10 分钟、每两小时时段最多 4 次；旧计数保留 3 天。`watchdog_health` 只存检查时间、结果和派发次数；不存凭据、新闻或译文。翻译的 `daily_budget` 表不改动。

公网只提供 GET `/api/watchdog/status`，无公网触发接口。密钥只发送到固定 GitHub API；不跟随重定向、不记录上游错误正文、不传入浏览器。Cloudflare 控制台日志关闭。Worker 只有一个 Cron 表达式，每日 48 次检查，保持免费账户，不启用付费升级。

## 最后配置：专用 GitHub 凭据

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token。
2. 名称 `Headline scheduler`，Resource owner 选择 `Suesone`，建议有效期 90 天。
3. Repository access 选择 **Only select repositories**，仅选择 **headline**。
4. Repository permissions 只增加 **Actions: Read and write**；Metadata 只读由 GitHub 自动提供。无需 Contents、Administration、账号权限或全部仓库权限。
5. 由账号主人确认并创建。不要将 Token 发到聊天、截图或仓库。
6. Cloudflare → Workers & Pages → **headline-schedule-watchdog** → Settings → Variables and Secrets，新增 **Secret** `GITHUB_ACTIONS_TOKEN`，直接粘贴并部署。
7. 确认保存后，将 `cloudflare/watchdog/wrangler.jsonc` 中 `WATCHDOG_ENABLED` 改为 `"true"` 并部署。凭据未配置时保持关闭。

首次创建的是 `github_pat_` 开头的细粒度凭据。模块拒绝本机 `gh` 使用的广权限 OAuth 凭据。凭据过期或权限不足时，网站显示需要检查 Secret，GitHub 自己的定时任务继续工作。凭据续期后直接替换 Secret，无需改前端。

## 运维与验证

- 网站显示独立兜底是否启用、上次结果及下次检查时间。[公开状态接口](https://headline.infinitas.top/api/watchdog/status)。
- 正常结果：本时段新闻已成功发布／已有任务执行／已请求补抓。**请求已发送不代表发布已成功**，应检查网页更新时间与 Actions。
- CF 发起的运行在 GitHub 中属于 `workflow_dispatch`，输入 `trigger_source=cloudflare-watchdog`，网页显示“Cloudflare 补抓”；不会伪称 GitHub 的 schedule。
- 手动测试 GitHub 去重：Run workflow，trigger_source 选择 cloudflare-watchdog。已有本时段发布时，schedule-check 成功、update 跳过；过期时才执行更新。
- 本地测试：`node --test tests/watchdog.test.mjs`（真实 SQLite 原子计数）；整体测试：Python pytest、JS 排序/缓存、云端认证与 watchdog 测试。
- 部署时始终明确配置路径：`npx wrangler@4 deploy --config /绝对路径/Headline/cloudflare/watchdog/wrangler.jsonc`，避免误用翻译 Worker 配置。

两套调度平台降低单个平台 cron 漏触发的风险，但最终执行和发布仍依赖 GitHub。GitHub 整体不可用、Cloudflare 故障、密钥过期或免费政策变化时，无法保证按时更新；保留旧新闻并显示状态，不自动购买服务。

官方依据：[Cloudflare Cron](https://developers.cloudflare.com/workers/configuration/cron-triggers/)、[免费限制](https://developers.cloudflare.com/workers/platform/limits/)、[GitHub workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)、[细粒度 Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)。
