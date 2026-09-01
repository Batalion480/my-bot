import sqlite3
from datetime import date
from typing import List, Dict, Optional, Any
import os
import json


class Database:
    """Класс для работы с SQLite"""

    def __init__(self):
        self.conn = None
        self.cursor = None
        self.db_path = os.getenv("DATABASE_URL", "sqlite:///data/bot.db").replace("sqlite:///", "")

    async def connect(self):
        """Подключается к базе данных SQLite"""
        # Создаем папку data, если её нет
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        await self._init_tables()

    async def _init_tables(self):
        """Создает таблицы, если их нет"""
        # Таблица users
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                company_name TEXT,
                default_law TEXT DEFAULT '44-FZ',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица suppliers
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                inn TEXT,
                name TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                price REAL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, inn)
            )
        """)

        # Таблица customer_settings (223-ФЗ)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_name TEXT NOT NULL,
                bid_submission_days INTEGER NOT NULL CHECK (bid_submission_days > 0),
                bid_review_days INTEGER NOT NULL CHECK (bid_review_days > 0),
                auction_delay_days INTEGER DEFAULT 2 CHECK (auction_delay_days >= 0),
                signing_days INTEGER DEFAULT 5 CHECK (signing_days > 0),
                bg_days_before_signing INTEGER DEFAULT 5 CHECK (bg_days_before_signing >= 0),
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, setting_name)
            )
        """)

        # Таблица procurements
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS procurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                law_type TEXT NOT NULL CHECK (law_type IN ('44-FZ', '223-FZ')),
                nmck REAL NOT NULL,
                selected_supplier_ids TEXT,
                customer_setting_id INTEGER,
                custom_bid_days INTEGER CHECK (custom_bid_days > 0),
                custom_review_days INTEGER CHECK (custom_review_days > 0),
                publication_date TEXT NOT NULL,
                bid_end_date TEXT NOT NULL,
                consideration_date TEXT,
                auction_date TEXT,
                signing_date TEXT NOT NULL,
                bg_deadline_date TEXT,
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'archived')),
                final_pdf_path TEXT,
                scatter_warning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (customer_setting_id) REFERENCES customer_settings(id) ON DELETE SET NULL
            )
        """)

        # Таблица procurement_timeline
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS procurement_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                procurement_id INTEGER NOT NULL,
                revision_number INTEGER NOT NULL,
                shift_days INTEGER DEFAULT 0,
                applied_bid_days INTEGER NOT NULL,
                applied_review_days INTEGER NOT NULL,
                applied_signing_days INTEGER NOT NULL,
                publication_date TEXT NOT NULL,
                bid_end_date TEXT NOT NULL,
                consideration_date TEXT,
                auction_date TEXT,
                signing_date TEXT NOT NULL,
                bg_deadline_date TEXT,
                risk_warning TEXT,
                is_final INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (procurement_id) REFERENCES procurements(id) ON DELETE CASCADE
            )
        """)

        # Индексы
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_procurements_user_id ON procurements(user_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_procurement_id ON procurement_timeline(procurement_id)")
        
        self.conn.commit()

    def _row_to_dict(self, row):
        """Преобразует sqlite3.Row в dict"""
        return {k: row[k] for k in row.keys()} if row else None

    def _rows_to_dicts(self, rows):
        """Преобразует список sqlite3.Row в список dict"""
        return [self._row_to_dict(row) for row in rows] if rows else []

    # -------- USERS --------
    async def get_or_create_user(self, telegram_id: int, username: str = None, first_name: str = None) -> int:
        self.cursor.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = self.cursor.fetchone()
        if row:
            user_id = row["id"]
            self.cursor.execute(
                "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,)
            )
            self.conn.commit()
            return user_id
        else:
            self.cursor.execute(
                """INSERT INTO users (telegram_id, username, first_name) 
                   VALUES (?, ?, ?) RETURNING id""",
                (telegram_id, username, first_name)
            )
            row = self.cursor.fetchone()
            self.conn.commit()
            return row["id"]

    # -------- CUSTOMER SETTINGS (223-ФЗ) --------
    async def get_settings(self, user_id: int) -> List[Dict]:
        self.cursor.execute(
            "SELECT * FROM customer_settings WHERE user_id = ? ORDER BY is_default DESC, created_at",
            (user_id,)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    async def get_default_settings(self, user_id: int) -> Optional[Dict]:
        self.cursor.execute(
            "SELECT * FROM customer_settings WHERE user_id = ? AND is_default = 1",
            (user_id,)
        )
        return self._row_to_dict(self.cursor.fetchone())

    async def create_settings(self, user_id: int, name: str, bid_days: int, review_days: int,
                              auction_delay: int = 2, signing_days: int = 5, bg_days: int = 5,
                              is_default: bool = False) -> int:
        if is_default:
            self.cursor.execute(
                "UPDATE customer_settings SET is_default = 0 WHERE user_id = ?",
                (user_id,)
            )
        self.cursor.execute(
            """INSERT INTO customer_settings 
               (user_id, setting_name, bid_submission_days, bid_review_days, 
                auction_delay_days, signing_days, bg_days_before_signing, is_default)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (user_id, name, bid_days, review_days, auction_delay, signing_days, bg_days, 1 if is_default else 0)
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    # -------- SUPPLIERS --------
    async def get_or_create_supplier(self, user_id: int, name: str, inn: str = None,
                                     price: float = None, note: str = None) -> int:
        self.cursor.execute(
            "SELECT id FROM suppliers WHERE user_id = ? AND inn = ?",
            (user_id, inn)
        )
        row = self.cursor.fetchone()
        if row:
            return row["id"]
        else:
            self.cursor.execute(
                """INSERT INTO suppliers (user_id, inn, name, price, note) 
                   VALUES (?, ?, ?, ?, ?) RETURNING id""",
                (user_id, inn, name, price, note)
            )
            row = self.cursor.fetchone()
            self.conn.commit()
            return row["id"]

    async def get_suppliers_by_ids(self, supplier_ids: List[int]) -> List[Dict]:
        if not supplier_ids:
            return []
        placeholders = ",".join(["?"] * len(supplier_ids))
        self.cursor.execute(
            f"SELECT * FROM suppliers WHERE id IN ({placeholders})", supplier_ids
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    # -------- PROCUREMENTS --------
    async def create_procurement(self, user_id: int, data: Dict) -> int:
        self.cursor.execute(
            """INSERT INTO procurements 
               (user_id, title, law_type, nmck, selected_supplier_ids, 
                customer_setting_id, custom_bid_days, custom_review_days,
                publication_date, bid_end_date, consideration_date, 
                auction_date, signing_date, bg_deadline_date, scatter_warning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (
                user_id,
                data.get("title"),
                data.get("law_type"),
                data.get("nmck"),
                json.dumps(data.get("supplier_ids", [])),
                data.get("setting_id"),
                data.get("custom_bid_days"),
                data.get("custom_review_days"),
                data.get("publication_date").isoformat() if data.get("publication_date") else None,
                data.get("bid_end_date").isoformat() if data.get("bid_end_date") else None,
                data.get("consideration_date").isoformat() if data.get("consideration_date") else None,
                data.get("auction_date").isoformat() if data.get("auction_date") else None,
                data.get("signing_date").isoformat() if data.get("signing_date") else None,
                data.get("bg_deadline_date").isoformat() if data.get("bg_deadline_date") else None,
                data.get("scatter_warning")
            )
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def update_procurement(self, procurement_id: int, data: Dict):
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [procurement_id]
        self.cursor.execute(
            f"UPDATE procurements SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values
        )
        self.conn.commit()

    async def get_procurement(self, procurement_id: int) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM procurements WHERE id = ?", (procurement_id,))
        return self._row_to_dict(self.cursor.fetchone())

    async def get_user_procurements(self, user_id: int, limit: int = 10) -> List[Dict]:
        self.cursor.execute(
            "SELECT * FROM procurements WHERE user_id = ? AND status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    # -------- TIMELINE --------
    async def add_timeline_entry(self, procurement_id: int, data: Dict) -> int:
        self.cursor.execute(
            """INSERT INTO procurement_timeline 
               (procurement_id, revision_number, shift_days,
                applied_bid_days, applied_review_days, applied_signing_days,
                publication_date, bid_end_date, consideration_date, 
                auction_date, signing_date, bg_deadline_date, risk_warning, is_final)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (
                procurement_id,
                data.get("revision_number"),
                data.get("shift_days"),
                data.get("applied_bid_days"),
                data.get("applied_review_days"),
                data.get("applied_signing_days"),
                data.get("publication_date").isoformat() if data.get("publication_date") else None,
                data.get("bid_end_date").isoformat() if data.get("bid_end_date") else None,
                data.get("consideration_date").isoformat() if data.get("consideration_date") else None,
                data.get("auction_date").isoformat() if data.get("auction_date") else None,
                data.get("signing_date").isoformat() if data.get("signing_date") else None,
                data.get("bg_deadline_date").isoformat() if data.get("bg_deadline_date") else None,
                data.get("risk_warning"),
                1 if data.get("is_final") else 0
            )
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def get_timeline(self, procurement_id: int) -> List[Dict]:
        self.cursor.execute(
            "SELECT * FROM procurement_timeline WHERE procurement_id = ? ORDER BY revision_number",
            (procurement_id,)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    async def get_final_timeline(self, procurement_id: int) -> Optional[Dict]:
        self.cursor.execute(
            "SELECT * FROM procurement_timeline WHERE procurement_id = ? AND is_final = 1",
            (procurement_id,)
        )
        return self._row_to_dict(self.cursor.fetchone())

    async def set_final_timeline(self, procurement_id: int, revision_number: int):
        self.cursor.execute(
            "UPDATE procurement_timeline SET is_final = 0 WHERE procurement_id = ?",
            (procurement_id,)
        )
        self.cursor.execute(
            "UPDATE procurement_timeline SET is_final = 1 WHERE procurement_id = ? AND revision_number = ?",
            (procurement_id, revision_number)
        )
        self.conn.commit()

    async def get_next_revision(self, procurement_id: int) -> int:
        self.cursor.execute(
            "SELECT MAX(revision_number) as max_rev FROM procurement_timeline WHERE procurement_id = ?",
            (procurement_id,)
        )
        row = self.cursor.fetchone()
        return (row["max_rev"] or 0) + 1

    # -------- PDF --------
    async def save_pdf_path(self, procurement_id: int, pdf_path: str):
        self.cursor.execute(
            "UPDATE procurements SET final_pdf_path = ?, status = 'approved' WHERE id = ?",
            (pdf_path, procurement_id)
        )
        self.conn.commit()
        
    async def close(self):
        """Закрывает соединение с БД"""
        if self.conn:
            self.conn.close()