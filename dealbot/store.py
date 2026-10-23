"""Price history and posting log, kept in a JSON file committed to the repo."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

HISTORY_DAYS = 60


class Store:
    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text("utf-8")) if path.exists() else {}
        # prices: {key: [[iso_date, lowest_price_that_day], ...]}
        self.prices: dict[str, list] = data.get("prices", {})
        # posted: {key: {"price": float, "at": iso_datetime}}
        self.posted: dict[str, dict] = data.get("posted", {})
        # line_sent: {iso_date: count}
        self.line_sent: dict[str, int] = data.get("line_sent", {})

    def history(self, key: str, days: int, today: date) -> list[float]:
        """Daily prices strictly before today, within the last `days` days."""
        start = (today - timedelta(days=days)).isoformat()
        return [p for d, p in self.prices.get(key, []) if start <= d < today.isoformat()]

    def record_price(self, key: str, price: float, today: date):
        series = self.prices.setdefault(key, [])
        if series and series[-1][0] == today.isoformat():
            series[-1][1] = min(series[-1][1], price)
        else:
            series.append([today.isoformat(), price])

    def last_posted(self, key: str) -> dict | None:
        return self.posted.get(key)

    def mark_posted(self, key: str, price: float, now: datetime):
        self.posted[key] = {"price": price, "at": now.isoformat(timespec="seconds")}

    def line_count(self, today: date) -> int:
        return self.line_sent.get(today.isoformat(), 0)

    def add_line_count(self, today: date, n: int = 1):
        self.line_sent[today.isoformat()] = self.line_count(today) + n

    def prune(self, today: date):
        cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
        for key in list(self.prices):
            self.prices[key] = [row for row in self.prices[key] if row[0] >= cutoff]
            if not self.prices[key]:
                del self.prices[key]
        self.posted = {k: v for k, v in self.posted.items() if v["at"][:10] >= cutoff}
        self.line_sent = {d: n for d, n in self.line_sent.items() if d >= cutoff}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"prices": self.prices, "posted": self.posted, "line_sent": self.line_sent}
        self.path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
