def build_cart_text(cart_items: list[dict]) -> str:
    """Build user-friendly cart text with total sum."""
    if not cart_items:
        return "🛒 <b>Ваша корзина пуста</b>"

    total_sum = 0
    lines: list[str] = ["<b>🛒 Содержимое корзины:</b>", ""]

    for index, item in enumerate(cart_items, start=1):
        model_name = item.get("model_name") or item.get("model", "Неизвестно")
        price = item.get("price", 0)
        lines.append(f"{index}. 🔹 {model_name} — <code>{price} руб.</code>")
        total_sum += price if isinstance(price, (int, float)) else 0

    lines.append("")
    lines.append(f"<b>💰 Итого к оплате: {total_sum} руб.</b>")
    return "\n".join(lines)
