# 本地与飞书文档同步

## 事实源

本项目的文档事实源始终是：

- `docs/DEVELOPMENT.md`
- `docs/USER_GUIDE.md`

飞书只作为团队发布与阅读入口。两份固定文档的映射保存在 `docs/feishu-docs.json`，后续更新不得重新创建同名文档。

飞书开发文档还会自动附加 `CHANGELOG.md`、`docs/DEVELOPMENT_LOG.md` 和 `docs/RELEASE_PROCESS.md`。这些文件任意一个发生变化，`docs:check` 都会要求重新同步。

## 标准流程

1. 根据代码变更更新开发文档或使用手册。
2. 如版本变化，先运行 `npm run version:set -- <version>`。
3. 预览同步目标：

   ```bash
   npm run docs:sync:feishu:dry-run
   ```

4. 覆盖同步并回读验证：

   ```bash
   npm run docs:sync:feishu
   ```

5. 检查本地源文件是否仍与最近成功同步状态一致：

   ```bash
   npm run docs:check
   ```

6. 运行完整发布门禁：

   ```bash
   npm run release:check
   ```

## 同步语义

- 同步命令使用 `lark-cli` 的用户身份。
- 长 Markdown 正文通过工作目录内的临时 `@file` 传给 `lark-cli`，完成后立即删除，避免 stdin 管道在大载荷下触发 `EPIPE`。
- 每次覆盖固定文档正文，不修改文档 ID 和分享链接。
- 脚本会去掉本地 Markdown 的第一个 H1，由飞书文档自身标题承担一级标题。
- 同步后立即回读，验证一级标题、全部二级章节和正文规模。
- 只有全部文档更新和回读都成功，才更新 `docs/feishu-sync-state.json`。
- 同步状态只保存文档 ID、修订号、本地文件哈希和时间，不保存凭据。

## 边界

覆盖同步会以本地 Markdown 取代飞书正文。因此，这两份文档不应在飞书中维护只存在于云端的正文、图片或内联批注。需要长期保留的内容应先写回本地事实源，再执行同步。

若飞书接口暂时不可用，不要伪造同步状态，也不要把发布标记为完成；保留本地改动，待认证或网络恢复后重新运行同步。
