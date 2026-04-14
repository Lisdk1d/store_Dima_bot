from fluentogram import TranslatorRunner


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


def build_cart_text(cart_items: list[dict], locale: TranslatorRunner) -> str:
    """Build user-friendly cart text with total sum."""
    if not cart_items:
        return locale.cart_empty()

    total_sum = 0
    lines: list[str] = [locale.cart_header(), ""]

    for index, item in enumerate(cart_items, start=1):
        model_name = item.get("model_name") or item.get("model", locale.unknown_model())
        category_name = str(item.get("category_name", ""))
        price = item.get("price", 0)
        icon = _resolve_item_icon(category_name, model_name)
        lines.append(locale.cart_item_line(index=index, icon=icon, model_name=model_name, price=price))
        total_sum += price if isinstance(price, (int, float)) else 0

    lines.append("")
    lines.append(locale.cart_total(total_sum=total_sum))
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
        full_name=full_name,
        username=username_text,
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
        full_name=full_name,
        username=username_text,
        user_id=user_id,
        model_name=model_name,
        price=price,
    )
