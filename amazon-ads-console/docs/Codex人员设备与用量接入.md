# Codex 人员、设备与用量接入

## 当前生产与候选版

rc.3已发布官方账户额度修正，保留设备具体Token。rc.4为统一入口账本候选：明确起点，逐来源列输入/输出/缓存/推理与未知用量、待补账。分母包含本期全部登记来源，包括停用设备及非活跃人员，不随搜索改变；官方账户总Token未核实时仍不计算账户占比。

## 统一入口账本rc.4

正式激活时，在私有backend.env设置CODEX_LEDGER_STARTED_AT为该次实际激活时刻的带时区ISO时间，并核验overview.ledger.startedAt一致。起点固定保存，后续发布不得自动重置；未设置、无时区或未来起点均不显示有效账本占比。区间为finished_at大于等于起点、小于等于throughAt，UTC计算。历史累计保留，未采集不填0；不改表结构；需由schema所有者显式执行backend/migrations/20261020_codex_ledger_usage_grant.sql，只授予6个用量/完成状态列UPDATE，不允许修改设备归属、响应ID或时间。发布脚本不自动执行该SQL。

ledger.scope=unified-entry，accountCoverage=partial。全账户Token保持null，入口占比即使相加100%也不表示官方账户全部消耗。未知请求不算0，待补账入库后才纳入；缓存、推理是父计数子集，不重复累加，缺失明细另计次数。主管直连、旧/v1和其他官方客户端未覆盖。管理员使用成员Key的历史验收仍归该成员；需专用来源Key才能区分，不能猜测重分类。

同一request_id/response_id去重；同设备未知响应随后返回有效usage时只补充一次，不改原发生时间、已知用量或跨设备归属。客户端断开或流异常保留已观察到的合法usage，缺失则未知。SSE最终data行无换行仍读取；不存储提示词、输出或认证正文。待补账失败不挡住已提交账本读取。

### 请求链路与出口

```mermaid
flowchart LR
  DEVICE[子设备独立Key] -->|HTTPS| NGINX[腾讯云Nginx统一入口]
  NGINX -->|/api/codex/v1| LEDGER[控制台鉴权和计量]
  LEDGER --> LOOP[服务器回环16160]
  LOOP --> TUNNEL[SSH反向隧道]
  TUNNEL --> LOCAL[本机网关6160]
  LOCAL --> SOURCE[Codex++模型源9542]
  SOURCE --> EGRESS[模型源实际网络出口]
  EGRESS --> UPSTREAM[上游账户服务]
  UPSTREAM -.响应沿连接返回.-> DEVICE
  NGINX -->|旧/v1，未计量| LOOP
  MAIN[主管官方直连] --> UPSTREAM
```

