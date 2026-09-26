"""解析函式的單元測試。樣本資料取自 2026/09/23～09/24 的真實回應（已截短）。"""
from datetime import date

import pytest

from report import fetchers

D = date(2026, 9, 24)

MARKET = {
    "stat": "OK",
    "data": [
        ["115/09/23", "10,473,893,046", "894,650,683,140", "4,407,031", "48,157.29", "357.12"],
        ["115/09/24", "8,626,109,510", "775,591,428,171", "3,880,761", "48,024.60", "-132.69"],
    ],
}

INSTITUTIONAL = {
    "stat": "OK",
    "data": [
        ["自營商(自行買賣)", "9,882,509,551", "5,646,973,463", "4,235,536,088"],
        ["自營商(避險)", "23,087,552,661", "25,984,658,328", "-2,897,105,667"],
        ["投信", "13,921,313,441", "26,744,576,741", "-12,823,263,300"],
        ["外資及陸資(不含外資自營商)", "272,421,262,886", "305,385,876,541", "-32,964,613,655"],
        ["外資自營商", "0", "0", "0"],
        ["合計", "319,312,638,539", "363,762,085,073", "-44,449,446,534"],
    ],
}

MARGIN = {
    "stat": "OK",
    "tables": [{
        "data": [
            ["融資(交易單位)", "270,795", "262,634", "10,711", "9,282,262", "9,279,712"],
            ["融券(交易單位)", "19,887", "12,187", "3,351", "213,059", "202,008"],
            ["融資金額(仟元)", "30,073,340", "20,479,799", "857,972", "606,367,833", "615,103,402"],
        ],
    }],
}


def _fut(day, who, net):
    return {"日期": day, "商品名稱": "臺股期貨", "身份別": who, "多空未平倉口數淨額": str(net)}


FUTURES = [
    _fut("2026/09/23", "自營商", -3056),
    _fut("2026/09/23", "投信", 73559),
    _fut("2026/09/23", "外資及陸資", -76084),
    _fut("2026/09/24", "自營商", -1520),
    _fut("2026/09/24", "投信", 72864),
    _fut("2026/09/24", "外資及陸資", -77031),
]


def test_parse_market():
    m = fetchers.parse_market(MARKET, D)
    assert m.close == 48024.60
    assert m.change == -132.69
    assert m.change_pct == pytest.approx(-132.69 / 48157.29 * 100)
    assert m.turnover_billion == pytest.approx(7755.91, abs=0.01)
    assert m.turnover_change_pct == pytest.approx(-13.31, abs=0.01)


def test_parse_market_uses_previous_month_on_first_trading_day():
    prev = {"data": [["115/08/31", "0", "1,000,000,000", "0", "100", "0"]]}
    first = {"data": [["115/09/01", "0", "1,100,000,000", "0", "101", "1"]]}
    m = fetchers.parse_market(first, date(2026, 9, 1), prev)
    assert m.turnover_change_pct == pytest.approx(10.0)


def test_parse_market_holiday():
    with pytest.raises(fetchers.NoTradingData):
        fetchers.parse_market(MARKET, date(2026, 9, 25))


def test_parse_institutional_merges_dealer_rows():
    flows = {f.name: f.net_billion for f in fetchers.parse_institutional(INSTITUTIONAL)}
    assert flows["外資"] == pytest.approx(-329.65, abs=0.01)
    assert flows["自營商"] == pytest.approx(13.38, abs=0.01)
    assert flows["合計"] == pytest.approx(-444.49, abs=0.01)


def test_parse_institutional_not_ready():
    with pytest.raises(fetchers.NoTradingData):
        fetchers.parse_institutional({"stat": "很抱歉，沒有符合條件的資料!"})


def test_parse_margin():
    m = fetchers.parse_margin(MARGIN)
    assert m.margin_balance_billion == pytest.approx(6151.03, abs=0.01)
    assert m.margin_change_billion == pytest.approx(87.36, abs=0.01)
    assert m.short_balance == 202008
    assert m.short_change == -11051


def test_parse_futures_computes_change_vs_previous_day():
    pos = {p.name: p for p in fetchers.parse_futures(FUTURES, D)}
    assert pos["外資"].net_oi == -77031
    assert pos["外資"].net_oi_change == -947
    assert pos["自營商"].net_oi_change == 1536


def test_parse_futures_first_row_has_no_change():
    pos = fetchers.parse_futures(FUTURES, date(2026, 9, 23))
    assert all(p.net_oi_change is None for p in pos)


def test_parse_pcr():
    rows = [{"日期": "2026/09/24", "買賣權成交量比率%": "121.11", "買賣權未平倉量比率%": "85.33"}]
    pcr = fetchers.parse_pcr(rows, D)
    assert (pcr.volume_ratio, pcr.oi_ratio) == (121.11, 85.33)
