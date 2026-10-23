"""Decide which price changes are real deals worth posting."""
from datetime import date, datetime, timedelta
from statistics import median

from dealbot.models import Deal, Product
from dealbot.store import Store


def find_deal(product: Product, store: Store, rules: dict, today: date) -> Deal | None:
    if product.rating is not None and product.rating < rules["min_rating"]:
        return None
    if product.sales is not None and product.sales < rules["min_sales"]:
        return None

    history = store.history(product.key, rules["lookback_days"], today)
    if len(history) >= rules["min_history_days"]:
        # Enough of our own data: compare against the typical recent price.
        reference = median(history)
        drop = (reference - product.price) / reference * 100
        is_lowest = product.price <= min(history)
        if drop >= rules["min_drop_pct"] and is_lowest:
            return Deal(product, round(drop, 1), reference, "history_low", is_lowest=True)
        return None

    # New item: fall back to the seller's claimed discount, with a stricter bar
    # since list prices are often inflated.
    if product.discount_rate is not None and product.discount_rate >= rules["min_seller_discount_pct"]:
        reference = product.price / (1 - product.discount_rate / 100)
        return Deal(product, round(product.discount_rate, 1), round(reference), "seller_discount")
    return None


def recently_posted(product: Product, store: Store, rules: dict, now: datetime) -> bool:
    """Skip repeats unless the price fell meaningfully since the last post."""
    last = store.last_posted(product.key)
    if not last:
        return False
    if now - datetime.fromisoformat(last["at"]) > timedelta(days=rules["repost_cooldown_days"]):
        return False
    return product.price > last["price"] * (1 - rules["repost_extra_drop_pct"] / 100)


def select_deals(products: list[Product], store: Store, rules: dict, now: datetime) -> list[Deal]:
    today = now.date()
    deals = []
    seen = set()
    for product in products:
        if product.key in seen:
            continue
        seen.add(product.key)
        deal = find_deal(product, store, rules, today)
        if deal and not recently_posted(product, store, rules, now):
            deals.append(deal)
        store.record_price(product.key, product.price, today)
    # Our own price history is stronger evidence than a seller's claimed discount.
    deals.sort(key=lambda d: (d.reason == "history_low", d.drop_pct), reverse=True)
    return deals[: rules["max_posts_per_run"]]
