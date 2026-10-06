"""
camera_snapshot — OpenClaw Skill：通过 Home Assistant REST API 获取摄像头截图

功能：
  - 调用 HA 的 GET /api/camera_proxy/{entity_id} 获取 JPEG 截图
  - 返回 base64 编码的图像数据 + 时间戳

依赖：
  - requests（pip install requests）

环境变量：
  - HA_URL：Home Assistant 地址，例如 http://192.168.1.100:8123
  - HA_TOKEN：HA 长期访问令牌（Long-Lived Access Token）

用法：
  from camera_snapshot import take_snapshot
  result = take_snapshot("camera.xiaomi_c700")
  # result = {"success": True, "image_base64": "...", "timestamp": "...", "entity_id": "..."}
"""

import base64
import os
from datetime import datetime, timezone

import requests


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

HA_URL: str = os.environ.get("HA_URL", "http://localhost:8123")
HA_TOKEN: str = os.environ.get("HA_TOKEN", "")

REQUEST_TIMEOUT: int = 15  # 秒


# ---------------------------------------------------------------------------
# 异常定义
# ---------------------------------------------------------------------------

class SnapshotError(Exception):
    """截图获取失败的基类异常。"""


class AuthenticationError(SnapshotError):
    """HA 认证失败（401）。"""


class CameraUnavailableError(SnapshotError):
    """摄像头离线或 entity_id 不存在。"""


class TimeoutError(SnapshotError):
    """请求超时。"""


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def take_snapshot(
    entity_id: str,
    ha_url: str | None = None,
    ha_token: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict:
    """
    获取指定摄像头的截图。

    Args:
        entity_id: HA 摄像头实体 ID，例如 "camera.xiaomi_c700"
        ha_url:    HA 地址，默认从环境变量 HA_URL 读取
        ha_token:  HA 令牌，默认从环境变量 HA_TOKEN 读取
        timeout:   请求超时秒数

    Returns:
        dict: {
            "success":      bool,
            "image_base64": str,       # JPEG 图像的 base64 编码
            "content_type": str,       # 例如 "image/jpeg"
            "timestamp":    str,       # ISO 8601 UTC 时间戳
            "entity_id":    str,
        }

    Raises:
        AuthenticationError:    HA 令牌无效或缺失
        CameraUnavailableError: 摄像头离线或 entity_id 无效
        TimeoutError:           请求超时
        SnapshotError:          其他错误
    """
    url = (ha_url or HA_URL).rstrip("/")
    token = ha_token or HA_TOKEN

    if not token:
        raise AuthenticationError("HA_TOKEN 未设置。请在环境变量中配置 Home Assistant 长期访问令牌。")

    endpoint = f"{url}/api/camera_proxy/{entity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        resp = requests.get(endpoint, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        raise TimeoutError(f"请求超时（{timeout}s）：{endpoint}")
    except requests.exceptions.ConnectionError:
        raise SnapshotError(f"无法连接到 Home Assistant：{url}")

    if resp.status_code == 401:
        raise AuthenticationError("HA 认证失败：令牌无效或已过期。")
    if resp.status_code == 404:
        raise CameraUnavailableError(f"摄像头不存在：{entity_id}")
    if resp.status_code == 500:
        raise CameraUnavailableError(f"摄像头可能离线：{entity_id}（HA 返回 500）")
    if resp.status_code != 200:
        raise SnapshotError(f"HA 返回异常状态码 {resp.status_code}：{resp.text[:200]}")

    content_type = resp.headers.get("Content-Type", "image/jpeg")
    image_b64 = base64.b64encode(resp.content).decode("ascii")
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "success": True,
        "image_base64": image_b64,
        "content_type": content_type,
        "timestamp": timestamp,
        "entity_id": entity_id,
    }


def take_snapshots(
    entity_ids: list[str],
    ha_url: str | None = None,
    ha_token: str | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict]:
    """
    批量获取多个摄像头截图。

    对于每个摄像头，如果获取失败则在结果中标记 success=False 并附带错误信息，
    不会因单个摄像头失败而中断整体流程。

    Args:
        entity_ids: 摄像头实体 ID 列表
        ha_url:     HA 地址
        ha_token:   HA 令牌
        timeout:    请求超时秒数

    Returns:
        list[dict]: 每个元素为 take_snapshot 的返回值，失败时包含 error 字段
    """
    results = []
    for eid in entity_ids:
        try:
            result = take_snapshot(eid, ha_url=ha_url, ha_token=ha_token, timeout=timeout)
        except SnapshotError as e:
            result = {
                "success": False,
                "entity_id": eid,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# CLI 入口（调试用）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    entity = sys.argv[1] if len(sys.argv) > 1 else "camera.xiaomi_c700"
    try:
        snap = take_snapshot(entity)
        print(f"[OK] {snap['entity_id']} @ {snap['timestamp']}")
        print(f"     Content-Type: {snap['content_type']}")
        print(f"     Base64 长度: {len(snap['image_base64'])} 字符")
    except SnapshotError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
