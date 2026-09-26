"""近 5 日趨勢圖：輸出 PNG，以內嵌圖片方式放進郵件（多數郵件軟體不支援 SVG 與 JavaScript）。

四個小圖上下排列，各自一個 y 軸（不同單位不共用軸），適合手機直式閱讀。
"""
import io
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from .models import TrendPoint  # noqa: E402

# 色彩：單一數列用藍色；買賣超依台股慣例紅買綠賣（深綠 #008300，已通過色盲分離度檢查的下限，
# 另以「在零軸上方／下方」與帶正負號的標籤作為第二重編碼）
SERIES = "#2a78d6"
UP = "#e34948"
DOWN = "#008300"
TEXT = "#1c1e21"
MUTED = "#6b6a66"
GRID = "#e6e6e3"
SURFACE = "#ffffff"

plt.rcParams.update({
    # 依序嘗試：GitHub Actions（Noto CJK）、Windows、macOS
    "font.sans-serif": ["Noto Sans CJK TC", "Microsoft JhengHei", "PingFang TC", "Heiti TC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9,
})


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=TEXT, pad=8)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0, labelsize=8.5)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _line(ax, xs: List[int], ys: List[float], label_fmt: str) -> None:
    ax.plot(xs, ys, color=SERIES, linewidth=1.8, marker="o", markersize=5.5,
            markerfacecolor=SERIES, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
    # 只標最新一點
    ax.annotate(label_fmt.format(ys[-1]), (xs[-1], ys[-1]), xytext=(0, 9), textcoords="offset points",
                ha="center", fontsize=9, fontweight="bold", color=TEXT)
    pad = (max(ys) - min(ys)) * 0.25 or abs(ys[-1]) * 0.01
    ax.set_ylim(min(ys) - pad, max(ys) + pad * 1.6)


def _bars(ax, xs: List[int], ys: List[float], label_fmt: str, signed: bool) -> None:
    colors = [(UP if y >= 0 else DOWN) if signed else SERIES for y in ys]
    ax.bar(xs, ys, width=0.55, color=colors, edgecolor=SURFACE, linewidth=1, zorder=3)
    if signed:
        ax.axhline(0, color=MUTED, linewidth=0.8, zorder=2)
    y = ys[-1]
    ax.annotate(label_fmt.format(y), (xs[-1], y), xytext=(0, 4 if y >= 0 else -4), textcoords="offset points",
                ha="center", va="bottom" if y >= 0 else "top", fontsize=9, fontweight="bold", color=TEXT)
    lo, hi = min(min(ys), 0), max(max(ys), 0)
    span = (hi - lo) or 1
    ax.set_ylim(lo - span * (0.32 if lo < 0 else 0), hi + span * 0.18)


def render_trend_png(points: List[TrendPoint]) -> Optional[bytes]:
    if len(points) < 2:
        return None

    labels = [f"{p.trade_date:%m/%d}" for p in points]
    xs = list(range(len(points)))
    panels = [
        ("加權指數", [p.close for p in points], "line", "{:,.0f}"),
        ("成交金額（億元）", [p.turnover_billion for p in points], "bar", "{:,.0f}"),
    ]
    if all(p.foreign_net_billion is not None for p in points):
        panels.append(("外資現貨買賣超（億元）", [p.foreign_net_billion for p in points], "signed", "{:+,.1f}"))
    if all(p.foreign_oi is not None for p in points):
        panels.append(("外資台指期未平倉淨額（口）", [p.foreign_oi for p in points], "line", "{:+,}"))

    fig, axes = plt.subplots(len(panels), 1, figsize=(6, 1.95 * len(panels)), dpi=200, facecolor=SURFACE)
    thousands = FuncFormatter(lambda v, _: f"{v:,.0f}")
    for ax, (title, ys, kind, fmt) in zip(axes, panels):
        _style(ax, title)
        if kind == "line":
            _line(ax, xs, ys, fmt)
        else:
            _bars(ax, xs, ys, fmt, signed=(kind == "signed"))
        ax.yaxis.set_major_formatter(thousands)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
        ax.set_xticks(xs)
        ax.set_xlim(-0.5, len(xs) - 0.5)  # 各小圖日期對齊
        ax.set_xticklabels(labels)
        ax.get_xticklabels()[-1].set_color(TEXT)
        ax.get_xticklabels()[-1].set_fontweight("bold")

    fig.tight_layout(h_pad=1.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=SURFACE)
    plt.close(fig)
    return buf.getvalue()
