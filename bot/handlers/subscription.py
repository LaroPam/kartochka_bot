import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.database.db import set_subscription, get_active_subscription
from bot.keyboards.inline import confirm_buy_kb, main_menu, back_kb
from bot.config import config

logger = logging.getLogger(__name__)
router = Router()

# ── Покупка подписки ──
# На старте используем ручное подтверждение (админ активирует).
# Позже можно подключить ЮKassa / Telegram Payments.

PAYMENT_INFO = """💳 <b>Оплата подписки «{plan_name}»</b>

Стоимость: <b>{price} ₽/мес</b>

Для оплаты:
1. Переведите <b>{price} ₽</b> на карту:
   <code>1234 5678 9012 3456</code> (Сбер, Иванов И.И.)

2. В комментарии к переводу укажите:
   <code>KP-{user_id}</code>

3. После перевода нажмите <b>«Подтвердить оплату»</b>

⏱ Подписка будет активирована в течение 15 минут после проверки."""


@router.callback_query(F.data == "buy_standard")
async def cb_buy_standard(callback: CallbackQuery):
    text = PAYMENT_INFO.format(
        plan_name="Стандарт",
        price=config.price_standard,
        user_id=callback.from_user.id,
    )
    await callback.message.edit_text(
        text, reply_markup=confirm_buy_kb("standard"), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "buy_pro")
async def cb_buy_pro(callback: CallbackQuery):
    text = PAYMENT_INFO.format(
        plan_name="Про",
        price=config.price_pro,
        user_id=callback.from_user.id,
    )
    await callback.message.edit_text(
        text, reply_markup=confirm_buy_kb("pro"), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def cb_confirm_payment(callback: CallbackQuery):
    plan = callback.data.replace("confirm_", "")
    user_id = callback.from_user.id
    plan_name = "Стандарт" if plan == "standard" else "Про"

    # Уведомляем админа
    from bot.main import bot
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"💰 <b>Запрос на оплату</b>\n\n"
                f"Пользователь: {callback.from_user.full_name} (@{callback.from_user.username})\n"
                f"ID: <code>{user_id}</code>\n"
                f"Тариф: {plan_name}\n\n"
                f"Для активации:\n"
                f"<code>/activate {user_id} {plan}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

    await callback.message.edit_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"Тариф: {plan_name}\n"
        f"Как только мы подтвердим оплату, подписка будет активирована.\n"
        f"Обычно это занимает до 15 минут.",
        reply_markup=back_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
