from datetime import date

import pytest

from report import fetchers, news

# 臺銀牌告 CSV（截短遠期欄位以外皆為真實格式）
BOT_CSV = (
    "資料日期,幣別,匯率,現金,即期,遠期10天,遠期30天,遠期60天,遠期90天,遠期120天,遠期150天,遠期180天,"
    "匯率,現金,即期,遠期10天,遠期30天,遠期60天,遠期90天,遠期120天,遠期150天,遠期180天\n"
    "20260924,USD,本行買入,31.38000,31.73000,0,0,0,0,0,0,0,本行賣出,32.05000,31.83000,0,0,0,0,0,0,0,\n"
    "20260923,USD,本行買入,31.30000,31.65000,0,0,0,0,0,0,0,本行賣出,31.97000,31.75000,0,0,0,0,0,0,0,\n"
)


def test_parse_usd_twd_uses_spot_mid_rate():
    rates = fetchers.parse_usd_twd(BOT_CSV)
    assert rates == {date(2026, 9, 24): 31.78, date(2026, 9, 23): 31.70}


def test_parse_fx_change_vs_previous_business_day():
    fx = fetchers.parse_fx(fetchers.parse_usd_twd(BOT_CSV), date(2026, 9, 24))
    assert fx.usd_twd == 31.78
    assert fx.change == pytest.approx(0.08)


def test_parse_fx_missing_day():
    with pytest.raises(fetchers.NoTradingData):
        fetchers.parse_fx(fetchers.parse_usd_twd(BOT_CSV), date(2026, 9, 25))


def _item(title, t, category="台股新聞"):
    return {"title": title, "publishAt": t, "categoryName": category, "newsId": t, "keyword": []}


def test_select_ranks_by_keywords_then_shows_newest_first():
    items = [
        _item("某公司辦尾牙", 300),
        _item("聯準會升息 美債殖利率走高", 100),
        _item("〈台股盤後〉台積電領跌", 200),
    ]
    picked = news.select(items, n=2)
    assert [it["title"] for it in picked] == ["〈台股盤後〉台積電領跌", "聯準會升息 美債殖利率走高"]


def test_select_drops_flash_quotes_and_duplicates():
    items = [
        _item("盤中速報 - 輝達大漲5%", 1),
        _item("台積電法說會 毛利率優於預期", 2),
        _item("台積電法說會　毛利率優於預期！", 3),
        _item("&lt;快訊&gt; 外資賣超", 4),
    ]
    titles = [it["title"] for it in news.select(items)]
    assert "盤中速報 - 輝達大漲5%" not in titles
    assert sum("台積電法說會" in t for t in titles) == 1
    assert "<快訊> 外資賣超" in titles  # HTML 實體會被還原
