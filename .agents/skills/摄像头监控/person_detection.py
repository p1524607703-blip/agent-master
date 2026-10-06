"""
person_detection — 摄像头人员检测

依赖：
  - requests ✅ 已安装

环境变量：
  - MINIMAX_API_KEY  必填，MiniMax API 密钥（.env 已配置）
  - GO2RTC_URL       可选，默认 http://localhost:1984
  - STREAM_NAME      可选，默认 xiaomi_cam

用法：
  from person_detection import detect_person
  result = detect_person()
  # {"has_person": True, "count": 2, "description": "两人在客厅沙发区域", "timestamp": "..."}
"""

import os

from camera_snapshot import SnapshotError, take_snapshot

MINIMAX_API_URL = "https://api.minimax.chat/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-M2"


def detect_person(
    stream: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    检测画面中是否有人。

    Returns:
        {
            "has_person":   bool,
            "count":        int,
            "description":  str,   # 中文描述
            "timestamp":    str,
            "stream":       str,
        }
    """
    import requests

    key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise ValueError("MINIMAX_API_KEY 未设置")

    snap = take_snapshot(stream=stream)

    resp = requests.post(
        MINIMAX_API_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": MINIMAX_MODEL,
            "max_tokens": 256,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{snap['image_base64']}"
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "这是一张摄像头截图。请回答：\n"
                                "1. 画面中是否有人？（是/否）\n"
                                "2. 如有人，大约几个人？\n"
                                "3. 用一句话描述他们的位置和动作。\n\n"
                                "请严格按以下格式回答（不要额外说明）：\n"
                                "有人: 是/否\n"
                                "人数: N\n"
                                "描述: ..."
                            ),
                        },
                    ],
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("base_resp", {}).get("status_code", 0) != 0:
        raise RuntimeError(f"MiniMax 错误：{data['base_resp']['status_msg']}")

    text = data["choices"][0]["message"]["content"].strip()
    has_person = False
    count = 0
    description = ""

    for line in text.split("\n"):
        if line.startswith("有人:"):
            has_person = "是" in line
        elif line.startswith("人数:"):
            try:
                count = int(line.split(":", 1)[1].strip())
            except ValueError:
                count = 1 if has_person else 0
        elif line.startswith("描述:"):
            description = line.split(":", 1)[1].strip()

    return {
        "has_person": has_person,
        "count": count,
        "description": description,
        "timestamp": snap["timestamp"],
        "stream": snap["stream"],
    }


if __name__ == "__main__":
    result = detect_person()
    status = "检测到人员" if result["has_person"] else "未检测到人员"
    print(f"[{status}]")
    if result["has_person"]:
        print(f"  人数：{result['count']}")
        print(f"  描述：{result['description']}")
    print(f"  时间：{result['timestamp']}")
