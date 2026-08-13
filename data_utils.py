# data_utils.py — 共用数据模块
# 第 2 页及以后都从这里读 review 数据，保证清洗口径一致。
# 负责：读取 Moon_review.csv → 解析评分/平台/日期 → 只保留"完整月份"

import os
import datetime
from pathlib import Path
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
REVIEW_PATH = BASE_DIR / "Moon_review.csv"

_RATING_MAP = {"1-Star": 1, "2-Star": 2, "3-Star": 3, "4-Star": 4, "5-Star": 5}
_PLATFORM_MAP = {"Google Business Profile": "Google", "Tripadvisor": "Tripadvisor"}

def load_reviews():
    """读取并清洗 review 数据（只保留完整月份）。
    把文件修改时间作为缓存键：CSV 一更新，缓存自动失效、重新读取最新数据。"""
    return _load_reviews(os.path.getmtime(REVIEW_PATH))

@st.cache_data
def _load_reviews(mtime):
    df = pd.read_csv(REVIEW_PATH)
    df["Stars"] = df["Rating"].map(_RATING_MAP)                 # "5-Star" → 5
    df["Platform"] = df["Platform"].replace(_PLATFORM_MAP)      # 统一平台名
    df["dt"] = pd.to_datetime(df["Review Date & Time"],
                              format="%b %d, %Y %H:%M", errors="coerce")
    df = df.dropna(subset=["dt", "Stars"]).copy()
    df["Stars"] = df["Stars"].astype(int)
    df["Year"] = df["dt"].dt.year
    df["MonthNum"] = df["dt"].dt.month
    df["Period"] = df["dt"].dt.to_period("M")

    # --- 只保留完整月份（不依赖系统日期、不 hardcode 月份、不怕月底没评论）---
    # 依据"文件更新时间"(≈你下载/更新数据的时间)：更新时间所在的那个月是"进行中的月"，
    # 只保留它之前的月份。例：8/1 更新 → 更新月是 8 月 → 保留到 7 月(7 月已完整)。
    file_date = datetime.date.fromtimestamp(mtime)
    current = pd.Period(file_date, freq="M")
    df = df[df["Period"] < current]
    return df