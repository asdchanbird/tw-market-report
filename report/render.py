from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import DailyReport

WEEKDAYS = "一二三四五六日"

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(report: DailyReport, chart_src: Optional[str] = None) -> str:
    """chart_src：趨勢圖網址。寄信時為 "cid:trend"（內嵌附件），本機預覽時為 PNG 檔名。"""
    return _env.get_template("report.html.j2").render(
        r=report, weekday=WEEKDAYS[report.trade_date.weekday()], chart_src=chart_src
    )


def subject(report: DailyReport) -> str:
    m = report.market
    arrow = "▲" if m.change > 0 else ("▼" if m.change < 0 else "－")
    return (
        f"台股盤後日報 {report.trade_date:%m/%d}｜加權 {m.close:,.0f} "
        f"{arrow}{abs(m.change):,.0f}（{m.change_pct:+.2f}%）"
    )
