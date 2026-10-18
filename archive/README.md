# 已归档功能

2026-10-18：热词与云端 AI 退出当前网页和定时流程。

- hotwords-index.html / hotwords-app.js：旧热词界面，仅保留源码，不发布。
- cloud_ai.py、settings-with-cloud-ai.json：旧 Cloudflare 调用方案，仅保留代码，不在采集或本地阅读器中导入。
- requirements-hotwords.txt：旧分析依赖。collect.py 中 TopicExtractor / rank_topics 为恢复热词保留，当前 topics_enabled=false；没有模型提取或云端翻译。

这里不是另一个可运行站点。恢复需要单独调整配置、页面和工作流。此前已经发布到 Git 历史的内容不会因本次改版从历史提交中抹去。
