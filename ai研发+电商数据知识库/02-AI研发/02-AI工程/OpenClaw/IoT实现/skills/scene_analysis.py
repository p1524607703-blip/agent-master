"""
scene_analysis — OpenClaw Skill：通用摄像头场景分析

功能：
  - 调用 camera_snapshot 获取截图
  - 将图像传给多模态大模型（Claude）进行场景理解
  - 返回 {scene, objects, anomaly, summary}

依赖：
  - requests（pip install requests）
  - anthropic（pip install anthropic）
  - camera_snapshot（同目录）

环境变量：
  - HA_URL / HA_TOKEN：Home Assistant 配置
  - ANTHROPIC_API_KEY：Anthropic API 密钥

用法：
  from scene_analysis import analyze_scene
  result = analyze_scene("camera.xiaomi_c700")
  # {"scene": "客厅", "objects": ["沙发", "电视"], "anomaly": False, "summary": "..."}
"""

import json
import os

import anthropic

from camera_snapshot import take_snapshot, SnapshotError


ANTHROPIC_MODEL = "claude-opus-4-6"

ANALYSIS_PROMPT = """请分析这张摄像头截图，识别场景信息。

请严格按照以下 JSON 格式返回结果，不要输出其他内容：
{
  "scene": "场景类型（如：客厅、门口、走廊、车库、户外等）",
  "objects": ["识别到的主要物体列表（中文）"],
  "anomaly": true/false,
  "anomaly_detail": "如果有异常情况请描述，没有则为空字符串",
  "summary": "一句话总结当前画面（中文）"
}

异常情况包括但不限于：陌生人、可疑物品、火焰/烟雾、门窗异常开启、地面积水等。
正常的日常场景请标记 anomaly 为 false。"""


def analyze_scene(
    entity_id: str,
    ha_url: str | None = None,
    ha_token: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    分析摄像头画面的场景信息。

    Args:
        entity_id: HA 摄像头实体 ID
        ha_url:    HA 地址
        ha_token:  HA 令牌
        api_key:   Anthropic API 密钥

    Returns:
        dict: {
            "scene":          str,   # 场景类型
            "objects":        list,  # 识别到的物体
            "anomaly":        bool,  # 是否存在异常
            "anomaly_detail": str,   # 异常描述
            "summary":        str,   # 一句话总结
            "entity_id":      str,
            "timestamp":      str,
        }

    Raises:
        SnapshotError: 截图获取失败
        Exception:     模型调用或解析失败
    """
    # 1. 获取截图
    snap = take_snapshot(entity_id, ha_url=ha_url, ha_token=ha_token)

    # 2. 调用多模态模型
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    media_type = snap["content_type"] if snap["content_type"].startswith("image/") else "image/jpeg"

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": snap["image_base64"],
                        },
                    },
                    {
                        "type": "text",
                        "text": ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )

    # 3. 解析结果
    raw_text = response.content[0].text.strip()
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    result = json.loads(raw_text)
    result["entity_id"] = entity_id
    result["timestamp"] = snap["timestamp"]

    return result


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    entity = sys.argv[1] if len(sys.argv) > 1 else "camera.xiaomi_c700"
    try:
        result = analyze_scene(entity)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
