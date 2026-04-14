"""
配置文件 — 填入你的 API Key、代理和关键词后再运行主程序
"""

import os
from pathlib import Path

# ── 搜索配置 ──────────────────────────────────────────────────
KEYWORDS = ["无核山楂", "山楂片", "山楂糕"]   # 要搜索的关键词列表
PLATFORMS = ["amazon", "1688", "temu", "shopee"]  # 启用的平台
RESULTS_PER_KEYWORD = 10  # 每个关键词在每个平台最多取多少条结果

# ── Obsidian 仓库路径 ─────────────────────────────────────────
VAULT_PATH = Path("D:/Download/agent-master")
DATA_OUTPUT_DIR = VAULT_PATH / "竞品分析" / "数据"

# ── Amazon PA-API 5.0 凭证 ───────────────────────────────────
# 申请地址：https://affiliate-program.amazon.com/
AMAZON_API = {
    "access_key": os.getenv("AMAZON_ACCESS_KEY", ""),       # 填入你的 Access Key
    "secret_key": os.getenv("AMAZON_SECRET_KEY", ""),       # 填入你的 Secret Key
    "partner_tag": os.getenv("AMAZON_PARTNER_TAG", ""),     # 填入你的 Partner Tag（Associates ID）
    "region": "US",   # 支持: US, JP, UK, DE, FR, CA, IN, AU 等
}

# ── 代理配置 ─────────────────────────────────────────────────
# 格式: "http://用户名:密码@代理IP:端口"
# 若不需要代理，设为空字符串 ""
PROXY = {
    "1688":   os.getenv("PROXY_CN", ""),    # 需要中国大陆 IP
    "temu":   os.getenv("PROXY_US", ""),    # 需要海外 IP
    "shopee": os.getenv("PROXY_SG", ""),    # 建议新加坡 IP
}

# ── 飞书多维表格配置 ─────────────────────────────────────────
# 获取方式：
#   1. open.feishu.cn 创建自建应用 → 获取 App ID 和 App Secret
#   2. 授权 bitable:app + bitable:record:write 权限
#   3. 飞书云文档新建多维表格 → URL 中提取 app_token 和 table_id
#      URL 格式：https://xxx.feishu.cn/base/<app_token>?table=<table_id>
FEISHU = {
    "app_id":     os.getenv("FEISHU_APP_ID", ""),       # 飞书自建应用 App ID
    "app_secret": os.getenv("FEISHU_APP_SECRET", ""),   # 飞书自建应用 App Secret
    "app_token":  os.getenv("FEISHU_APP_TOKEN", ""),    # 多维表格 Token（URL 中 /base/ 后面部分）
    "table_id":   os.getenv("FEISHU_TABLE_ID", ""),     # 数据表 ID（URL 中 ?table= 后面部分）
}

# ── Cookie 文件路径 ──────────────────────────────────────────
COOKIES_DIR = Path(__file__).parent / "cookies"
COOKIES_1688 = COOKIES_DIR / "1688_cookies.json"

# ── Playwright 浏览器配置 ────────────────────────────────────
BROWSER_HEADLESS = True     # False = 显示浏览器窗口（调试时用）
PAGE_TIMEOUT = 30_000       # 页面加载超时（毫秒）
SCROLL_PAUSE = 2.0          # 滚动后等待时间（秒）

# ── 反爬延迟配置 ────────────────────────────────────────────
DELAY_MIN = 1.5   # 请求间最小随机延迟（秒）
DELAY_MAX = 4.0   # 请求间最大随机延迟（秒）
MAX_RETRIES = 3   # 失败重试次数
