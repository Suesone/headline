# infinitas.top：公开新闻，私有翻译

状态：源码已准备；必须完成 Cloudflare 登录、核查现有 DNS、配置 Access、D1 与 Secrets 后才能上线。未配置时 API 拒绝所有翻译调用。不要将此文当作已经部署的证明。

## 结构与数据

`https://infinitas.top/` → Cloudflare Worker → GitHub Pages 上的公开英文新闻。

`/api/cloud/*` → Cloudflare Access 登录保护 → Worker 验证 JWT 签名、issuer、audience、有效期与唯一获准邮箱 → Gemini。

浏览器不保存或收到 Gemini Key。`GEMINI_API_KEY` 与 `ALLOWED_EMAIL` 放 Worker Secrets。Secret 不是绝对不可获取：有权修改 Worker 的 Cloudflare 管理员可以让代码读取 Secret，因此保护管理账号、启用 MFA、减少管理员与 Token 权限。不要在聊天、命令参数、代码或仓库写入真实密钥。

译文和输入只在浏览器内存与处理请求期间存在；本应用不持久保存、不记录请求正文、不上传 GitHub。Cloudflare 和 Google 会处理这些内容，平台自身数据政策仍适用。D1 仅存日期、调用数量、暂停标志，不存用户、文本或密钥。当前不做译文跨设备同步。

## 一次性配置（仅 Free 计划）

1. Cloudflare 选择 `infinitas.top`，核查根域名当前 A/AAAA/CNAME、Worker route。若已有网站，先确认替换用途或改用专门子域名；不要删除 MX/TXT 邮件或验证记录。本版只允许根域名，改子域名还须同步修改前端允许域名与 Worker 配置。
2. Zero Trust → Access → Applications → 添加 Self-hosted 应用，域名 `infinitas.top`，路径 `/api/cloud/*`。Allow 策略仅 Include 你指定的邮箱，不选 Everyone，不添加 Bypass。登录方式可用邮箱一次性验证码。仅在确认免费计划后继续；如果出现购买或计费要求，停止。记录 team domain（`https://你的团队.cloudflareaccess.com`）和应用 AUD。
3. 在终端进入 `cloudflare` 目录。安装依赖 `npm ci --ignore-scripts`。通过官方 Wrangler 登录 `npx wrangler@4 login`，在浏览器核对授权范围，由账号主人完成授权。
4. 创建免费 D1：`npx wrangler@4 d1 create headline-budget`。将返回的 database_id 填入 `wrangler.jsonc` 的 `d1_databases`，binding 为 `BUDGET`，database_name 为 `headline-budget`。不要把 API Token 填入配置。
5. `npx wrangler@4 d1 execute headline-budget --remote --file schema.sql` 建表。配置 vars 的 ACCESS_ISSUER、ACCESS_AUD。确认 Gemini 项目 Free Tier 且未关联计费后才将 FREE_TIER_CONFIRMED 改为字符串 `true`；程序无法凭 Key 验证 Google 账单状态。
6. 用 `npx wrangler@4 secret put GEMINI_API_KEY` 在私有交互提示输入 Gemini Key。用 `npx wrangler@4 secret put ALLOWED_EMAIL` 输入唯一获准邮箱。不把值放命令行参数中。
7. 确认 Access 已覆盖 `/api/cloud/*` 后，启用配置中的 routes：`[{"pattern":"infinitas.top","custom_domain":true}]`，再 `npm run deploy`。如果已有冲突 DNS，先核查并由域名主人确认替换对应网站记录。Custom Domain 由 Cloudflare 管理 DNS 与 TLS，不需要另给 GitHub Pages 设置相同根域名。
8. 保持 workers_dev=false、preview_urls=false、observability.enabled=false；不要开启正文或完整 headers 日志。部署后检查没有其他可绕过登录的路由。JWT 验证本身也会拒绝未获准调用。

## 必须完成的上线验证

- 未登录：新闻可读；`/api/cloud/login` 出现 Access 登录；status/translate 不向 Google 发起请求。
- 错误邮箱：Access 拒绝；Worker 也校验唯一邮箱。
- 正确邮箱：点击登录后回到网页，选 Gemini，手动翻译一条标题。Key 不出现在浏览器网络请求、HTML、GitHub 和错误消息中；译文响应 Cache-Control:no-store。
- 手机和电脑分别登录，均可使用；不用保持个人电脑开机。
- 触发上限、429 或 D1 故障：停止调用；不重试、不换模型、不升级账户。
- API 使用固定 Gemini 地址与模型，不接受浏览器传入 Key、模型、工具或 URL，单次最多 2,000 字符。长文在浏览器按段发送，限额按段计。

默认北京时间每日最多 100 段，服务端 D1 原子计数；每分钟 10 段的边缘速率限制是辅助保护，并非全球严格计数。模型 gemini-2.5-flash-lite 只有在官方免费档仍适用时使用。计数包含失败请求；上游 429 暂停到北京时间次日。D1/Workers/Gemini 免费政策改变时停用接口，不启用付费。

## 更新与回退

新闻继续由 GitHub Actions 每四小时更新，Worker 仅转发公开页面，无需为每次新闻更新重新部署 Worker。网页资源增加版本号以避免旧浏览器缓存。

代码修改后：`npm ci --prefix cloudflare --ignore-scripts`、`npm test --prefix cloudflare`，从 cloudflare 目录 `npm run deploy`。本仓库没有 Cloudflare 自动部署 Token。

紧急停用翻译：把 FREE_TIER_CONFIRMED 改为 `false`，部署；必要时在 Google 撤销密钥。轮换密钥用 `secret put`，不写回源码。域名解绑前确认替代页面或原 DNS 记录，再删除对应 Worker Custom Domain，保留其他业务记录。

官方参考：
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/workers/configuration/routing/custom-domains/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
- https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/
- https://ai.google.dev/gemini-api/docs/pricing
