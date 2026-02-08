from aiogram import Router
from aiogram.types import Message
from bot.keyboards.inline import main_menu

router = Router()


@router.message()
async def fallback_message(message: Message):
    """Ловит все сообщения, не попавшие в другие хэндлеры."""
    await message.answer(
        "🤖 Я не понял команду.\n\n"
        "Воспользуйтесь меню или нажмите /help для справки.",
        reply_markup=main_menu(),
    )
