import openai
import logging
from bot.config import config

logger = logging.getLogger(__name__)

client = openai.AsyncOpenAI(
    api_key=config.openai_api_key,
    base_url=config.openai_base_url,
)

# ── Системные промпты ──

SYSTEM_PROMPT = """Ты — лучший специалист по SEO-оптимизации карточек товаров на маркетплейсах Wildberries и Ozon в России.
У тебя 7 лет опыта, ты знаешь все нюансы алгоритмов ранжирования и поведение покупателей.

ПРАВИЛА ГЕНЕРАЦИИ:
1. Заголовок: главные ключевые слова первыми, до 100 символов (WB) или 150 (Ozon). Без caps lock, без эмодзи.
2. Описание: 500-1000 символов. Каждое предложение несёт пользу. Ключевые слова вплетены естественно. Начинай с главного преимущества.
3. Ключевые слова: 15-25 штук. От высокочастотных к низкочастотным. Включай синонимы и разговорные варианты.
4. Характеристики: только те, что реально влияют на решение о покупке в данной категории.

СТИЛЬ:
- Пиши как для живого человека, не для робота
- Подчёркивай конкретные выгоды, а не абстрактные плюсы
- Используй цифры и факты где возможно
- НЕ пиши «уникальный», «инновационный», «лучший» — это пустые слова
- НЕ начинай описание со слов «Представляем вам» или «Данный товар»"""

QUESTIONS_PROMPT = """Ты помогаешь продавцу на маркетплейсе {marketplace} создать идеальную карточку товара.

Товар: {product_name}

Задай 3-5 коротких вопросов, ответы на которые КРИТИЧЕСКИ важны для создания продающей карточки именно этого товара.

ПРАВИЛА:
- Вопросы должны быть КОНКРЕТНЫМИ для данного товара, а не общими
- Спрашивай о том, что реально влияет на решение покупателя
- НЕ спрашивай название и маркетплейс — это уже известно
- НЕ спрашивай цену — она не входит в карточку
- Пронумеруй вопросы
- Каждый вопрос — 1 строка, коротко и понятно
- В скобках дай пример ответа для удобства

Примеры хороших вопросов:
Для кроссовок: «Материал верха и подошвы? (сетка + пена EVA)»
Для чайника: «Объём и мощность? (1.7л, 2200 Вт)»
Для крема: «Тип кожи и главная проблема? (сухая, шелушение)»"""

GENERATE_PROMPT = """Маркетплейс: {marketplace}
Товар: {product_name}
{details_block}

Сгенерируй карточку товара в следующем формате:

📌 ЗАГОЛОВОК:
[заголовок]

📝 ОПИСАНИЕ:
[описание]

🔑 КЛЮЧЕВЫЕ СЛОВА:
[через запятую]

📋 РЕКОМЕНДУЕМЫЕ ХАРАКТЕРИСТИКИ:
[характеристика: значение — по одной на строку]"""

COMPETITOR_PROMPT = """Проанализируй карточку товара конкурента на {marketplace} и создай улучшенную версию.

Текст карточки конкурента:
---
{competitor_text}
---

Формат ответа:

🔍 АНАЛИЗ:
✅ Что хорошо:
[перечисли 2-3 пункта]

❌ Что плохо:
[перечисли 2-3 пункта]

📌 УЛУЧШЕННЫЙ ЗАГОЛОВОК:
[заголовок]

📝 УЛУЧШЕННОЕ ОПИСАНИЕ:
[описание]

🔑 РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА:
[через запятую]"""

REWRITE_PROMPT = """Перепиши карточку товара в другом стиле. Сохрани все ключевые слова и факты, измени только подачу.

Исходная карточка:
---
{original_text}
---

Новый стиль: {style}
Маркетплейс: {marketplace}

Формат: тот же (заголовок, описание, ключевые слова, характеристики)."""


# ── API-вызовы ──

async def generate_questions(marketplace: str, product_name: str) -> str:
    """Генерация уточняющих вопросов по товару."""
    try:
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {
                    "role": "user",
                    "content": QUESTIONS_PROMPT.format(
                        marketplace=marketplace,
                        product_name=product_name,
                    ),
                }
            ],
            temperature=0.6,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating questions: {e}")
        raise


async def generate_card(
    marketplace: str,
    product_name: str,
    details: str = "",
) -> tuple[str, int, int]:
    """
    Генерация карточки товара.
    Возвращает (текст, токены_вход, токены_выход).
    """
    details_block = ""
    if details:
        details_block = f"Детали от продавца:\n{details}"

    user_prompt = GENERATE_PROMPT.format(
        marketplace=marketplace,
        product_name=product_name,
        details_block=details_block,
    )

    try:
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        text = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        return text, tokens_in, tokens_out

    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_card: {e}")
        raise


async def analyze_competitor(
    competitor_text: str,
    marketplace: str,
) -> tuple[str, int, int]:
    """Анализ карточки конкурента."""
    user_prompt = COMPETITOR_PROMPT.format(
        competitor_text=competitor_text,
        marketplace=marketplace,
    )

    try:
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
        )

        text = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        return text, tokens_in, tokens_out

    except Exception as e:
        logger.error(f"Error in analyze_competitor: {e}")
        raise


async def rewrite_card(
    original_text: str,
    style: str,
    marketplace: str,
) -> tuple[str, int, int]:
    """Перегенерация карточки в другом стиле."""
    user_prompt = REWRITE_PROMPT.format(
        original_text=original_text,
        style=style,
        marketplace=marketplace,
    )

    try:
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=2000,
        )

        text = response.choices[0].message.content
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        return text, tokens_in, tokens_out

    except Exception as e:
        logger.error(f"Error in rewrite_card: {e}")
        raise
