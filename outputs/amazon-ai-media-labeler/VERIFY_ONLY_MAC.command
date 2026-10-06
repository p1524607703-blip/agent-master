#!/bin/bash

set -u

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$BASE_DIR/AI_MEDIA_TO_TAG}"
AUTO_MODE="${2:-}"
REPORT_DIR="$BASE_DIR/REPORTS"
CSV_FILE="$REPORT_DIR/all_tags.csv"
PASS_FILE="$REPORT_DIR/pass.txt"
MISSING_FILE="$REPORT_DIR/fail_missing_or_incorrect.txt"
DUPLICATE_FILE="$REPORT_DIR/fail_duplicate.txt"
READ_ERRORS="$REPORT_DIR/scan_errors.txt"
SUMMARY_FILE="$REPORT_DIR/summary.txt"

if [ -f "$BASE_DIR/exiftool-mac/exiftool" ]; then
  EXIFTOOL=(/usr/bin/perl "$BASE_DIR/exiftool-mac/exiftool")
elif command -v exiftool >/dev/null 2>&1; then
  EXIFTOOL=("$(command -v exiftool)")
else
  echo
  echo "[错误] 未找到 ExifTool。"
  echo "请使用包含 exiftool-mac 的完整便携包。"
  echo
  if [ "$AUTO_MODE" != "--auto" ]; then
    read -r -p "按回车键关闭……" _
  fi
  exit 1
fi

if [ ! -e "$TARGET" ]; then
  echo
  echo "[错误] 文件或文件夹不存在："
  printf '"%s"\n' "$TARGET"
  echo
  if [ "$AUTO_MODE" != "--auto" ]; then
    read -r -p "按回车键关闭……" _
  fi
  exit 1
fi

mkdir -p "$REPORT_DIR"
: > "$READ_ERRORS"

echo
echo "============================================================"
echo "扫描 XMP-dc:Subject 标签（macOS）"
echo "============================================================"
echo "目标："
printf '"%s"\n' "$TARGET"
echo

"${EXIFTOOL[@]}" -q -r -csv \
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov \
  -FileName -Directory -FileType -XMP-dc:Subject \
  "$TARGET" > "$CSV_FILE" 2>> "$READ_ERRORS"

"${EXIFTOOL[@]}" -q -q -m -r \
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov \
  -if '$XMP-dc:Subject =~ /(^|, )contains-synthetic-performer(, |$)/' \
  -p '$Directory/$FileName' \
  "$TARGET" > "$PASS_FILE" 2>> "$READ_ERRORS"

"${EXIFTOOL[@]}" -q -q -m -r \
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov \
  -if 'not $XMP-dc:Subject =~ /(^|, )contains-synthetic-performer(, |$)/' \
  -p '$Directory/$FileName' \
  "$TARGET" > "$MISSING_FILE" 2>> "$READ_ERRORS"

"${EXIFTOOL[@]}" -q -q -m -r \
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov \
  -if '$XMP-dc:Subject =~ /contains-synthetic-performer.*contains-synthetic-performer/' \
  -p '$Directory/$FileName' \
  "$TARGET" > "$DUPLICATE_FILE" 2>> "$READ_ERRORS"

PASS_COUNT="$(wc -l < "$PASS_FILE" | tr -d ' ')"
MISSING_COUNT="$(wc -l < "$MISSING_FILE" | tr -d ' ')"
DUPLICATE_COUNT="$(wc -l < "$DUPLICATE_FILE" | tr -d ' ')"
ERROR_COUNT="$(wc -l < "$READ_ERRORS" | tr -d ' ')"

{
  echo "Amazon AI 逼真人物媒体标签校验汇总"
  echo
  printf '目标："%s"\n' "$TARGET"
  echo "准确标签：$PASS_COUNT"
  echo "缺失或不准确：$MISSING_COUNT"
  echo "重复标签：$DUPLICATE_COUNT"
  echo "扫描错误行数：$ERROR_COUNT"
  echo
  echo "必须满足："
  echo "1. “缺失或不准确”为 0。"
  echo "2. “重复标签”为 0。"
  echo "3. “扫描错误行数”为 0。"
  echo "4. “准确标签”应等于本批次准备上传的文件数量。"
} > "$SUMMARY_FILE"

echo "准确标签：$PASS_COUNT"
echo "缺失或不准确：$MISSING_COUNT"
echo "重复标签：$DUPLICATE_COUNT"
echo "扫描错误行数：$ERROR_COUNT"
echo
echo "完整报告："
printf '"%s"\n' "$REPORT_DIR"
echo

SCAN_EXIT=0
if [ "$PASS_COUNT" -eq 0 ] || \
   [ "$MISSING_COUNT" -ne 0 ] || \
   [ "$DUPLICATE_COUNT" -ne 0 ] || \
   [ "$ERROR_COUNT" -ne 0 ]; then
  SCAN_EXIT=2
fi

if [ "$SCAN_EXIT" -eq 0 ]; then
  echo "[PASS] 本批次扫描通过。"
else
  echo "[FAIL] 请查看报告中的失败名单或扫描错误。"
fi

echo
if [ "$AUTO_MODE" != "--auto" ]; then
  if [ "${AMAZON_TAGGER_NO_OPEN:-0}" != "1" ]; then
    open "$REPORT_DIR" >/dev/null 2>&1 || true
  fi
  if [ -t 0 ]; then
    read -r -p "按回车键关闭……" _
  fi
fi
exit "$SCAN_EXIT"
