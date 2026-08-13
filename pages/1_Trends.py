# pages/1_Trends.py — 第二页：Trends（Overview + Star 分布，2024 年起）
# 侧边栏平台筛选作用于整页；Overview 内的日期筛选只作用于两张 KPI 卡。

import calendar
import altair as alt
import pandas as pd
import streamlit as st
import theme
from data_utils import load_reviews

BRONZE, INK, DARK_TEXT = theme.BRONZE, theme.INK, theme.DARK_TEXT
MUTED, DIVIDER = theme.MUTED, theme.DIVIDER

st.set_page_config(page_title="Moon Review Insights",
                   page_icon=theme.get_favicon(), layout="wide")

# --- 样式：深色 KPI 卡 + 小节标题 + 居中单选 ---
st.markdown(f"""<style>
.dcard {{ background:{INK}; border-radius:14px; padding:26px 20px; text-align:center;
        box-shadow:0 3px 14px rgba(43,49,56,.15); }}
.dcard-label {{ font-size:15px; letter-spacing:2px; text-transform:uppercase;
        color:{MUTED}; margin-bottom:10px; }}
.dcard-value {{ font-size:56px; font-weight:700; color:{DARK_TEXT}; line-height:1; }}
.dcard-value span {{ font-size:22px; color:{DARK_TEXT}; font-weight:400; }}
.dcard-sub {{ font-size:13px; color:{MUTED}; margin-top:10px; }}
.section {{ font-size:28px; font-weight:700; color:{INK}; margin:10px 0 6px 0; }}
.subtitle {{ font-size:18px; font-weight:600; color:{INK}; margin:6px 0 2px 0; }}
div[role="radiogroup"] {{ justify-content:center !important; gap:10px; }}
</style>""", unsafe_allow_html=True)

# ==========================================================================
# 侧边栏：只有一个平台下拉（作用于整页）
# ==========================================================================
platform = st.sidebar.radio("Platform", ["Both", "Google", "Tripadvisor"], index=0)

df = load_reviews()
pdf = df if platform == "Both" else df[df["Platform"] == platform]   # 整页平台过滤
min_d, max_d = df["dt"].min().date(), df["dt"].max().date()
# 真实数据覆盖边界：最后一个完整月的月末（如 2025-07-31）。所有 KPI 计算都不会超过它。
data_max = df["Period"].max().end_time.date()

# ==========================================================================
# 顶部：日期筛选 + 两张 KPI 卡（无标题，直接置顶）
# ==========================================================================
# --- 日期筛选（只作用于两张 KPI 卡）---
# 单个范围选择器（自带 Past Week / Month 等预设）。
# min_value 对齐到最早评论所在月的 1 号（如 2024-01-01），这样能从月初选起；
# max_value 用今天：让 today-锚定的预设不越界报错。残月数据已在 data_utils 层剔除，
# 即使选到当月，KPI 也只会算到最后一个完整月，不会出错、不会算进残缺数据。
import datetime as _dt
today = _dt.date.today()
cal_min = min_d.replace(day=1)          # 最早评论所在月的 1 号（动态，不 hardcode）

if "ov_range" not in st.session_state:
    st.session_state.ov_range = (cal_min, data_max)

st.markdown(f'<div style="color:{MUTED}; font-weight:600; font-size:15px; '
            f'margin-bottom:2px;">Select a period</div>', unsafe_allow_html=True)
fcol, _ = st.columns([3, 5])
with fcol:
    rng = st.date_input("period", key="ov_range", label_visibility="collapsed",
                        min_value=cal_min, max_value=today, format="DD/MM/YYYY")
    # 明确告诉用户数据实际覆盖到哪天（超出部分不会被统计）
    st.caption(f"Data available: {cal_min:%d/%m/%Y} – {data_max:%d/%m/%Y}")

# 取出起止日期（选择过程中可能只返回一个，做个兜底）
if isinstance(rng, (list, tuple)) and len(rng) == 2:
    start_d, end_d = rng
