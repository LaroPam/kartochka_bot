import logging
from aiogram import Bot
from bot.database.db import get_inactive_users, mark_inactive_notified

logger = logging.getLogger(__name__)

REMINDER_TEXT = """👋 Давно вас не видели!

У вас есть <b>{limit}</b> бесплатных карточек — самое время создать новую.

За время вашего отсутствия мы улучшили качество генерации. Попробуйте — результат вас приятно удивит!

Нажмите /menu, чтобы начать."""


async def send_inactive_reminders(bot: Bot, free_daily_limit: int = 3):
    """
    Отправляет напоминания пользователям, неактивным 3+ дня.
    Вызывается планировщиком раз в 6 часов.
    """
    users = await get_inactive_users(days=3)

    if not users:
        return

    logger.info(f"Sending reminders to {len(users)} inactive users")

    sent_ids = []
    for user in users:
        try:
            await bot.send_message(
                user["user_id"],
                REMINDER_TEXT.format(limit=free_daily_limit),
                parse_mode="HTML",
            )
            sent_ids.append(user["user_id"])
        except Exception as e:
            # Пользователь заблокировал бота — помечаем как уведомлённого
            logger.debug(f"Could not send reminder to {user['user_id']}: {e}")
            sent_ids.append(user["user_id"])

    await mark_inactive_notified(sent_ids)
    logger.info(f"Reminders sent: {len(sent_ids)}")