Nginx公网地址、设备内网地址和模型源实际出口是三个不同概念。统一入口不表示所有请求都已覆盖，旧/v1仍绕过控制台。官方允许本人多设备，禁止将个人账号提供给他人；统一IP不会改变授权范围，也不保证不封号。来源：[账号共享政策](https://help.openai.com/en/articles/10471989-openai-account-sharing-policy)、[使用条款](https://openai.com/policies/terms-of-use/)。

### 迁移顺序与验收

1. 发布账本并固定起点，现有/api/codex/v1子设备继续使用原Key，无需换包。
2. 主管独立试点、管理员测试应分别登记专用来源Key，先新增非当前供应商并独立多开；验收单次usage、归属和本期分母，再决定主管迁移。执行当前任务时不覆盖主管认证或全局重启。
3. 旧/v1设备逐台改用各自新入口并实机验收；无法由HTTP请求日志补造历史Token。确认无人使用后再单独批准撤销旧入口。
4. 各目标设备通过可用操作通道完成迁移；服务器探测不等于Windows桌面已配置。其他官方客户端、历史缺失及未返回usage继续列为未覆盖/未知。
5. 团队成员使用需确认上游具有成员授权；个人订阅不是团队共享许可。此账本可沿用到合法授权的团队上游，不以统一IP代替授权。

试点保留现有 M4 模型测试节点与腾讯云入口，未来日本生产迁移仍是独立任务。不是为了此次试点更换上游账户授权，也不复制主账户 OAuth。给新的成员服务前，管理员须确认上游允许的成员使用方式；个人订阅登录身份和设备 Key 是两类凭据。

## v0.2 独立多开试点

```mermaid
flowchart LR
  OLD[原 Codex 窗口与原账户] --> ORIGINAL[原本工作流程保持]
  AI[设备 AI 使用 Skill] --> NEW[新增非当前供应商]
  HUMAN[人工操作指南] --> NEW
  NEW --> MULTI[Codex++ 独立多开<br/>独立配置、数据库和用户数据]
  MULTI -->|设备 Key + HTTPS| MODEL[控制台模型试点入口<br/>/api/codex/v1]
  MODEL --> UP[现有受控上游模型链路]
  MODEL -->|最终 usage 去重| USAGE[设备 Token 计量]
  HEART[Windows 心跳程序<br/>30 秒/次] -->|同一设备凭据| STATUS[心跳与进程状态<br/>120 秒超时]
  USAGE --> PAGE[管理层人员与设备页]
  STATUS --> PAGE
```

Skill 位于仓库 `.agents/skills/codex-device-relay/`；人工版在该 Skill 的 `references/windows-pilot.md`。私有设备包包含这两种入口、连接配置及测试程序，不含管理员/模型源登录令牌。试点只新增非当前供应商并从「Codex多开」启动，不使用会改变默认选中项的原生待确认导入，不点新供应商「设为当前」或全局「重启 Codex」。停止时仅结束试点实例与心跳，原窗口保留。

### 部署前需要准备的实际配置

- 明确发布指定候选 commit；按既有《开发提交与上线流程》先 prepare，收到发布确认后再 deploy。
- 单独执行 `backend/migrations/20261018_codex_device_telemetry.sql`：只新增 `codex_ops.devices` 与 `codex_ops.model_requests`，外键引用已有 iam 人员；不更改用户密码、角色、名册、广告事实表。
- 私有后端配置启用 `CODEX_TELEMETRY_ENABLED=true`，设置 `CODEX_UPSTREAM_BASE_URL`、`CODEX_UPSTREAM_KEY_FILE`、`CODEX_EVENT_SPOOL_DIR` 和 `CODEX_DEPLOYMENT_TARGET`。上游 Key 是服务端专用模型入口凭据，文件 600、目录 700；不放客户端包或 Git。
- 本次服务端上游可为现有 SSH 回环入口 `http://127.0.0.1:16160/v1`；HTTP 只允许回环，非回环必须 HTTPS。子设备使用受信 HTTPS 地址，Base URL 以实际交付为准。
- 在现有 Nginx server 中为 `/api/codex/v1/responses` 与 `/api/codex/v1/responses/compact` 各加一个 exact location，include 本候选的 `deploy/infra/codex-model-proxy.conf`；语法检查后平滑重载。不能整份覆盖已有 server，保留原模型及控制台路由。
- 私有设备登记清单由管理员绑定真实人员ID和随机 Key。激活时在候选 backend 下运行 `scripts/register_codex_device.py --manifest-file /private/device-manifest.json`；标准输出不包含 Key。重复导入相同清单幂等，换人或换 Key 会冲突，不擅自覆盖。
- 客户端 `device.json` 只含本设备 UUID、标签、连接参数与设备 Key，不携带管理层会话或主账户 OAuth。未激活返回404/503时客户端只准备，不宣称已安装连接。

### 接口、授权与计量

`GET /api/codex/overview`、`POST /api/codex/devices` 和 `DELETE /api/codex/devices/{uuid}` 仅管理层/超级管理员可用。创建设备只返回一次 Key；数据库只存 SHA256。`POST /api/codex/heartbeat` 与 `/api/codex/v1/*` 按设备 Key 认证，并检查绑定人员仍 active、设备未撤销。心跳不能指定或伪造人员ID、设备ID和 Token 数，客户端没有用量上报接口。撤销后拒绝新调用及心跳，不强制中断已经发出的模型任务。

计量从服务端收到的 `response.completed` 等最终响应中读取 usage；非流式/compact 读取最终 JSON。仅保存响应ID、设备ID、时间、状态和 Token 字段，不保存输入、输出正文或认证头。Token 缺失或非法记为未计量；缓存/推理属于输入/输出子集，不能额外相加。同一响应ID全局去重，避免同一次响应被重试重复累计；唯一请求ID防止 outbox 重放重复入库。请求失败或中断不能因为HTTP头为200就冒充完成。无效 usage、上游错误或连接失败应独立记录未计量，而非零消耗。

完成事件先写到服务端私有 outbox 后入库；数据库暂时不可用时保留待重放文件，管理端读取会重放一批。设备页在数据读取失败或过期时停止显示绿点；DB 和 outbox 是不同持久层，回滚不删除它们。磁盘错误或长期数据库故障须按监控处理，不能声称无限可靠计量。Token 是模型返回的实际计量，不是 Pro 剩余额度、计费金额或用户活跃工时。

在线依赖服务端接收的心跳时间与报告的 Codex/ChatGPT 进程存在性。模型目录或模型请求不更新在线状态；后台进程存在不证明真人在线或指定聊天正在执行。客户端测试心跳默认只运行5分钟，不设开机任务。停止后超过120秒应离线。

### 官方额度、设备Token与总量口径

管理接口GET /api/codex/account-quota及overview.accountQuota只返回经过字段白名单处理的官方额度快照。主模型源通过官方app-server的account/rateLimits/read获取5小时/每周usedPercent，服务端计算remainingPercent=100-usedPercent，并显示重置时间与采集时间。不能从原始Token或团队小计反推套餐总容量。

控制台保留成员具体Token数。全账户Token分母须独立验证；当前accountTotalTokens=null、tokenTotalScope=unverified，因此不计算设备占账户总量，不把两设备归一成100%。本地account/usage/read实测在空SQLite目录返回0，换为同一账号的主会话库副本后返回不同累计值，未验证为跨设备完整账目，不用作账户总分母。不根据官方配额百分比强行分摊成员配额成本。

新增配置CODEX_QUOTA_SNAPSHOT_FILE指向服务器私有JSON文件。快照schemaVersion=1，仅含status、capturedAt、primary/secondary的usedPercent/windowDurationMins/resetsAt及planType；服务端不接收或返回OAuth。文件必须私有且小于32KiB，超过5分钟、格式异常或采集失败时显示不可用/过期，不保留旧数字冒充实时。

源主机采集脚本scripts/collect_codex_quota.py读取私有配置（600），字段codexExecutable、codexHome、expectedAccountDigest、localSnapshot、remoteSnapshot和sshHost。脚本用独立临时SQLite目录读取官方限额，核对源accountId的SHA256，仅用现有受信SSH发送白名单快照，不发送账户认证文件。--once做一次核验，常驻模式每120秒读取，锁防重复进程；主源或当前会话不重启。正式启用后台组件及后端文件路径须在候选明确发布时配置，不把一次成功采集称为已常驻。

device agentOnline表示最近120秒内真实心跳；codexRunning单独显示客户端运行状态，不依赖是否对话。旧5分钟程序保留作测试，新Windows包可用4开启当前用户登录启动的持续心跳，5停止本次心跳、6移除登录启动；不能把Mac测试称为Windows原生验收。客户端不持管理层会话、无授权审批权限，也不上传Token计数。

### 管理员授权接口的实现边界

当前已上线设备Key注册/撤销、心跳和模型认证。另一路成员授权、Key签发/轮换与审计代码位于独立开发分支，尚未部署；不能把代码存在等同接口上线。当前没有完整的设备申请-管理员批准-设备领取结果的注册回传闭环，也没有设备命令执行的管理员远程审批通道。这两种需求须先明确，不能用设备心跳或管理层登录冒充审批回传。

### 验收与回滚

隔离测试命令（仅临时 Unix socket PostgreSQL，无 TCP 监听）：

```bash
python backend/scripts/test_codex_isolated.py --pg-bin /path/to/postgresql/bin
```

显式 `--live-key-file`、`--live-base-url`、`--receipt-file` 选项仅在已获模型调用授权时使用；会发一次真实请求，用临时合成人员身份验证计量，不能算作实际 Windows 或 XT 已上线。真实用量与测试身份回执留在仓库外。

实际 Windows 验收须分别核对：主窗口保留及配置未被接入流程改写、独立多开目录、模型目录与真实流式、随机本地文件读取、两轮上下文、控制台计量匹配、真实心跳变在线、停止后超过120秒离线、单台撤销与其它设备保持可用。M4上或模拟心跳的通过不能代替这些验收。

回滚先停止本试点实例和心跳，禁用试点功能；按批准的旧 commit 回滚控制台并只移除试点 Nginx exact locations。保留数据库记录与 outbox，暂不撤销其他设备或删除已有登录文件。恢复原窗口不依赖本试点 Key 或服务器可达。

## 原筹备阶段记录

管理层及超级管理员访问 `/codex-devices`。左侧按运营组 / AI 小组展示18名分发人员，右侧预留设备状态、今日及累计 Token。模块和导航入口使用圆角边框，灰点表示离线或尚未接入，绿点仅在后续获得有效设备心跳后显示。

当前仅接入 `amazon_ads.codex_ops.personnel_roster` 的真实人员名单；设备、在线和用量均明确显示待接入，不生成测试消耗或在线记录。完整名单只对管理层开放，普通运营和AI账号不增加CPO业务权限。服务端以只读事务查询应用库，无模型请求、设备注册、心跳采集或Token写入接口。

最终 Codex 主账户将统一部署至日本代理服务器，随后再实施分发和实际计量。公司 M4 只是代理测试节点，不能作为最终生产主账户位置。当前版本不修改现有腾讯云与M4的模型代理链路。

后续接入需绑定独立设备ID与人员ID，在代理最终响应中记录实际Token并按响应ID去重，设备通过心跳确定在线状态；缓存和推理Token属于父计数子集，避免重复累加。暂定30秒心跳、120秒超时，届时根据部署情况确认。
