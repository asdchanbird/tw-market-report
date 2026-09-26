"""命令列進入點。

    python -m report                     # 抓今天（台北時間）的資料並寄信
    python -m report --date 2026-09-24   # 指定日期
    python -m report --dry-run           # 不寄信，輸出 HTML 到 output/
    python -m report --no-ai             # 不呼叫 Claude
"""
import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import fetchers
from .ai_summary import generate_summary
from .mailer import send_email
from .models import DailyReport
from .render import render_html, subject

TAIPEI = timezone(timedelta(hours=8))
log = logging.getLogger("report")


def build_report(d: date) -> DailyReport:
    s = fetchers.make_session()
    # 大盤資料是判斷是否為交易日的依據，抓不到就整份不做
    report = DailyReport(trade_date=d, market=fetchers.fetch_market(s, d))

    # 其餘區塊各自獨立，某個來源失敗只在報告中註記，不影響整體寄送
    sections = [
        ("institutional", "三大法人現貨買賣超", fetchers.fetch_institutional),
        ("futures", "台指期法人未平倉", fetchers.fetch_futures),
        ("pcr", "選擇權 P/C Ratio", fetchers.fetch_pcr),
        ("margin", "融資融券", fetchers.fetch_margin),
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

    html = render_html(report)
    title = subject(report)

    if args.dry_run:
        out = Path("output") / f"report-{args.date}.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        log.info("已輸出 %s", out.resolve())
        log.info("主旨：%s", title)
    else:
        send_email(title, html)
        log.info("已寄出：%s", title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
