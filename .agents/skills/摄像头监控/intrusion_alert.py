"""
intrusion_alert — 入侵检测 + 飞书告警

依赖：
  - requests ✅ 已安装
  - anthropic ❌ 需安装：pip install anthropic

环境变量：
  - ANTHROPIC_API_KEY   必填
  - FEISHU_WEBHOOK_URL  必填（入侵告警推送）
  - GO2RTC_URL          可选，默认 http://localhost:1984
  - STREAM_NAME         可选，默认 xiaomi_cam

用法：
  from intrusion_alert import check_and_alert, start_monitoring

  # 单次检测
  result = check_and_alert()

  # 持续监控（每30秒，5分钟静默期）
  start_monitoring(interval=30, cooldown=300)
"""

import os
import time
from datetime import datetime, timezone

import requests

from person_detection import detect_person


def send_feishu_alert(text: str, webhook_url: str) -> bool:
    """发送飞书 Webhook 消息。返回是否成功。"""
    try:
        resp = requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def check_and_alert(
    stream: str | None = None,
    api_key: str | None = None,
    webhook_url: str | None = None,
) -> dict:
    """
    单次检测：若发现人员则推送飞书告警。

    Returns:
        {
            "has_person":   bool,
            "alert_sent":   bool,
            "description":  str,
            "timestamp":    str,
        }
    """
    webhook = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "")

    result = detect_person(stream=stream, api_key=api_key)
    alert_sent = False

    if result["has_person"] and webhook:
        ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"⚠️ 入侵告警\n"
            f"时间：{ts}\n"
            f"人数：{result['count']}\n"
            f"描述：{result['description']}"
        )
        alert_sent = send_feishu_alert(msg, webhook)

    return {
        "has_person": result["has_person"],
        "alert_sent": alert_sent,
        "description": result["description"],
        "timestamp": result["timestamp"],
    }


def start_monitoring(
    stream: str | None = None,
    interval: int = 30,
    cooldown: int = 300,
    api_key: str | None = None,
    webhook_url: str | None = None,
) -> None:
    """
    持续监控，Ctrl+C 停止。

    Args:
        interval: 检测间隔（秒），默认 30
        cooldown: 告警静默期（秒），默认 300（5分钟内不重复告警）
    """
    last_alert_time = 0
    print(f"开始监控（间隔 {interval}s，静默期 {cooldown}s）。Ctrl+C 停止。")

    while True:
        try:
            result = check_and_alert(stream=stream, api_key=api_key, webhook_url=webhook_url)
            ts = result["timestamp"]

            if result["has_person"]:
                now = time.time()
                if now - last_alert_time > cooldown:
                    print(f"[{ts}] ⚠️ 检测到人员 — {result['description']}")
                    if result["alert_sent"]:
                        print(f"          飞书告警已发送")
                    last_alert_time = now
                else:
                    remaining = int(cooldown - (now - last_alert_time))
                    print(f"[{ts}] 检测到人员（静默期剩余 {remaining}s）")
            else:
                print(f"[{ts}] 无人")

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n监控已停止。")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(interval)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        result = check_and_alert()
        print(f"[{'⚠️ 有人' if result['has_person'] else '无人'}]")
        if result["has_person"]:
            print(f"  描述：{result['description']}")
            print(f"  飞书：{'已发送' if result['alert_sent'] else '未发送（未配置 FEISHU_WEBHOOK_URL）'}")
    else:
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
        start_monitoring(interval=interval)
