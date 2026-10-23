"""Price checks for a hand-picked list of momo / Coupang products.

Neither platform offers a public product API, so each watchlist entry is a
product page plus the affiliate link you generated in that platform's
dashboard. The current price is read from the page's structured data
(JSON-LD or meta tags). Keep the list small and the schedule infrequent.
"""
import json
import re
import time

import requests

from dealbot.models import Product

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
META_PRICE_RE = re.compile(
    r'<meta[^>]+(?:property|itemprop|name)=["\'](?:product:price:amount|price)["\'][^>]+'
    r'content=["\']([\d,.]+)["\']', re.I)


def _to_price(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _offer_price(obj) -> float | None:
    """Walk a JSON-LD object looking for a Product offer price."""
    if isinstance(obj, list):
        for item in obj:
            price = _offer_price(item)
            if price:
                return price
    elif isinstance(obj, dict):
        offers = obj.get("offers")
        if offers is not None:
            for offer in offers if isinstance(offers, list) else [offers]:
                if isinstance(offer, dict):
                    price = _to_price(offer.get("price") or offer.get("lowPrice"))
                    if price:
                        return price
        for value in obj.values():
            if isinstance(value, (dict, list)):
                price = _offer_price(value)
                if price:
                    return price
    return None


def extract_price(html: str, price_regex: str | None = None) -> float | None:
    if price_regex:
        match = re.search(price_regex, html, re.S)
        if match:
            return _to_price(match.group(1))
    for block in JSON_LD_RE.findall(html):
        try:
            price = _offer_price(json.loads(block.strip()))
        except json.JSONDecodeError:
            continue
        if price:
            return price
    match = META_PRICE_RE.search(html)
    return _to_price(match.group(1)) if match else None


def fetch(entries: list[dict]) -> list[Product]:
    products = []
    for entry in entries:
        try:
            resp = requests.get(entry["page_url"], headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[watchlist] {entry['name']}: fetch failed ({e})")
            continue
        price = extract_price(resp.text, entry.get("price_regex"))
        if not price:
            print(f"[watchlist] {entry['name']}: price not found on page")
            continue
        products.append(Product(
            source=entry["source"],
            product_id=entry.get("id") or entry["page_url"],
            name=entry["name"],
            price=price,
            url=entry["affiliate_url"],
            niche=entry.get("niche", ""),
            image_url=entry.get("image_url", ""),
        ))
        time.sleep(3)
    return products
