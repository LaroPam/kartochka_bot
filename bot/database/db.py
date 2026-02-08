import aiosqlite
from datetime import datetime, timedelta
from bot.config import config

DB_PATH = config.db_path


async def init_db():
    """Создание таблиц при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                subscription TEXT DEFAULT 'free',
                sub_expires_at TEXT,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                referral_bonus_days INTEGER DEFAULT 0,
                last_active_at TEXT DEFAULT (datetime('now')),
                inactive_notified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                is_blocked INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                marketplace TEXT,
                category TEXT,
                product_name TEXT,
                result_text TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_gen_user_date
            ON generations(user_id, created_at)
        """)

        # Миграции для существующих БД
        await _migrate(db)
        await db.commit()


async def _migrate(db: aiosqlite.Connection):
    """Добавляет новые колонки если их нет (безопасно для существующих БД)."""
    columns = [
        ("users", "referral_code", "TEXT"),
        ("users", "referred_by", "INTEGER"),
        ("users", "referral_bonus_days", "INTEGER DEFAULT 0"),
        ("users", "last_active_at", "TEXT"),
        ("users", "inactive_notified", "INTEGER DEFAULT 0"),
        ("generations", "result_text", "TEXT"),
    ]
    for table, col, col_type in columns:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except Exception:
            pass


# ── Пользователи ──

def _make_ref_code(user_id: int) -> str:
    import hashlib
    h = hashlib.md5(str(user_id).encode()).hexdigest()[:8]
    return f"KP{h.upper()}"


async def get_or_create_user(
    user_id: int, username: str = "", full_name: str = "",
    referred_by: int | None = None,
) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

        if row:
            await db.execute(
                "UPDATE users SET last_active_at = datetime('now'), inactive_notified = 0 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
            return dict(row)

        ref_code = _make_ref_code(user_id)
        await db.execute(
            """INSERT INTO users
               (user_id, username, full_name, referral_code, referred_by, last_active_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (user_id, username, full_name, ref_code, referred_by),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row)


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_ref_code(ref_code: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE referral_code = ?", (ref_code,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def touch_active(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_active_at = datetime('now'), inactive_notified = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def set_subscription(user_id: int, plan: str, days: int = 30):
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subscription = ?, sub_expires_at = ? WHERE user_id = ?",
            (plan, expires, user_id),
        )
        await db.commit()


async def extend_subscription(user_id: int, extra_days: int):
    user = await get_user(user_id)
    if not user:
        return
    current_plan = user["subscription"]
    current_expires = user["sub_expires_at"]

    if current_plan == "free" or not current_expires:
        await set_subscription(user_id, "pro", extra_days)
    else:
        expires_dt = datetime.fromisoformat(current_expires)
        if expires_dt < datetime.utcnow():
            expires_dt = datetime.utcnow()
        new_expires = (expires_dt + timedelta(days=extra_days)).isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET sub_expires_at = ? WHERE user_id = ?",
                (new_expires, user_id),
            )
            await db.commit()


async def get_active_subscription(user_id: int) -> str:
    user = await get_user(user_id)
    if not user:
        return "free"
    plan = user["subscription"]
    expires = user["sub_expires_at"]
    if plan == "free" or not expires:
        return "free"
    if datetime.fromisoformat(expires) < datetime.utcnow():
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET subscription = 'free', sub_expires_at = NULL WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
        return "free"
    return plan


# ── Рефералы ──

async def count_referrals(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        return (await cursor.fetchone())[0]


async def add_referral_bonus(inviter_id: int, bonus_days: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_bonus_days = referral_bonus_days + ? WHERE user_id = ?",
            (bonus_days, inviter_id),
        )
        await db.commit()
    await extend_subscription(inviter_id, bonus_days)


# ── Генерации ──

async def count_today_generations(user_id: int) -> int:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM generations WHERE user_id = ? AND created_at >= ?",
            (user_id, today),
        )
        return (await cursor.fetchone())[0]


async def count_month_generations(user_id: int) -> int:
    month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM generations WHERE user_id = ? AND created_at >= ?",
            (user_id, month_start),
        )
        return (await cursor.fetchone())[0]


async def log_generation(
    user_id: int,
    marketplace: str,
    category: str,
    product_name: str,
    result_text: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO generations
               (user_id, marketplace, category, product_name, result_text, tokens_in, tokens_out)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, marketplace, category, product_name, result_text, tokens_in, tokens_out),
        )
        await db.commit()
    await touch_active(user_id)


async def get_user_generations(user_id: int, limit: int = 5, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, marketplace, product_name, result_text, created_at
               FROM generations
               WHERE user_id = ? AND result_text IS NOT NULL AND result_text != ''
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def get_generation_by_id(gen_id: int, user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM generations WHERE id = ? AND user_id = ?", (gen_id, user_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def count_user_generations(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM generations WHERE user_id = ? AND result_text IS NOT NULL AND result_text != ''",
            (user_id,),
        )
        return (await cursor.fetchone())[0]


# ── Лимиты ──

async def check_limit(user_id: int) -> tuple[bool, int, int]:
    plan = await get_active_subscription(user_id)
    if plan == "free":
        used = await count_today_generations(user_id)
        limit = config.free_daily_limit
        return used < limit, used, limit
    elif plan == "standard":
        used = await count_month_generations(user_id)
        limit = config.standard_monthly_limit
        return used < limit, used, limit
    elif plan == "pro":
        used = await count_month_generations(user_id)
        limit = config.pro_monthly_limit
        return used < limit, used, limit
    return False, 0, 0


# ── Напоминания ──

async def get_inactive_users(days: int = 3) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT user_id, full_name, last_active_at
               FROM users
               WHERE last_active_at < ?
                 AND inactive_notified = 0
                 AND is_blocked = 0""",
            (cutoff,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def mark_inactive_notified(user_ids: list[int]):
    if not user_ids:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join("?" for _ in user_ids)
        await db.execute(
            f"UPDATE users SET inactive_notified = 1 WHERE user_id IN ({placeholders})",
            user_ids,
        )
        await db.commit()


# ── Статистика ──

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE subscription != 'free'")
        paid_users = (await cursor.fetchone())[0]

        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor = await db.execute("SELECT COUNT(*) FROM generations WHERE created_at >= ?", (today,))
        today_gens = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM generations")
        total_gens = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT SUM(tokens_in), SUM(tokens_out) FROM generations")
        row = await cursor.fetchone()
        total_tokens_in = row[0] or 0
        total_tokens_out = row[1] or 0

        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
        total_referrals = (await cursor.fetchone())[0]

    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "today_gens": today_gens,
        "total_gens": total_gens,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_referrals": total_referrals,
    }
