import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, CallbackQuery
from bot.database.db import (
    get_or_create_user, get_active_subscription,
    count_today_generations, count_month_generations,
    get_user, get_user_by_ref_code, count_referrals,
    add_referral_bonus, touch_active,
)
from bot.keyboards.inline import main_menu, pricing_kb, back_kb
from bot.config import config

logger = logging.getLogger(__name__)
router = Router()

WELCOME_TEXT = """👋 <b>Привет! Я КарточкаPRO</b>

Создаю продающие карточки товаров для <b>Wildberries</b> и <b>Ozon</b> за секунды с помощью AI.

Что я умею:
🔹 SEO-заголовки, которые выводят товар в топ
🔹 Продающие описания с ключевыми словами
🔹 Подбор ключевых слов и характеристик
🔹 Анализ и улучшение карточек конкурентов

Нажмите <b>«Создать карточку»</b>, чтобы попробовать 👇"""

HELP_TEXT = """❓ <b>Как пользоваться ботом</b>

<b>Создание карточки:</b>
1. Нажмите «Создать карточку»
2. Выберите маркетплейс (WB или Ozon)
3. Введите название товара
4. Ответьте на уточняющие вопросы (или пропустите)
5. Получите готовую карточку!

<b>После генерации можно:</b>
🔄 <b>Другой вариант</b> — новая версия карточки
✨ <b>Сменить стиль</b> — премиум, бюджетный, молодёжный, деловой

<b>📂 Мои карточки</b> — все генерации сохраняются

<b>🎁 Пригласить друга</b> — 3 дня Pro за каждого!

<b>Тарифы:</b>
🆓 Бесплатно — {free_limit} карточки в день
⭐ Стандарт ({price_std} ₽/мес) — {std_limit} карточек + анализ + стили
💎 Про ({price_pro} ₽/мес) — безлимит

<b>Команды:</b>  /start · /menu · /help"""


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_ref(message: Message, command: CommandObject):
    """Запуск с реферальной ссылкой: /start KP1A2B3C4D"""
    user = message.from_user
    ref_code = command.args

    existing = await get_user(user.id)
    inviter_id = None

    if not existing and ref_code:
        inviter = await get_user_by_ref_code(ref_code)
        if inviter and inviter["user_id"] != user.id:
            inviter_id = inviter["user_id"]

    await get_or_create_user(
        user.id, user.username or "", user.full_name or "",
        referred_by=inviter_id,
    )

    if inviter_id and not existing:
        try:
            await add_referral_bonus(inviter_id, bonus_days=3)
            from bot.main import bot
            ref_count = await count_referrals(inviter_id)
            await bot.send_message(
                inviter_id,
                f"🎉 <b>По вашей ссылке пришёл новый пользователь!</b>\n\n"
                f"Вам начислено <b>+3 дня Pro</b>.\n"
                f"Всего приглашено: {ref_count} чел.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Error notifying inviter {inviter_id}: {e}")

    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await get_or_create_user(user.id, user.username or "", user.full_name or "")
    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await touch_active(message.from_user.id)
    await message.answer("📋 <b>Главное меню</b>", reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = HELP_TEXT.format(
        free_limit=config.free_daily_limit,
        price_std=config.price_standard,
        std_limit=config.standard_monthly_limit,
        price_pro=config.price_pro,
    )
    await message.answer(text, reply_markup=back_kb(), parse_mode="HTML")


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    text = HELP_TEXT.format(
        free_limit=config.free_daily_limit,
        price_std=config.price_standard,
        std_limit=config.standard_monthly_limit,
        price_pro=config.price_pro,
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Главное меню</b>", reply_markup=main_menu(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    uid = callback.from_user.id
    plan = await get_active_subscription(uid)
    today = await count_today_generations(uid)
    month = await count_month_generations(uid)
    refs = await count_referrals(uid)
    user = await get_user(uid)

    plan_names = {"free": "🆓 Бесплатный", "standard": "⭐ Стандарт", "pro": "💎 Про"}
    plan_name = plan_names.get(plan, plan)

    if plan == "free":
        limit_text = f"Сегодня: {today}/{config.free_daily_limit}"
    elif plan == "standard":
        limit_text = f"В этом месяце: {month}/{config.standard_monthly_limit}"
    else:
        limit_text = f"В этом месяце: {month} (безлимит)"

    expires = ""
    if plan != "free" and user and user.get("sub_expires_at"):
        expires = f"\nПодписка до: {user['sub_expires_at'][:10]}"

    bonus = user.get("referral_bonus_days", 0) if user else 0

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"Тариф: {plan_name}{expires}\n"
        f"Карточек: {limit_text}\n\n"
        f"👥 Приглашено друзей: {refs}\n"
        f"🎁 Бонусных дней Pro: {bonus}"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "pricing")
async def cb_pricing(callback: CallbackQuery):
    text = (
        "💎 <b>Тарифы КарточкаPRO</b>\n\n"
        f"🆓 <b>Бесплатный</b>\n"
        f"• {config.free_daily_limit} карточки в день\n"
        f"• Базовая генерация\n\n"
        f"⭐ <b>Стандарт — {config.price_standard} ₽/мес</b>\n"
        f"• {config.standard_monthly_limit} карточек в месяц\n"
        f"• Анализ конкурентов\n"
        f"• 4 стиля подачи\n\n"
        f"💎 <b>Про — {config.price_pro} ₽/мес</b>\n"
        f"• Безлимит карточек\n"
        f"• Всё из Стандарта\n"
        f"• Приоритетная генерация"
    )
    await callback.message.edit_text(text, reply_markup=pricing_kb(), parse_mode="HTML")
    await callback.answer()


# ── Реферальная программа ──

@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    ref_code = user.get("referral_code", "")
    refs = await count_referrals(callback.from_user.id)
    bonus = user.get("referral_bonus_days", 0)

    from bot.main import bot
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={ref_code}"

    text = (
        f"🎁 <b>Пригласите друга — получите Pro!</b>\n\n"
        f"За каждого нового пользователя по вашей ссылке "
        f"вы получаете <b>3 дня Pro</b> бесплатно.\n\n"
        f"Ваша ссылка:\n"
        f"<code>{link}</code>\n\n"
        f"👥 Приглашено: <b>{refs}</b>\n"
        f"🎁 Бонусов: <b>{bonus}</b> дней\n\n"
        f"<i>Нажмите на ссылку, чтобы скопировать</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer()