else:
    start_d, end_d = cal_min, data_max

# 核心兜底：把用户所选区间"钳制"到真实数据覆盖范围内（cal_min ~ data_max），
# 这样即使用户选到数据尚未覆盖的未来日期，KPI 也只会统计到有完整数据的最后一天。
eff_start = max(start_d, cal_min)
eff_end = min(end_d, data_max)
valid = eff_start <= eff_end
kpi_df = (pdf[(pdf["dt"].dt.date >= eff_start) & (pdf["dt"].dt.date <= eff_end)]
          if valid else pdf.iloc[0:0])
total_reviews = len(kpi_df)
avg_rating = kpi_df["Stars"].mean() if total_reviews else 0
# 副标题：平台（Both 时展开成两个平台名）+ 实际统计到的日期（已钳制）
plat_label = "Google & Tripadvisor" if platform == "Both" else platform
period_txt = (f"{eff_start.strftime('%d/%m/%Y')} – {eff_end.strftime('%d/%m/%Y')}"
              if valid else "no complete data in range")

k1, k2 = st.columns(2)
with k1:
    st.markdown(f"""<div class="dcard">
        <div class="dcard-label">Total Reviews</div>
        <div class="dcard-value">{total_reviews:,}</div>
        <div class="dcard-sub">{plat_label} · {period_txt}</div></div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="dcard">
        <div class="dcard-label">Average Rating</div>
        <div class="dcard-value">{avg_rating:.2f}<span> / 5</span></div>
        <div class="dcard-sub">{plat_label} · {period_txt}</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Volume Insights：Review Volume by Month（YoY 分组柱，年份不同色相）---
st.markdown('<div class="section">Review Volume</div>', unsafe_allow_html=True)

years = sorted(pdf["Year"].unique())
picked = st.multiselect("Years", years, default=years, label_visibility="collapsed")

if picked:
    counts = (pdf[pdf["Year"].isin(picked)]
              .groupby(["Year", "MonthNum"]).size().reset_index(name="Reviews"))
    counts["Month"] = counts["MonthNum"].map(lambda m: calendar.month_abbr[m])
    counts["Year"] = counts["Year"].astype(str)
    month_order = [calendar.month_abbr[m] for m in range(1, 13)]
    year_order = [str(y) for y in picked]
    year_range = theme.year_colors(picked)      # 年份 = 不同色相

    base = alt.Chart(counts).encode(
        x=alt.X("Month:N", sort=month_order, axis=alt.Axis(labelAngle=0, title=None)),
        xOffset=alt.XOffset("Year:N", sort=year_order),
        y=alt.Y("Reviews:Q", axis=alt.Axis(title=None)),
        tooltip=[alt.Tooltip("Year:N"), alt.Tooltip("Month:N"), alt.Tooltip("Reviews:Q")],
    )
    bars = base.mark_bar(cornerRadiusEnd=2).encode(
        color=alt.Color("Year:N", sort=year_order,
                        scale=alt.Scale(domain=year_order, range=year_range),
                        legend=alt.Legend(title=None, orient="top")))
    st.altair_chart(bars.properties(height=360), use_container_width=True)
else:
    st.info("Select at least one year.")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================================================
# 第二区块：STAR DISTRIBUTION —— 分「Volume」和「Trend」两部分
# ==========================================================================
st.markdown('<div class="section">Star Rating</div>', unsafe_allow_html=True)

STAR_SCALE = theme.STAR_SCALE
STAR_DESC = [5, 4, 3, 2, 1]                              # 堆叠从左到右 / 图例顺序
STAR_LBL = [f"{s}★" for s in STAR_DESC]
star_color_scale = alt.Scale(domain=STAR_LBL, range=[STAR_SCALE[s] for s in STAR_DESC])

# 完整月份列表（供月份下拉用；来自已判定完整月的数据，断月不会出现）
all_periods = sorted(pdf["Period"].unique())

# --------------------------------------------------------------------------
# 第一部分：Volume —— 水平堆叠条（按日期区间筛选，跟随侧边栏平台）
# --------------------------------------------------------------------------
if not all_periods:
    st.info("No data for this platform.")
else:
    # 具体到天的起止日期（区间会自动钳制到真实数据覆盖范围内）
    if "vol_range" not in st.session_state:
        st.session_state.vol_range = (cal_min, data_max)
    st.markdown(f'<div style="color:{MUTED}; font-weight:600; font-size:15px; '
                f'margin-bottom:2px;">Select a period</div>', unsafe_allow_html=True)
    vc, _ = st.columns([3, 5])
    with vc:
        vrng = st.date_input("vol_period", key="vol_range", label_visibility="collapsed",
                             min_value=cal_min, max_value=today, format="DD/MM/YYYY")
        st.caption(f"Data available: {cal_min:%d/%m/%Y} – {data_max:%d/%m/%Y}")
    if isinstance(vrng, (list, tuple)) and len(vrng) == 2:
        v_start, v_end = vrng
    else:
        v_start, v_end = cal_min, data_max
    v_start, v_end = max(v_start, cal_min), min(v_end, data_max)   # 钳制到数据范围

    vsub = pdf[(pdf["dt"].dt.date >= v_start) & (pdf["dt"].dt.date <= v_end)]
    total = len(vsub)
    if total == 0:
        st.info("No reviews in the selected range.")
    else:
        counts = vsub["Stars"].value_counts().reindex(range(1, 6), fill_value=0)
        vol = pd.DataFrame({"Star": STAR_DESC, "Count": [int(counts[s]) for s in STAR_DESC]})
        vol["StarLabel"] = [f"{s}★" for s in STAR_DESC]
        vol["End"] = vol["Count"].cumsum()
        vol["Start"] = vol["End"] - vol["Count"]
        vol["Mid"] = (vol["Start"] + vol["End"]) / 2
        vol["Pct"] = vol["Count"] / total * 100
        vol["PctStr"] = vol["Pct"].round().astype(int).astype(str) + "%"
        # 占比太小的段不标文字，避免拥挤
        vol["Label"] = vol.apply(
            lambda r: f"{int(r.Count)} ({r.Pct:.0f}%)" if r.Pct >= 4 else "", axis=1)

        tip = [alt.Tooltip("StarLabel:N", title="Rating"),
               alt.Tooltip("Count:Q", title="Reviews"),
               alt.Tooltip("PctStr:N", title="Percentage")]
        bar = alt.Chart(vol).mark_bar().encode(
            x=alt.X("Start:Q", axis=None), x2="End:Q",
            color=alt.Color("StarLabel:N", scale=star_color_scale, sort=STAR_LBL,
                            legend=alt.Legend(title=None, orient="top")),
            tooltip=tip,
        )
        txt = alt.Chart(vol).mark_text(color="white", fontSize=13, fontWeight="bold").encode(
            x="Mid:Q", text="Label:N", tooltip=tip)   # 文字层用同一套 tooltip，避免带出 Mid/Label
        st.altair_chart((bar + txt).properties(height=90), use_container_width=True)

        # 备注：区间信息 + 若某星级为 0，明确标出（避免用户以为漏了）
        cap = f"{plat_label} · {v_start:%d/%m/%Y} – {v_end:%d/%m/%Y} · {total:,} reviews"
        zero_stars = [f"{s}★" for s in STAR_DESC if int(counts[s]) == 0]
        if zero_stars:
            cap += f"　·　None: {', '.join(zero_stars)}"
        st.caption(cap)

st.markdown("<br>", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 第二部分：Rating Mix Over Time —— Percentage / Volume 切换，带月份滑块
# （MoM / YoY 的 Compare 视图代码保留在文件末尾、暂不启用）
# --------------------------------------------------------------------------
st.markdown('<div class="subtitle"><span style="font-size:20px; vertical-align:middle;">▪</span> Rating Distribution Over Time</div>', unsafe_allow_html=True)

def month_star_table(period):
    """某月各星级的 (数量, 占比%)。无数据返回 None。"""
    sub = pdf[pdf["Period"] == period]
    n = len(sub)
    if n == 0:
        return None
    cnt = sub["Stars"].value_counts().reindex(range(1, 6), fill_value=0)
    return cnt, cnt / n * 100

# 月份滑块：以月为单位选区间，从最早完整月到最新完整月
month_opts = [p.strftime("%b %Y") for p in all_periods]
lbl2p = dict(zip(month_opts, all_periods))

if not month_opts:
    st.info("No data for this platform.")
else:
    metric = st.radio("metric", ["Volume", "Percentage"],
                      horizontal=True, label_visibility="collapsed")

    if len(month_opts) >= 2:
        s_lbl, e_lbl = st.select_slider(
            "months", options=month_opts,
            value=(month_opts[0], month_opts[-1]), label_visibility="collapsed")
    else:
        s_lbl = e_lbl = month_opts[0]

    ps, pe = lbl2p[s_lbl], lbl2p[e_lbl]
    if ps > pe:
        ps, pe = pe, ps
    periods = [p for p in all_periods if ps <= p <= pe]

    rows = []
    for p in periods:
        tbl = month_star_table(p)
        if tbl is None:
            continue
        cnt, pct = tbl
        for s in STAR_DESC:
            rows.append({"Month": p.strftime("%b %Y"), "Star": f"{s}★",
                         "Count": int(cnt[s]), "Pct": pct[s],
                         "PctStr": f"{pct[s]:.0f}%", "ord": s})
    if not rows:
        st.info("No data in the selected range.")
    else:
        long = pd.DataFrame(rows)
        month_order = [p.strftime("%b %Y") for p in periods]
        tip = [alt.Tooltip("Month:N", title="Month"),
               alt.Tooltip("Star:N", title="Rating"),
               alt.Tooltip("Count:Q", title="Volume"),                       # 数量
               alt.Tooltip("PctStr:N", title="Percentage")]                  # 整数 + %

        if metric == "Percentage":
            # 100% 堆叠：看构成比例
            y_enc = alt.Y("Pct:Q", stack="normalize", axis=alt.Axis(title=None, format="%"))
        else:
            # 绝对数量堆叠：看真实评论量的高低
            y_enc = alt.Y("Count:Q", stack="zero", axis=alt.Axis(title=None))

        chart = alt.Chart(long).mark_bar().encode(
            x=alt.X("Month:N", sort=month_order,
                    axis=alt.Axis(labelAngle=-45, title=None)),
            y=y_enc,
            color=alt.Color("Star:N", scale=star_color_scale, sort=STAR_LBL,
                            legend=alt.Legend(title=None, orient="top")),
            order=alt.Order("ord:Q", sort="descending"),
            tooltip=tip,
        )
        st.altair_chart(chart.properties(height=360), use_container_width=True)
        st.caption(f"{plat_label} · {s_lbl} – {e_lbl} · {len(periods)} months")

    # ---- 图 2：总评论量(柱) + 平均星级(线) 组合图，独立月份滑块 ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="subtitle"><span style="font-size:20px; vertical-align:middle;">▪</span> Volume & Average Rating</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    # 独立滑块（和上面的堆叠柱互不影响）
    if len(month_opts) >= 2:
        va_s, va_e = st.select_slider(
            "va_months", options=month_opts,
            value=(month_opts[0], month_opts[-1]),
            label_visibility="collapsed", key="va_slider")
    else:
        va_s = va_e = month_opts[0]
    va_ps, va_pe = lbl2p[va_s], lbl2p[va_e]
    if va_ps > va_pe:
        va_ps, va_pe = va_pe, va_ps
    va_periods = [p for p in all_periods if va_ps <= p <= va_pe]

    va_rows = []
    for p in va_periods:
        sub = pdf[pdf["Period"] == p]
        if len(sub):
            va_rows.append({"Month": p.strftime("%b %Y"),
                            "Volume": int(len(sub)), "Avg": round(sub["Stars"].mean(), 2)})
    va_df = pd.DataFrame(va_rows)
    va_order = [p.strftime("%b %Y") for p in va_periods]
    # 柱和线共用同一套 tooltip：Month / Reviews / Avg Rating
    va_tip = [alt.Tooltip("Month:N", title="Month"),
              alt.Tooltip("Volume:Q", title="Reviews"),
              alt.Tooltip("Avg:Q", title="Avg Rating", format=".2f")]

    base_x = alt.X("Month:N", sort=va_order, axis=alt.Axis(labelAngle=-45, title=None))
    vol_bars = alt.Chart(va_df).mark_bar(color="#7E8B94", opacity=0.75).encode(
        x=base_x,
        y=alt.Y("Volume:Q", axis=alt.Axis(title="Reviews", titleColor="#7E8B94")),
        tooltip=va_tip,
    )
    avg_line = alt.Chart(va_df).mark_line(
        color=BRONZE, strokeWidth=2.5,
        point=alt.OverlayMarkDef(color=BRONZE, size=55)).encode(
        x=base_x,
        y=alt.Y("Avg:Q", scale=alt.Scale(domain=[1, 5]),
                axis=alt.Axis(title="Avg rating", titleColor=BRONZE, values=[1, 2, 3, 4, 5])),
        tooltip=va_tip,
    )
    combo = alt.layer(vol_bars, avg_line).resolve_scale(y="independent")
    st.altair_chart(combo.properties(height=340), use_container_width=True)
    st.caption(f"{plat_label} · {va_s} – {va_e} · bars = review volume · line = average rating (1–5)")

st.markdown("<br>", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Star Rating → 固定单月 MoM / YoY 对比（表格 + 分组柱，并排）
# --------------------------------------------------------------------------
st.markdown('<div class="subtitle"><span style="font-size:20px; vertical-align:middle;">▪</span> Month-over-Month & Year-over-Year</div>',
            unsafe_allow_html=True)

GREEN, RED = "#5B8A72", "#B5654A"
# 三个时间点用三个不同色相（类别，非深浅），本月用品牌青铜最突出
PT = [("YoY", "#7E8B94"), ("MoM", "#C29A5B"), ("This month", BRONZE)]

def m_count(period):
    sub = pdf[pdf["Period"] == period]
    if len(sub) == 0:
        return None
    return sub["Stars"].value_counts().reindex(range(1, 6), fill_value=0)

if not month_opts:
    st.info("No data for this platform.")
else:
    # 年 + 月 两级下拉（并排）+ 右侧总评论量头条，同一行
    years_av = sorted({p.year for p in all_periods})
    yc, mc, hc = st.columns([1.2, 1.2, 4])
    with yc:
        sel_year = st.selectbox("Year", years_av, index=len(years_av) - 1, label_visibility="collapsed")
    months_in_year = [p for p in all_periods if p.year == sel_year]
    mon_labels = [p.strftime("%b") for p in months_in_year]
    with mc:
        sel_mon = st.selectbox("Month", mon_labels, index=len(mon_labels) - 1, label_visibility="collapsed")
    sel_p = months_in_year[mon_labels.index(sel_mon)]
    sel_month = sel_p.strftime("%b %Y")

    cur_c, mom_c, yoy_c = m_count(sel_p), m_count(sel_p - 1), m_count(sel_p - 12)
    mom_lbl_m, yoy_lbl_m = (sel_p - 1).strftime("%b %Y"), (sel_p - 12).strftime("%b %Y")

    def share(cnt, star):
        return None if cnt is None else cnt[star] / cnt.sum() * 100

    def dir_color(d, star):
        if d == 0:
            return MUTED
        up = d > 0
        if star >= 4:
            good = up
        elif star <= 2:
            good = not up
        else:
            good = None
        return GREEN if good else (RED if good is False else MUTED)

    # 总评论量头条（放在下拉右侧，与下拉框垂直对齐）
    cur_t = int(cur_c.sum()) if cur_c is not None else 0
    def tot_cell(cmp_c):
        if cmp_c is None:
            return f"<span style='color:{MUTED}'>–</span>"
        d = cur_t - int(cmp_c.sum())
        if d == 0:
            return f"<span style='color:{MUTED}'>– 0</span>"
        arrow = "▲" if d > 0 else "▼"
        return f"<span style='color:{GREEN if d>0 else RED}; font-weight:600'>{arrow} {d:+d}</span>"
    with hc:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='font-size:16px; text-align:right;'>"
            f"Total reviews <b style='color:{INK}'>{cur_t}</b>　"
            f"MoM {tot_cell(mom_c)}　YoY {tot_cell(yoy_c)}</div>",
            unsafe_allow_html=True)

    # ---- 转置表格：1–5 星做列，本月 / MoM / YoY 做行 ----
    def chg_cell(cmp_c, star):
        """对比月的数量 + 占比变化%（彩色箭头）。"""
        if cmp_c is None:
            return f"<span style='color:{MUTED}'>–</span>"
        cmp_v = int(cmp_c[star])
        d = share(cur_c, star) - share(cmp_c, star)      # 占比变化(百分点)
        if abs(d) < 0.5:
            chg = f"<span style='color:{MUTED}'>(– 0%)</span>"
        else:
            arrow = "▲" if d > 0 else "▼"
            chg = f"<span style='color:{dir_color(d, star)}; font-weight:600'>({arrow} {d:+.0f}%)</span>"
        return f"{cmp_v} {chg}"

    stars = [5, 4, 3, 2, 1]
    LABEL_W = "22%"                       # 首列(时间段)宽度，其余 5 列均分
    # 表头：左上角填 "Period"，其余为星级列（带彩色圆点）
    head = (f"<th style='padding:11px 16px; text-align:center; vertical-align:middle; "
            f"width:{LABEL_W}; font-weight:600;'>Period</th>")
    for s in stars:
        head += (f"<th style='padding:11px 16px; text-align:center; vertical-align:middle; "
                 f"font-weight:600;'><span style='color:{theme.STAR_SCALE[s]};'>●</span> {s}★</th>")

    def data_row(label, sub, cells, top_border=True):
        bd = f"border-top:1px solid {DIVIDER};" if top_border else ""
        row = (f"<td style='padding:11px 16px; color:{MUTED}; text-align:center; "
               f"vertical-align:middle; {bd}'>{label}{sub}</td>")
        for c in cells:
            row += (f"<td style='padding:11px 16px; text-align:center; "
                    f"vertical-align:middle; {bd}'>{c}</td>")
        return f"<tr>{row}</tr>"

    r_this = data_row(
        sel_month, "",
        ["–" if cur_c is None else f"<b>{int(cur_c[s])}</b>" for s in stars],
        top_border=False)
    r_mom = data_row(
        "MoM", f"<br><span style='font-size:11px;'>{mom_lbl_m}</span>",
        [chg_cell(mom_c, s) for s in stars])
    r_yoy = data_row(
        "YoY", f"<br><span style='font-size:11px;'>{yoy_lbl_m}</span>",
        [chg_cell(yoy_c, s) for s in stars])

    st.markdown(
        f"<table style='border-collapse:collapse; width:100%; font-size:14px;'>"
        f"<tr style='color:{MUTED}; border-bottom:1px solid {DIVIDER};'>{head}</tr>"
        f"{r_this}{r_mom}{r_yoy}</table>",
        unsafe_allow_html=True)
    st.caption(f"{plat_label} · numbers = review count · "
               f"change = share of reviews (%)")
