# 本地版本与发布流程

## 版本事实源

仓库根目录的 `VERSION` 是应用版本的唯一事实源。以下位置必须与它保持一致：

- 根目录及 `extension`、`server`、`report`、`packages/contracts` 的 `package.json`
- `package-lock.json` 中对应的工作区条目
- `extension/manifest.json`（构建后也会复制到 `extension/dist/manifest.json`）
- `packages/contracts/src/types.ts` 中的 `APP_VERSION`
- `docs/DEVELOPMENT.md` 和 `docs/USER_GUIDE.md` 顶部的对应应用版本

应用版本使用稳定的三段式 SemVer，例如 `0.2.0`。Chrome Manifest 不接受 SemVer 预发布后缀，因此应用版本暂不使用 `-alpha`、`-beta` 等后缀；开发阶段状态写入开发日志。

`SCHEMA_VERSION`、`FOOTWEAR_PROMPT_VERSION` 和 `JUDGMENT_STANDARDS_VERSION` 是独立的协议版本，不随应用版本机械递增。只有对应契约、题集或评分口径发生不兼容/可审计变化时才分别更新。

## 日常开发记录

每个可交付变更完成并验证后追加日志：

```bash
npm run devlog:add -- \
  --type feature \
  --summary "加入简体中文提问语言" \
  --files "extension/src/sidepanel/App.vue,server/src/runs/prompt-builder.ts" \
  --verification "npm test; npm run typecheck; npm run build"
```

可用类型：`feature`、`fix`、`refactor`、`docs`、`test`、`infrastructure`、`release`、`security`。

先预览而不写文件：

```bash
npm run devlog:add -- \
  --type docs \
  --summary "更新开发文档" \
  --dry-run
```

日志内容不得包含 API Key、Cookie、Amazon 账号、配送地址或原始模型凭据。

## 准备新版本

1. 确认工作区中的功能、测试和文档已完成。
2. 将 `CHANGELOG.md` 的相关 `Unreleased` 内容整理到目标版本。
3. 统一更新版本：

```bash
npm run version:set -- 0.2.0
```

4. 审核并更新 `docs/DEVELOPMENT.md` 和 `docs/USER_GUIDE.md`。
5. 同步固定飞书文档：

```bash
npm run docs:sync:feishu
```

6. 执行完整发布门禁：

```bash
npm run release:check
```

7. 检查构建后的 `extension/dist/manifest.json` 版本。
8. 追加一条类型为 `release` 的开发日志，记录测试、构建、飞书同步和人工验收结果。
9. 再创建 Git tag 或发布包。

## 自动检查

```bash
npm run version:check
```

检查失败时会逐项列出不一致位置并以非零状态退出。`npm run build` 和 `npm run release:check` 均会先执行版本检查，避免生成版本号不一致的扩展包或服务。

版本更新命令会修改所有受管版本文件；若已存在构建后的 `extension/dist/manifest.json`，也会同步它，避免新版本构建前被旧产物阻断。命令不会自动编辑 `CHANGELOG.md`、提交 Git、创建标签或发布，发布说明仍需开发者审核。

## 飞书文档同步

两份固定飞书文档的 ID 和本地源文件记录在 `docs/feishu-docs.json`。不要在后续版本中重新创建同名文档。

```bash
npm run docs:sync:feishu:dry-run
npm run docs:sync:feishu
npm run docs:check
```

同步脚本依赖已登录的 `lark-cli` 用户身份，逐份覆盖正文并回读验证标题、章节和正文规模。只有两份文档全部成功后才写入 `docs/feishu-sync-state.json`。该状态文件不含访问令牌或供应商密钥。
