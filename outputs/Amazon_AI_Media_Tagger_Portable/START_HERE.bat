@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

set "BASE_DIR=%~dp0"
set "EXIFTOOL=%BASE_DIR%exiftool.exe"
set "TARGET=%~1"
set "REPORT_DIR=%BASE_DIR%REPORTS"
set "WRITE_ERRORS=%REPORT_DIR%\write_errors.txt"

if not defined TARGET set "TARGET=%BASE_DIR%AI_MEDIA_TO_TAG"

if not exist "%EXIFTOOL%" (
  echo.
  echo [错误] 未找到 "%EXIFTOOL%"
  echo 请下载 Windows 版 ExifTool，并将 exiftool^(-k^).exe 重命名为 exiftool.exe，
  echo 然后放到本 BAT 文件所在目录。
  echo.
  pause
  exit /b 1
)

if not exist "%TARGET%" (
  echo.
  echo [错误] 文件或文件夹不存在：
  echo "%TARGET%"
  echo.
  pause
  exit /b 1
)

if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"
if not exist "%REPORT_DIR%" (
  echo [错误] 无法创建报告目录：
  echo "%REPORT_DIR%"
  pause
  exit /b 1
)

type nul > "%WRITE_ERRORS%"

echo.
echo ============================================================
echo Amazon AI 逼真人物媒体批量打标
echo ============================================================
echo 目标：
echo "%TARGET%"
echo.
echo 即将写入：
echo XMP-dc:Subject = contains-synthetic-performer
echo.
echo 说明：
echo 1. 仅处理 JPG、JPEG、PNG、GIF、TIF、TIFF、MP4、MOV。
echo 2. 保留已有 XMP 关键词。
echo 3. 已含准确标签的文件会跳过，不会重复添加。
echo 4. 默认生成“原文件名_original”备份。
echo.

"%EXIFTOOL%" -P -progress -r ^
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov ^
  -if "not defined $XMP-dc:Subject or $XMP-dc:Subject !~ /(^|, )contains-synthetic-performer(, |$)/" ^
  "-XMP-dc:Subject+=contains-synthetic-performer" ^
  -efile "%WRITE_ERRORS%" ^
  "%TARGET%"

set "WRITE_EXIT=%ERRORLEVEL%"
set "WRITE_ERROR_COUNT=0"
for /f %%N in ('find /v /c "" ^< "%WRITE_ERRORS%"') do set "WRITE_ERROR_COUNT=%%N"

echo.
echo 写入步骤结束，正在自动扫描最终文件……
echo.

call "%BASE_DIR%VERIFY_ONLY.bat" "%TARGET%" /AUTO
set "SCAN_EXIT=%ERRORLEVEL%"

echo.
if not "%WRITE_ERROR_COUNT%"=="0" (
  echo [警告] 写入过程返回错误码 %WRITE_EXIT%，请查看：
  echo "%WRITE_ERRORS%"
)

if "%SCAN_EXIT%"=="0" (
  echo [完成] 所有扫描到的目标文件均含准确标签，且未发现重复标签。
) else (
  echo [需检查] 扫描发现缺失、重复、无有效文件或读取错误。
)

echo 报告目录：
echo "%REPORT_DIR%"
echo.
pause

if not "%WRITE_ERROR_COUNT%"=="0" exit /b %WRITE_EXIT%
exit /b %SCAN_EXIT%
