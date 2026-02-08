from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Создать карточку", callback_data="new_card")],
        [InlineKeyboardButton(text="🔍 Анализ конкурента", callback_data="analyze")],
        [
            InlineKeyboardButton(text="📂 Мои карточки", callback_data="my_cards:0"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="🎁 Пригласить друга", callback_data="referral"),
            InlineKeyboardButton(text="💎 Тарифы", callback_data="pricing"),
        ],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])


def marketplace_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟣 Wildberries", callback_data="mp_wb"),
            InlineKeyboardButton(text="🔵 Ozon", callback_data="mp_ozon"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Пропустить — без деталей", callback_data="skip_questions")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_main")],
    ])


def after_generation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Другой вариант", callback_data="regenerate"),
            InlineKeyboardButton(text="✨ Сменить стиль", callback_data="restyle"),
        ],
        [InlineKeyboardButton(text="🛍 Новая карточка", callback_data="new_card")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
    ])


def restyle_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👑 Премиум", callback_data="style_premium"),
            InlineKeyboardButton(text="💰 Бюджетный", callback_data="style_budget"),
        ],
        [
            InlineKeyboardButton(text="🔥 Молодёжный", callback_data="style_young"),
            InlineKeyboardButton(text="📋 Деловой", callback_data="style_business"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


STYLE_MAP = {
    "style_premium": "Премиальный, люксовый — подчёркивай качество, эксклюзивность, статус.",
    "style_budget": "Бюджетный — акцент на выгоде, соотношении цена/качество, экономии.",
    "style_young": "Молодёжный — лёгкий, трендовый, динамичный. Короткие предложения.",
    "style_business": "Деловой — строгий, фактический, без эмоций. Только характеристики и цифры.",
}


def history_kb(cards: list[dict], offset: int, total: int) -> InlineKeyboardMarkup:
    """Список карточек с пагинацией по 5 шт."""
    keyboard = []
    for card in cards:
        created = card["created_at"][:10] if card.get("created_at") else ""
        mp_icon = "🟣" if card.get("marketplace") == "Wildberries" else "🔵"
        name = card.get("product_name", "")
        if len(name) > 30:
            name = name[:30] + "…"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{mp_icon} {name}  •  {created}",
                callback_data=f"show_card:{card['id']}:{offset}",
            )
        ])

    nav_row = []
    if offset > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"my_cards:{offset - 5}"))
    if offset + 5 < total:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"my_cards:{offset + 5}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def card_detail_kb(offset: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К списку", callback_data=f"my_cards:{offset}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")],
    ])


def pricing_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Стандарт — 490 ₽/мес", callback_data="buy_standard")],
        [InlineKeyboardButton(text="💎 Про — 990 ₽/мес", callback_data="buy_pro")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def confirm_buy_kb(plan: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{plan}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="pricing")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])
