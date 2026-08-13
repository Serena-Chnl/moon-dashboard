# Home.py — Moon Review Insights 首页
# 只读 Moon_rating.csv（有史以来累计数据）。图表用 Streamlit 自带的 Altair。

import altair as alt
import calendar
import re
import pandas as pd
import streamlit as st
from pathlib import Path
from PIL import Image
import theme

# --- 路径 ---
BASE_DIR = Path(__file__).resolve().parent
HERO_PATH = BASE_DIR / "Moon_hero_img.png"
RATING_PATH = BASE_DIR / "Moon_rating.csv"
GATING_PATH = BASE_DIR / "Moon_gating.csv"   # 手动维护：拦截的 gated feedback 数量
REVIEW_PATH = BASE_DIR / "Moon_review.csv"   # 明细：算 Funnel 期间(2025-08起)的分
GOOGLE_LOGO = BASE_DIR / "Google_logo.png"
TA_LOGO = BASE_DIR / "Tripadvisor_logo.png"

# --- 颜色（取自共用 theme）---
BRONZE = theme.BRONZE
INK = theme.INK
MUTED = theme.MUTED
TRACK = "#EFE7DD"
SLATE = "#6E8CA0"                                      # TA 用的灰蓝
GREEN, RED = "#5B8A72", theme.NEGATIVE
# Home 分布图配色：Google 青铜 / TA 灰蓝（中性、不引起积极消极误解）
CHART_COLOR = {"Google": BRONZE, "Tripadvisor": SLATE}

st.set_page_config(page_title="Moon Review Insights",
                   page_icon=theme.get_favicon(), layout="wide")

# --- 侧边栏（Home 不需要筛选，保持干净）---

# --- 样式：KPI 卡片 + 平台单选（小圆圈，均匀铺开）---
st.markdown(f"""<style>
.card {{ background:#FFFFFF; border-radius:14px; padding:22px 18px;
        text-align:center; box-shadow:0 2px 12px rgba(43,43,43,.06); }}
.card-logo {{ height:34px; margin-bottom:10px; vertical-align:middle; }}
.card-platform {{ font-size:22px; font-weight:600; letter-spacing:1px;
        color:#5A5A5A; margin-bottom:8px; }}
.card-rating {{ font-size:68px; font-weight:700; color:{INK}; line-height:1; }}
.card-note {{ font-size:18px; color:{MUTED}; margin-top:12px; }}
.card-date {{ font-size:13px; color:{MUTED}; margin-top:4px; font-style:italic; }}
.rp-title {{ font-size:24px; font-weight:700; color:{INK}; margin:6px 0; }}
.fn-desc {{ font-size:16px; color:{INK}; line-height:1.7; margin-bottom:6px;
        background:#FFFFFF; border-radius:12px; padding:20px 22px;
        box-shadow:0 2px 12px rgba(43,43,43,.06); }}
.ba-plat {{ font-size:16px; font-weight:700; text-align:center; margin-bottom:2px; }}
div[role="radiogroup"] {{ justify-content:space-around !important; width:100% !important; }}
div[role="radiogroup"] label {{ font-size:16px !important; }}
</style>""", unsafe_allow_html=True)

# --- 顶部 hero 大图 ---
try:
    st.image(Image.open(HERO_PATH), use_container_width=True)
except FileNotFoundError:
    st.warning(f"未找到 hero 图片：{HERO_PATH}")

# --- 读数据：按平台把 1~5 星加总（排除 All Time 汇总行，避免重复计数）---
df = pd.read_csv(RATING_PATH)
atomic = df[df["Month"] != "All Time"]
star_cols = ["Star_1", "Star_2", "Star_3", "Star_4", "Star_5"]
totals = atomic.groupby("Platform")[star_cols].sum()
STAR_ORDER = ["1★", "2★", "3★", "4★", "5★"]

def latest_month_label(month_series):
    """从 Month 列取最新月份，返回如 'June 2026'。"""
    ym = []
    for m in month_series:
        m = str(m)
        if m == "All Time":
            continue
        hit = re.search(r"_to_(\d{4})-(\d{2})", m) or re.match(r"(\d{4})-(\d{2})$", m)
        if hit:
            ym.append((int(hit.group(1)), int(hit.group(2))))
    if not ym:
        return ""
    y, mo = max(ym)
    return f"{calendar.month_name[mo]} {y}"

