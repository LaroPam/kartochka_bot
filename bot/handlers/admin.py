import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.database.db import set_subscription, get_stats, get_user
from bot.config import config

logger = logging.getLogger(__name__)
router = Router()


def is_admin(uid: int) -> bool:
    return uid in config.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = await get_stats()

    cost_in = s["total_tokens_in"] / 1_000_000 * 65
    cost_out = s["total_tokens_out"] / 1_000_000 * 516
    total_cost = cost_in + cost_out

    text = (
        "📊 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{s['total_users']}</b>\n"
        f"💎 Платных: <b>{s['paid_users']}</b>\n"
        f"👥 Пришли по рефералу: <b>{s['total_referrals']}</b>\n"
        f"📝 Генераций сегодня: <b>{s['today_gens']}</b>\n"
        f"📝 Генераций всего: <b>{s['total_gens']}</b>\n\n"
        f"🔤 Токены: {s['total_tokens_in']:,} → {s['total_tokens_out']:,}\n"
        f"💰 Расход API: ≈ <b>{total_cost:.0f} ₽</b>\n\n"
        f"/activate <code>user_id plan</code>\n"
        f"/userinfo <code>user_id</code>\n"
        f"/broadcast <code>текст</code>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("activate"))
async def cmd_activate(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /activate user_id plan\nplan: standard, pro, free")
        return
    try:
        uid = int(parts[1])
        plan = parts[2]
    except ValueError:
        await message.answer("⚠️ Некорректный user_id")
        return
    if plan not in ("standard", "pro", "free"):
        await message.answer("⚠️ plan: standard / pro / free")
        return

    user = await get_user(uid)
    if not user:
        await message.answer("⚠️ Пользователь не найден")
        return

    if plan == "free":
        await set_subscription(uid, "free", 0)
    else:
        await set_subscription(uid, plan, 30)

    names = {"free": "Бесплатный", "standard": "Стандарт", "pro": "Про"}
    await message.answer(f"✅ <b>{names[plan]}</b> активирован для {uid}", parse_mode="HTML")

    from bot.main import bot
    try:
        await bot.send_message(
            uid,
            f"🎉 <b>Подписка «{names[plan]}» активирована!</b>\nСрок: 30 дней\n\n/menu",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /userinfo user_id")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("⚠️ Некорректный user_id")
        return
    user = await get_user(uid)
    if not user:
        await message.answer("⚠️ Не найден")
        return
    text = (
        f"👤 ID: <code>{user['user_id']}</code>\n"
        f"Username: @{user['username'] or '—'}\n"
        f"Имя: {user['full_name'] or '—'}\n"
        f"Тариф: {user['subscription']}\n"
        f"До: {user['sub_expires_at'] or '—'}\n"
        f"Реф.код: <code>{user.get('referral_code', '—')}</code>\n"
        f"Приглашён: {user.get('referred_by') or '—'}\n"
        f"Бонусов: {user.get('referral_bonus_days', 0)} дней\n"
        f"Рег.: {user['created_at']}\n"
        f"Активен: {user.get('last_active_at', '—')}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("Формат: /broadcast текст")
        return

    from bot.main import bot
    import aiosqlite
    sent = failed = 0
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE is_blocked = 0")
        rows = await cursor.fetchall()
    for row in rows:
        try:
            await bot.send_message(row[0], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"📨 Доставлено: {sent} · Ошибок: {failed}")
