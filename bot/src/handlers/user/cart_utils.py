import html
import logging
import re

from aiogram import Bot
from fluentogram import TranslatorRunner

logger = logging.getLogger(__name__)


async def notify_managers(bot: Bot, text: str, admin_ids: list[int]) -> int:
    """Send an HTML message to every admin/manager; returns how many were reached.

    Shared by the checkout handler and the payment-webhook service (a separate
    process), so admin_ids is passed in rather than read from settings here.
    """
    sent = 0
    for manager_id in admin_ids:
        try:
            await bot.send_message(chat_id=manager_id, text=text, parse_mode="HTML")
            sent += 1
        except Exception as error:
            logger.exception("Failed to notify manager %s: %s", manager_id, error)
    return sent


def format_price_with_ruble(price: int | float | str | None) -> str:
    raw_price = str(price or "").strip()
    if not raw_price:
        return ""
    if "₽" in raw_price:
        return raw_price
    return f"{raw_price} ₽"


def format_total_ruble(total_sum: int) -> str:
    return f"{total_sum:,}".replace(",", " ") + " ₽"


def _extract_numeric_price(price: int | float | str | None) -> int | None:
    if isinstance(price, (int, float)):
        return int(price)

    if not isinstance(price, str):
        return None

    # Admin may save prices like:
    # - "60000"
    # - "10.000 - 12.000"
    # - "80 000 — 120 000 ₽"
    # We should not concatenate both ends of a range into one number.
    # Instead, take the first numeric chunk (typically the lower bound).
    price_str = price.strip()
    match = re.search(r"\d[\d\s\.]*", price_str)
    if not match:
        return None

    token = match.group(0)
    digits = re.sub(r"\D", "", token)  # remove spaces/dots/currency
    if not digits:
        return None

    return int(digits)


def _resolve_item_icon(category_name: str, model_name: str) -> str:
    category_lower = category_name.lower()
    model_lower = model_name.lower()
    lookup_text = f"{category_lower} {model_lower}"

    if "iphone" in lookup_text:
        return "📱"
    if "macbook" in lookup_text or "mac" in lookup_text:
        return "💻"
    if "ipad" in lookup_text:
        return "🖥"
    if "watch" in lookup_text:
        return "⌚️"
    if "airpods" in lookup_text or "науш" in lookup_text:
        return "🎧"
    if "мыш" in lookup_text or "mouse" in lookup_text:
        return "🖱"
    if "клав" in lookup_text or "keyboard" in lookup_text:
        return "⌨️"
    if "playstation" in lookup_text or "xbox" in lookup_text or "game" in lookup_text:
        return "🎮"
    return "📱"


def calculate_cart_total(cart_items: list[dict]) -> int:
    """Sum numeric prices from cart items."""
    total = 0
    for item in cart_items:
        numeric = _extract_numeric_price(item.get("price"))
        if numeric is not None:
            total += numeric
    return total


def build_cart_text(cart_items: list[dict], locale: TranslatorRunner) -> str:
    """Build user-friendly cart text with total sum."""
    if not cart_items:
        return locale.cart_empty()

    total_sum = 0
    has_numeric_prices = False
    lines: list[str] = [locale.cart_header(), ""]

    for index, item in enumerate(cart_items, start=1):
        model_name = item.get("model_name") or item.get("model", locale.unknown_model())
        category_name = str(item.get("category_name", ""))
        price = item.get("price", 0)
        display_price = format_price_with_ruble(price)
        icon = _resolve_item_icon(category_name, model_name)
        lines.append(
            locale.cart_item_line(
                index=index,
                icon=icon,
                model_name=html.escape(str(model_name)),
                price=html.escape(display_price),
            )
        )
        numeric_price = _extract_numeric_price(price)
        if numeric_price is not None:
            total_sum += numeric_price
            has_numeric_prices = True

    if has_numeric_prices:
        lines.append("")
        lines.append(locale.cart_total(total_sum=format_total_ruble(total_sum)))
    return "\n".join(lines)


def build_manager_order_text(
    cart_items: list[dict],
    locale: TranslatorRunner,
    full_name: str,
    username: str | None,
    user_id: int,
) -> str:
    username_text = f"@{username}" if username else locale.manager_order_username_missing()
    cart_items_text = build_cart_text(cart_items, locale)
    return locale.manager_order_text(
        full_name=html.escape(full_name or ""),
        username=html.escape(username_text),
        user_id=user_id,
        cart_items=cart_items_text,
    )


def build_manager_product_request_text(
    locale: TranslatorRunner,
    full_name: str,
    username: str | None,
    user_id: int,
    model_name: str,
    price: int | float | str,
) -> str:
    username_text = f"@{username}" if username else locale.manager_order_username_missing()
    return locale.manager_product_request_text(
        full_name=html.escape(full_name or ""),
        username=html.escape(username_text),
        user_id=user_id,
        model_name=html.escape(str(model_name)),
        price=html.escape(format_price_with_ruble(price)),
    )
