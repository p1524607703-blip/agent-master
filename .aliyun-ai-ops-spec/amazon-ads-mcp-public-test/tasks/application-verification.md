# 应用边界验证记录

验证日期：2026-08-22

## 自动化测试

- `uv run pytest -q`：38 项全部通过，其中包含带签名加密信封的真实 MCP
  `initialize` 与 `tools/list` HTTP 往返验证。
- 运营服务实际注册 10 个工具；10 个工具的 `read_only_hint` 均为 `true`。
- 管理员服务实际注册 25 个工具：10 个只读工具、14 个受控写入工具、1 个
  `execute_database_admin_sql` 管理员工具。
- HTTP 传输测试证明 `/healthz` 只返回固定存活状态；没有云端公开验证公钥时服务
  关闭，缺少、签名错误、模式错误或过期的请求信封返回 503/401。
- 请求信封使用 Ed25519 签名、X25519 密钥协商、HKDF-SHA256 和 AES-256-GCM；
  单元测试确认解密后的密码只在当前请求可见，请求结束后立即清除上下文。
- Linux x86_64 / Python 3.12 部署包 SHA-256：
  `be93e6313650bb0e45768fede0db8bda8dc1da12052de2553d76b8f6789819ca`。
- 部署包内 ApsaraDB CA 首张证书 SHA-256 指纹：
  `88BEB566B208979AF58F5223EC0DC4548BB96B4C7E648F58D70178E3F1B9809C`。

## 数据库权限边界

- 所有查询由 `_query` 统一以 `read_only=True` 和 10 秒 statement timeout 连接。
- 运营服务在启动时固定 `ADS_MCP_QUERY_ROLE=amazon_ads_ops_reader`，且未注册任何
  写入、删除、任意 SQL、DDL 或角色管理工具。
- 管理员常规查询和受控写入使用 `codex_reader`；唯一管理员 SQL 工具在函数内部
  固定改用 `amazon_ads_admin`，要求确认短语
  `CONFIRM_DATABASE_ADMIN_EXECUTION`。
- 管理员 SQL 先写 RDS 审计记录，再执行目标 SQL；测试部署中的 `/tmp` JSONL
  只是附加审计，不是唯一持久记录。

## 云端验收限制

- 本轮仅验证鉴权、10/25 工具清单和只读数据库连通性。
- 不调用任何受控写入、文件导入、删除、DDL 或管理员 SQL 工具。
- FC HTTP 触发器使用 EdDSA JWT 网关鉴权，JWKS 只含公钥；数据库密码不写入
  Function Compute 环境变量或 Terraform state。
- 云端验收完成后停用并销毁测试资源，再删除本机钥匙串中的测试私钥。
