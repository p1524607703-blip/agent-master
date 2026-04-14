"""
person_detection — OpenClaw Skill：摄像头人物检测

功能：
  - 调用 camera_snapshot 获取截图
  - 将图像传给多模态大模型（Claude）分析是否有人
  - 返回 {has_person, count, description}

依赖：
  - requests（pip install requests）
  - anthropic（pip install anthropic）
  - camera_snapshot（同目录）

环境变量：
  - HA_URL / HA_TOKEN：Home Assistant 配置（camera_snapshot 使用）
  - ANTHROPIC_API_KEY：Anthropic API 密钥

用法：
  from person_detection import detect_person
  result = detect_person("camera.xiaomi_c700")
  # {"has_person": True, "count": 2, "description": "两人站在门口附近"}
"""

import json
import os

import anthropic

from camera_snapshot import take_snapshot, SnapshotError


ANTHROPIC_MODEL = "claude-opus-4-6"

DETECTION_PROMPT = """请分析这张摄像头截图，判断画面中是否有人。

请严格按照以下 JSON 格式返回结果，不要输出其他内容：
{
  "has_person": true/false,
  "count": 人数（整数，没有人时为 0）,
  "description": "简短描述画面中人物的位置和动作（中文，没有人时写'画面中无人'）"
}"""


def detect_person(
    entity_id: str,
    ha_url: str | None = None,
    ha_token: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    检测摄像头画面中是否有人。

    Args:
        entity_id: HA 摄像头实体 ID
        ha_url:    HA 地址
        ha_token:  HA 令牌
        api_key:   Anthropic API 密钥，默认从 ANTHROPIC_API_KEY 读取

    Returns:
        dict: {
            "has_person":  bool,
            "count":       int,
            "description": str,
            "entity_id":   str,
            "timestamp":   str,
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
        max_tokens=256,
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
                        "text": DETECTION_PROMPT,
                    },
                ],
            }
        ],
    )

    # 3. 解析结果
    raw_text = response.content[0].text.strip()
    # 提取 JSON（模型可能在 JSON 前后添加 markdown 代码块标记）
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
        result = detect_person(entity)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
