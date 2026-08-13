# nlp_utils.py — 本地 NLP 处理（只在本地/aggregate 时跑，dashboard 不 import 它）
# 功能：翻译成英文 + 语言检测 + 情绪(1~5星, 多语言BERT) + 主题支柱(关键词多标签)
# 设计为"增量处理"：只处理还没有译文的行，历史行不重算 → 每月省算力。
#
# 依赖（仅本地需要，勿放进 dashboard 的 requirements）：
#   pip install deep-translator langdetect transformers torch pandas openpyxl

import re
import pandas as pd

# ---- 处理后会新增的列 ----
NLP_COLS = ["Language", "Review_EN", "Sent_stars", "Sent_label", "Sent_score",
            "T_Food", "T_Service", "T_View", "T_Value", "T_Ambiance"]

# ---- 主题支柱关键词（在英文译文上匹配；可自行增删让它更准）----
THEME_KEYWORDS = {
    "Food": ["food", "dish", "dishes", "menu", "course", "courses", "taste", "tasty",
             "flavour", "flavor", "cooked", "cook", "salty", "meal", "starter", "main",
             "dessert", "portion", "chef", "kitchen", "cuisine", "fish", "meat", "lamb",
             "tuna", "cheese", "sauce", "bread", "wine", "drinks", "cocktail", "delicious",
             "undercooked", "overcooked", "fresh", "bland"],
    "Service": ["service", "staff", "waiter", "waitress", "waiters", "host", "hostess",
                "server", "attentive", "rude", "friendly", "slow", "waited", "waiting",
                "reservation", "booking", "welcoming", "unfriendly", "professional"],
    "View": ["view", "views", "scenery", "skyline", "city", "panorama", "window",
             "windows", "tower", "rooftop", "height", "overlooking"],
    "Value": ["price", "prices", "priced", "expensive", "value", "money", "worth",
              "overpriced", "cost", "costly", "cheap", "pricey", "affordable"],
    "Ambiance": ["ambiance", "ambience", "atmosphere", "decor", "interior", "music",
                 "noise", "noisy", "loud", "tables", "seating", "crowded", "rundown",
                 "temperature", "airco", "air conditioning", "romantic", "cozy",
                 "vibe", "lighting", "spacious"],
}

# ---- 惰性加载重模型（import 本模块时不会加载 torch）----
_translator = None
_sent_pipe = None

def _get_translator():
    global _translator
    if _translator is None:
        from deep_translator import GoogleTranslator
        _translator = GoogleTranslator(source="auto", target="en")
    return _translator

def _get_sentiment():
    global _sent_pipe
    if _sent_pipe is None:
        from transformers import pipeline
        # 多语言 1~5 星情绪，最适合餐厅评论
        _sent_pipe = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment",
            truncation=True, max_length=512)
    return _sent_pipe

def detect_language(text):
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"

def extract_english(raw):
    """从原文提取干净英文，避免重复/失败翻译：
    - '(Translated by Google) X (Original) Y' → 取 X
    - '(Translated by Google) X'               → 取 X
    - 无标记 → 原文(去空白)，needs_tr=True 交给后续判断是否要翻译
    返回 (text, needs_translation)。
    """
    if not isinstance(raw, str):
        return "", False
    t = raw.replace("\r", " ").strip()
    if "(Translated by Google)" in t:
        after = t.split("(Translated by Google)", 1)[1]
        eng = re.split(r"\(Original\)", after, 1)[0].strip().strip('"').strip()
        return (eng, False) if eng else ("", True)
    return (t, True)

def _looks_failed(text):
    """翻译是否失败（Error 500 之类）。"""
    if not isinstance(text, str) or not text.strip():
        return True
    return bool(re.search(r"that.?s an error|error 500|please try again later", text, re.I))


def translate_to_en(text, lang=None):
    """非英文→英文；已是英文或翻译失败则原样返回。"""
    if lang == "en":
        return text
    try:
        t = _get_translator().translate(text[:4900])
        if _looks_failed(t):
            return text                                 # 失败则退回原文，避免写入 Error 500
        return t if t else text
    except Exception:
        return text

def sentiment_of(text_en):
    """返回 (stars 1~5, label neg/neutral/pos, score -1~1)。"""
    try:
        out = _get_sentiment()(text_en[:2000])[0]
        stars = int(out["label"][0])                    # '4 stars' → 4
    except Exception:
        return (None, "unknown", None)
    label = "negative" if stars <= 2 else ("neutral" if stars == 3 else "positive")
    score = round((stars - 3) / 2, 3)                   # 归一化到 -1~1
    return (stars, label, score)

def themes_of(text_en):
    """在英文译文上按关键词匹配主题，返回 {Food:0/1, ...} 多标签。"""
    low = " " + re.sub(r"[^a-z ]", " ", text_en.lower()) + " "
    res = {}
    for pillar, kws in THEME_KEYWORDS.items():
        hit = any((" " + k + " ") in low or (k in low if " " in k else False) for k in kws)
        res[pillar] = int(hit)
    return res

def _rating_to_sentiment(rating):
    """真实星级 → (stars, label, score)。解析 '5-Star' 这类。"""
    try:
        s = int(str(rating).split("-")[0])
    except Exception:
        return None
    label = "negative" if s <= 2 else ("neutral" if s == 3 else "positive")
    return (s, label, round((s - 3) / 2, 3))


def process_dataframe(df, text_col, rating_col=None, verbose=True):
    """对 df 做增量 NLP：只处理 Review_EN 还是空的行。
    若给了 rating_col（如公开评论的真实星级），情绪直接用星级（比模型准）；
    否则（如内部 feedback，无星级）用多语言情绪模型。"""
    for c in NLP_COLS:
        if c not in df.columns:
            df[c] = pd.NA

    todo = df[df["Review_EN"].isna() & df[text_col].notna() &
              (df[text_col].astype(str).str.strip() != "")].index
    if verbose:
        print(f"[NLP] 待处理 {len(todo)} 行（其余已处理/无文字，跳过）")

    for i, idx in enumerate(todo, 1):
        raw = str(df.at[idx, text_col]).replace("\\n", " ").strip()
        eng, needs_tr = extract_english(raw)            # 先提取 Google 已嵌入的英文
        if needs_tr:
            lang = detect_language(eng)
            en = eng if lang == "en" else translate_to_en(eng, lang)
        else:
            en = eng                                     # 直接用 Google 嵌入译文
            if "(Original)" in raw:
                orig = raw.split("(Original)", 1)[1]
            else:
                orig = raw.split("(Translated by Google)", 1)[0]
            lang = detect_language(orig.strip() or eng)

        # 情绪：优先用真实星级；无星级才用模型
        rt = _rating_to_sentiment(df.at[idx, rating_col]) if rating_col and rating_col in df.columns else None
        if rt is not None:
            stars, label, score = rt
        else:
            stars, label, score = sentiment_of(en)
        th = themes_of(en)
        df.at[idx, "Language"] = lang
        df.at[idx, "Review_EN"] = en
        df.at[idx, "Sent_stars"] = stars
        df.at[idx, "Sent_label"] = label
        df.at[idx, "Sent_score"] = score
        for p in THEME_KEYWORDS:
            df.at[idx, f"T_{p}"] = th[p]
        if verbose and i % 25 == 0:
            print(f"[NLP]   {i}/{len(todo)} ...")
    if verbose:
        print("[NLP] 完成")
    return df
