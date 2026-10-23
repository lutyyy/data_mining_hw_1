"""Entry point: python -m dealbot.main [--dry-run] [--config config.yaml]"""
import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from dealbot import copywriter, publishers
from dealbot.deals import select_deals
from dealbot.sources import shopee, watchlist
from dealbot.store import Store

TAIPEI = timezone(timedelta(hours=8))


def collect(config: dict) -> list:
    products = []
    app_id, secret = os.environ.get("SHOPEE_APP_ID"), os.environ.get("SHOPEE_SECRET")
    if app_id and secret:
        try:
            products += shopee.fetch(app_id, secret, config["shopee_keywords"])
        except Exception as e:
            print(f"[shopee] failed: {e}")
    else:
        print("[shopee] SHOPEE_APP_ID / SHOPEE_SECRET not set, skipping")
    products += watchlist.fetch(config.get("watchlist") or [])
    return products


def publish(deal, headline, blurb, dry_run) -> bool:
    if dry_run:
        print(publishers.plain_text(deal, headline, blurb), end="\n\n")
        return True
    sent = False
    channels = [
        ("telegram", os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"),
         lambda: publishers.send_telegram(os.environ["TELEGRAM_BOT_TOKEN"],
                                          os.environ["TELEGRAM_CHAT_ID"], deal, headline, blurb)),
        ("discord", os.environ.get("DISCORD_WEBHOOK_URL"),
         lambda: publishers.send_discord(os.environ["DISCORD_WEBHOOK_URL"], deal, headline, blurb)),
    ]
    for name, configured, send in channels:
        if not configured:
            continue
        try:
            send()
            sent = True
        except Exception as e:
            print(f"[{name}] send failed: {e}")
    return sent


def publish_line(deals, copies, store, config, now, dry_run):
    """LINE broadcasts count against a monthly quota: send only the top few per day."""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    remaining = config["line_max_per_day"] - store.line_count(now.date())
    if (not token and not dry_run) or remaining <= 0:
        return
    for deal in deals[:remaining]:
        if deal.drop_pct < config["line_min_drop_pct"]:
            continue
        headline, blurb = copies[deal.product.key]
        if dry_run:
            print(f"[line] would broadcast: {headline}")
            continue
        try:
            publishers.send_line_broadcast(token, deal, headline, blurb)
            store.add_line_count(now.date())
        except Exception as e:
            print(f"[line] send failed: {e}")


def run(config_path: Path, dry_run: bool):
    config = yaml.safe_load(config_path.read_text("utf-8"))
    store = Store(Path(config["state_file"]))
    now = datetime.now(TAIPEI).replace(tzinfo=None)

    products = collect(config)
    print(f"collected {len(products)} products")
    deals = select_deals(products, store, config["rules"], now)
    print(f"{len(deals)} deals to post")

    copies = {}
    for deal in deals:
        headline, blurb = copywriter.write_copy(deal, config["claude_model"])
        copies[deal.product.key] = (headline, blurb)
        if publish(deal, headline, blurb, dry_run) and not dry_run:
            store.mark_posted(deal.product.key, deal.product.price, now)
    publish_line(deals, copies, store, config, now, dry_run)

    store.prune(now.date())
    if not dry_run:
        store.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml", type=Path)
    parser.add_argument("--dry-run", action="store_true",
                        help="print posts instead of sending, and don't save state")
    args = parser.parse_args()
    run(args.config, args.dry_run)


if __name__ == "__main__":
    main()
