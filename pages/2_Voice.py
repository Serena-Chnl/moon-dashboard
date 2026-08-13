# pages/2_Voice.py — Voice（NLP 分析：2024 起带文字评论 + 被拦截 feedback）
# 只读已处理好的列（本地 process_all.py / aggregate 生成），不做任何 NLP。

import altair as alt
import pandas as pd
import streamlit as st
from pathlib import Path
import theme

BASE_DIR = Path(__file__).resolve().parent.parent
REVIEW_PATH = BASE_DIR / "Moon_review.csv"
FEEDBACK_PATH = BASE_DIR / "Moon_feedback_processed.csv"

BRONZE, INK, MUTED, DIVIDER = theme.BRONZE, theme.INK, theme.MUTED, theme.DIVIDER
GREEN, RED, NEU = "#5B8A72", "#B5654A", "#B7BCC0"
PILLARS = ["Food", "Service", "View", "Value", "Ambiance"]
SENT_ORDER = ["positive", "neutral", "negative"]
SENT_COLOR = alt.Scale(domain=SENT_ORDER, range=[GREEN, NEU, RED])

st.set_page_config(page_title="Moon Review Insights",
                   page_icon=theme.get_favicon(), layout="wide")

st.markdown(f"""<style>
.section {{ font-size:26px; font-weight:700; color:{INK}; margin:14px 0 6px 0; }}
.legend {{ text-align:center; font-size:13px; margin:6px 0; white-space:nowrap; }}
.legend span {{ margin:0 6px; }}
.tcard {{ background:#FFFFFF; border-radius:12px; padding:16px 16px 18px;
        box-shadow:0 2px 10px rgba(43,43,43,.06); height:100%; }}
.tcard-name {{ font-size:17px; font-weight:700; color:{INK}; }}
.tcard-n {{ font-size:12px; color:{MUTED}; margin-bottom:8px; }}
.tcard-q {{ font-size:12.5px; color:{INK}; margin-top:10px; font-style:italic;
        line-height:1.5; }}
div[role="radiogroup"] {{ justify-content:center !important; gap:10px; }}
</style>""", unsafe_allow_html=True)

NLP_COLS = ["Review_EN", "Sent_label", "Sent_score"] + [f"T_{p}" for p in PILLARS]

@st.cache_data
def load_processed():
    rev = pd.read_csv(REVIEW_PATH)
    if not all(c in rev.columns for c in NLP_COLS):
        return None, None
    rev["dt"] = pd.to_datetime(rev["Review Date & Time"], format="mixed", errors="coerce")
    rev = rev[(rev["dt"] >= "2024-01-01") & rev["Review_EN"].notna()].copy()
    rev["Source"] = "Public review"
    fb = None
    if FEEDBACK_PATH.exists():
        fb = pd.read_csv(FEEDBACK_PATH)
        if all(c in fb.columns for c in NLP_COLS):
            fb["dt"] = pd.to_datetime(fb.get("dt", fb.get("Date")), format="mixed", errors="coerce")
            fb = fb[fb["Review_EN"].notna()].copy()
            fb["Source"] = "Intercepted feedback"
        else:
            fb = None
    return rev, fb

rev, fb = load_processed()
if rev is None:
    st.warning("Reviews haven't been NLP-processed yet. Run `python process_all.py` "
               "locally once, then push the updated files.")
    st.stop()

# 来源选择（放在侧边栏，作用于整页）
opts = ["All", "Public reviews", "Internal feedback"]
src = st.sidebar.radio("Source", opts, index=0)
frames = []
if src in ("All", "Public reviews"):
    frames.append(rev)
if src in ("All", "Internal feedback") and fb is not None:
    frames.append(fb)
data = pd.concat(frames, ignore_index=True) if frames else rev.iloc[0:0]
# 全量(不受 sidebar 来源筛选影响)——供 Read Guest Voices 使用
all_frames = [rev] + ([fb] if fb is not None else [])
data_all = pd.concat(all_frames, ignore_index=True)
st.caption(f"{len(data):,} texts analysed · reviews with text since 2024 "
           f"+ intercepted feedback (translated to English)")

