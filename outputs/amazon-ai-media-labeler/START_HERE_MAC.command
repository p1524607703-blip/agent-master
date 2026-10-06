#!/bin/bash

set -u

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$BASE_DIR/AI_MEDIA_TO_TAG}"
REPORT_DIR="$BASE_DIR/REPORTS"
WRITE_ERRORS="$REPORT_DIR/write_errors.txt"

if [ -f "$BASE_DIR/exiftool-mac/exiftool" ]; then
  EXIFTOOL=(/usr/bin/perl "$BASE_DIR/exiftool-mac/exiftool")
elif command -v exiftool >/dev/null 2>&1; then
  EXIFTOOL=("$(command -v exiftool)")
else
  echo
  echo "[错误] 未找到 ExifTool。"
  echo "请使用包含 exiftool-mac 的完整便携包。"
  echo
  read -r -p "按回车键关闭……" _
  exit 1
fi

if [ ! -e "$TARGET" ]; then
  echo
  echo "[错误] 文件或文件夹不存在："
  printf '"%s"\n' "$TARGET"
  echo
  read -r -p "按回车键关闭……" _
  exit 1
fi

mkdir -p "$REPORT_DIR"
: > "$WRITE_ERRORS"

echo
echo "============================================================"
echo "Amazon AI 逼真人物媒体批量打标（macOS）"
echo "============================================================"
echo "目标："
printf '"%s"\n' "$TARGET"
echo
echo "即将写入："
echo "XMP-dc:Subject = contains-synthetic-performer"
echo
echo "说明："
echo "1. 仅处理 JPG、JPEG、PNG、GIF、TIF、TIFF、MP4、MOV。"
echo "2. 保留已有 XMP 关键词。"
echo "3. 已含准确标签的文件会跳过，不会重复添加。"
echo "4. 默认生成“原文件名_original”备份。"
echo

"${EXIFTOOL[@]}" -P -progress -r \
  -ext jpg -ext jpeg -ext png -ext gif -ext tif -ext tiff -ext mp4 -ext mov \
  -if 'not defined $XMP-dc:Subject or $XMP-dc:Subject !~ /(^|, )contains-synthetic-performer(, |$)/' \
  '-XMP-dc:Subject+=contains-synthetic-performer' \
  -efile "$WRITE_ERRORS" \
  "$TARGET"

WRITE_EXIT=$?
WRITE_ERROR_COUNT="$(wc -l < "$WRITE_ERRORS" | tr -d ' ')"

echo
echo "写入步骤结束，正在自动扫描最终文件……"
echo

/bin/bash "$BASE_DIR/VERIFY_ONLY_MAC.command" "$TARGET" --auto
SCAN_EXIT=$?

echo
if [ "$WRITE_ERROR_COUNT" -ne 0 ]; then
  echo "[警告] 写入过程返回错误码 ${WRITE_EXIT}，请查看："
  printf '"%s"\n' "$WRITE_ERRORS"
fi

if [ "$SCAN_EXIT" -eq 0 ]; then
  echo "[完成] 所有扫描到的目标文件均含准确标签，且未发现重复标签。"
else
  echo "[需检查] 扫描发现缺失、重复、无有效文件或读取错误。"
fi

echo "报告目录："
printf '"%s"\n' "$REPORT_DIR"
echo

if [ "${AMAZON_TAGGER_NO_OPEN:-0}" != "1" ]; then
  open "$REPORT_DIR" >/dev/null 2>&1 || true
fi
if [ -t 0 ]; then
  read -r -p "按回车键关闭……" _
fi

if [ "$WRITE_ERROR_COUNT" -ne 0 ]; then
  exit "$WRITE_EXIT"
fi
exit "$SCAN_EXIT"
