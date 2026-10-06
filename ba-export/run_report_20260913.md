# 川鹏2号 BA 周报管线 — 执行报告 (2026-09-13)

> 状态：**未成功 / 被 RDS 网络阻断**，非脚本逻辑错误。

## 1. 前置检查
- `ziniao-cli doctor`：全绿 ✅
- `extract_data mode=running`：含 `27661378824000`(川鹏2号) ✅
- 结论：浏览器在线、Bridge 正常，**前置通过**。

## 2. 管线执行
- 目标周（LATEST）：**2026-09-05**（报告周期约 08-30 ~ 09-05）
- Phase 1 `ba_export.sh`：日志标记 `GEN scp 2026-09-05` / `GEN sqp 2026-09-05`，
  但此为「已点击生成」标记，**不代表 DM 实际产生下载项**（脚本在点击后无条件写 done）。
- Phase 2 `drain_dm.py --download-only`：下载管理器**实际为空**（独立只读探针确认 0 行），
  故 0 文件落盘。
- Phase 3 `load_local.py`：磁盘 0 个 BA Week CSV，**无数据可灌**。

## 3. 阻断根因（关键）
RDS 连接被 `pg_hba.conf` 拒绝：
```
FATAL: pg_hba.conf rejects connection for host "112.49.170.54",
       user "amazon_ads_admin", database "amazon_ads"
```
- 端口 5432 **可达**（nc 测试通过），但**源 IP 不在白名单** → 连接被主机过滤拒绝。
- 重试 2 次均失败，确认**持续性**阻断。
- 本机直连出口 IP = `112.49.170.54`（psql 报错 host）；curl 走代理出口为 `27.151.65.193`。
- `amazon_ads_admin/Root_1234` 与 `postgres`(pgpass) **两条凭据报相同错误** → 排除密码问题，
  确认为 **IP 白名单 / 安全组** 问题。上次成功运行（09-06）后，本机出口 IP 或 RDS 白名单已变动。
- 副作用：`drain_dm.existing_weeks()` 因连接失败返回空集 → 日志里 `RDS 已有周: scp=0 sqp=0`
  是**假信号**，不能据此认为表已空。当前**无法确认 RDS 真实状态**。

## 4. 数据缺口风险（已就地缓解）
- `done.txt` 原先含 `scp:2026-09-05=done` / `sqp:2026-09-05=done`，
  会导致未来运行**永久跳过** 09-05 周（但该周从未真正入 RDS）。
- 已删除这两条**假 done 标记**（仅改本地缓存，未触碰任何 Amazon 账号），
  待 RDS 恢复后可通过回灌（指定 2026-09-05）补回。

## 5. 磁盘
- 0 个 BA Week CSV ✅（符合「不保留本地文件」要求）。

## 6. 需要用户处理
1. **恢复 RDS 网络访问**：在阿里云 RDS `amazon_ads` 的安全组 / pg_hba 中，
   将出口 IP `112.49.170.54`（或当前稳定出口）加入白名单。
2. 白名单生效后，**重跑管线补 09-05**：
   `cd ba-export && MODE=latest bash ./pipeline.sh`（或针对 09-05 做回灌）。
3. 本周（09-12 周六）的 LATEST 运行会在下次定时触发，届时请确认 RDS 已通。

> 红线遵守：全程未对 Amazon 账号 / 广告做任何改动。未下载任何 CSV 到本地（DM 本就为空）。
