"""近期新聞整理：從鉅亨網（cnyes）抓取區間內的新聞，依關鍵字評分挑出重點。

不依賴 AI：以總經／權值股關鍵字與鉅亨網的盤勢專欄標記（〈台股〉、〈台幣〉…）評分，
同分時較新的排前面。
"""
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

import requests

from .models import NewsGroup, NewsItem

API = "https://api.cnyes.com/media/api/v1/newslist/category"
TAIPEI = timezone(timedelta(hours=8))
PER_GROUP = 6

INTERNATIONAL = {"國際政經", "美股雷達", "歐亞股", "外匯", "債券", "能源", "黃金"}

# 顯示名稱 -> [(鉅亨網分類, 篩選條件)]
GROUPS = {
    "台股": [
        ("tw_stock", lambda it: True),
        ("forex", lambda it: it["title"].startswith("〈台幣〉")),  # 台幣收盤專欄
    ],
    "國際財經": [
        ("headline", lambda it: it.get("categoryName") in INTERNATIONAL),
    ],
}

KEYWORDS = {
    3: ["聯準會", "Fed", "升息", "降息", "央行", "關稅", "川習", "外資", "加權指數"],
    2: ["殖利率", "通膨", "CPI", "PCE", "非農", "美元", "台幣", "台積電", "輝達", "川普", "習近平", "法說"],
    1: ["鴻海", "聯發科", "AI", "半導體", "營收", "ETF", "美股", "那斯達克", "費半", "油價"],
}
WRAP_COLUMN = re.compile(r"^〈(台股|台幣|美股|紐約匯市|台北匯市|債市)")
EXCLUDE = re.compile(r"^(盤中速報|【.+?】)")  # 個股漲跌快訊、銀行業配稿


def score(item: dict) -> int:
    title = item["title"]
    s = sum(w for w, words in KEYWORDS.items() for k in words if k in title)
    if WRAP_COLUMN.match(title) or item.get("categoryName") == "台股盤勢":
        s += 4
    return s


def _normalize(title: str) -> str:
    return re.sub(r"[\s\W]", "", title)[:18]


def select(items: Iterable[dict], n: int = PER_GROUP) -> List[dict]:
    seen, candidates = set(), []
    for it in items:
        title = html.unescape(it["title"]).strip()
        key = _normalize(title)
        if EXCLUDE.match(title) or key in seen:
            continue
        seen.add(key)
        candidates.append({**it, "title": title})
    top = sorted(candidates, key=lambda it: (score(it), it["publishAt"]), reverse=True)[:n]
    return sorted(top, key=lambda it: it["publishAt"], reverse=True)  # 顯示時新到舊


def _fetch_all(s: requests.Session, category: str, start: datetime, end: datetime) -> List[dict]:
    items, page = [], 1
    while page <= 5:  # 最多 500 則，足以涵蓋長假
        r = s.get(
            f"{API}/{category}",
            params={"limit": 100, "page": page,
                    "startAt": int(start.timestamp()), "endAt": int(end.timestamp())},
            timeout=20,
        )
        r.raise_for_status()
        body = r.json()["items"]
        # API 的後續分頁偶爾會混入區間外的新聞，再篩一次
        items.extend(it for it in body["data"]
                     if start.timestamp() <= it["publishAt"] <= end.timestamp())
        if body["current_page"] >= body["last_page"]:
            break
        page += 1
    return items


def _to_news_item(it: dict) -> NewsItem:
    return NewsItem(
        title=it["title"],
        url=f"https://news.cnyes.com/news/id/{it['newsId']}",
        published=datetime.fromtimestamp(it["publishAt"], TAIPEI),
        tags=(it.get("keyword") or [])[:3],
    )


def fetch_news(s: requests.Session, start: datetime, end: datetime) -> List[NewsGroup]:
    groups = []
    for name, sources in GROUPS.items():
        items = [it for category, keep in sources
                 for it in _fetch_all(s, category, start, end) if keep(it)]
        picked = select(items)
        if picked:
            groups.append(NewsGroup(name, [_to_news_item(it) for it in picked]))
    if not groups:
        raise RuntimeError("區間內沒有新聞")
    return groups
