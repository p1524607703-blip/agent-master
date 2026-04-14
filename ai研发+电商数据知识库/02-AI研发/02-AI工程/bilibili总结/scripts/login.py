#!/usr/bin/env python3
"""
Bilibili 扫码登录

职责：生成二维码 → 轮询直到确认 → 保存 Cookie → 退出

用法：
  python login.py

输出（stdout，供 Claude 解析）：
  QR_CODE_PATH:<图片绝对路径>   ← 读此路径展示二维码
  POLLING:<n>/<total>           ← 轮询进度
  LOGIN_SUCCESS:<用户名>        ← 登录完成
  LOGIN_FAILED:<原因>           ← 失败
"""
import asyncio, os, sys
from pathlib import Path

VAULT_ROOT  = Path(r"D:\Download\agent-master")
ENV_FILE    = VAULT_ROOT / ".env"
QR_PATH     = VAULT_ROOT / "bilibili_login_qr.png"
COOKIE_KEYS = ["SESSDATA", "bili_jct", "buvid3", "buvid4", "DedeUserID"]
MAX_POLLS   = 90   # 最多等 3 分钟（每 2 秒一次）


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def save_env_key(key, value):
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main():
    load_env()
    from bilibili_api import login_v2

    # 生成二维码
    login_obj = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
    await login_obj.generate_qrcode()
    login_obj.get_qrcode_picture().to_file(str(QR_PATH))

    # 立即输出路径，Claude 用 Read 工具读取并展示给用户
    print(f"QR_CODE_PATH:{QR_PATH}", flush=True)

    # 轮询直到确认
    for i in range(1, MAX_POLLS + 1):
        await asyncio.sleep(2)
        event = await login_obj.check_state()
        print(f"POLLING:{i}/{MAX_POLLS} state={event.name}", flush=True)

        if event == login_v2.QrCodeLoginEvents.DONE:
            cred = login_obj.get_credential()
            for k in COOKIE_KEYS:
                val = getattr(cred, k.lower(), None) or getattr(cred, k, None)
                if val:
                    save_env_key(f"BILIBILI_{k}", str(val))
            # 获取用户名
            try:
                from bilibili_api import user
                me = await user.get_self_info(credential=cred)
                uname = me.get("name", "未知")
            except Exception:
                uname = "未知"
            print(f"LOGIN_SUCCESS:{uname}", flush=True)
            return

        elif event == login_v2.QrCodeLoginEvents.TIMEOUT:
            print("LOGIN_FAILED:二维码已过期", flush=True)
            return

        elif event == login_v2.QrCodeLoginEvents.SCAN:
            print("SCANNED:已扫码，等待手机确认...", flush=True)

    print("LOGIN_FAILED:等待超时（3分钟）", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
