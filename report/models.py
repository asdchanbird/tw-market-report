"""報告用的資料結構。所有金額單位在此統一換算完成，模板只負責顯示。"""
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import List, Optional


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
class DailyReport:
    trade_date: date
    market: MarketSummary
    institutional: List[InstitutionalFlow] = field(default_factory=list)
    futures: List[FuturesPosition] = field(default_factory=list)
    pcr: Optional[PutCallRatio] = None
    margin: Optional[MarginSummary] = None
    ai_summary: Optional[str] = None
    warnings: List[str] = field(default_factory=list)  # 抓取失敗的區塊

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trade_date"] = self.trade_date.isoformat()
        d.pop("ai_summary")
        d.pop("warnings")
        return d
