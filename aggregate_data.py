"""
aggregate_date.py
------------------
每月运行一次：
  1) 把新下载的 Moon_new.csv 合并进 Moon_review.csv（按 Platform + Reviewer Name +
     Review Date & Time 去重，不会重复计入）。
  2) 用合并后、去重后的 Moon_review.csv 完整数据，重新计算 baseline 截止月份之后
     每个月 / 每个平台的 1~5 星分布，写入 Moon_rating.csv（保留原有的 baseline 行）。
  3) 额外算出 "All Time"（baseline + 所有月份）的星级汇总，每个平台一行，
     再加一行 "All Platforms" 的总汇总，方便看板直接取用画图。

用法：
    把这个脚本、Moon_review.csv、Moon_rating.csv 放在同一文件夹。
    每个月把新下载的文件命名为 Moon_new.csv（覆盖掉上个月那份），放进同一文件夹，运行：
        python aggregate_date.py

设计要点（为什么第 2 步是"完整重算"而不是"只加本月新增"）：
    Moon_new.csv 每次下载的时间窗口可能和上个月有重叠，也可能有缺漏。如果只统计
    Moon_new.csv 里的行，重叠部分会被重复计数，缺漏部分则会漏算。
    这里改成：每次都以合并去重后的 Moon_review.csv 为唯一真相源，把 baseline 截止
    月份之后的所有行重新分月统计一遍——所以不管 Moon_new.csv 下载窗口怎么变，
    结果永远是当下最准确、不重不漏的状态。
"""

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from nlp_utils import process_dataframe, NLP_COLS  # 本地 NLP（翻译/情绪/主题）

MASTER = Path("Moon_review.csv")
NEW = Path("Moon_new.csv")
RATING_OUT = Path("Moon_rating.csv")
FEEDBACK_XLSX = Path("Moon_feedback.xlsx")
FEEDBACK_FULL = Path("Moon_feedback_full.csv")        # 本地留存：含 Email（.gitignore 排除，不上传）
FEEDBACK_OUT = Path("Moon_feedback_processed.csv")    # 上传用：不含 Email，dashboard 读它

# Moon_review.csv 只保留这 5 列；Moon_new.csv 里多出的 Brand Name / Location Name /
# Reply / Timezone / Tags 会被忽略。
MASTER_COLS = ["Platform", "Review", "Rating", "Reviewer Name", "Review Date & Time"]

# 判断"是不是同一条评论"的唯一键：同平台 + 同用户名 + 同时间 = 重复
KEY_COLS = ["Platform", "Reviewer Name", "Review Date & Time"]
DATE_COL = "Review Date & Time"

PLATFORM_MAP = {
    "google business profile": "Google",
    "tripadvisor": "Tripadvisor",
}

RATING_FIELDS = ["Month", "Platform", "Star_1", "Star_2", "Star_3", "Star_4", "Star_5", "Total", "Avg_Rating"]


def normalize_platform(p):
    return PLATFORM_MAP.get(str(p).strip().lower(), str(p).strip())


def parse_star(rating_str):
    """'5-Star' -> 5；解析失败返回 None，不会中断整个流程"""
    try:
        s = int(str(rating_str).strip().split("-")[0])
        return s if s in (1, 2, 3, 4, 5) else None
    except (ValueError, AttributeError, IndexError):
        return None


def parse_dates(series):
    return pd.to_datetime(series, format="mixed", errors="coerce")


def date_range_str(dt_series):
    dt_series = dt_series.dropna()
    if len(dt_series) == 0:
        return "N/A", "N/A"
    return dt_series.min().strftime("%Y-%m-%d %H:%M"), dt_series.max().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# STEP 1：合并评论明细
# ---------------------------------------------------------------------------

def build_key(row):
    return tuple(str(row[c]).strip() for c in KEY_COLS)


def content_sig(row):
    """用来判断"是不是同一条评论内容"：Review 文本 + 星级。"""
    return (str(row["Review"]).strip(), str(row["Rating"]).strip())


def truncate(text, n=120):
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= n else text[:n] + "…"


def ask_keep_ambiguous_row(existing_row, new_row):
    """同一个 (Platform, Reviewer Name, Review Date & Time)，但内容不一样。
    这不是脚本能自动判断的情况，交给用户人工确认要不要把新这条也保留下来。"""
    print("\n" + "-" * 70)
    print("⚠️ 发现疑似重复，但内容不同，需要你确认：")
    print(f"  Platform        : {new_row['Platform']}")
    print(f"  Reviewer Name   : {new_row['Reviewer Name']}")
    print(f"  Review Date&Time: {new_row['Review Date & Time']}")
    print(f"  [已有记录] Rating={existing_row['Rating']} | Review: {truncate(existing_row['Review'])}")
    print(f"  [本次新增] Rating={new_row['Rating']} | Review: {truncate(new_row['Review'])}")
    while True:
        ans = input("  这是另一条独立的评论，要保留吗？(y=保留 / n=当作重复跳过): ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  请输入 y 或 n")


