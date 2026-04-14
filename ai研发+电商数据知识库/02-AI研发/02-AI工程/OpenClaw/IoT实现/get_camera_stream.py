"""
用 mijiaAPI 获取 C700 摄像头流地址
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
from mijiaAPI import mijiaAPI
import inspect

api = mijiaAPI()

# 查看 run_action 和 get_devices_prop 的参数
print("=== run_action 签名 ===")
print(inspect.signature(api.run_action))

print("\n=== get_devices_prop 签名 ===")
print(inspect.signature(api.get_devices_prop))

DID = '1190512086'

# 尝试获取摄像头属性（SIID=1 是基本信息）
print("\n=== 获取设备属性 ===")
try:
    # 格式可能是: [{did, siid, piid}]
    props = api.get_devices_prop([
        {"did": DID, "siid": 1, "piid": 1},  # 设备名
        {"did": DID, "siid": 1, "piid": 2},  # 固件版本
        {"did": DID, "siid": 3, "piid": 1},  # 摄像头相关
    ])
    print(json.dumps(props, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"失败: {e}")

# 尝试 run_action — 获取 RTSP 地址
print("\n=== 尝试获取流 action ===")
for action_name in ['get_rtsp_url', 'start_stream', 'get_stream']:
    try:
        r = api.run_action(DID, action_name)
        print(f"{action_name}:", json.dumps(r, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"{action_name} 失败: {e}")

# 查看 auth_data 里有没有可用于 go2rtc 的 token
print("\n=== Auth Token 摘要（供 go2rtc 使用）===")
d = api.auth_data
print(f"userId: {d.get('userId')}")
print(f"serviceToken (前20位): {str(d.get('serviceToken',''))[:20]}...")
print(f"ssecurity: {d.get('ssecurity')}")
print(f"cUserId: {d.get('cUserId')}")
