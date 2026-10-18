# headline.infinitas.top：跨设备私有翻译

当前方案：GitHub Pages 提供公开新闻；Cloudflare Worker 仅处理 `/api/cloud/*`；Google 登录限制唯一获准邮箱。Cloudflare Access 免费版要求绑卡并授权超额费用，因此不启用 Access，不开通 Zero Trust，不关联支付方式。

## 已准备的资源

- Worker：`headline-private-gateway`，Workers Free；workers.dev 与预览 URL 关闭，正文日志关闭。
- D1：`headline-budget`，仅存日期、调用次数与暂停状态。
- `SESSION_SECRET`：系统随机生成的会话签名密钥，存 Worker Secret，不提交仓库。
- `ALLOWED_EMAIL`：唯一获准邮箱，存 Worker Secret，不公开。
- Google 项目：Headline News，不启用计费。Google 登录 Client ID 为公开标识，配置为 Worker var `GOOGLE_CLIENT_ID`；本方案不需要 OAuth client secret。

部署是否真正完成，以实际登录和翻译验证结果为准。只有资源创建不代表可以翻译。未配置时服务器拒绝调用 Gemini。

## Google 登录设置

1. Google Cloud Console → 选择 Headline News → Google Auth Platform。设置应用名称 Headline News，支持邮箱与联系邮箱为账号主人；选择 External，测试阶段仅添加你的邮箱。只使用登录所需的 openid、email、profile，不申请 Gmail、Drive 或其他权限。
2. 创建 Web application 类型的 OAuth 客户端，名称 Headline Web；Authorized JavaScript origins 仅填 `https://headline.infinitas.top`。采用 Google Identity Services 整页跳转登录；Authorized redirect URIs 填 `https://headline.infinitas.top/api/cloud/google/callback`。回调校验 Google 双提交 CSRF token 后签发会话，不依赖弹窗。
3. 复制公开 Client ID（以 `.apps.googleusercontent.com` 结尾）到 `cloudflare/wrangler.jsonc` 的 `GOOGLE_CLIENT_ID`。不要复制或存储客户端 secret。
4. 如需主页及隐私链接，使用 `https://headline.infinitas.top/` 与 `https://headline.infinitas.top/privacy.html`，Authorized domain 填 `infinitas.top`。

Google 登录只验证身份，不向 Google Identity 发送新闻。Worker 校验 Google RSA 签名、issuer、audience、有效期、email_verified 与唯一允许邮箱；随后签发一小时会话 Cookie。Cookie 设置 HttpOnly、Secure、SameSite=Strict，Path=/api/cloud，普通新闻请求不携带它到 GitHub。会话和 Google ID token 不放 localStorage。

## Gemini 密钥与零费用边界

1. 在 https://aistudio.google.com/api-keys 创建密钥，确认项目为 Free Tier 且未关联计费账户。模型为 `gemini-2.5-flash-lite`，只有官方仍提供免费档时使用。
2. Cloudflare → Workers & Pages → headline-private-gateway → Settings → Variables and Secrets → Add：类型 **Secret**，名称 `GEMINI_API_KEY`，值由你直接输入 Cloudflare，不发聊天、不填网页前端。
3. CLI 等价操作：进入 cloudflare 目录运行 `npx wrangler@4 secret put GEMINI_API_KEY`，在私有提示中输入。不要把真实 Key 写在命令参数、代码或环境示例文件。
4. 核实 Gemini 项目免费且未关联计费后才把 `FREE_TIER_CONFIRMED` 设为字符串 `true` 并部署。程序不能凭 Key 独立核实 Google 账单状态。

默认北京时间每天最多 100 段、单次最多 2,000 字符。D1 在调用前原子预留额度，多个设备共用。失败请求也计数；Google 返回 429 时当天暂停，不重试、不换付费模型、不升级账户。每分钟翻译 10 次、登录 5 次的边缘限流是辅助保护，不是全球严格计数。长文按段翻译，每段单独计数。

## 域名路由与部署

`headline.infinitas.top` CNAME 指向 `suesone.github.io`，GitHub Pages 自定义域名与强制 HTTPS 已配置。只将此记录切换为 Cloudflare 代理，保留根域名和其他子域名，TLS 使用 Full (strict)，不关闭源站证书校验。

启用 Worker route：`headline.infinitas.top/api/cloud/*`，zone_name 为 `infinitas.top`。不设置整个域名的 Worker Custom Domain。公开新闻仍由 GitHub Pages 提供。

命令：

```sh
cd cloudflare
npm ci --ignore-scripts
npm test
npx wrangler@4 d1 execute headline-budget --remote --file schema.sql
npm run deploy
```

部署工具授权使用官方 Wrangler OAuth，权限仅限账户读取、Workers、路由、D1 和 zone 读取。凭据以加密文件保存，解密密钥留 macOS Keychain。不需要提供 Cloudflare Global API Key。

## 上线验证

- 未登录 GET status / POST translate 返回 401；伪造或过期 Cookie 拒绝；这些请求不调用 Gemini。
- config 只返回公开 Client ID，不返回邮箱、Gemini Key 或会话密钥。
- 登录页 `/login.html` 用获准 Google 账号登录，回到新闻页选择 Gemini，手动翻译一条标题。
- 其他 Google 邮箱被 Worker 拒绝，不能仅凭 Google 登录成功使用翻译。
- 手机和电脑分别登录后均可使用，不需保持个人电脑开机。译文不跨设备同步，刷新页面清除。
- 限流、D1 故障、Google 429 均停止调用；请求与译文 no-store，密钥不出现在浏览器网络、HTML、GitHub 或错误消息里。

## 数据与维护

输入与译文经过 Cloudflare 和 Google，但本项目不持久保存或记录正文。Google 免费档输入输出的处理遵循其条款。Cloudflare 管理员可以修改代码读取 Secret，因此管理账号与部署权限仍需妥善保护。

退出：登录页点击“退出本站翻译登录”，清除本设备 Cookie。紧急撤销所有会话可轮换 SESSION_SECRET；轮换后旧 Cookie 签名失效。暂停翻译：把 FREE_TIER_CONFIRMED 设为 false 并部署。Gemini Key 轮换通过 Worker Secret 完成，永不写入源码。

GitHub Actions 仍每四小时更新新闻。页面脚本更新时增加资源版本，Worker 修改后重新部署。免费政策变化时暂停受影响服务，不接受超额付费条款。

参考：
- https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developers.cloudflare.com/workers/configuration/secrets/
- https://developers.cloudflare.com/workers/configuration/routing/routes/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://ai.google.dev/gemini-api/docs/pricing