def merge_reviews():
    print("=" * 70)
    print("STEP 1 / 合并评论明细：Moon_new.csv -> Moon_review.csv")
    print("=" * 70)

    if MASTER.exists():
        master_df = pd.read_csv(MASTER)
    else:
        print(f"未找到 {MASTER}，将视为空数据集，全部由 {NEW} 填充。")
        master_df = pd.DataFrame(columns=MASTER_COLS)

    before_n = len(master_df)
    old_start, old_end = date_range_str(parse_dates(master_df[DATE_COL]) if before_n else pd.Series([], dtype="datetime64[ns]"))
    print(f"[合并前] Moon_review.csv：{old_start} ~ {old_end}，共 {before_n} 条")

    if not NEW.exists():
        print(f"未找到 {NEW}，本次跳过合并，直接使用现有 Moon_review.csv 继续第 2 步。")
        return master_df

    new_df_raw = pd.read_csv(NEW)
    missing_cols = [c for c in MASTER_COLS if c not in new_df_raw.columns]
    if missing_cols:
        raise ValueError(f"{NEW} 缺少必要列: {missing_cols}，请检查下载文件格式是否变化。")
    new_df = new_df_raw[MASTER_COLS].copy()

    new_n = len(new_df)
    new_dates = parse_dates(new_df[DATE_COL])
    new_start, new_end = date_range_str(new_dates)
    print(f"[本次新下载] Moon_new.csv：{new_start} ~ {new_end}，共 {new_n} 条")

    bad_dates = new_df[new_dates.isna()]
    if len(bad_dates):
        print(f"  ⚠️ 有 {len(bad_dates)} 行日期格式无法解析，已列出（仍会被合并，只是无法参与月份统计）：")
        print(bad_dates.to_string(index=False))

    # 关键改动：不再用 drop_duplicates 一刀切。只有"key 相同 且 内容(Review+Rating)也相同"
    # 才自动判定为真重复、跳过；如果 key 相同但内容不同，一律停下来问你，而不是静默丢弃。
    seen = {}  # key -> (content_sig, 该 key 已保留下来的原始行, 是否来自本次新增)
    for _, row in master_df.iterrows():
        seen[build_key(row)] = content_sig(row)

    keep_rows = []
    auto_skipped = 0
    ambiguous_kept = 0
    ambiguous_skipped = 0
    ambiguous_log = []

    for _, row in new_df.iterrows():
        key = build_key(row)
        sig = content_sig(row)

        if key not in seen:
            keep_rows.append(row)
            seen[key] = sig
            continue

        if sig == seen[key]:
            auto_skipped += 1
            continue

        # key 相同但内容不同 -> 人工确认
        # 找一条已保留的、同 key 的行用于展示对比（优先从 master，其次从本次已保留的新行）
        existing_row = None
        match = master_df[
            (master_df["Platform"].astype(str).str.strip() == key[0])
            & (master_df["Reviewer Name"].astype(str).str.strip() == key[1])
            & (master_df["Review Date & Time"].astype(str).str.strip() == key[2])
        ]
        if len(match):
            existing_row = match.iloc[0]
        else:
            for kept in keep_rows:
                if build_key(kept) == key:
                    existing_row = kept
                    break

        keep_it = ask_keep_ambiguous_row(existing_row, row)
        ambiguous_log.append({
            "Platform": row["Platform"],
            "Reviewer Name": row["Reviewer Name"],
            "Review Date & Time": row["Review Date & Time"],
            "Existing_Rating": existing_row["Rating"] if existing_row is not None else "",
            "Existing_Review": existing_row["Review"] if existing_row is not None else "",
            "New_Rating": row["Rating"],
            "New_Review": row["Review"],
            "Decision": "保留" if keep_it else "跳过",
        })
        if keep_it:
            keep_rows.append(row)
            ambiguous_kept += 1
            # 注意：不更新 seen[key]，这样如果后面还有第三条同 key 内容又不同的行，
            # 仍然会拿"原始那条"来对比、继续问你，逻辑保持一致。
        else:
            ambiguous_skipped += 1

    new_kept_df = pd.DataFrame(keep_rows, columns=MASTER_COLS) if keep_rows else pd.DataFrame(columns=MASTER_COLS)
    combined = pd.concat([master_df, new_kept_df], ignore_index=True).reset_index(drop=True)

    added_n = len(new_kept_df)
    skipped_n = auto_skipped + ambiguous_skipped

    if before_n:
        backup = Path(f"Moon_review_backup_{datetime.now():%Y%m%d}.csv")
        master_df.to_csv(backup, index=False)
        print(f"已备份合并前的 Moon_review.csv 到 {backup}")

    if ambiguous_log:
        log_path = Path(f"Moon_ambiguous_review_log_{datetime.now():%Y%m%d}.csv")
        pd.DataFrame(ambiguous_log).to_csv(log_path, index=False)
        print(f"已将 {len(ambiguous_log)} 条人工确认记录写入 {log_path}，方便日后核对")

    combined.to_csv(MASTER, index=False)

    m_start, m_end = date_range_str(parse_dates(combined[DATE_COL]))
    print(f"[合并后] Moon_review.csv：{m_start} ~ {m_end}，共 {len(combined)} 条")
    print(f"  实际新增 {added_n} 条")
    print(f"  自动判定为真重复而跳过：{auto_skipped} 条（key 和内容都完全一致）")
    if ambiguous_log:
        print(f"  人工确认的疑似重复：{len(ambiguous_log)} 条 -> 保留 {ambiguous_kept} 条，跳过 {ambiguous_skipped} 条")

    return combined


