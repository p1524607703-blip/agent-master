# Amazon AI 逼真人物媒体 XMP 批量打标工具

## 文件说明

- `START_HERE.bat`：主入口，批量追加标签，完成后自动运行扫描校验。
- `VERIFY_ONLY.bat`：只读扫描，不修改文件。
- `START_HERE_MAC.command`：macOS 主入口。
- `VERIFY_ONLY_MAC.command`：macOS 只读扫描。
- `AI_MEDIA_TO_TAG/`：默认待处理文件夹。
- `REPORTS/`：校验报告文件夹；包内已预先创建，运行后会在这里生成结果。

## 无需安装 ExifTool

便携版 ZIP 已包含官方 Windows 64 位 ExifTool 13.59 和所需的 `exiftool_files`，接收方不需要安装或配置环境。

跨平台便携版还包含 macOS 使用的 ExifTool Perl 发行文件。Mac 用户不运行 BAT，将素材放入 `AI_MEDIA_TO_TAG` 后双击 `START_HERE_MAC.command`。如果系统阻止首次打开，请右键该文件选择“打开”；也可以打开终端，进入解压后的工具目录并运行：

```bash
bash START_HERE_MAC.command
```

## 建议先做正反样本测试

不能只测试一个带标签文件，至少准备一组正样本和一组负样本。

1. 新建一个临时文件夹，例如 `校验测试`。
2. 准备两张图片副本：
   - `测试_应有标签.jpg`
   - `测试_不应有标签.jpg`
3. Windows：将 `测试_应有标签.jpg` 单独拖到 `START_HERE.bat` 上。
4. macOS：只将 `测试_应有标签.jpg` 放进 `AI_MEDIA_TO_TAG`，双击 `START_HERE_MAC.command`。
5. 不处理 `测试_不应有标签.jpg`。
6. Windows：将整个 `校验测试` 文件夹拖到 `VERIFY_ONLY.bat` 上。macOS：将两个测试文件放进同一测试文件夹，在终端运行 `bash VERIFY_ONLY_MAC.command "/测试文件夹的完整路径"`。
7. 预期结果：
   - `测试_应有标签.jpg` 出现在 `REPORTS/pass.txt`；
   - `测试_不应有标签.jpg` 出现在 `REPORTS/fail_missing_or_incorrect.txt`；
   - `REPORTS/fail_duplicate.txt` 为空。
8. 视频也按相同方式准备一对小 MP4 文件再测一次。

## 正式批量处理

有两种用法：

### Windows

把单个文件或整个文件夹拖到 `START_HERE.bat` 上。

### Windows 或 macOS 默认文件夹方式

1. 将确认含 AI 生成逼真人物的最终文件放入 `AI_MEDIA_TO_TAG`。
2. Windows 双击 `START_HERE.bat`；macOS 双击 `START_HERE_MAC.command`。

## 校验标准

打开 `REPORTS/summary.txt`，正式上传批次应同时满足：

- “准确标签”等于准备上传的文件数；
- “缺失或不准确”为 0；
- “重复标签”为 0；
- “扫描错误行数”为 0。

`REPORTS/all_tags.csv` 会列出每个文件的路径、格式和完整 `XMP-dc:Subject` 内容，可用 Excel 打开复核。

## 重要说明

- 只把确定含 AI 生成逼真人物的文件交给打标脚本。
- 脚本写入的准确值是 `contains-synthetic-performer`，大小写和连字符均固定。
- 写入使用追加方式，不覆盖已有 XMP 关键词。
- ExifTool 默认生成 `原文件名_original` 备份，测试完成前不要删除。
- 应对最终导出的上传文件执行脚本；后续重新剪辑、导出或压缩可能移除元数据。
- 本工具只验证文件内标签，不包含 Amazon 上传后的端到端验证。
