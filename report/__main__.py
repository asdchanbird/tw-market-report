"""命令列進入點。

    python -m report                     # 抓今天（台北時間）的資料並寄信
    python -m report --date 2026-09-24   # 指定日期
    python -m report --dry-run           # 不寄信，輸出 HTML 到 output/
    python -m report --no-ai             # 不呼叫 Claude
"""
import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from . import fetchers
from .ai_summary import generate_summary
from .chart import render_trend_png
from .mailer import send_email
from .models import DailyReport, InstitutionalFlow, MarketDay, TrendPoint
from .render import render_html, subject

TAIPEI = timezone(timedelta(hours=8))
log = logging.getLogger("report")


TREND_DAYS = 5


def _foreign_net(flows: List[InstitutionalFlow]) -> float:
    return next(f.net_billion for f in flows if f.name == "外資")


def build_trend(s, days: List[MarketDay], today_flows: List[InstitutionalFlow],
                foreign_oi: Dict[date, int]) -> List[TrendPoint]:
    recent = days[-TREND_DAYS:]
    points = [TrendPoint(x.trade_date, x.close, x.turnover_billion, foreign_oi=foreign_oi.get(x.trade_date))
              for x in recent]
    if today_flows:
        points[-1].foreign_net_billion = _foreign_net(today_flows)
        for p in points[:-1]:
            time.sleep(fetchers.TWSE_DELAY)
            p.foreign_net_billion = _foreign_net(fetchers.fetch_institutional(s, p.trade_date))
    return points


def build_report(d: date) -> DailyReport:
    s = fetchers.make_session()
    # 大盤資料是判斷是否為交易日的依據，抓不到就整份不做
    days = fetchers.fetch_market_days(s, d)
    report = DailyReport(trade_date=d, market=fetchers.parse_market(days, d))

    # 其餘區塊各自獨立，某個來源失敗只在報告中註記，不影響整體寄送
    futures_rows: List[dict] = []

    def fetch_futures(s, d):
        futures_rows.extend(fetchers.fetch_futures_rows(s, d))
        return fetchers.parse_futures(futures_rows, d)

    sections = [
        ("institutional", "三大法人現貨買賣超", fetchers.fetch_institutional),
        ("futures", "台指期法人未平倉", fetch_futures),
        ("pcr", "選擇權 P/C Ratio", fetchers.fetch_pcr),
        ("margin", "融資融券", fetchers.fetch_margin),
        ("trend", "近 5 日趨勢", lambda s, d: build_trend(
            s, days, report.institutional, fetchers.parse_foreign_oi(futures_rows))),
    ]
    for attr, label, fetch in sections:
        try:
            setattr(report, attr, fetch(s, d))
        except Exception as e:  # noqa: BLE001 - 任何失敗都降級為警告
            log.warning("%s 取得失敗：%s", label, e)
            report.warnings.append(f"{label}（{e}）")
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="台股盤後自動報告")
    p.add_argument("--date", type=date.fromisoformat, default=datetime.now(TAIPEI).date())
    p.add_argument("--dry-run", action="store_true", help="不寄信，只輸出 HTML 檔")
    p.add_argument("--no-ai", action="store_true", help="不產生 AI 摘要")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        report = build_report(args.date)
    except fetchers.NoTradingData as e:
        log.info("%s，今日不寄送報告", e)
        return 0

    if not args.no_ai:
        report.ai_summary = generate_summary(report)

    title = subject(report)
    png = render_trend_png(report.trend)

    if args.dry_run:
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        chart_name = f"trend-{args.date}.png"
        if png:
            (out_dir / chart_name).write_bytes(png)
        out = out_dir / f"report-{args.date}.html"
        out.write_text(render_html(report, chart_name if png else None), encoding="utf-8")
        log.info("已輸出 %s", out.resolve())
        log.info("主旨：%s", title)
    else:
        html = render_html(report, "cid:trend" if png else None)
        send_email(title, html, images={"trend": png} if png else None)
        log.info("已寄出：%s", title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
