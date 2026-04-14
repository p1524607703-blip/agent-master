"""
scene_analysis — 摄像头场景分析

依赖：
  - requests ✅ 已安装

环境变量：
  - MINIMAX_API_KEY  必填，MiniMax API 密钥（.env 已配置）
  - GO2RTC_URL       可选，默认 http://localhost:1984
  - STREAM_NAME      可选，默认 xiaomi_cam

用法：
  from scene_analysis import analyze_scene
  result = analyze_scene()
  # {"scene": "客厅", "objects": ["沙发","电视"], "anomaly": False, "summary": "..."}
"""

import os

from camera_snapshot import take_snapshot

MINIMAX_API_URL = "https://api.minimax.chat/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-M2"


def analyze_scene(
    stream: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    分析摄像头画面的场景内容。

    Returns:
        {
            "scene":     str,        # 场景类型，如"客厅"、"门口"
            "objects":   list[str],  # 识别到的主要物体
            "anomaly":   bool,       # 是否存在异常情况
            "summary":   str,        # 中文一句话总结
            "timestamp": str,
            "stream":    str,
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
            "max_tokens": 384,
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
                                "这是一张摄像头截图，请分析画面内容：\n"
                                "1. 场景类型（如：客厅、卧室、门口、走廊、厨房）\n"
                                "2. 主要物体（逗号分隔，最多5个）\n"
                                "3. 是否存在异常（如：陌生人、火焰、烟雾、破损）\n"
                                "4. 一句话总结\n\n"
                                "请严格按以下格式回答：\n"
                                "场景: ...\n"
                                "物体: 物体1, 物体2, ...\n"
                                "异常: 是/否\n"
                                "总结: ..."
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
    scene, objects_raw, anomaly_raw, summary = "", [], False, ""

    for line in text.split("\n"):
        if line.startswith("场景:"):
            scene = line.split(":", 1)[1].strip()
        elif line.startswith("物体:"):
            objects_raw = [o.strip() for o in line.split(":", 1)[1].split(",") if o.strip()]
        elif line.startswith("异常:"):
            anomaly_raw = "是" in line
        elif line.startswith("总结:"):
            summary = line.split(":", 1)[1].strip()

    return {
        "scene": scene,
        "objects": objects_raw,
        "anomaly": anomaly_raw,
        "summary": summary,
        "timestamp": snap["timestamp"],
        "stream": snap["stream"],
    }


if __name__ == "__main__":
    result = analyze_scene()
    print(f"[场景] {result['scene']}")
    print(f"[物体] {', '.join(result['objects'])}")
    print(f"[异常] {'有异常' if result['anomaly'] else '正常'}")
    print(f"[总结] {result['summary']}")
    print(f"[时间] {result['timestamp']}")
