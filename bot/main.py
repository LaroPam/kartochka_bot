import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import config
from bot.database.db import init_db
from bot.middlewares.throttle import ThrottleMiddleware
from bot.services.scheduler import send_inactive_reminders

from bot.handlers.start import router as start_router
from bot.handlers.generate import router as generate_router
from bot.handlers.history import router as history_router
from bot.handlers.subscription import router as subscription_router
from bot.handlers.admin import router as admin_router
from bot.handlers.fallback import router as fallback_router

bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode="HTML"),
)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logger = logging.getLogger(__name__)

    await init_db()
    logger.info("Database initialized")

    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ThrottleMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottleMiddleware(rate_limit=0.5))

    dp.include_router(start_router)
    dp.include_router(generate_router)
    dp.include_router(history_router)
    dp.include_router(subscription_router)
    dp.include_router(admin_router)
    dp.include_router(fallback_router)  # последним

    # ── Планировщик: напоминания неактивным каждые 6 часов ──
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_inactive_reminders,
        "interval",
        hours=6,
        args=[bot, config.free_daily_limit],
        id="inactive_reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (reminders every 6h)")

    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
