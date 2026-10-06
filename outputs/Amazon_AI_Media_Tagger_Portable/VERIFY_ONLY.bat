@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

set "BASE_DIR=%~dp0"
set "EXIFTOOL=%BASE_DIR%exiftool.exe"
set "TARGET=%~1"
set "AUTO_MODE=%~2"
set "REPORT_DIR=%BASE_DIR%REPORTS"
set "CSV_FILE=%REPORT_DIR%\all_tags.csv"
set "PASS_FILE=%REPORT_DIR%\pass.txt"
set "MISSING_FILE=%REPORT_DIR%\fail_missing_or_incorrect.txt"
set "DUPLICATE_FILE=%REPORT_DIR%\fail_duplicate.txt"
set "READ_ERRORS=%REPORT_DIR%\scan_errors.txt"
set "SUMMARY_FILE=%REPORT_DIR%\summary.txt"

if not defined TARGET set "TARGET=%BASE_DIR%AI_MEDIA_TO_TAG"

if not exist "%EXIFTOOL%" (
  echo.
  echo [错误] 未找到 "%EXIFTOOL%"
  echo 请将 Windows 版 ExifTool 重命名为 exiftool.exe 后放到本目录。
  echo.
  if /i not "%AUTO_MODE%"=="/AUTO" pause
  exit /b 1
)

if not exist "%TARGET%" (
  echo.
  echo [错误] 文件或文件夹不存在：
  echo "%TARGET%"
  echo.
  if /i not "%AUTO_MODE%"=="/AUTO" pause
  exit /b 1
)

if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"
if not exist "%REPORT_DIR%" (
  echo [错误] 无法创建报告目录：
  echo "%REPORT_DIR%"
  if /i not "%AUTO_MODE%"=="/AUTO" pause
  exit /b 1
)

type nul > "%READ_ERRORS%"

echo.
echo ============================================================
echo 扫描 XMP-dc:Subject 标签
echo ============================================================
echo 目标：
echo "%TARGET%"
echo.

"%EXIFTOOL%" -q -r -csv ^
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov ^
  -FileName -Directory -FileType -XMP-dc:Subject ^
  "%TARGET%" > "%CSV_FILE%" 2>> "%READ_ERRORS%"

"%EXIFTOOL%" -q -q -m -r ^
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov ^
  -if "$XMP-dc:Subject =~ /(^|, )contains-synthetic-performer(, |$)/" ^
  -p "$Directory/$FileName" ^
  "%TARGET%" > "%PASS_FILE%" 2>> "%READ_ERRORS%"

"%EXIFTOOL%" -q -q -m -r ^
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov ^
  -if "not $XMP-dc:Subject =~ /(^|, )contains-synthetic-performer(, |$)/" ^
  -p "$Directory/$FileName" ^
  "%TARGET%" > "%MISSING_FILE%" 2>> "%READ_ERRORS%"

"%EXIFTOOL%" -q -q -m -r ^
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov ^
  -if "$XMP-dc:Subject =~ /contains-synthetic-performer.*contains-synthetic-performer/" ^
  -p "$Directory/$FileName" ^
  "%TARGET%" > "%DUPLICATE_FILE%" 2>> "%READ_ERRORS%"

set "PASS_COUNT=0"
set "MISSING_COUNT=0"
set "DUPLICATE_COUNT=0"
set "ERROR_COUNT=0"

for /f %%N in ('find /v /c "" ^< "%PASS_FILE%"') do set "PASS_COUNT=%%N"
for /f %%N in ('find /v /c "" ^< "%MISSING_FILE%"') do set "MISSING_COUNT=%%N"
for /f %%N in ('find /v /c "" ^< "%DUPLICATE_FILE%"') do set "DUPLICATE_COUNT=%%N"
for /f %%N in ('find /v /c "" ^< "%READ_ERRORS%"') do set "ERROR_COUNT=%%N"

(
  echo Amazon AI 逼真人物媒体标签校验汇总
  echo.
  echo 目标："%TARGET%"
  echo 准确标签：%PASS_COUNT%
  echo 缺失或不准确：%MISSING_COUNT%
  echo 重复标签：%DUPLICATE_COUNT%
  echo 扫描错误行数：%ERROR_COUNT%
  echo.
  echo 必须满足：
  echo 1. “缺失或不准确”为 0。
  echo 2. “重复标签”为 0。
  echo 3. “扫描错误行数”为 0。
  echo 4. “准确标签”应等于本批次准备上传的文件数量。
) > "%SUMMARY_FILE%"

echo 准确标签：%PASS_COUNT%
echo 缺失或不准确：%MISSING_COUNT%
echo 重复标签：%DUPLICATE_COUNT%
echo 扫描错误行数：%ERROR_COUNT%
echo.
echo 完整报告：
echo "%REPORT_DIR%"
echo.

set "SCAN_EXIT=0"
if "%PASS_COUNT%"=="0" set "SCAN_EXIT=2"
if not "%MISSING_COUNT%"=="0" set "SCAN_EXIT=2"
if not "%DUPLICATE_COUNT%"=="0" set "SCAN_EXIT=2"
if not "%ERROR_COUNT%"=="0" set "SCAN_EXIT=2"

if "%SCAN_EXIT%"=="0" (
  echo [PASS] 本批次扫描通过。
) else (
  echo [FAIL] 请查看报告中的失败名单或扫描错误。
)

echo.
if /i not "%AUTO_MODE%"=="/AUTO" pause
exit /b %SCAN_EXIT%
