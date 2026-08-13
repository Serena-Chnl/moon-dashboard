# process_all.py — 一次性本地跑：把现有 Moon_review.csv 和 Moon_feedback.xlsx 做完整 NLP
# 用法（本地，装好依赖后）：  python process_all.py
# 之后每月的新数据由 aggregate_data.py 增量处理，不用再跑这个。
#
# 依赖：pip install deep-translator langdetect transformers torch pandas openpyxl

import pandas as pd
from pathlib import Path
from nlp_utils import process_dataframe, NLP_COLS

BASE = Path(__file__).resolve().parent
REVIEW = BASE / "Moon_review.csv"
FEEDBACK_XLSX = BASE / "Moon_feedback.xlsx"
FEEDBACK_OUT = BASE / "Moon_feedback_processed.csv"

# ---------- 1) Moon_review.csv：只处理 2024 起、带文字的评论 ----------
print("=== 处理 Moon_review.csv ===")
rev = pd.read_csv(REVIEW)
rev = process_dataframe(rev, text_col="Review", rating_col="Rating")
rev.to_csv(REVIEW, index=False)
print(f"已写回 {REVIEW}，新增列：{', '.join(NLP_COLS)}\n")

# ---------- 2) Moon_feedback.xlsx：解析日期 + NLP → 单独存 CSV ----------
print("=== 处理 Moon_feedback.xlsx ===")
fb = pd.read_excel(FEEDBACK_XLSX)
# 日期是手动复制粘贴的，格式可能不一，统一解析
fb["dt"] = pd.to_datetime(fb["Date"], format="mixed", errors="coerce")
fb = fb.rename(columns={"Feedback": "Review"})          # 统一成 Review 便于复用同一套处理
fb = process_dataframe(fb, text_col="Review")
fb.to_csv(FEEDBACK_OUT, index=False)
print(f"已写出 {FEEDBACK_OUT}（{len(fb)} 条）")
print("\n全部完成。把这几个文件 push 到 GitHub 即可部署。")
