# theme.py — 全站共用的品牌颜色盘 & 标签页图标（方案 B：Slate & Bronze）
# 所有页面从这里取色，保证风格统一、一处修改全站生效。

from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent

# --- 基底 ---
BRONZE = "#A9754C"        # 主色 / 品牌强调（KPI 数字、强调、logo 呼应）
INK = "#2B3138"           # 深色卡背景 / 近黑蓝灰
DARK_TEXT = "#E8E6E1"     # 深色卡上的浅色文字
WHITE = "#FFFFFF"
PAGE_BG = "#F4F5F6"
MUTED = "#8A8F94"         # 次要文字
DIVIDER = "#EAE4DC"
NEGATIVE = "#B5654A"      # 负面（低饱和砖红，不刺眼）

# --- 平台色（区分 Google / Tripadvisor）：暖 vs 冷，都与主色错开 ---
GOOGLE = "#C2703D"        # 赤陶
TRIPADVISOR = "#5B8A72"   # 墨绿
PLATFORM_COLOR = {"Google": GOOGLE, "Tripadvisor": TRIPADVISOR}

# --- 年份色（类别，用不同色相而非深浅，避免"多/少"误导）---
YEAR_COLOR = {"2024": "#7E8B94", "2025": "#C29A5B", "2026": "#3F6B7D"}
_YEAR_FALLBACK = ["#7E8B94", "#C29A5B", "#3F6B7D", "#9C6B6B", "#6B8E9C", "#7A6B8E"]

# --- 星级色阶（方案 A：红→黄→绿情绪色阶，第一直觉看懂好坏，低饱和高级版）---
STAR_SCALE = {
    5: "#5B8A72",   # 墨绿（最好，呼应 TA 平台色系）
    4: "#8DA97C",   # 浅绿
    3: "#D4B96A",   # 暖黄（中性）
    2: "#CE8F5E",   # 橙
    1: "#B5654A",   # 砖红（最差 = 颜色盘的负面色）
}

def year_colors(years):
    """给一组年份返回对应颜色（已知年份用固定色，未知年份按备用色轮换）。"""
    out = []
    for i, y in enumerate(years):
        out.append(YEAR_COLOR.get(str(y), _YEAR_FALLBACK[i % len(_YEAR_FALLBACK)]))
    return out

def get_favicon():
    """浏览器标签页图标：用 Moon logo，缺失时回退到月亮 emoji。"""
    try:
        return Image.open(BASE_DIR / "Moon_logo.png")
    except FileNotFoundError:
        return "🌙"