CUTOFF = latest_month_label(df["Month"])

def earliest_month_label(month_series):
    """最早月份，返回如 'Sep 2019'（从 baseline 起始 YYYY-MM 取）。"""
    ym = []
    for m in month_series:
        m = str(m)
        if m == "All Time":
            continue
        hit = re.match(r"(\d{4})-(\d{2})", m)   # baseline 以 '2019-09_to...' 开头
        if hit:
            ym.append((int(hit.group(1)), int(hit.group(2))))
    if not ym:
        return ""
    y, mo = min(ym)
    return f"{calendar.month_abbr[mo]} {y}"

def _short(label):
    """'June 2026' → 'Jun 2026'（月份缩写）。"""
    parts = label.split()
    if len(parts) == 2 and parts[0] in calendar.month_name[1:]:
        return f"{parts[0][:3]} {parts[1]}"
    return label

EARLIEST = earliest_month_label(df["Month"])            # 如 Sep 2019
CUTOFF_SHORT = _short(CUTOFF)                            # 如 Jul 2026
CARD_RANGE = f"{EARLIEST} – {CUTOFF_SHORT}"             # 卡片区间

import base64
def _logo_tag(path, height=34):
    """把 logo 转 base64 内嵌进 HTML；找不到返回空串（由调用方回退文字）。"""
    try:
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="height:{height}px; margin:0; display:block; vertical-align:middle;">'
    except Exception:
        return ""

# --- Smart Review Funnel：Funnel 启动(2025-08)后的公开分 vs 真实分 ---
def load_gating():
    """读取手动维护的 gated feedback 数量与启动月（Moon_gating.csv）。"""
    try:
        g = pd.read_csv(GATING_PATH)
        cnt = int(g["gated_feedback"].iloc[0])
        col = "funnel_start" if "funnel_start" in g.columns else "gating_start"
        start = str(g[col].iloc[0]) if col in g.columns else "2025-08"
        return cnt, start
    except Exception:
        return 0, "2025-08"

def _avg(counts):
    n = sum(counts.values())
    return (sum(s * counts[s] for s in range(1, 6)) / n if n else 0), n

def funnel_stats():
    """返回 Funnel 前基准 / Funnel 期间公开分（分平台）+ 期间真实分（合计）。"""
    start, gated = None, None
    gated, start_str = load_gating()
    start = pd.Period(start_str, freq="M")

    # 读明细，取 Funnel 期间(>= start)的各平台各星级计数（全部，不做完整月过滤，
    # 以保证 baseline + funnel == All Time 精确成立）
    d = pd.read_csv(REVIEW_PATH)
    d["Star"] = d["Rating"].map({"1-Star": 1, "2-Star": 2, "3-Star": 3, "4-Star": 4, "5-Star": 5})
    d["dt"] = pd.to_datetime(d["Review Date & Time"], format="%b %d, %Y %H:%M", errors="coerce")
    d = d.dropna(subset=["dt", "Star"]).copy()
    d["Star"] = d["Star"].astype(int)
    d["Period"] = d["dt"].dt.to_period("M")
    d["Plat"] = d["Platform"].apply(lambda x: "Google" if "oogle" in str(x) else "Tripadvisor")
    after = d[d["Period"] >= start]

    res = {"gated": gated, "start": start}
    combined = {s: 0 for s in range(1, 6)}
    for p in ["Google", "Tripadvisor"]:
        fc = {s: int(((after["Plat"] == p) & (after["Star"] == s)).sum()) for s in range(1, 6)}
        at = totals.loc[p]                                   # All Time 该平台各星级
        before = {s: int(at[f"Star_{s}"]) - fc[s] for s in range(1, 6)}
        res[p] = {"before": _avg(before), "after": _avg(fc)}
        for s in range(1, 6):
            combined[s] += fc[s]
    # 期间合计公开分 → 并入 gated（按 1 星）→ 真实分
    pub, n = _avg(combined)
    real = (sum(s * combined[s] for s in range(1, 6)) + gated * 1) / (n + gated) if (n + gated) else 0
    res["combined"] = {"public": pub, "n": n, "real": real, "gap": pub - real}
    return res

