---
tags: [亚马逊, AIGC, 图片合规, 视频合规, XMP]
date: 2026-07-23
status: 现行
---

# 亚马逊AI逼真人物媒体标签合规与批处理方案

> [!summary] 摘要
> Amazon 要求在商品信息和 A+ 商品描述中使用含 AI 生成逼真人物的图片或视频时，在最终上传文件的 XMP `dc:subject` 字段加入 `contains-synthetic-performer`。推荐使用 ExifTool 配合 Windows BAT 批量写入和复核；脚本只负责写标签，素材是否属于“AI 生成逼真人物”应先由人工或审核流程确认。

## 核心知识

- 需要打标：图片或视频中含有 AI 生成的逼真人物。
- 无需打标：
  - 只含真实人物，即使使用 AI 工具进行过修图；
  - 只含影视、电视、流媒体、纪录片、电子游戏等表现性作品中的角色；
  - 不含任何人物；
  - 不含逼真人物。
- 标签必须写入 XMP `dc:subject`，值为 `contains-synthetic-performer`。
- `dc:subject` 是可容纳多个值的 XMP Bag；写入时应追加新值，不能覆盖已有关键词。
- 应对最终导出、压缩和剪辑后的上传文件打标，因为后续软件或平台转换可能移除元数据。

## Windows 属性标签与 XMP 的关系

- Windows 资源管理器“属性 → 详细信息 → 标签”对应系统字段 `System.Keywords`。
- 对 JPEG 和 TIFF，微软的读取与写入策略把 XMP `dc:subject` 列为首要路径，同时还会读取或写入 IPTC Keywords、Windows EXIF Keywords 等其他路径。
- Windows 会合并多个元数据架构的关键词。因此，在 JPEG/TIFF 的 Windows 属性中看到 `contains-synthetic-performer`，可能与 XMP `dc:subject` 一致，但不能仅凭界面证明该值确实存在于 Amazon 指定的 XMP 字段。
- PNG、MP4、MOV 等格式的 Windows 属性处理方式不同；资源管理器可能不显示已嵌入的 XMP 标签，尤其不能用视频属性界面作为失败依据。
- 最终验收应使用 ExifTool 指定读取 `XMP-dc:Subject`。本工具的扫描脚本和 CSV 报告读取的正是该字段，而不是 Windows 界面中的合并标签。

```bat
exiftool.exe -G1 -a -s -XMP-dc:Subject "example.jpg"
exiftool.exe -G1 -a -s -XMP-dc:Subject "example.mp4"
```

只有输出组名为 `[XMP-dc]` 且值准确包含 `contains-synthetic-performer`，才满足本地字段校验。

> [!warning] 不建议让 BAT 自动判断画面
> BAT 只能按文件或文件夹规则处理，不能可靠识别画面是否属于“AI 生成的逼真人物”。最稳妥的流程是先人工审核，再把符合条件的最终成品放入专用文件夹统一打标。

## 推荐工作流

1. 设计或视频团队导出最终上传版本。
2. 将确认含 AI 逼真人物的文件放入 `AI人物_待打标` 文件夹。
3. 运行 ExifTool BAT，批量追加 XMP 标签。
4. 导出校验报告，确认每个目标文件都含准确关键词且没有重复值。
5. 从打标后的文件直接上传 Amazon，不再经过会清除元数据的二次编辑或压缩。
6. 在资产台账记录 ASIN、文件名、审核人、标签状态和上传日期。

## Windows BAT 方案

将 Windows 版 `exiftool.exe` 与 BAT 放在同一目录，把待处理文件夹拖到 BAT 上。以下命令支持递归处理 JPG、JPEG、PNG、TIFF、MP4 和 MOV，保留已有关键词，重复运行不会重复添加标签；ExifTool 默认保留 `_original` 备份。

可直接使用的本地工具包位于 `outputs/amazon-ai-media-labeler/`，其中包含批量写入脚本、独立扫描脚本、正反样本测试步骤和报告说明。

Windows 64 位与 macOS 跨平台离线便携包位于 `outputs/Amazon_AI_Media_Tagger_Portable_Win64_macOS_v1.2.zip`，工作区内另有已解压目录 `outputs/Amazon_AI_Media_Tagger_Portable/`。便携包已内置官方 ExifTool 13.59、两套运行依赖和许可证，并预先创建 `REPORTS` 文件夹；接收方解压后将最终文件或包含素材的子文件夹放入 `AI_MEDIA_TO_TAG`。Windows 双击 `START_HERE.bat`，macOS 双击 `START_HERE_MAC.command`，均可完成打标和校验，无需安装软件或配置环境。

