"""Send deal posts to Telegram, Discord and LINE."""
import html

import requests

from dealbot.models import Deal

PLATFORM_NAMES = {"shopee": "蝦皮", "momo": "momo", "coupang": "酷澎"}
DISCLOSURE = "＊含分潤連結，透過連結購買我可能獲得佣金，不影響你的價格。"


def format_lines(deal: Deal, headline: str, blurb: str) -> dict:
    p = deal.product
    ref_label = "近期均價" if deal.reason == "history_low" else "原價"
    return {
        "headline": headline,
        "blurb": blurb,
        "price": f"NT${p.price:,.0f}（{ref_label} NT${deal.reference_price:,.0f}，-{deal.drop_pct:.0f}%）",
        "lowest": "近 30 天最低價" if deal.is_lowest else "",
        "platform": PLATFORM_NAMES.get(p.source, p.source),
        "url": p.url,
    }


def plain_text(deal: Deal, headline: str, blurb: str) -> str:
    f = format_lines(deal, headline, blurb)
    parts = [f"🔥 {f['headline']}", f["blurb"], f"💰 {f['price']}"]
    if f["lowest"]:
        parts.append(f"📉 {f['lowest']}")
    parts += [f"🛒 {f['platform']}：{f['url']}", DISCLOSURE]
    return "\n".join(parts)


def send_telegram(token: str, chat_id: str, deal: Deal, headline: str, blurb: str):
    f = {k: html.escape(v) for k, v in format_lines(deal, headline, blurb).items()}
    parts = [f"🔥 <b>{f['headline']}</b>", f["blurb"], f"💰 {f['price']}"]
    if f["lowest"]:
        parts.append(f"📉 {f['lowest']}")
    parts += [f'🛒 <a href="{f["url"]}">前往{f["platform"]}</a>', f"<i>{html.escape(DISCLOSURE)}</i>"]
    text = "\n".join(parts)
    base = f"https://api.telegram.org/bot{token}"
    if deal.product.image_url:
        resp = requests.post(f"{base}/sendPhoto", timeout=30, data={
            "chat_id": chat_id, "photo": deal.product.image_url,
            "caption": text, "parse_mode": "HTML"})
        if resp.ok:
            return
    resp = requests.post(f"{base}/sendMessage", timeout=30, data={
        "chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    resp.raise_for_status()


def send_discord(webhook_url: str, deal: Deal, headline: str, blurb: str):
    f = format_lines(deal, headline, blurb)
    description = "\n".join(filter(None, [
        f["blurb"], f"💰 {f['price']}", f"📉 {f['lowest']}" if f["lowest"] else "",
        f"🛒 {f['platform']}", DISCLOSURE]))
    embed = {"title": f"🔥 {f['headline']}"[:256], "url": f["url"], "description": description}
    if deal.product.image_url:
        embed["image"] = {"url": deal.product.image_url}
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=30)
    resp.raise_for_status()


def send_line_broadcast(access_token: str, deal: Deal, headline: str, blurb: str):
    resp = requests.post(
        "https://api.line.me/v2/bot/message/broadcast",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"messages": [{"type": "text", "text": plain_text(deal, headline, blurb)}]},
        timeout=30,
    )
    resp.raise_for_status()
