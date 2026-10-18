> 历史研究记录：当前版本已归档热词与云端 AI，AFP 候选已删除。最新行为和本地翻译见 [README](../README.md)。

# 社区维护 RSS 的采用情况

核查日期：2026-10-18。当前已启用 **Reuters · 社区 RSS**，使用 [Feedseek](https://github.com/trvny/feedseek) 生成的 Atom 订阅。

## 为什么选择 Feedseek

- 有公开源码、维护者、自动更新工作流和可查看的提交记录。
- 项目说明约每两小时刷新；Reuters 订阅文件今天仍有更新（核查时最新相关提交为北京时间 08:19）。这不是服务可用性保证。
- 本机实测 HTTP 200，100 条，全部有发布时间字段，链接全部指向 `www.reuters.com`。
- 核查时最新条目的订阅日期为北京时间 06:10。网站仍按每日六次读取，显示上游提供的日期，不用抓取时间冒充原站时间。

[订阅地址](https://raw.githubusercontent.com/trvny/feedseek/main/feeds/feed_reuters.xml) · [维护记录](https://github.com/trvny/feedseek/commits/main/feeds/feed_reuters.xml)

## 网站如何使用

作为标题与原文链接的阅读榜单接入，明确标注由 Feedseek 社区维护，保留 Reuters 来源；不显示订阅正文，不调用媒体详情页。

此来源配置为 `mode: links_only`：不生成本站热词，不调用 AI，也不复用以前的中文翻译缓存。社区软件许可不等于 Reuters 内容重新授权；本站不把这条订阅描述为 Reuters 官方 API。

链接只接受 `reuters.com` 及其子域名；例如 `reuters.com.attacker.example` 会被拒绝。无日期条目跳过。订阅没有可用条目，或最新条目超过 36 小时，会显示异常并保留先前记录，避免把停止更新的缓存报告为健康来源。来源之间统计仍按媒体主体区分，不把两个 Reuters 转发服务算成两个媒体。

## 其他社区方案的实测

| 社区方案 | 本次结果 | 处理 |
| --- | --- | --- |
| Feedseek Reuters | 200，100 条，100 条有日期 | 已启用标题链接模式 |
| RSSHub Blackcat Reuters | 403 | 暂不启用 |
| RSSHub Blackcat AP mobile | 403 | 暂不启用 |
| RSS-Bridge 官方列出的 bridge01 / Reuters | 500 | 暂不启用 |
| RSS-Bridge bridge01 / AssociatedPressNews | 500 | 暂不启用 |

以上只是本机网络的一次测试，不代表其他 IP 的结果。公开实例没有本站可控制的稳定性承诺，500 也可能来自实例配置或上游故障。没有批量轮换实例、绕过访问限制或付费代理。

源码依据：[RSSHub](https://github.com/DIYgod/RSSHub)、[RSS-Bridge Reuters](https://github.com/RSS-Bridge/rss-bridge/blob/master/bridges/ReutersBridge.php)、[RSS-Bridge AP](https://github.com/RSS-Bridge/rss-bridge/blob/master/bridges/AssociatedPressNewsBridge.php)、[RSS-Bridge 公共实例目录](https://rss-bridge.github.io/rss-bridge/General/Public_Hosts.html)。

原始诊断：[community-rss-probes.json](community-rss-probes.json)。可复跑：

```sh
.venv/bin/python -m scripts.probe_community
```

AP 暂时保留为候选；Google News 的 AP 标题搜索可用，但它不是独立社区维护的 RSS，所以没有将其冒充社区源自动加入。
