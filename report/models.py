"""報告用的資料結構。所有金額單位在此統一換算完成，模板只負責顯示。"""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import List, Optional


@dataclass
class MarketDay:
    trade_date: date
    close: float
    change: float
    turnover_billion: float


@dataclass
class TrendPoint:
    """近 5 日趨勢圖的一個交易日。抓不到的欄位為 None。"""
    trade_date: date
    close: float
    turnover_billion: float
    foreign_net_billion: Optional[float] = None  # 外資現貨買賣超（億元）
    foreign_oi: Optional[int] = None  # 外資台指期未平倉淨額（口）
    usd_twd: Optional[float] = None  # 新台幣兌美元（臺銀即期買賣中價）


@dataclass
class MarketSummary:
    close: float  # 加權指數收盤
    change: float  # 漲跌點數
    change_pct: float  # 漲跌幅 %
    turnover_billion: float  # 成交金額（億元）
    turnover_change_pct: Optional[float]  # 成交金額較前一交易日 %


@dataclass
class InstitutionalFlow:
    name: str
    net_billion: float  # 買賣超（億元）


@dataclass
class FuturesPosition:
    name: str  # 自營商 / 投信 / 外資
    net_oi: int  # 多空未平倉口數淨額
    net_oi_change: Optional[int]  # 較前一交易日增減


@dataclass
class PutCallRatio:
    volume_ratio: float  # 成交量 P/C %
    oi_ratio: float  # 未平倉 P/C %


@dataclass
class MarginSummary:
    margin_balance_billion: float  # 融資餘額（億元）
    margin_change_billion: float
    short_balance: int  # 融券餘額（張）
    short_change: int


@dataclass
class FxRate:
    usd_twd: float  # 1 美元兌多少新台幣；數字變大代表台幣貶值
    change: Optional[float]  # 較前一營業日


@dataclass
class NewsItem:
    title: str
    url: str
    published: datetime
    tags: List[str] = field(default_factory=list)


@dataclass
class NewsGroup:
    name: str
    items: List[NewsItem]


@dataclass
class DailyReport:
    trade_date: date
    market: MarketSummary
    institutional: List[InstitutionalFlow] = field(default_factory=list)
    futures: List[FuturesPosition] = field(default_factory=list)
    pcr: Optional[PutCallRatio] = None
    margin: Optional[MarginSummary] = None
    fx: Optional[FxRate] = None
    trend: List[TrendPoint] = field(default_factory=list)
    news: List[NewsGroup] = field(default_factory=list)
    ai_summary: Optional[str] = None
    warnings: List[str] = field(default_factory=list)  # 抓取失敗的區塊

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trade_date"] = self.trade_date.isoformat()
        for t in d["trend"]:
            t["trade_date"] = t["trade_date"].isoformat()
        # 給 AI 摘要參考的新聞只保留標題
        d["news"] = {g.name: [i.title for i in g.items] for g in self.news}
        d.pop("ai_summary")
        d.pop("warnings")
        return d