def gap_chart(public, real):
    """一根横向刻度条，标出公开分(青铜) 与 真实分(灰) 两个点，中间即 Funnel 抬升。"""
    lo, hi = min(public, real) - 0.2, max(public, real) + 0.2
    seg = pd.DataFrame({"x": [real], "x2": [public], "y": ["r"]})
    gline = alt.Chart(seg).mark_rule(color=BRONZE, strokeWidth=4, opacity=0.4).encode(
        x=alt.X("x:Q", scale=alt.Scale(domain=[lo, hi]),
                axis=alt.Axis(title=None, format=".2f")),
        x2="x2:Q", y=alt.Y("y:N", axis=None))
    pts = pd.DataFrame({"x": [real, public], "label": ["Real", "Public"], "y": ["r", "r"]})
    cscale = alt.Scale(domain=["Real", "Public"], range=[MUTED, BRONZE])
    dots = alt.Chart(pts).mark_circle(size=380, opacity=1).encode(
        x="x:Q", y=alt.Y("y:N", axis=None),
        color=alt.Color("label:N", scale=cscale, legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("x:Q", title="Rating", format=".2f")])
    labels = alt.Chart(pts).mark_text(dy=-24, fontSize=15, fontWeight="bold").encode(
        x="x:Q", y=alt.Y("y:N", axis=None), text=alt.Text("x:Q", format=".2f"),
        color=alt.Color("label:N", scale=cscale, legend=None))
    return (gline + dots + labels).properties(height=130)

def get_stats(platform):
    c = totals.loc[platform]
    total = int(c.sum())
    avg = sum((i + 1) * c[f"Star_{i + 1}"] for i in range(5)) / total
    return round(avg, 1), avg, total

def render_card(platform):
    public_score, exact, total = get_stats(platform)
    logo_path = GOOGLE_LOGO if platform == "Google" else TA_LOGO
    logo = _logo_tag(logo_path, height=30)
    header = (f'<div style="display:flex; align-items:center; justify-content:center; '
              f'gap:10px; margin-bottom:8px; line-height:1;">{logo}'
              f'<span class="card-platform" style="margin:0; line-height:1;">{platform}</span></div>')
    st.markdown(f"""
    <div class="card">
        {header}
        <div class="card-rating">{public_score:.1f}</div>
        <div class="card-note">{exact:.2f} / 5 &nbsp;·&nbsp; {total:,} reviews</div>
        <div class="card-date">{CARD_RANGE}</div>
    </div>""", unsafe_allow_html=True)

def single_chart(platform):
    c = totals.loc[platform]
    data = pd.DataFrame({"Star": STAR_ORDER,
                         "Reviews": [int(c[f"Star_{i}"]) for i in range(1, 6)]})
    base = alt.Chart(data).encode(
        x=alt.X("Star:N", sort=STAR_ORDER, axis=alt.Axis(labelAngle=0, title=None, labelFontSize=15)),
        y=alt.Y("Reviews:Q", axis=alt.Axis(title=None)),
        tooltip=[alt.Tooltip("Star:N"), alt.Tooltip("Reviews:Q")],
    )
    bars = base.mark_bar(color=CHART_COLOR[platform], cornerRadiusEnd=3, size=100)
    labels = base.mark_text(dy=-8, color=INK, fontSize=14).encode(text="Reviews:Q")
    return (bars + labels).properties(height=340, title=platform)

def grouped_chart():
    rows = []
    for p in ["Tripadvisor", "Google"]:
        c = totals.loc[p]
        for i in range(1, 6):
            rows.append({"Star": f"{i}★", "Platform": p, "Reviews": int(c[f"Star_{i}"])})
    long = pd.DataFrame(rows)
    plat_order = ["Tripadvisor", "Google"]
    color_scale = alt.Scale(domain=plat_order,
                            range=[CHART_COLOR["Tripadvisor"], CHART_COLOR["Google"]])
    base = alt.Chart(long).encode(
        x=alt.X("Star:N", sort=STAR_ORDER, axis=alt.Axis(labelAngle=0, title=None, labelFontSize=15)),
        xOffset=alt.XOffset("Platform:N", sort=plat_order),
        y=alt.Y("Reviews:Q", axis=alt.Axis(title=None)),
        tooltip=[alt.Tooltip("Platform:N"), alt.Tooltip("Star:N"), alt.Tooltip("Reviews:Q")],
    )
    bars = base.mark_bar(cornerRadiusEnd=3).encode(
        color=alt.Color("Platform:N", scale=color_scale, sort=plat_order,
                        legend=alt.Legend(title=None, orient="top", labelFontSize=14, symbolSize=220)),
    )
    labels = base.mark_text(dy=-6, color=INK, fontSize=12).encode(text="Reviews:Q")
    return (bars + labels).properties(height=360)

