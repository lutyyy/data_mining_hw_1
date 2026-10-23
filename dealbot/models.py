from dataclasses import dataclass


@dataclass
class Product:
    source: str            # "shopee" / "momo" / "coupang"
    product_id: str
    name: str
    price: float           # current price in TWD
    url: str               # affiliate link
    niche: str = ""
    image_url: str = ""
    list_price: float | None = None     # seller's "original" price, if known
    discount_rate: float | None = None  # seller-claimed discount, 0-100
    rating: float | None = None
    sales: int | None = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.product_id}"


@dataclass
class Deal:
    product: Product
    drop_pct: float        # how far below the reference price, 0-100
    reference_price: float # 30-day median, or seller's list price for new items
    reason: str            # "history_low" / "seller_discount"
    is_lowest: bool = False
