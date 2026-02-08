import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.database.db import check_limit, log_generation, get_active_subscription, touch_active
from bot.services.ai_service import generate_card, analyze_competitor, rewrite_card, generate_questions
from bot.keyboards.inline import (
    marketplace_kb, after_generation_kb, restyle_kb,
    main_menu, back_kb, skip_kb, STYLE_MAP,
)

logger = logging.getLogger(__name__)
router = Router()


class GenStates(StatesGroup):
    choosing_marketplace = State()
    entering_product = State()
    answering_questions = State()
    result = State()
    competitor_marketplace = State()
    entering_competitor_text = State()


# ── Создание карточки ──

@router.callback_query(F.data == "new_card")
async def cb_new_card(callback: CallbackQuery, state: FSMContext):
    await touch_active(callback.from_user.id)
    allowed, used, limit = await check_limit(callback.from_user.id)
    if not allowed:
        plan = await get_active_subscription(callback.from_user.id)
        if plan == "free":
            text = f"⚠️ Лимит исчерпан ({limit} карточки в день).\n\nОформите подписку для увеличения лимита 👇"
        else:
            text = f"⚠️ Лимит на этот месяц исчерпан ({limit} карточек)."
        await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
        await callback.answer()
        return

    await state.clear()
    await state.set_state(GenStates.choosing_marketplace)
    await callback.message.edit_text(
        "🏪 <b>Для какого маркетплейса создаём карточку?</b>",
        reply_markup=marketplace_kb(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(GenStates.choosing_marketplace, F.data.startswith("mp_"))
async def cb_choose_mp(callback: CallbackQuery, state: FSMContext):
    mp = "Wildberries" if callback.data == "mp_wb" else "Ozon"
    await state.update_data(marketplace=mp)
    await state.set_state(GenStates.entering_product)
    await callback.message.edit_text(
        f"🏪 <b>{mp}</b>\n\n"
        f"📦 <b>Что за товар?</b>\n\n"
        f"Напишите название как можно подробнее.\n\n"
        f"<i>Примеры:\n"
        f"• Кроссовки женские беговые Nike Air Max 90\n"
        f"• Набор кастрюль с антипригарным покрытием 5 шт\n"
        f"• Сыворотка для лица с витамином С 30 мл</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GenStates.entering_product)
async def msg_enter_product(message: Message, state: FSMContext):
    product = message.text.strip()
    if len(product) < 3:
        await message.answer("⚠️ Слишком короткое название. Опишите товар подробнее.")
        return
    if len(product) > 500:
        await message.answer("⚠️ Слишком длинно. Сократите до 500 символов.")
        return

    await state.update_data(product_name=product)
    data = await state.get_data()

    wait_msg = await message.answer("🤔 <b>Анализирую товар, подбираю вопросы...</b>", parse_mode="HTML")

    try:
        questions = await generate_questions(data["marketplace"], product)
        await state.update_data(ai_questions=questions)
        await state.set_state(GenStates.answering_questions)
        await wait_msg.delete()
        await message.answer(
            f"📦 <b>{product}</b>\n\n"
            f"Ответьте на вопросы, чтобы карточка получилась точнее:\n\n"
            f"{questions}\n\n"
            f"💬 <b>Напишите ответы в свободной форме</b> — можно коротко, главное по сути.",
            reply_markup=skip_kb(), parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Questions error: {e}")
        await wait_msg.delete()
        await state.set_state(GenStates.answering_questions)
        await message.answer(
            f"📦 <b>{product}</b>\n\n"
            f"Расскажите подробности о товаре:\n"
            f"<i>Материал, размеры, цвет, для кого, чем лучше конкурентов...</i>",
            reply_markup=skip_kb(), parse_mode="HTML",
        )


@router.callback_query(GenStates.answering_questions, F.data == "skip_questions")
async def cb_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _do_generation(callback.message, callback.from_user.id, state, "")


@router.message(GenStates.answering_questions)
async def msg_answers(message: Message, state: FSMContext):
    answers = message.text.strip()
    if len(answers) > 3000:
        await message.answer("⚠️ Слишком длинно. Сократите до 3000 символов.")
        return
    await _do_generation(message, message.from_user.id, state, answers)


async def _do_generation(message: Message, user_id: int, state: FSMContext, answers: str):
    allowed, _, _ = await check_limit(user_id)
    if not allowed:
        await message.answer("⚠️ Лимит исчерпан.", reply_markup=back_kb())
        await state.clear()
        return

    data = await state.get_data()
    wait_msg = await message.answer(
        "⏳ <b>Генерирую карточку...</b>\n<i>10-20 секунд</i>", parse_mode="HTML"
    )

    try:
        text, tokens_in, tokens_out = await generate_card(
            marketplace=data["marketplace"],
            product_name=data["product_name"],
            details=answers,
        )

        # Сохраняем с текстом результата для истории
        await log_generation(
            user_id=user_id,
            marketplace=data["marketplace"],
            category="",
            product_name=data["product_name"],
            result_text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

        await state.update_data(last_result=text, details=answers)
        await state.set_state(GenStates.result)
        await wait_msg.delete()

        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                chunk = text[i:i + 4000]
                if i + 4000 >= len(text):
                    await message.answer(chunk, reply_markup=after_generation_kb())
                else:
                    await message.answer(chunk)
        else:
            await message.answer(text, reply_markup=after_generation_kb())

    except Exception as e:
        logger.error(f"Generation error for {user_id}: {e}")
        await wait_msg.delete()
        await message.answer(
            "❌ <b>Ошибка генерации.</b> Попробуйте через несколько секунд.",
            reply_markup=main_menu(), parse_mode="HTML",
        )
        await state.clear()


# ── Перегенерация ──

@router.callback_query(F.data == "regenerate")
async def cb_regenerate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("product_name"):
        await callback.message.edit_text("⚠️ Нет данных для перегенерации.", reply_markup=main_menu())
        await callback.answer()
        return

    allowed, _, _ = await check_limit(callback.from_user.id)
    if not allowed:
        await callback.answer("⚠️ Лимит исчерпан", show_alert=True)
        return

    await callback.answer("⏳ Генерирую...")
    wait_msg = await callback.message.answer("⏳ <b>Генерирую другой вариант...</b>", parse_mode="HTML")

    try:
        text, tokens_in, tokens_out = await generate_card(
            marketplace=data["marketplace"],
            product_name=data["product_name"],
            details=data.get("details", ""),
        )
        await log_generation(
            user_id=callback.from_user.id,
            marketplace=data["marketplace"], category="",
            product_name=data["product_name"],
            result_text=text,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        await state.update_data(last_result=text)
        await wait_msg.delete()
        await callback.message.answer(text, reply_markup=after_generation_kb())
    except Exception as e:
        logger.error(f"Regen error: {e}")
        await wait_msg.delete()
        await callback.message.answer("❌ Ошибка. Попробуйте ещё раз.", reply_markup=main_menu())


# ── Стили ──

@router.callback_query(F.data == "restyle")
async def cb_restyle(callback: CallbackQuery, state: FSMContext):
    plan = await get_active_subscription(callback.from_user.id)
    if plan == "free":
        await callback.answer("💎 Смена стиля доступна на тарифе Стандарт+", show_alert=True)
        return
    await callback.message.edit_text("✨ <b>Выберите стиль:</b>", reply_markup=restyle_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("style_"))
async def cb_style(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last = data.get("last_result")
    if not last:
        await callback.answer("⚠️ Нет карточки", show_alert=True)
        return
    allowed, _, _ = await check_limit(callback.from_user.id)
    if not allowed:
        await callback.answer("⚠️ Лимит исчерпан", show_alert=True)
        return

    style = STYLE_MAP.get(callback.data, "Нейтральный")
    await callback.answer("⏳ Применяю стиль...")
    wait_msg = await callback.message.answer("⏳ <b>Переписываю...</b>", parse_mode="HTML")

    try:
        text, tokens_in, tokens_out = await rewrite_card(last, style, data.get("marketplace", "Wildberries"))
        await log_generation(
            user_id=callback.from_user.id,
            marketplace=data.get("marketplace", ""), category="",
            product_name=data.get("product_name", ""),
            result_text=text,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        await state.update_data(last_result=text)
        await wait_msg.delete()
        await callback.message.answer(text, reply_markup=after_generation_kb())
    except Exception as e:
        logger.error(f"Restyle error: {e}")
        await wait_msg.delete()
        await callback.message.answer("❌ Ошибка.", reply_markup=main_menu())


# ── Анализ конкурента ──

@router.callback_query(F.data == "analyze")
async def cb_analyze(callback: CallbackQuery, state: FSMContext):
    plan = await get_active_subscription(callback.from_user.id)
    if plan == "free":
        await callback.answer("💎 Анализ конкурентов — тариф Стандарт+", show_alert=True)
        return
    allowed, _, _ = await check_limit(callback.from_user.id)
    if not allowed:
        await callback.answer("⚠️ Лимит исчерпан", show_alert=True)
        return
    await state.clear()
    await state.set_state(GenStates.competitor_marketplace)
    await callback.message.edit_text(
        "🔍 <b>Анализ карточки конкурента</b>\n\nВыберите маркетплейс:",
        reply_markup=marketplace_kb(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(GenStates.competitor_marketplace, F.data.startswith("mp_"))
async def cb_comp_mp(callback: CallbackQuery, state: FSMContext):
    mp = "Wildberries" if callback.data == "mp_wb" else "Ozon"
    await state.update_data(marketplace=mp)
    await state.set_state(GenStates.entering_competitor_text)
    await callback.message.edit_text(
        f"🏪 <b>{mp}</b>\n\n📋 Скопируйте и отправьте <b>заголовок и описание</b> карточки конкурента:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GenStates.entering_competitor_text)
async def msg_comp_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 20:
        await message.answer("⚠️ Текст слишком короткий.")
        return
    if len(text) > 5000:
        await message.answer("⚠️ Максимум 5000 символов.")
        return

    data = await state.get_data()
    wait_msg = await message.answer("⏳ <b>Анализирую...</b>", parse_mode="HTML")

    try:
        result, tokens_in, tokens_out = await analyze_competitor(text, data["marketplace"])
        await log_generation(
            user_id=message.from_user.id,
            marketplace=data["marketplace"], category="анализ",
            product_name="конкурент",
            result_text=result,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        await state.update_data(last_result=result)
        await state.set_state(GenStates.result)
        await wait_msg.delete()
        await message.answer(result, reply_markup=after_generation_kb())
    except Exception as e:
        logger.error(f"Competitor error: {e}")
        await wait_msg.delete()
        await message.answer("❌ Ошибка анализа.", reply_markup=main_menu())
        await state.clear()
