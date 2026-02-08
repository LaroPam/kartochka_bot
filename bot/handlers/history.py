import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.database.db import get_user_generations, get_generation_by_id, count_user_generations
from bot.keyboards.inline import history_kb, card_detail_kb, back_kb

logger = logging.getLogger(__name__)
router = Router()

PER_PAGE = 5


@router.callback_query(F.data.startswith("my_cards:"))
async def cb_my_cards(callback: CallbackQuery):
    uid = callback.from_user.id
    offset = int(callback.data.split(":")[1])
    total = await count_user_generations(uid)

    if total == 0:
        await callback.message.edit_text(
            "📂 <b>Мои карточки</b>\n\n"
            "Пока пусто. Создайте первую карточку — нажмите «Создать карточку» в меню!",
            reply_markup=back_kb(), parse_mode="HTML",
        )
        await callback.answer()
        return

    cards = await get_user_generations(uid, limit=PER_PAGE, offset=offset)
    page = (offset // PER_PAGE) + 1
    total_pages = (total + PER_PAGE - 1) // PER_PAGE

    await callback.message.edit_text(
        f"📂 <b>Мои карточки</b> — {total} шт. (стр. {page}/{total_pages})\n\n"
        f"Нажмите, чтобы просмотреть:",
        reply_markup=history_kb(cards, offset, total),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("show_card:"))
async def cb_show_card(callback: CallbackQuery):
    parts = callback.data.split(":")
    gen_id = int(parts[1])
    offset = int(parts[2]) if len(parts) > 2 else 0
    uid = callback.from_user.id

    card = await get_generation_by_id(gen_id, uid)
    if not card:
        await callback.answer("⚠️ Карточка не найдена", show_alert=True)
        return

    mp_icon = "🟣" if card.get("marketplace") == "Wildberries" else "🔵"
    created = card.get("created_at", "")[:16].replace("T", " ")
    result = card.get("result_text") or "Текст не сохранён"

    header = f"{mp_icon} <b>{card.get('product_name', '—')}</b>\n📅 {created}\n{'─' * 28}\n\n"
    full = header + result

    if len(full) > 4000:
        full = full[:3990] + "\n\n<i>…обрезано</i>"

    await callback.message.edit_text(
        full, reply_markup=card_detail_kb(offset), parse_mode="HTML",
    )
    await callback.answer()
