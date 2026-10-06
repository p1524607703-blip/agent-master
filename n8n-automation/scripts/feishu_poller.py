#!/usr/bin/env python3
"""
飞书 A+ 任务轮询器
每60秒扫描"任务状态=待处理"的记录，触发 n8n webhook 执行爬取回填
"""
import subprocess
import time
import json
import requests

APP_ID = "cli_a9460d39a5395bdd"
BASE_TOKEN = "TaHNbaexlapD6IsV6escowAknrd"
TABLE_ID = "tblPl7Z8o4mTy4La"
SKU_TABLE_ID = "tblEOeeD4HARuHuI"
N8N_WEBHOOK = "http://localhost:5678/webhook/amazon-aplus-scrape"
POLL_INTERVAL = 60


def get_app_secret():
    r = subprocess.run(
        ["security", "find-generic-password", "-a", APP_ID, "-s", f"appsecret:{APP_ID}", "-w"],
        capture_output=True, text=True
    )
    return r.stdout.strip()


def get_token(app_secret):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": app_secret},
        timeout=10
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token failed: {data}")
    return data["tenant_access_token"]


def search_pending(token):
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records/search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "任务状态", "operator": "is", "value": ["待处理"]},
                    {"field_name": "商品URL", "operator": "isNotEmpty", "value": []}
                ]
            },
            "page_size": 5
        },
        timeout=15
    )
    return resp.json().get("data", {}).get("items", [])


def extract_url(field_value):
    if isinstance(field_value, dict):
        return field_value.get("link") or field_value.get("text") or ""
    return field_value or ""


def poll_once():
    app_secret = get_app_secret()
    if not app_secret:
        print("ERROR: keychain lookup failed")
        return

    token = get_token(app_secret)
    records = search_pending(token)

    if not records:
        print(f"[{ts()}] no pending records")
        return

    print(f"[{ts()}] {len(records)} pending record(s)")

    for rec in records:
        record_id = rec["record_id"]
        url = extract_url(rec.get("fields", {}).get("商品URL", ""))
        if not url:
            print(f"  skip {record_id}: no URL")
            continue

        print(f"  → {record_id}  {url[:70]}")
        try:
            resp = requests.post(
                N8N_WEBHOOK,
                json={
                    "app_token": BASE_TOKEN,
                    "table_id": TABLE_ID,
                    "record_id": record_id,
                    "sku_table_id": SKU_TABLE_ID,
                    "url": url,
                },
                timeout=120,
            )
            result = resp.json()
            print(f"     ✓ asin={result.get('asin')} variants={result.get('variants_count')}")
        except Exception as e:
            print(f"     ✗ {e}")


def ts():
    return time.strftime("%H:%M:%S")


if __name__ == "__main__":
    print(f"[{ts()}] Amazon A+ poller started (interval={POLL_INTERVAL}s)")
    while True:
        try:
            poll_once()
        except Exception as e:
            print(f"[{ts()}] ERROR: {e}")
        time.sleep(POLL_INTERVAL)
