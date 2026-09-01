import asyncpg
from datetime import date
from typing import List, Dict, Optional, Any
from config import DATABASE_URL


class Database:
    """Класс для работы с PostgreSQL"""

    def __init__(self):
        self.pool = None

    async def connect(self):
        """Создает пул соединений с БД"""
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        await self._init_tables()

    async def _init_tables(self):
        """Создает таблицы, если их нет"""
        async with self.pool.acquire() as conn:
            # Таблица users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(64),
                    first_name VARCHAR(100),
                    company_name VARCHAR(200),
                    default_law VARCHAR(10) DEFAULT '44-FZ',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица suppliers
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    inn VARCHAR(12),
                    name VARCHAR(200) NOT NULL,
                    contact_person VARCHAR(100),
                    phone VARCHAR(20),
                    price NUMERIC(15, 2),
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, inn)
                )
            """)

            # Таблица customer_settings (223-ФЗ)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS customer_settings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    setting_name VARCHAR(100) NOT NULL,
                    bid_submission_days INTEGER NOT NULL CHECK (bid_submission_days > 0),
                    bid_review_days INTEGER NOT NULL CHECK (bid_review_days > 0),
                    auction_delay_days INTEGER DEFAULT 2 CHECK (auction_delay_days >= 0),
                    signing_days INTEGER DEFAULT 5 CHECK (signing_days > 0),
                    bg_days_before_signing INTEGER DEFAULT 5 CHECK (bg_days_before_signing >= 0),
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, setting_name)
                )
            """)

            # Таблица procurements
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS procurements (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title VARCHAR(255) NOT NULL,
                    law_type VARCHAR(10) NOT NULL CHECK (law_type IN ('44-FZ', '223-FZ')),
                    nmck NUMERIC(15, 2) NOT NULL,
                    selected_supplier_ids INTEGER[] NOT NULL,
                    customer_setting_id INTEGER REFERENCES customer_settings(id) ON DELETE SET NULL,
                    custom_bid_days INTEGER CHECK (custom_bid_days > 0),
                    custom_review_days INTEGER CHECK (custom_review_days > 0),
                    publication_date DATE NOT NULL,
                    bid_end_date DATE NOT NULL,
                    consideration_date DATE,
                    auction_date DATE,
                    signing_date DATE NOT NULL,
                    bg_deadline_date DATE,
                    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'archived')),
                    final_pdf_path TEXT,
                    scatter_warning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица procurement_timeline
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS procurement_timeline (
                    id SERIAL PRIMARY KEY,
                    procurement_id INTEGER NOT NULL REFERENCES procurements(id) ON DELETE CASCADE,
                    revision_number INTEGER NOT NULL,
                    shift_days INTEGER DEFAULT 0,
                    applied_bid_days INTEGER NOT NULL,
                    applied_review_days INTEGER NOT NULL,
                    applied_signing_days INTEGER NOT NULL,
                    publication_date DATE NOT NULL,
                    bid_end_date DATE NOT NULL,
                    consideration_date DATE,
                    auction_date DATE,
                    signing_date DATE NOT NULL,
                    bg_deadline_date DATE,
                    risk_warning TEXT,
                    is_final BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Индексы
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_user_id ON procurements(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_timeline_procurement_id ON procurement_timeline(procurement_id)")

    # -------- USERS --------
    async def get_or_create_user(self, telegram_id: int, username: str = None, first_name: str = None) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", telegram_id
            )
            if row:
                user_id = row["id"]
                await conn.execute(
                    "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE id = $1",
                    user_id
                )
                return user_id
            else:
                row = await conn.fetchrow(
                    """INSERT INTO users (telegram_id, username, first_name) 
                       VALUES ($1, $2, $3) RETURNING id""",
                    telegram_id, username, first_name
                )
                return row["id"]

    # -------- CUSTOMER SETTINGS (223-ФЗ) --------
    async def get_settings(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM customer_settings WHERE user_id = $1 ORDER BY is_default DESC, created_at",
                user_id
            )
            return [dict(row) for row in rows]

    async def get_default_settings(self, user_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM customer_settings WHERE user_id = $1 AND is_default = TRUE",
                user_id
            )
            return dict(row) if row else None

    async def create_settings(self, user_id: int, name: str, bid_days: int, review_days: int,
                              auction_delay: int = 2, signing_days: int = 5, bg_days: int = 5,
                              is_default: bool = False) -> int:
        async with self.pool.acquire() as conn:
            if is_default:
                await conn.execute(
                    "UPDATE customer_settings SET is_default = FALSE WHERE user_id = $1",
                    user_id
                )
            row = await conn.fetchrow(
                """INSERT INTO customer_settings 
                   (user_id, setting_name, bid_submission_days, bid_review_days, 
                    auction_delay_days, signing_days, bg_days_before_signing, is_default)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id""",
                user_id, name, bid_days, review_days, auction_delay, signing_days, bg_days, is_default
            )
            return row["id"]

    # -------- SUPPLIERS --------
    async def get_or_create_supplier(self, user_id: int, name: str, inn: str = None,
                                     price: float = None, note: str = None) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM suppliers WHERE user_id = $1 AND inn = $2",
                user_id, inn
            )
            if row:
                return row["id"]
            else:
                row = await conn.fetchrow(
                    """INSERT INTO suppliers (user_id, inn, name, price, note) 
                       VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                    user_id, inn, name, price, note
                )
                return row["id"]

    async def get_suppliers_by_ids(self, supplier_ids: List[int]) -> List[Dict]:
        if not supplier_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM suppliers WHERE id = ANY($1::int[])", supplier_ids
            )
            return [dict(row) for row in rows]

    # -------- PROCUREMENTS --------
    async def create_procurement(self, user_id: int, data: Dict) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO procurements 
                   (user_id, title, law_type, nmck, selected_supplier_ids, 
                    customer_setting_id, custom_bid_days, custom_review_days,
                    publication_date, bid_end_date, consideration_date, 
                    auction_date, signing_date, bg_deadline_date, scatter_warning)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                   RETURNING id""",
                user_id,
                data.get("title"),
                data.get("law_type"),
                data.get("nmck"),
                data.get("supplier_ids", []),
                data.get("setting_id"),
                data.get("custom_bid_days"),
                data.get("custom_review_days"),
                data.get("publication_date"),
                data.get("bid_end_date"),
                data.get("consideration_date"),
                data.get("auction_date"),
                data.get("signing_date"),
                data.get("bg_deadline_date"),
                data.get("scatter_warning")
            )
            return row["id"]

    async def update_procurement(self, procurement_id: int, data: Dict):
        async with self.pool.acquire() as conn:
            set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(data.keys())])
            values = [procurement_id] + list(data.values())
            await conn.execute(
                f"UPDATE procurements SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                *values
            )

    async def get_procurement(self, procurement_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM procurements WHERE id = $1", procurement_id)
            return dict(row) if row else None

    async def get_user_procurements(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM procurements WHERE user_id = $1 AND status = 'approved' ORDER BY created_at DESC LIMIT $2",
                user_id, limit
            )
            return [dict(row) for row in rows]

    # -------- TIMELINE --------
    async def add_timeline_entry(self, procurement_id: int, data: Dict) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO procurement_timeline 
                   (procurement_id, revision_number, shift_days,
                    applied_bid_days, applied_review_days, applied_signing_days,
                    publication_date, bid_end_date, consideration_date, 
                    auction_date, signing_date, bg_deadline_date, risk_warning, is_final)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                   RETURNING id""",
                procurement_id,
                data.get("revision_number"),
                data.get("shift_days"),
                data.get("applied_bid_days"),
                data.get("applied_review_days"),
                data.get("applied_signing_days"),
                data.get("publication_date"),
                data.get("bid_end_date"),
                data.get("consideration_date"),
                data.get("auction_date"),
                data.get("signing_date"),
                data.get("bg_deadline_date"),
                data.get("risk_warning"),
                data.get("is_final", False)
            )
            return row["id"]

    async def get_timeline(self, procurement_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM procurement_timeline WHERE procurement_id = $1 ORDER BY revision_number",
                procurement_id
            )
            return [dict(row) for row in rows]

    async def get_final_timeline(self, procurement_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM procurement_timeline WHERE procurement_id = $1 AND is_final = TRUE",
                procurement_id
            )
            return dict(row) if row else None

    async def set_final_timeline(self, procurement_id: int, revision_number: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE procurement_timeline SET is_final = FALSE WHERE procurement_id = $1",
                procurement_id
            )
            await conn.execute(
                "UPDATE procurement_timeline SET is_final = TRUE WHERE procurement_id = $1 AND revision_number = $2",
                procurement_id, revision_number
            )

    async def get_next_revision(self, procurement_id: int) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT MAX(revision_number) as max_rev FROM procurement_timeline WHERE procurement_id = $1",
                procurement_id
            )
            return (row["max_rev"] or 0) + 1

    # -------- PDF --------
    async def save_pdf_path(self, procurement_id: int, pdf_path: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE procurements SET final_pdf_path = $1, status = 'approved' WHERE id = $2",
                pdf_path, procurement_id
            )