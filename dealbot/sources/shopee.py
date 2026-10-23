"""Shopee Taiwan Affiliate Open API (GraphQL).

Apply for API access in the Shopee affiliate dashboard (聯盟行銷 > Open API)
to get an App ID and Secret.
"""
import hashlib
import json
import time

import requests

from dealbot.models import Product

ENDPOINT = "https://open-api.affiliate.shopee.tw/graphql"

PRODUCT_QUERY = """
query ($keyword: String, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: 2, page: $page, limit: $limit) {
    nodes {
      itemId
      productName
      price
      priceMin
      priceDiscountRate
      imageUrl
      offerLink
      ratingStar
      sales
    }
  }
}
"""


def sign(app_id: str, secret: str, timestamp: int, payload: str) -> str:
    raw = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _post(app_id: str, secret: str, query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}, separators=(",", ":"))
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, "
                         f"Signature={sign(app_id, secret, ts, payload)}",
    }
    resp = requests.post(ENDPOINT, data=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"Shopee API error: {body['errors']}")
    return body["data"]


def parse_node(node: dict, niche: str) -> Product | None:
    price = node.get("priceMin") or node.get("price")
    if not price or not node.get("offerLink"):
        return None
    discount = node.get("priceDiscountRate")
    return Product(
        source="shopee",
        product_id=str(node["itemId"]),
        name=node.get("productName", ""),
        price=float(price),
        url=node["offerLink"],
        niche=niche,
        image_url=node.get("imageUrl", ""),
        discount_rate=float(discount) if discount is not None else None,
        rating=float(node["ratingStar"]) if node.get("ratingStar") else None,
        sales=int(node["sales"]) if node.get("sales") is not None else None,
    )


def fetch(app_id: str, secret: str, niches: dict, limit: int = 50) -> list[Product]:
    """niches: {"3C": ["機械鍵盤", "SSD"], ...} -> products for every keyword."""
    products = []
    for niche, keywords in niches.items():
        for keyword in keywords:
            data = _post(app_id, secret, PRODUCT_QUERY,
                         {"keyword": keyword, "page": 1, "limit": limit})
            for node in data["productOfferV2"]["nodes"]:
                product = parse_node(node, niche)
                if product:
                    products.append(product)
            time.sleep(1)
    return products
