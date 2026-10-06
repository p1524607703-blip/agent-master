"""
camera_snapshot — 从 go2rtc 直接获取摄像头截图

依赖：
  - requests（pip show requests）✅ 已安装

环境变量（可选）：
  - GO2RTC_URL   go2rtc 地址，默认 http://localhost:1984
  - STREAM_NAME  流名称，默认 xiaomi_cam

用法：
  from camera_snapshot import take_snapshot
  result = take_snapshot()
  # {"success": True, "image_base64": "...", "timestamp": "...", "size_bytes": 474250}
"""

import base64
import io
import os
from datetime import datetime, timezone

import requests

GO2RTC_URL: str = os.environ.get("GO2RTC_URL", "http://localhost:1984")
STREAM_NAME: str = os.environ.get("STREAM_NAME", "xiaomi_cam")
REQUEST_TIMEOUT: int = 20


class SnapshotError(Exception):
    pass


def check_go2rtc() -> bool:
    """检查 go2rtc 是否在运行。"""
    try:
        r = requests.get(f"{GO2RTC_URL}/api/streams", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def take_snapshot(
    stream: str | None = None,
    go2rtc_url: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict:
    """
    从 go2rtc 获取一帧 JPEG 截图。

    Args:
        stream:     流名称，默认使用 STREAM_NAME 环境变量（xiaomi_cam）
        go2rtc_url: go2rtc 地址，默认 http://localhost:1984
        timeout:    超时秒数

    Returns:
        {
            "success":      bool,
            "image_base64": str,        # JPEG base64
            "size_bytes":   int,
            "timestamp":    str,        # ISO 8601 UTC
            "stream":       str,
        }
    """
    url = (go2rtc_url or GO2RTC_URL).rstrip("/")
    src = stream or STREAM_NAME
    endpoint = f"{url}/api/frame.jpeg?src={src}"

    try:
        resp = requests.get(endpoint, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise SnapshotError(
            f"无法连接到 go2rtc（{url}）。\n"
            "请启动 go2rtc：\n"
            r'  "D:\Download\agent-master\OpenClaw+IoT\go2rtc.exe" '
            r'-config "D:\Download\agent-master\OpenClaw+IoT\configs\go2rtc.yaml"'
        )
    except requests.exceptions.Timeout:
        raise SnapshotError(f"请求超时（{timeout}s）")

    if resp.status_code != 200:
        raise SnapshotError(f"go2rtc 返回 {resp.status_code}：{resp.text[:200]}")

    if len(resp.content) < 100:
        raise SnapshotError("截图为空（摄像头可能离线，等待几秒后重试）")

    raw = resp.content
    # 若图片超过 200KB 则压缩，避免 MiniMax 500 错误
    if len(raw) > 200 * 1024:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(raw))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            raw = buf.getvalue()
        except ImportError:
            pass  # Pillow 未安装时跳过压缩，直接传原图

    return {
        "success": True,
        "image_base64": base64.b64encode(raw).decode("ascii"),
        "size_bytes": len(resp.content),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stream": src,
    }


if __name__ == "__main__":
    if not check_go2rtc():
        print("[ERROR] go2rtc 未运行，请先启动：")
        print(r'  "D:\Download\agent-master\OpenClaw+IoT\启动go2rtc.bat"')
        raise SystemExit(1)

    snap = take_snapshot()
    print(f"[OK] 截图成功")
    print(f"     流：{snap['stream']}")
    print(f"     大小：{snap['size_bytes']:,} bytes")
    print(f"     时间：{snap['timestamp']}")
    print(f"     Base64 长度：{len(snap['image_base64'])} 字符")
