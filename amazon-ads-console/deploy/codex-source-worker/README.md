# 主机模型源 worker

仅用于模型源主机，普通 API 子设备不安装此程序。

复用 [CodexPlusPlus 固定源码](https://github.com/BigPizzaV3/CodexPlusPlus/tree/9a581df9394b6fb9340beb5453862e202079298b) 的 launcher、Responses 协议和既有凭据读取。保留原项目 AGPL-3.0 授权与 LICENSE。修改完整记录在本目录的 worker 和 `scripts/build_codex_source_worker.py`，不复制或导出 OAuth。

本机修复：流式响应头截止由固定120秒变为进程私有配置 `CPO_SOURCE_HEADER_TIMEOUT_SECONDS`，允许60–900秒，当前部署600秒；非流式保留原策略。仅连接建立失败时重连一次；HTTP错误、读失败及已发送请求不重放。worker保持运行，避免单次CDP探测失败导致反复关闭、重开隔离窗口；真实持续故障由监督进程恢复。

构建需要 Python 3.12+、Rust 和本机编译工具。构建脚本导出上述固定 Git archive，核对原函数再修补；Cargo.lock 固定依赖，包含锁文件时使用 --locked。构建不启动正式模型源或改账号。先执行5组无启动的截止参数自检，再调用受控回环上游：等待125秒才返回HTTP响应，确认旧120秒截止不再误杀；测试不发送凭据、不调用模型。

```sh
python3 scripts/build_codex_source_worker.py \
  --vendor-source /path/to/pinned/CodexPlusPlus \
  --build-dir /private/source-worker-build \
  --cargo /private/toolchain/bin/cargo
```

部署前核对所有 CODEX_HOME、CODEX_SQLITE_HOME、HOME、状态目录均为现有隔离源目录，不得指向主管。只在现有模型请求排空后替换 sourceExecutable，并向该隔离进程增加600秒截止。保持现有Key、HTTP入口、硬件可选审批及个人采集。使用有期限的服务端维护队列，失败恢复原执行文件；不要结束所有Codex或重置主管登录。

运行程序拒绝非隔离目录，只有 --self-check 与 --test-header-wait 可在不启动源的情况下执行。安装后保留二进制、LICENSE、来源及构建回执；确认动态链接仅依赖系统库后，可清理编译缓存及临时工具链。
