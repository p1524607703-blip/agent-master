# Codex 设备密钥绑定 rc.10

## 用户接入

管理员创建成员设备 Key → 设备安装公开连接器包并输入 HTTPS 地址/设备 Key → 生成硬件密钥并提交申请 → 管理员核对设备端完整指纹并批准 → 使用私有 provider.txt 中的本机地址/本地 Key 新增非当前 Responses 供应商 → Codex++ 独立多开验收。主设备的官方 Codex 配置、登录和进程不由连接器修改。

设备 Key 是本系统接入凭据，不是主账户 OAuth，也不是 OpenAI API Key。连接器只监听127.0.0.1:58961，拒绝浏览器 Origin、错误 Host、本地 Key、不支持路径和超大请求；对 HTTPS 上游不关闭证书校验、不接受重定向、不采用系统代理，不记录请求正文和签名材料。包、脚本和公开下载不含设备 Key。Python3.9+，Windows需TPM，Mac需Secure Enclave；Mac通用助手 arm64最低macOS12、Intel最低macOS13且硬件支持。

## 身份与一次性签名

数据库登记 UUID 只标识记录，不能证明实体设备。本版每个有效 Key 额外绑定**一个经管理员批准的P-256公钥**；每次请求都需要该公钥验证的签名。请求的规范字节为 UTF-8：

```text
cpo-device-v1\nSHA256(设备Key)\nHTTP方法\n原始ASCII路径\nUnix秒\n随机数\nSHA256(原始正文)
```

算法 ECDSA-P256-SHA256，公钥为65字节SEC1未压缩点Base64，签名为64字节P1363 Base64。请求头 X-CPO-Time / X-CPO-Nonce / X-CPO-Proof；允许90秒时钟偏差。随机数32–64字符，服务器数据库唯一约束防跨进程重放，保存4分钟以覆盖完整时间有效期。查询字符串与编码路径不接受。认证在转换Responses请求正文之前完成，签名原始正文与转给模型的协议适配正文分开。

首用不自动信任。申请同时证明候选密钥持有权，但管理员需核对安装器指纹后批准；最多5个候选，竞争申请不能覆盖已批准绑定。绑定审批使用事务锁、唯一约束，并记录操作者、指纹和时间。一个公钥不能重复登记给多个Key。换机撤销旧Key后创建新Key，避免原Key被解除绑定后抢注；撤销保留原具体Token和归属历史，已经接受的任务允许完成。

Windows助手只使用Microsoft Platform Crypto Provider创建不可导出P-256签名密钥；Mac助手使用CryptoKit SecureEnclave.P256，配置中只存本机Enclave封装表示。硬件不可用时失败，禁止软件回退。服务端没有远程硬件证明，provider字段不是TPM证明；管理员必须确认受信安装流程。目标是阻止单独复制Key或本地配置到另一台使用，不能承诺阻止已控制的原设备被主动用作远程转发/签名机。

## 发布与旧入口

先按已发布commit执行release.py prepare，再由数据库所有者显式执行20261023_codex_device_binding.sql（只建codex_ops绑定/候选/随机数/审计表并授予现有应用角色必要权限）；不修改原设备Key、账户登录或业务表。模型目录、Responses、compact与心跳统一校验签名，缺少绑定也拒绝，不保留旧Key的无签名白名单。

旧公网/v1路由由codex-legacy-disabled.conf返回410，替换原codex-relay-routes.conf，避免绕过签名入口；只关闭公网旧入口，源主机回环6160/9542不变。保存原Nginx片段的私有备份并nginx -t后reload。新后台按现有expected-current保护发布并排空原请求；管理员页面下载公开ZIP并按指纹批准。旧设备需一次升级，主设备官方直连不受影响。回退至无签名旧代码会重新打开新入口的Bearer认证，因此安全回退应先关闭公网模型入口，不以移除绑定表作为回退。

## 验收边界

必须验证：无Key401、Key但无绑定403、待批准403、批准后签名200、同Key另一密钥403、并发重放仅一次通过、时钟过期/改正文/改路径拒绝、同IP多设备并发正确、撤销401、管理权限、硬件失败不降级。真实Mac硬件和另一台服务器复制Key的验证与模拟fixture分开记载。Windows未在实机执行前不得称已验收。原Codex文件摘要与进程保留独立核对；不要把正常OAuth刷新误判为配置被改写。

具体客户端操作以公开包内使用说明为准。源码：scripts/device-binding；打包：scripts/build_device_binding_package.py；服务端：services/codex_binding.py；流程API：/api/codex/device-enrollment与管理员device-bindings。
