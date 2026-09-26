from datetime import date

from report.chart import render_trend_png
from report.models import TrendPoint


def _points(n, **kw):
    return [TrendPoint(date(2026, 9, 14 + i), 47000 + i * 100, 9000, **kw) for i in range(n)]


def test_renders_png():
    png = render_trend_png(_points(5, foreign_net_billion=-120.5, foreign_oi=-70000))
    assert png.startswith(b"\x89PNG")


def test_skips_panels_with_missing_data():
    # 外資資料缺漏時仍可畫出大盤兩張小圖
    assert render_trend_png(_points(5)).startswith(b"\x89PNG")


def test_needs_at_least_two_days():
    assert render_trend_png(_points(1)) is None
