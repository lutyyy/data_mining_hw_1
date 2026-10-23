"""Short promotional copy for each deal, written by Claude.

Prices and links are never taken from the model's output: the message
template fills them in from the product data, so a wrong number can't slip in.
"""
import os

import anthropic

from dealbot.models import Deal

SYSTEM_PROMPT = """你是台灣特價情報頻道的小編，讀者是對 3C、電腦周邊和遊戲有興趣的人。
根據商品資料寫兩行繁體中文：
第一行：吸睛但不誇大的標題（20 字內，不要加 emoji、不要重複價格數字）。
第二行：一句說明這個商品適合誰、為什麼值得注意（40 字內）。
只輸出這兩行，不要加任何其他文字。不要捏造商品資料中沒有的規格或功能。"""


def fallback_copy(deal: Deal) -> tuple[str, str]:
    return (deal.product.name[:40], f"比平常便宜約 {deal.drop_pct:.0f}%，需要的可以看看。")


def write_copy(deal: Deal, model: str) -> tuple[str, str]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return fallback_copy(deal)
    p = deal.product
    facts = (f"商品名稱：{p.name}\n分類：{p.niche}\n平台：{p.source}\n"
             f"目前價格：NT${p.price:,.0f}\n比參考價便宜：{deal.drop_pct:.0f}%")
    if p.rating:
        facts += f"\n評分：{p.rating:.1f}"
    if p.sales:
        facts += f"\n已售出：{p.sales}"
    try:
        response = anthropic.Anthropic().beta.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": facts}],
        )
    except anthropic.APIError as e:
        print(f"[copywriter] API error, using template: {e}")
        return fallback_copy(deal)
    if response.stop_reason != "end_turn":
        return fallback_copy(deal)
    text = "".join(b.text for b in response.content if b.type == "text")
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return fallback_copy(deal)
    return lines[0], lines[1]