# ---------------------------------------------------------------------------
# STEP 2：重新计算月度星级分布 + All Time 汇总
# ---------------------------------------------------------------------------

def parse_baseline_end(existing_df):
    """从形如 '2019-09_to_2026-06(baseline)' 的字符串里取出截止月份 'YYYY-MM'。
    如果存在多条 baseline 行，取其中最晚的月份，确保后面统计不会和 baseline 重叠。"""
    ends = []
    for month in existing_df.get("Month", []):
        m = re.search(r"_to_(\d{4}-\d{2})", str(month))
        if m:
            ends.append(m.group(1))
    return max(ends) if ends else None


def compute_monthly_ratings(master_df, baseline_end):
    df = master_df.copy()
    df["_Month"] = parse_dates(df[DATE_COL]).dt.strftime("%Y-%m")
    df["_Platform"] = df["Platform"].apply(normalize_platform)
    df["_Star"] = df["Rating"].apply(parse_star)

    bad_month = df[df["_Month"].isna()]
    if len(bad_month):
        print(f"  ⚠️ Moon_review.csv 中有 {len(bad_month)} 行日期无法解析，已跳过月度统计")

    bad_star = df[df["_Month"].notna() & df["_Star"].isna()]
    if len(bad_star):
        print(f"  ⚠️ 有 {len(bad_star)} 行星级无法解析，已跳过月度统计：")
        print(bad_star[["Platform", "Reviewer Name", "Review Date & Time", "Rating"]].to_string(index=False))

    valid = df[df["_Month"].notna() & df["_Star"].notna()]
    if baseline_end:
        valid = valid[valid["_Month"] > baseline_end]

    counts = defaultdict(lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
    for (month, platform, star), n in valid.groupby(["_Month", "_Platform", "_Star"]).size().items():
        counts[(month, platform)][star] = n

    return counts, len(valid)


def make_row(month, platform, star_counts):
    total = sum(star_counts.values())
    avg = sum(s * c for s, c in star_counts.items()) / total if total else 0
    return {
        "Month": month,
        "Platform": platform,
        "Star_1": star_counts[1],
        "Star_2": star_counts[2],
        "Star_3": star_counts[3],
        "Star_4": star_counts[4],
        "Star_5": star_counts[5],
        "Total": total,
        "Avg_Rating": round(avg, 2),
    }


def update_ratings(master_df):
    if RATING_OUT.exists():
        existing_df = pd.read_csv(RATING_OUT)
    else:
        existing_df = pd.DataFrame(columns=RATING_FIELDS)

    baseline_end = parse_baseline_end(existing_df)
    if baseline_end:
        print(f"检测到历史 baseline 数据，截止月份：{baseline_end}（该行保留不变）")
    else:
        print("未检测到 baseline 行，将对 Moon_review.csv 全部数据做月度统计")

    baseline_rows = {}
    for _, row in existing_df.iterrows():
        if "baseline" in str(row["Month"]).lower():
            baseline_rows[(row["Month"], row["Platform"])] = row.to_dict()

    monthly_counts, valid_n = compute_monthly_ratings(master_df, baseline_end)
    monthly_rows = {
        (month, platform): make_row(month, platform, star_counts)
        for (month, platform), star_counts in monthly_counts.items()
    }

    # All Time = baseline + 所有月份，按平台汇总；再加一行所有平台合计
    all_time_by_platform = defaultdict(lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
    for row in list(baseline_rows.values()) + list(monthly_rows.values()):
        for s in range(1, 6):
            all_time_by_platform[row["Platform"]][s] += int(row[f"Star_{s}"])

    all_time_rows = {}
    grand_total = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for platform, star_counts in all_time_by_platform.items():
        all_time_rows[("All Time", platform)] = make_row("All Time", platform, star_counts)
        for s in range(1, 6):
            grand_total[s] += star_counts[s]
    all_time_rows[("All Time", "All Platforms")] = make_row("All Time", "All Platforms", grand_total)

    final_rows = {**baseline_rows, **monthly_rows, **all_time_rows}

    def sort_key(item):
        (month, platform), _row = item
        if "baseline" in month.lower():
            return (0, month, platform)
        if month == "All Time":
            return (2, platform)
        return (1, month, platform)

    ordered = sorted(final_rows.items(), key=sort_key)
    out_df = pd.DataFrame([row for _, row in ordered], columns=RATING_FIELDS)
    out_df.to_csv(RATING_OUT, index=False)

    print(f"\n已更新 {RATING_OUT}，共 {len(out_df)} 行（baseline + 月度 + All Time 汇总）")
    print(f"  本次参与月度统计的评论明细：{valid_n} 条（baseline 截止月份之后）")
    print(f"  本次计算出的月份/平台组合：{sorted(monthly_rows.keys())}")

    print("\n[All Time 星级汇总]（看板画图用）：")
    print(out_df[out_df["Month"] == "All Time"][
        ["Platform", "Star_1", "Star_2", "Star_3", "Star_4", "Star_5", "Total", "Avg_Rating"]
    ].to_string(index=False))

    return out_df, valid_n


# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# STEP 3：对评论文字做增量 NLP（翻译 + 情绪 + 主题），只处理还没处理过的新行
# ---------------------------------------------------------------------------

def nlp_reviews():
    print("=" * 70)
    print("STEP 3 / NLP 处理评论文字（翻译 + 情绪 + 主题，只处理新增行）")
    print("=" * 70)
    df = pd.read_csv(MASTER)
    done_before = int(df["Review_EN"].notna().sum()) if "Review_EN" in df.columns else 0
    df = process_dataframe(df, text_col="Review", rating_col="Rating")
    df.to_csv(MASTER, index=False)
    done_after = int(df["Review_EN"].notna().sum())
    print(f"  本月新处理 {done_after - done_before} 条，累计已处理 {done_after} 条")


# ---------------------------------------------------------------------------
# STEP 4：对内部 feedback 做增量 NLP，写出 Moon_feedback_processed.csv
# ---------------------------------------------------------------------------

def nlp_feedback():
    print("=" * 70)
    print("STEP 4 / NLP 处理内部 feedback（Moon_feedback.xlsx）")
    print("=" * 70)
    if not FEEDBACK_XLSX.exists():
        print(f"  未找到 {FEEDBACK_XLSX}，跳过。")
        return
    raw = pd.read_excel(FEEDBACK_XLSX)
    raw["dt"] = pd.to_datetime(raw["Date"], format="mixed", errors="coerce")
    raw = raw.rename(columns={"Feedback": "Review"})
    # 增量：从"含 Email 的本地全量文件"对齐上次已算结果，已处理的行不重算
    if FEEDBACK_FULL.exists():
        prev = pd.read_csv(FEEDBACK_FULL)
        keep = [c for c in NLP_COLS if c in prev.columns]
        if keep and {"Date", "Email"}.issubset(prev.columns):
            raw = raw.merge(prev[["Date", "Email"] + keep], on=["Date", "Email"], how="left")
    df = process_dataframe(raw, text_col="Review")
    # ① 本地全量（含 Email）——不上传，作你的记录
    df.to_csv(FEEDBACK_FULL, index=False)
    # ② 上传版（去掉 Email）——dashboard 读它、push 到 GitHub
    df.drop(columns=["Email"], errors="ignore").to_csv(FEEDBACK_OUT, index=False)
    print(f"  feedback 共 {len(df)} 条 -> {FEEDBACK_FULL}(含Email,本地) + {FEEDBACK_OUT}(去Email,上传)")


def main():
    master_df = merge_reviews()

    print()
    print("=" * 70)
    print("STEP 2 / 重新计算月度星级分布 Moon_rating.csv")
    print("=" * 70)
    rating_df, valid_n = update_ratings(master_df)

    print()
    print("=" * 70)
    print("数据自检 Sanity Check")
    print("=" * 70)
    non_baseline = rating_df[
        (rating_df["Month"] != "All Time") & (~rating_df["Month"].str.contains("baseline", case=False))
    ]
    monthly_sum = int(non_baseline["Total"].sum())
    print(f"月度明细 Total 之和：{monthly_sum}")
    print(f"参与统计的评论明细行数：{valid_n}")
    if monthly_sum == valid_n:
        print("✅ 一致，没有漏算/多算")
    else:
        print("⚠️ 数量不一致，请检查上面打印的无法解析行")

    print()
    nlp_reviews()
    print()
    nlp_feedback()


if __name__ == "__main__":
    main()