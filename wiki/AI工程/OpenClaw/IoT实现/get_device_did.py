"""
临时脚本：通过扫码登录米家，列出所有设备的 DID
会生成二维码图片，用图片查看器打开后扫码登录
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8')

from mijiaAPI import mijiaAPI
import qrcode
import json

# 猴子补丁：把 print_ascii 替换为保存图片
_original_qr_login = None

class PatchedAPI(mijiaAPI):
    def _print_qr(self, url):
        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        out = r'D:\Download\agent-master\OpenClaw+IoT\mijia_qr.png'
        img.save(out)
        print(f"二维码已保存到：{out}")
        print("请用文件资源管理器打开该图片，然后用手机米家App扫码...")
        os.startfile(out)  # 自动用默认图片查看器打开

api = PatchedAPI()
print("正在生成登录二维码...")
api.login()

print("\n登录成功！获取设备列表中...\n")
devices = api.get_devices_list()

print(f"{'设备名称':<30} {'型号':<25} {'DID':<20} {'本地IP'}")
print("-" * 90)
for d in devices:
    name  = str(d.get('name', ''))[:28]
    model = str(d.get('model', ''))[:23]
    did   = str(d.get('did', ''))
    ip    = str(d.get('localip', ''))
    print(f"{name:<30} {model:<25} {did:<20} {ip}")

print("\n--- 摄像头设备 ---")
found = False
for d in devices:
    model = str(d.get('model', ''))
    name  = str(d.get('name', ''))
    if any(k in model.lower() for k in ['camera', 'chuangmi', 'isa.camera', 'xiaomi.camera', 'mjsxj']):
        found = True
        print(f"名称 : {name}")
        print(f"型号 : {model}")
        print(f"DID  : {d.get('did')}")
        print(f"IP   : {d.get('localip', '未知')}")
        print()
if not found:
    print("（未找到摄像头，请查看上方完整列表）")
