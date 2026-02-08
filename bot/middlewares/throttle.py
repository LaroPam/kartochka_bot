import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class ThrottleMiddleware(BaseMiddleware):
    """Простой антиспам: 1 запрос в секунду на пользователя."""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.user_last_request: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            now = time.monotonic()
            last = self.user_last_request.get(user.id, 0)
            if now - last < self.rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ Подождите секунду...", show_alert=False)
                return
            self.user_last_request[user.id] = now

            # Чистим старые записи каждые 1000 запросов
            if len(self.user_last_request) > 10000:
                cutoff = now - 60
                self.user_last_request = {
                    uid: t for uid, t in self.user_last_request.items() if t > cutoff
                }

        return await handler(event, data)
