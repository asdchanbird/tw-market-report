from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import DailyReport

WEEKDAYS = "一二三四五六日"

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(report: DailyReport) -> str:
    return _env.get_template("report.html.j2").render(
        r=report, weekday=WEEKDAYS[report.trade_date.weekday()]
    )


def subject(report: DailyReport) -> str:
    m = report.market
    arrow = "▲" if m.change > 0 else ("▼" if m.change < 0 else "－")
    return (
        f"台股盤後日報 {report.trade_date:%m/%d}｜加權 {m.close:,.0f} "
        f"{arrow}{abs(m.change):,.0f}（{m.change_pct:+.2f}%）"
    )