# --- KPI 卡片（logo + 大标题 + 区间日期）---
st.markdown("<br>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    render_card("Google")
with c2:
    render_card("Tripadvisor")

# ==========================================================================
# Smart Review Funnel：描述 + 两个哑铃图（紧贴 KPI 下方、分别对齐两卡）
# ==========================================================================
fn = funnel_stats()
start_p = fn["start"]
after_start = start_p.strftime("%b %Y")                 # Aug 2025
gated = fn["gated"]

# 描述（纯文字、无框、无 emoji；Happy 绿、unhappy 红）
desc = (f'We launched our <b>Smart Review Funnel</b> in <b>{after_start}</b>. '
        f'Happy guests are guided to Google &amp; TripAdvisor; '
        f'unhappy guests are guided to leave private feedback '
        f'only visible to us. As of <b>{CUTOFF_SHORT}</b>, we\'ve intercepted '
        f'<b>{gated} negative feedback</b> before they reached public platforms — '
        f'lifting the average rating on both platforms.')
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(f'<div style="font-size:16px; color:{INK}; line-height:1.7;">{desc}</div>',
            unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

def build_dumbbell(p):
    """时间轴(3 均分刻度: Sep2019 / Aug2025 / 最新月)，三个点，
    左段中点标 funnel 前均分、右段中点标 funnel 后均分（均分保留 1 位小数）。"""
    before_a = fn[p]["before"][0]
    after_a = fn[p]["after"][0]
    DARK = "#4A4A4A"
    lbl_expr = (f"datum.value == 0 ? '{EARLIEST}' : "
                f"datum.value == 1 ? '{after_start}' : '{CUTOFF_SHORT}'")
    xax = alt.X("x:Q", scale=alt.Scale(domain=[-0.15, 2.15]),
                axis=alt.Axis(values=[0, 1, 2], labelExpr=lbl_expr, title=None,
                              grid=True, gridColor="#E6E6E6", ticks=False,
                              domain=False, labelFontSize=12, labelColor=MUTED))
    yfix = alt.Y("y:N", axis=None)
    # 整条连线：统一深灰
    seg = pd.DataFrame({"x": [0.0], "x2": [2.0], "y": ["r"]})
    lines = alt.Chart(seg).mark_rule(color=DARK, strokeWidth=4).encode(
        x=xax, x2="x2:Q", y=yfix)
    # 三个点：Sep2019 / Aug2025 / 最新月，统一深灰
    dots = pd.DataFrame({"x": [0.0, 1.0, 2.0], "y": ["r", "r", "r"]})
    dchart = alt.Chart(dots).mark_circle(size=180, opacity=1, color=DARK).encode(
        x="x:Q", y=yfix)
    # 区间均分（1 位小数）：左段中点 x=0.5，右段中点 x=1.5
    avg = pd.DataFrame({"x": [0.5, 1.5], "y": ["r", "r"],
                        "t": [f"{before_a:.1f}", f"{after_a:.1f}"]})
    alab = alt.Chart(avg).mark_text(dy=-16, fontSize=17, fontWeight="bold", color=INK).encode(
        x="x:Q", y=yfix, text="t:N")
    return (lines + dchart + alab).properties(height=110)

d1, d2 = st.columns(2)
for col, p in [(d1, "Google"), (d2, "Tripadvisor")]:
    lift = fn[p]["after"][0] - fn[p]["before"][0]
    with col:
        # 顶部中间：平台名 + 绿色增长（两个均分数字之间）
        st.markdown(f'<div class="ba-plat" style="color:{INK};">{p} '
                    f'<span style="color:{GREEN};">▲ +{lift:.1f}</span></div>',
                    unsafe_allow_html=True)
        st.altair_chart(build_dumbbell(p), use_container_width=True)

# --- 星级分布图（放在 Funnel 下方）：两个平台并排，Google 青铜 / TA 灰蓝 ---
st.markdown("<br>", unsafe_allow_html=True)
st.altair_chart(grouped_chart(), use_container_width=True)