# ==========================================================================
# 情绪：甜甜圈 + 月度走势（pie 顶与 bar 顶对齐，图例放在 pie 下方）
# ==========================================================================
st.markdown('<div class="section">Sentiment</div>', unsafe_allow_html=True)
H = 300
DONUT = 220
c1, c2 = st.columns([1, 2])
with c1:
    sc = data["Sent_label"].value_counts().reindex(SENT_ORDER, fill_value=0)
    sdf = pd.DataFrame({"Sentiment": SENT_ORDER, "Count": [int(sc[s]) for s in SENT_ORDER]})
    sdf["Pct"] = (sdf["Count"] / max(len(data), 1) * 100).round(0).astype(int).astype(str) + "%"
    donut = alt.Chart(sdf).mark_arc(innerRadius=52).encode(
        theta="Count:Q",
        color=alt.Color("Sentiment:N", scale=SENT_COLOR, sort=SENT_ORDER, legend=None),
        tooltip=[alt.Tooltip("Sentiment:N"), alt.Tooltip("Count:Q"), alt.Tooltip("Pct:N")])
    st.altair_chart(donut.properties(width=DONUT, height=DONUT), use_container_width=False)
    # 图例放在甜甜圈正下方（与右侧柱状图的 x 轴刻度平行）
    st.markdown(
        f'<div class="legend" style="width:{DONUT}px;">'
        f'<span style="color:{GREEN};">● positive</span>'
        f'<span style="color:{NEU};">● neutral</span>'
        f'<span style="color:{RED};">● negative</span></div>', unsafe_allow_html=True)
with c2:
    d = data.dropna(subset=["dt"]).copy()
    d["Month"] = d["dt"].dt.to_period("M").astype(str)
    g = d.groupby(["Month", "Sent_label"]).size().reset_index(name="n")
    trend = alt.Chart(g).mark_bar().encode(
        x=alt.X("Month:N", axis=alt.Axis(labelAngle=-45, title=None)),
        y=alt.Y("n:Q", stack="normalize", axis=alt.Axis(title=None, format="%")),
        color=alt.Color("Sent_label:N", scale=SENT_COLOR, sort=SENT_ORDER, legend=None),
        order=alt.Order("Sent_label:N"),
        tooltip=[alt.Tooltip("Month:N"), alt.Tooltip("Sent_label:N", title="Sentiment"),
                 alt.Tooltip("n:Q", title="Count")])
    st.altair_chart(trend.properties(height=H), use_container_width=True)

# ==========================================================================
# Themes —— Quadrant: how often each theme is mentioned vs how guests feel
# ==========================================================================
st.markdown('<div class="section">Topics</div>', unsafe_allow_html=True)
st.markdown(
    f"<div style='color:{INK}; font-size:15px; line-height:1.6; margin-bottom:6px;'>"
    f"Each dot is a topic guests talk about. "
    f"<b>Right</b> = mentioned more often. <b>Higher</b> = guests are happier about it. "
    f"So a topic in the <b>bottom-right</b> is talked about a lot but not loved — "
    f"that's where to improve first.</div>", unsafe_allow_html=True)

trows = []
for p in PILLARS:
    sub = data[data[f"T_{p}"] == 1]
    n = len(sub)
    pos = (sub["Sent_label"] == "positive").mean() * 100 if n else 0
    neg = (sub["Sent_label"] == "negative").mean() * 100 if n else 0
    trows.append({"Topic": p, "Mentions": n, "Sentiment": round(pos - neg)})
tdf = pd.DataFrame(trows)
NET_SCALE = alt.Scale(domain=[0, 70], range=[RED, "#D4B96A", GREEN])
mx, my = tdf["Mentions"].mean(), tdf["Sentiment"].mean()

vline = alt.Chart(pd.DataFrame({"x": [mx]})).mark_rule(
    color=MUTED, strokeDash=[4, 4]).encode(x="x:Q")
