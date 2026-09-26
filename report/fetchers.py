"""從證交所（TWSE）與期交所（TAIFEX）抓取盤後資料。

每個資料源分成 fetch_*（負責 HTTP）與 parse_*（純函式，負責解析），
parse_* 不碰網路，方便用固定的樣本資料做單元測試。
"""
import csv
import io
from datetime import date, timedelta
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import (
    FuturesPosition,
    InstitutionalFlow,
    MarginSummary,
    MarketSummary,
    PutCallRatio,
)

TWSE = "https://www.twse.com.tw/rwd/zh"
TAIFEX = "https://www.taifex.com.tw/cht/3"
HUNDRED_MILLION = 100_000_000


class NoTradingData(Exception):
    """指定日期沒有交易資料（假日、颱風假，或資料尚未公布）。"""


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (tw-market-report)"
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _num(s: str) -> float:
    return float(s.replace(",", "").strip())


def _roc_date(d: date) -> str:
    """2026-09-24 -> '115/09/24'（證交所用民國年）"""
    return f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"


# ---------- 大盤 ----------

def parse_market(payload: dict, d: date, prev_payload: Optional[dict] = None) -> MarketSummary:
    rows = payload.get("data") or []
    key = _roc_date(d)
    idx = next((i for i, r in enumerate(rows) if r[0] == key), None)
    if idx is None:
        raise NoTradingData(f"{d} 無大盤成交資料")

    row = rows[idx]
    close, change = _num(row[4]), _num(row[5])
    turnover = _num(row[2])

    prev_row = rows[idx - 1] if idx > 0 else ((prev_payload or {}).get("data") or [None])[-1]
    turnover_change_pct = None
    if prev_row:
        prev_turnover = _num(prev_row[2])
        turnover_change_pct = (turnover / prev_turnover - 1) * 100

    return MarketSummary(
        close=close,
        change=change,
        change_pct=change / (close - change) * 100,
        turnover_billion=turnover / HUNDRED_MILLION,
        turnover_change_pct=turnover_change_pct,
    )


def fetch_market(s: requests.Session, d: date) -> MarketSummary:
    url = f"{TWSE}/afterTrading/FMTQIK"
    payload = s.get(url, params={"date": d.strftime("%Y%m%d"), "response": "json"}, timeout=20).json()
    prev_payload = None
    rows = payload.get("data") or []
    if rows and rows[0][0] == _roc_date(d):
        # 當月第一個交易日：前一交易日在上個月
        last_month = d.replace(day=1) - timedelta(days=1)
        prev_payload = s.get(
            url, params={"date": last_month.strftime("%Y%m%d"), "response": "json"}, timeout=20
        ).json()
    return parse_market(payload, d, prev_payload)


# ---------- 三大法人現貨買賣超 ----------

def parse_institutional(payload: dict) -> List[InstitutionalFlow]:
    if payload.get("stat") != "OK":
        raise NoTradingData("三大法人資料尚未公布")
    net = {r[0]: _num(r[3]) for r in payload["data"]}
    dealer = net.get("自營商(自行買賣)", 0) + net.get("自營商(避險)", 0)
    return [
        InstitutionalFlow("外資", net["外資及陸資(不含外資自營商)"] / HUNDRED_MILLION),
        InstitutionalFlow("投信", net["投信"] / HUNDRED_MILLION),
        InstitutionalFlow("自營商", dealer / HUNDRED_MILLION),
        InstitutionalFlow("合計", net["合計"] / HUNDRED_MILLION),
    ]


def fetch_institutional(s: requests.Session, d: date) -> List[InstitutionalFlow]:
    payload = s.get(
        f"{TWSE}/fund/BFI82U",
        params={"type": "day", "dayDate": d.strftime("%Y%m%d"), "response": "json"},
        timeout=20,
    ).json()
    return parse_institutional(payload)


# ---------- 融資融券 ----------

def parse_margin(payload: dict) -> MarginSummary:
    if payload.get("stat") != "OK":
        raise NoTradingData("融資融券資料尚未公布（通常晚間才會公布）")
    table = payload["tables"][0]
    rows = {r[0]: r for r in table["data"]}
    # 欄位：項目, 買進, 賣出, 現金(券)償還, 前日餘額, 今日餘額
    margin = rows["融資金額(仟元)"]
    short = rows["融券(交易單位)"]
    thousand_to_billion = 1000 / HUNDRED_MILLION
    return MarginSummary(
        margin_balance_billion=_num(margin[5]) * thousand_to_billion,
        margin_change_billion=(_num(margin[5]) - _num(margin[4])) * thousand_to_billion,
        short_balance=int(_num(short[5])),
        short_change=int(_num(short[5]) - _num(short[4])),
    )


def fetch_margin(s: requests.Session, d: date) -> MarginSummary:
    payload = s.get(
        f"{TWSE}/marginTrading/MI_MARGN",
        params={"date": d.strftime("%Y%m%d"), "selectType": "MS", "response": "json"},
        timeout=20,
    ).json()
    return parse_margin(payload)


# ---------- 期交所：台指期三大法人未平倉 ----------

def _taifex_csv(s: requests.Session, path: str, data: dict) -> List[dict]:
    r = s.post(f"{TAIFEX}/{path}", data=data, timeout=20)
    r.raise_for_status()
    text = r.content.decode("cp950")  # 期交所 CSV 為 Big5 編碼
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _date_range(d: date, days: int = 14) -> dict:
    return {
        "queryStartDate": (d - timedelta(days=days)).strftime("%Y/%m/%d"),
        "queryEndDate": d.strftime("%Y/%m/%d"),
    }


def parse_futures(rows: List[dict], d: date) -> List[FuturesPosition]:
    key = d.strftime("%Y/%m/%d")
    dates = sorted({r["日期"] for r in rows if r.get("日期")})
    if key not in dates:
        raise NoTradingData(f"{d} 無台指期法人資料")
    prev_key = dates[dates.index(key) - 1] if dates.index(key) > 0 else None

    def net_oi(day: Optional[str], who: str) -> Optional[int]:
        for r in rows:
            if r["日期"] == day and r["身份別"] == who:
                return int(r["多空未平倉口數淨額"])
        return None

    result = []
    for who, label in [("外資及陸資", "外資"), ("投信", "投信"), ("自營商", "自營商")]:
        today = net_oi(key, who)
        prev = net_oi(prev_key, who)
        result.append(FuturesPosition(label, today, today - prev if prev is not None else None))
    return result


def fetch_futures(s: requests.Session, d: date) -> List[FuturesPosition]:
    rows = _taifex_csv(s, "futContractsDateDown", {**_date_range(d), "commodityId": "TXF"})
    return parse_futures(rows, d)


def parse_pcr(rows: List[dict], d: date) -> PutCallRatio:
    key = d.strftime("%Y/%m/%d")
    for r in rows:
        if r.get("日期") == key:
            return PutCallRatio(
                volume_ratio=_num(r["買賣權成交量比率%"]),
                oi_ratio=_num(r["買賣權未平倉量比率%"]),
            )
    raise NoTradingData(f"{d} 無 P/C Ratio 資料")


def fetch_pcr(s: requests.Session, d: date) -> PutCallRatio:
    rows = _taifex_csv(s, "pcRatioDown", _date_range(d))
    return parse_pcr(rows, d)