```bat
@echo off
setlocal

set "EXIFTOOL=%~dp0exiftool.exe"
set "TARGET=%~1"
if not defined TARGET set "TARGET=%~dp0AI人物_待打标"

if not exist "%EXIFTOOL%" (
  echo [ERROR] exiftool.exe not found.
  pause
  exit /b 1
)

if not exist "%TARGET%" (
  echo [ERROR] Target folder not found: %TARGET%
  pause
  exit /b 1
)

"%EXIFTOOL%" -r ^
  -ext jpg -ext jpeg -ext png -ext tif -ext tiff -ext mp4 -ext mov ^
  -if "not $XMP-dc:Subject =~ /contains-synthetic-performer/i" ^
  "-XMP-dc:Subject+=contains-synthetic-performer" ^
  "%TARGET%"

"%EXIFTOOL%" -r -csv ^
  -ext jpg -ext jpeg -ext png -ext tif -ext tiff -ext mp4 -ext mov ^
  -FileName -Directory -XMP-dc:Subject ^
  "%TARGET%" > "%~dp0amazon_xmp_check.csv"

echo Done. Review amazon_xmp_check.csv before uploading.
pause
```

单文件读取验证命令：

```bat
exiftool.exe -G1 -s -XMP-dc:Subject "example.jpg"
exiftool.exe -G1 -s -XMP-dc:Subject "example.mp4"
```

预期结果：

```text
[XMP-dc] Subject : contains-synthetic-performer
```

如果文件已有其他关键词，结果可能是：

```text
[XMP-dc] Subject : existing-keyword, contains-synthetic-performer
```

## 验证结论

- 使用 ExifTool 13.55 对测试 JPEG 和 MP4 成功写入 `XMP-dc:Subject`。
- 原有 `dc:subject` 关键词得到保留。
- 第二次运行因条件不匹配而跳过，未产生重复关键词。
- MP4 打标前后视频编码流的 SHA-256 哈希一致，说明只修改容器元数据，没有重新编码视频或降低画质。
- 独立扫描脚本已用“准确标签、缺失标签、重复标签”三类控制文件测试，能够分别输出通过、缺失和重复名单，并导出完整 CSV。
- ExifTool Windows 64 位官方原包 SHA2-256 已与官方校验文件匹配；离线便携包通过 ZIP 完整性检查。
- macOS `.command` 已在本机使用未打标的 JPG 和 MP4 完整测试：首次运行写入成功、生成 `_original` 备份、报告 2 项通过且零缺失/重复/错误；重复运行会跳过已打标文件并保持校验通过。

## 风险与控制

- 错误分类：不要对“所有 AI 图片”一键打标，只处理含 AI 逼真人物的素材。
- 元数据丢失：打标必须位于制作链最后一步；上传前再次读取最终文件验证。
- 覆盖原关键词：使用 `+=` 追加，不使用 `=` 覆盖。
- 重复标签：增加 `-if` 条件，重复执行时跳过已含关键词的文件。
- 视频体积和速度：MP4/MOV 写元数据通常需要重写容器文件，大视频耗时和临时磁盘占用会明显高于图片，但不会重新编码。
- 备份占用：ExifTool 默认生成 `_original` 备份。确认打标文件正常并完成组织归档后，再按团队留存策略处理备份。

## 后续工具化建议

- 小规模：直接使用 ExifTool + BAT，成本最低。
- 团队规模：增加一个“拖入文件夹—确认合规范围—开始打标—导出 CSV”的桌面界面。
- 大规模：在素材管理系统中增加 `synthetic_performer` 布尔字段，以审核状态驱动 ExifTool 任务，并保存写入日志和文件校验值。
- 自动识别只能作为候选筛选，不应替代最终人工确认。

## 关联

- [[亚马逊A+页面模板与规范]]
- [[亚马逊A+页面制作SOP]]
- [[AIGC动漫漫剧岗位技能图谱]]

## 来源

- 用户提供的 Amazon Seller Central 政策截图，2026-07-23
- [Amazon Seller Central：为含 AI 生成人物的商品媒体添加标签](https://sellercentral.amazon.com/help/hub/reference/external/GNHU43TN2RHER9BQ)
- [Amazon Ads：AI-generated people in ads disclosure requirement](https://advertising.amazon.co.uk/help/GZZX6RJVMWBVBB6W)
- [IPTC Photo Metadata Standard 2025.1：Keywords 映射到 dc:subject](https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata-2025.1.html)
- [IPTC：使用 ExifTool 读写 IPTC/XMP 元数据](https://iptc.atlassian.net/wiki/spaces/PMD/pages/649330691)
- [ExifTool：QuickTime/MOV/MP4 元数据写入说明](https://exiftool.org/TagNames/QuickTime.html)
- [Microsoft：System.Keywords Photo Metadata Policy](https://learn.microsoft.com/en-us/windows/win32/wic/-wic-photoprop-system-keywords)
