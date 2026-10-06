# Alexa 商品推荐诊断插件维护规则

本文件补充仓库根目录 `AGENTS.md`，仅适用于 `apps/alexa-recommendation-auditor/`。

## 文档与版本

1. `VERSION` 是应用版本唯一事实源；不得只修改某个 `package.json` 或 Chrome Manifest。
2. 用户可感知功能、配置、工作流或安全边界变化时，更新 `CHANGELOG.md` 的 `Unreleased`。
3. 每个可交付变更完成后，使用 `npm run devlog:add` 追加 `docs/DEVELOPMENT_LOG.md`，不得回写历史。
4. 开发实现、接口、架构、评分或发布流程变化时更新 `docs/DEVELOPMENT.md`。
5. 安装、连接、操作、界面、报告解释或常见错误变化时更新 `docs/USER_GUIDE.md`。

## 飞书同步

1. 本地 Markdown 是事实源；飞书文档是固定发布目标。
2. 文档 ID 只取自 `docs/feishu-docs.json`，不得为普通更新重复创建新文档。
3. 文档变化后必须运行 `npm run docs:sync:feishu`，并确认回读验证成功。
4. `docs/feishu-sync-state.json` 只能由同步脚本写入，不得手工伪造。
5. 同步失败时报告失败原因并保留本地改动，不得宣称发布完成。
6. 任何文档、日志、清单或飞书正文都不得包含 API Key、Cookie、Amazon 登录信息或供应商凭据。
7. `CHANGELOG.md`、`docs/DEVELOPMENT_LOG.md` 和 `docs/RELEASE_PROCESS.md` 会作为开发文档附录同步，变更后同样必须重新同步。

## 交付门禁

完成开发交付前运行：

```bash
npm run release:check
```

该命令必须验证版本一致、飞书文档同步状态、类型检查、测试和生产构建。真实 Amazon/Alexa 现场测试仍需用户明确启动，不能因发布门禁而自动执行。
