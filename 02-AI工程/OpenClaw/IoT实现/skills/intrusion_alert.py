"""
intrusion_alert — OpenClaw Skill：定时入侵检测 + 飞书告警推送

功能：
  - 定时调用 person_detection 检测画面中是否有人
  - 检测到人时通过飞书 Webhook 推送告警消息（含截图）
  - 支持设置检测间隔和静默期（避免重复告警）

依赖：
  - requests（pip install requests）
  - anthropic（pip install anthropic）
  - camera_snapshot（同目录）
  - person_detection（同目录）

环境变量：
  - HA_URL / HA_TOKEN：Home Assistant 配置
  - ANTHROPIC_API_KEY：Anthropic API 密钥
  - FEISHU_WEBHOOK_URL：飞书自定义机器人 Webhook 地址

用法：
  from intrusion_alert import start_monitoring
  start_monitoring("camera.xiaomi_c700", interval=30, cooldown=300)

  # 或单次检测 + 推送：
  from intrusion_alert import check_and_alert
  check_and_alert("camera.xiaomi_c700")
"""

import json
import os
import time
import logging
from datetime import datetime, timezone

import requests

from camera_snapshot import take_snapshot, SnapshotError
from person_detection import detect_person


logger = logging.getLogger(__name__)

FEISHU_WEBHOOK_URL: str = os.environ.get("FEISHU_WEBHOOK_URL", "")


# ---------------------------------------------------------------------------
# 飞书推送
# ---------------------------------------------------------------------------

def send_feishu_alert(
    detection_result: dict,
    image_base64: str | None = None,
    webhook_url: str | None = None,
) -> bool:
    """
    通过飞书 Webhook 发送入侵告警。

    Args:
        detection_result: person_detection 的返回结果
        image_base64:     截图 base64（可选，用于富文本消息）
        webhook_url:      飞书 Webhook 地址

    Returns:
        bool: 是否发送成功
    """
    url = webhook_url or FEISHU_WEBHOOK_URL
    if not url:
        logger.error("FEISHU_WEBHOOK_URL 未设置，无法推送告警")
        return False

    timestamp = detection_result.get("timestamp", datetime.now(timezone.utc).isoformat())
    entity_id = detection_result.get("entity_id", "unknown")
    count = detection_result.get("count", 0)
    description = detection_result.get("description", "")

    # 飞书富文本消息
    content = [
        [
            {"tag": "text", "text": f"摄像头: {entity_id}\n"},
        ],
        [
            {"tag": "text", "text": f"检测到 {count} 人\n"},
        ],
        [
            {"tag": "text", "text": f"描述: {description}\n"},
        ],
        [
            {"tag": "text", "text": f"时间: {timestamp}"},
        ],
    ]

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"⚠ 入侵告警 — {entity_id}",
                    "content": content,
                }
            }
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 or data.get("StatusCode") == 0:
                logger.info("飞书告警发送成功")
                return True
            logger.warning(f"飞书返回错误: {data}")
            return False
        logger.warning(f"飞书 HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"飞书推送失败: {e}")
        return False


# ---------------------------------------------------------------------------
# 单次检测 + 告警
# ---------------------------------------------------------------------------

def check_and_alert(
    entity_id: str,
    ha_url: str | None = None,
    ha_token: str | None = None,
    webhook_url: str | None = None,
) -> dict:
    """
    执行一次人物检测，如果检测到人则推送飞书告警。

    Args:
        entity_id:   HA 摄像头实体 ID
        ha_url:      HA 地址
        ha_token:    HA 令牌
        webhook_url: 飞书 Webhook 地址

    Returns:
        dict: {
            "has_person": bool,
            "alert_sent": bool,
            "detection":  person_detection 完整结果,
        }
    """
    detection = detect_person(entity_id, ha_url=ha_url, ha_token=ha_token)

    alert_sent = False
    if detection.get("has_person"):
        alert_sent = send_feishu_alert(detection, webhook_url=webhook_url)

    return {
        "has_person": detection.get("has_person", False),
        "alert_sent": alert_sent,
        "detection": detection,
    }


# ---------------------------------------------------------------------------
# 持续监控
# ---------------------------------------------------------------------------

def start_monitoring(
    entity_id: str,
    interval: int = 30,
    cooldown: int = 300,
    ha_url: str | None = None,
    ha_token: str | None = None,
    webhook_url: str | None = None,
) -> None:
    """
    持续监控摄像头，检测到人时推送飞书告警。

    Args:
        entity_id: HA 摄像头实体 ID
        interval:  检测间隔（秒），默认 30
        cooldown:  告警静默期（秒），默认 300（5 分钟内不重复告警）
        ha_url:    HA 地址
        ha_token:  HA 令牌
        webhook_url: 飞书 Webhook 地址
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info(f"开始监控 {entity_id}，间隔 {interval}s，静默期 {cooldown}s")

    last_alert_time: float = 0

    while True:
        try:
            detection = detect_person(entity_id, ha_url=ha_url, ha_token=ha_token)

            if detection.get("has_person"):
                now = time.time()
                if now - last_alert_time >= cooldown:
                    logger.warning(
                        f"检测到 {detection.get('count', '?')} 人: {detection.get('description', '')}"
                    )
                    sent = send_feishu_alert(detection, webhook_url=webhook_url)
                    if sent:
                        last_alert_time = now
                else:
                    remaining = int(cooldown - (now - last_alert_time))
                    logger.info(f"检测到人，但仍在静默期（剩余 {remaining}s），跳过告警")
            else:
                logger.debug(f"未检测到人 — {entity_id}")

        except SnapshotError as e:
            logger.error(f"截图失败: {e}")
        except Exception as e:
            logger.error(f"检测异常: {e}")

        time.sleep(interval)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    entity = sys.argv[1] if len(sys.argv) > 1 else "camera.xiaomi_c700"
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    if "--once" in sys.argv:
        result = check_and_alert(entity)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        start_monitoring(entity, interval=interval)