hline = alt.Chart(pd.DataFrame({"y": [my]})).mark_rule(
    color=MUTED, strokeDash=[4, 4]).encode(y="y:Q")
dots = alt.Chart(tdf).mark_circle(size=600, opacity=0.9).encode(
    x=alt.X("Mentions:Q", title="How often it's mentioned",
            scale=alt.Scale(nice=True)),
    y=alt.Y("Sentiment:Q", title="How guests feel  (negative → positive)"),
    color=alt.Color("Sentiment:Q", scale=NET_SCALE, legend=None),
    tooltip=[alt.Tooltip("Topic:N"), alt.Tooltip("Mentions:Q", title="Mentions"),
             alt.Tooltip("Sentiment:Q", title="Net sentiment")])
names = alt.Chart(tdf).mark_text(dy=-20, fontSize=14, fontWeight="bold", color=INK).encode(
    x="Mentions:Q", y="Sentiment:Q", text="Topic:N")
st.altair_chart((vline + hline + dots + names).properties(height=380),
                use_container_width=True)

# ==========================================================================
# Read Guest Voices —— 只按 Topic 筛选；左侧彩色边框=整条评论情绪（不误导为主题级）
# ==========================================================================
st.markdown('<div class="section">Read Guest Voices</div>', unsafe_allow_html=True)
st.markdown(
    f"<div style='color:{MUTED}; font-size:13px; margin-bottom:8px;'>"
    f"Filter by sentiment or topic.</div>",
    unsafe_allow_html=True)

SENT_OPTS = {"🟢 Positive": "positive", "⚪ Neutral": "neutral", "🔴 Negative": "negative"}
options = ["Any"] + PILLARS + list(SENT_OPTS.keys())
fcol, _ = st.columns([1, 3])
with fcol:
    pick = st.selectbox("Filter", options, label_visibility="collapsed")

q = data_all.copy()
if pick in PILLARS:                       # 选了 topic
    q = q[q[f"T_{pick}"] == 1]
elif pick in SENT_OPTS:                    # 选了情绪
    q = q[q["Sent_label"] == SENT_OPTS[pick]]
q = q.sort_values("dt", ascending=False, na_position="last").reset_index(drop=True)

PER = 5
sig = f"{pick}"
if st.session_state.get("voice_sig") != sig:      # 筛选变了就回第一页
    st.session_state.voice_sig = sig
    st.session_state.voice_page = 0
total_pages = max((len(q) - 1) // PER + 1, 1)
page = min(st.session_state.get("voice_page", 0), total_pages - 1)

nav1, nav2, nav3 = st.columns([1, 2, 1])
with nav1:
    if st.button("← Prev", disabled=page <= 0, use_container_width=True):
        st.session_state.voice_page = page - 1
        st.rerun()
with nav2:
    st.markdown(f"<div style='text-align:center; color:{MUTED}; padding-top:6px;'>"
                f"{len(q):,} reviews · page {page + 1} / {total_pages}</div>",
                unsafe_allow_html=True)
with nav3:
    if st.button("Next →", disabled=page >= total_pages - 1, use_container_width=True):
        st.session_state.voice_page = page + 1
        st.rerun()

badge = {"positive": GREEN, "neutral": NEU, "negative": RED}
for _, r in q.iloc[page * PER:(page + 1) * PER].iterrows():
    color = badge.get(r["Sent_label"], MUTED)
    date = r["dt"].strftime("%b %Y") if pd.notna(r["dt"]) else ""
    lang = str(r.get("Language", "")).strip()
    lang_tag = ""
    if lang and lang.lower() not in ("nan", "unknown", "via-google"):
        lang_tag = f"{lang.upper()} · "
    st.markdown(
        f"<div style='border-left:3px solid {color}; padding:6px 14px; margin:8px 0;'>"
        f"<div style='font-size:12px; color:{MUTED};'>{r.get('Source','')} · {date} · "
        f"{lang_tag}<b style='color:{color};'>{r['Sent_label']}</b></div>"
        f"<div style='font-size:14px; color:{INK};'>{str(r['Review_EN'])}</div></div>",
        unsafe_allow_html=True)