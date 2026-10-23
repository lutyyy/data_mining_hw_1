import hashlib
from datetime import date, datetime, timedelta

import pytest

from dealbot import publishers
from dealbot.deals import find_deal, recently_posted, select_deals
from dealbot.models import Deal, Product
from dealbot.sources import shopee, watchlist
from dealbot.store import Store

RULES = {
    "lookback_days": 30, "min_history_days": 7, "min_drop_pct": 10,
    "min_seller_discount_pct": 40, "min_rating": 4.5, "min_sales": 50,
    "repost_cooldown_days": 7, "repost_extra_drop_pct": 5, "max_posts_per_run": 5,
}
TODAY = date(2026, 10, 23)
NOW = datetime(2026, 10, 23, 12, 0)


def product(price, **kw):
    defaults = dict(source="shopee", product_id="1", name="機械鍵盤", url="https://s.shopee.tw/x")
    return Product(price=price, **{**defaults, **kw})


def store_with_history(tmp_path, prices, key="shopee:1"):
    store = Store(tmp_path / "state.json")
    for i, p in enumerate(prices):
        store.record_price(key, p, TODAY - timedelta(days=len(prices) - i))
    return store


def test_history_low_is_a_deal(tmp_path):
    store = store_with_history(tmp_path, [1000] * 10)
    deal = find_deal(product(850), store, RULES, TODAY)
    assert deal.reason == "history_low"
    assert deal.drop_pct == 15.0
    assert deal.reference_price == 1000


def test_small_drop_is_not_a_deal(tmp_path):
    store = store_with_history(tmp_path, [1000] * 10)
    assert find_deal(product(950), store, RULES, TODAY) is None


def test_not_a_deal_unless_period_low(tmp_path):
    # 15% under the median, but it was even cheaper last week
    store = store_with_history(tmp_path, [1000] * 9 + [800])
    assert find_deal(product(850), store, RULES, TODAY) is None


def test_new_item_uses_strict_seller_discount(tmp_path):
    store = Store(tmp_path / "state.json")
    assert find_deal(product(600, discount_rate=30), store, RULES, TODAY) is None
    deal = find_deal(product(600, discount_rate=40), store, RULES, TODAY)
    assert deal.reason == "seller_discount"
    assert deal.reference_price == 1000


def test_low_rating_or_sales_filtered(tmp_path):
    store = Store(tmp_path / "state.json")
    assert find_deal(product(600, discount_rate=50, rating=4.0), store, RULES, TODAY) is None
    assert find_deal(product(600, discount_rate=50, sales=10), store, RULES, TODAY) is None


def test_repost_cooldown(tmp_path):
    store = Store(tmp_path / "state.json")
    store.mark_posted("shopee:1", 1000, NOW - timedelta(days=2))
    assert recently_posted(product(980), store, RULES, NOW)
    assert not recently_posted(product(940), store, RULES, NOW)       # fell another 6%
    assert not recently_posted(product(980), store, RULES, NOW + timedelta(days=6))


def test_select_deals_records_prices_and_ranks(tmp_path):
    store = store_with_history(tmp_path, [1000] * 10)
    products = [
        product(600, product_id="2", discount_rate=45),
        product(800),                                  # history low, -20%
        product(800),                                  # duplicate in same run
    ]
    deals = select_deals(products, store, RULES, NOW)
    assert [d.product.product_id for d in deals] == ["1", "2"]
    assert store.prices["shopee:1"][-1] == [TODAY.isoformat(), 800]
    assert store.history("shopee:1", 30, TODAY) == [1000] * 10


def test_store_roundtrip_and_prune(tmp_path):
    store = Store(tmp_path / "state.json")
    store.record_price("a", 100, TODAY - timedelta(days=90))
    store.record_price("b", 200, TODAY)
    store.record_price("b", 180, TODAY)
    store.add_line_count(TODAY)
    store.prune(TODAY)
    store.save()
    loaded = Store(tmp_path / "state.json")
    assert "a" not in loaded.prices
    assert loaded.prices["b"] == [[TODAY.isoformat(), 180]]
    assert loaded.line_count(TODAY) == 1


def test_shopee_signature():
    expected = hashlib.sha256(b"app1700000000{}secret").hexdigest()
    assert shopee.sign("app", "secret", 1700000000, "{}") == expected


def test_shopee_parse_node():
    node = {"itemId": 99, "productName": "SSD", "price": "1990", "priceMin": "1890",
            "priceDiscountRate": 25, "offerLink": "https://s.shopee.tw/abc",
            "imageUrl": "https://img", "ratingStar": "4.9", "sales": 1200}
    p = shopee.parse_node(node, "3C周邊")
    assert (p.key, p.price, p.discount_rate, p.rating, p.sales) == ("shopee:99", 1890, 25, 4.9, 1200)
    assert shopee.parse_node({**node, "offerLink": None}, "3C周邊") is None


@pytest.mark.parametrize("html,expected", [
    ('<script type="application/ld+json">{"@type":"Product","offers":{"price":"1,290"}}</script>', 1290),
    ('<script type="application/ld+json">[{"@graph":[{"offers":[{"lowPrice":990}]}]}]</script>', 990),
    ('<meta property="product:price:amount" content="2490">', 2490),
    ('<div>no price</div>', None),
])
def test_extract_price(html, expected):
    assert watchlist.extract_price(html) == expected


def test_extract_price_custom_regex():
    assert watchlist.extract_price('"finalPrice": 3990,', r'"finalPrice":\s*([\d.]+)') == 3990


def test_message_has_disclosure_and_exact_price():
    deal = Deal(product(850, source="coupang"), 15.0, 1000, "history_low", is_lowest=True)
    text = publishers.plain_text(deal, "標題", "說明")
    assert "NT$850（近期均價 NT$1,000，-15%）" in text
    assert "酷澎" in text and "近 30 天最低價" in text
    assert publishers.DISCLOSURE in text
