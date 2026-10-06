---
tags: [AI工程, Skill, AIGC, 视频生成]
date: 2026-05-20
status: 现行
---

# LibTV-Skill使用说明

> [!summary] 摘要
> LibTV-Skill 是通过 liblib.tv agent-im OpenAPI 调用 AI 图片与视频创作能力的本地 Skill。它的核心不是在用户侧写复杂 prompt，而是上传参考文件、原样传递用户需求、轮询结果并下载产物。

## 核心知识

### 能力边界

LibTV-Skill 覆盖所有 AI 图片和视频的生成、编辑、复刻和续写类任务，包括文生图、文生视频、图生视频、视频续写、局部修改、元素替换、风格迁移、短剧生成、音乐 MV、产品广告视频、分镜和故事板。

触发判断很宽：只要用户请求涉及 AI 图片或视频创作、生成、编辑、修改，或提到 liblib、libtv、参考图、参考视频、查看生成进度，就应优先使用这个 Skill。

### 核心原则

用户侧 Agent 只做三件事：

- 上传：用户提供本地图片或视频时，先调用 `upload_file.py` 获得 OSS URL。
- 传话：把用户原始描述和 OSS URL 原样发送给 `create_session.py`。
- 取件：用 `query_session.py` 轮询进展，生成完成后用 `download_results.py` 下载结果。

不要在用户侧扩写、润色、翻译或自行拆分 prompt。LibTV 后端 Agent 负责理解任务、拆解分镜、选择模型、编排工作流和生成最终内容；用户侧过度加工反而可能降低质量。

### 本地脚本结构

- `_common.py`：公共 OpenAPI 客户端，读取 `LIBTV_ACCESS_KEY`，默认连接 `https://im.liblib.tv`，提供 POST/GET、会话创建、查询和项目切换。
- `create_session.py`：创建新会话，或向已有会话发送消息。返回 `projectUuid`、`sessionId`、`projectUrl`。
- `query_session.py`：按 `sessionId` 查询消息列表，支持 `--after-seq` 增量拉取，也可用 `--project-id` 附带项目画布链接。
- `change_project.py`：切换当前 access key 绑定的项目，后续新会话使用新 `projectUuid`。
- `upload_file.py`：上传图片或视频到 OSS，仅接受 `image/*` 和 `video/*` MIME 类型，要求文件小于 200MB。
- `download_results.py`：从会话消息或指定 URL 中提取 libtv 结果地址，并批量下载图片或视频到本地。

### 标准工作流

直接生成图片或视频：

```bash
python3 .agents/skills/libtv-skill/scripts/create_session.py "用户原始描述"
python3 .agents/skills/libtv-skill/scripts/query_session.py SESSION_ID --after-seq 0 --project-id PROJECT_UUID
python3 .agents/skills/libtv-skill/scripts/download_results.py SESSION_ID --output-dir ~/Downloads/libtv_results --prefix task
```

基于参考文件编辑或生成：

```bash
python3 .agents/skills/libtv-skill/scripts/upload_file.py /path/to/reference.png
python3 .agents/skills/libtv-skill/scripts/create_session.py "用户原始描述。参考图：https://libtv-res.liblib.art/..."
```

追加已有会话：

```bash
python3 .agents/skills/libtv-skill/scripts/create_session.py "新的用户原始描述" --session-id SESSION_ID
```

### 轮询与完成判断

- 查询间隔建议为 8 秒。
- 首次使用 `--after-seq 0`，后续用上次消息中的最大 seq 做增量查询。
- 当 assistant 或 tool 消息中出现图片、视频结果 URL 时，视为可下载。
- 连续轮询 3 分钟仍无结果时，应告知用户生成耗时较长，可稍后继续查。
- 单次查询失败可重试 1 次，连续 3 次失败后停止并说明原因。

### 输出给用户

任务完成时应同时提供：

- 本地下载文件路径。
- 生成结果链接。
- 项目画布链接 `https://www.liblib.tv/canvas?projectId=PROJECT_UUID`。

过程中不要提前展示项目画布链接；等完成或需要用户稍后查看时再给。

### 使用风险与注意事项

- `LIBTV_ACCESS_KEY` 是必填环境变量，属于敏感凭据，不应写入 wiki 或日志。
- `OPENAPI_IM_BASE` 或 `IM_BASE_URL` 可覆盖默认服务地址，一般无需设置。
- `change_project.py` 会改变当前 access key 绑定项目，除非明确需要新项目，否则不要随意调用。
- `upload_file.py` 会把本地素材上传到 OSS，用户给的私密素材应先确认用途和外发边界。
- `download_results.py` 通过 URL 正则和 tool 消息结构提取结果，若后端返回格式变化，可能需要同步更新解析逻辑。

## 关联

- [[工具参考/Skills工作原理]]
- [[视频广告素材与亚马逊广告分析工作计划]]
- [[WHITIN乐福鞋A+页面AIGC生图提示词]]

## 来源

- `.agents/skills/libtv-skill/SKILL.md`
- `.agents/skills/libtv-skill/scripts/_common.py`
- `.agents/skills/libtv-skill/scripts/create_session.py`
- `.agents/skills/libtv-skill/scripts/query_session.py`
- `.agents/skills/libtv-skill/scripts/upload_file.py`
- `.agents/skills/libtv-skill/scripts/download_results.py`
- `.agents/skills/libtv-skill/scripts/change_project.py`
