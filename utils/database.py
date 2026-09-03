import sqlite3
from datetime import date, datetime
from typing import List, Dict, Optional, Any
import os
import json
from config import DATABASE_URL


class Database:
    """Класс для работы с SQLite"""

    def __init__(self):
        self.conn = None
        self.cursor = None
        if DATABASE_URL.startswith("sqlite:///"):
            self.db_path = DATABASE_URL.replace("sqlite:///", "")
        else:
            self.db_path = "/data/bot.db"

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        await self._init_tables()
        print("✅ База данных SQLite подключена")

    async def _ensure_connection(self):
        if self.conn is None or self.cursor is None:
            await self.connect()
        try:
            self.cursor.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            await self.connect()

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

        # Таблица customer_settings
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_name TEXT NOT NULL,
                bid_submission_days INTEGER NOT NULL,
                bid_review_days INTEGER NOT NULL,
                auction_delay_days INTEGER DEFAULT 2,
                signing_days INTEGER DEFAULT 5,
                bg_days_before_signing INTEGER DEFAULT 5,
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
                law_type TEXT NOT NULL,
                nmck REAL NOT NULL,
                selected_supplier_ids TEXT,
                customer_setting_id INTEGER,
                custom_bid_days INTEGER,
                custom_review_days INTEGER,
                publication_date TEXT NOT NULL,
                bid_end_date TEXT NOT NULL,
                consideration_date TEXT,
                auction_date TEXT,
                signing_date TEXT NOT NULL,
                bg_deadline_date TEXT,
                status TEXT DEFAULT 'draft',
                final_pdf_path TEXT,
                scatter_warning TEXT,
                positions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

        # ============================================================
        # ТАБЛИЦА knowledge_base (база знаний законов)
        # ============================================================
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                law_type TEXT NOT NULL,
                procedure_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                article TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                calculation_type TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Индексы для knowledge_base
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_law_procedure ON knowledge_base(law_type, procedure_type)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_stage ON knowledge_base(stage)")

        # Индексы для остальных таблиц
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_procurements_user_id ON procurements(user_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_procurement_id ON procurement_timeline(procurement_id)")

        self.conn.commit()

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================

    def _row_to_dict(self, row):
        return {k: row[k] for k in row.keys()} if row else None

    def _rows_to_dicts(self, rows):
        return [self._row_to_dict(row) for row in rows] if rows else []

    def _format_date(self, dt):
        if dt is None:
            return None
        if isinstance(dt, date):
            return dt.isoformat()
        return dt

    # ============================================================
    # USERS
    # ============================================================

    async def get_or_create_user(self, telegram_id: int, username: str = None, first_name: str = None) -> int:
        await self._ensure_connection()
        self.cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        row = self.cursor.fetchone()
        if row:
            user_id = row["id"]
            self.cursor.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
            self.conn.commit()
            return user_id
        else:
            self.cursor.execute(
                "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?) RETURNING id",
                (telegram_id, username, first_name)
            )
            row = self.cursor.fetchone()
            self.conn.commit()
            return row["id"]

    # ============================================================
    # CUSTOMER SETTINGS
    # ============================================================

    async def get_settings(self, user_id: int) -> List[Dict]:
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM customer_settings WHERE user_id = ? ORDER BY is_default DESC, created_at",
            (user_id,)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    async def get_default_settings(self, user_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM customer_settings WHERE user_id = ? AND is_default = 1",
            (user_id,)
        )
        return self._row_to_dict(self.cursor.fetchone())

    async def create_settings(self, user_id: int, name: str, bid_days: int, review_days: int,
                              auction_delay: int = 2, signing_days: int = 5, bg_days: int = 5,
                              is_default: bool = False) -> int:
        await self._ensure_connection()
        if is_default:
            self.cursor.execute("UPDATE customer_settings SET is_default = 0 WHERE user_id = ?", (user_id,))
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

    # ============================================================
    # SUPPLIERS
    # ============================================================

    async def get_or_create_supplier(self, user_id: int, name: str, inn: str = None,
                                     price: float = None, note: str = None) -> int:
        await self._ensure_connection()
        self.cursor.execute("SELECT id FROM suppliers WHERE user_id = ? AND inn = ?", (user_id, inn))
        row = self.cursor.fetchone()
        if row:
            return row["id"]
        self.cursor.execute(
            "INSERT INTO suppliers (user_id, inn, name, price, note) VALUES (?, ?, ?, ?, ?) RETURNING id",
            (user_id, inn, name, price, note)
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def get_suppliers_by_ids(self, supplier_ids: List[int]) -> List[Dict]:
        if not supplier_ids:
            return []
        await self._ensure_connection()
        placeholders = ",".join(["?"] * len(supplier_ids))
        self.cursor.execute(f"SELECT * FROM suppliers WHERE id IN ({placeholders})", supplier_ids)
        return self._rows_to_dicts(self.cursor.fetchall())

    # ============================================================
    # PROCUREMENTS
    # ============================================================

    async def create_procurement(self, user_id: int, data: Dict) -> int:
        await self._ensure_connection()
        self.cursor.execute(
            """INSERT INTO procurements 
               (user_id, title, law_type, nmck, selected_supplier_ids, 
                customer_setting_id, custom_bid_days, custom_review_days,
                publication_date, bid_end_date, consideration_date, 
                auction_date, signing_date, bg_deadline_date, scatter_warning, positions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (
                user_id,
                data.get("title"),
                data.get("law_type"),
                data.get("nmck"),
                json.dumps(data.get("supplier_ids", [])),
                data.get("setting_id"),
                data.get("custom_bid_days"),
                data.get("custom_review_days"),
                self._format_date(data.get("publication_date")),
                self._format_date(data.get("bid_end_date")),
                self._format_date(data.get("consideration_date")),
                self._format_date(data.get("auction_date")),
                self._format_date(data.get("signing_date")),
                self._format_date(data.get("bg_deadline_date")),
                data.get("scatter_warning"),
                json.dumps(data.get("positions", [])) if data.get("positions") else None
            )
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def update_procurement(self, procurement_id: int, data: Dict):
        await self._ensure_connection()
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [procurement_id]
        self.cursor.execute(
            f"UPDATE procurements SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values
        )
        self.conn.commit()

    async def get_procurement(self, procurement_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        self.cursor.execute("SELECT * FROM procurements WHERE id = ?", (procurement_id,))
        row = self.cursor.fetchone()
        if row:
            res = dict(row)
            if res.get("positions"):
                res["positions"] = json.loads(res["positions"])
            if res.get("selected_supplier_ids"):
                res["selected_supplier_ids"] = json.loads(res["selected_supplier_ids"])
            return res
        return None

    async def get_user_procurements(self, user_id: int, limit: int = 10) -> List[Dict]:
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM procurements WHERE user_id = ? AND status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("positions"):
                d["positions"] = json.loads(d["positions"])
            if d.get("selected_supplier_ids"):
                d["selected_supplier_ids"] = json.loads(d["selected_supplier_ids"])
            result.append(d)
        return result

    # ============================================================
    # TIMELINE
    # ============================================================

    async def add_timeline_entry(self, procurement_id: int, data: Dict) -> int:
        await self._ensure_connection()
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
                self._format_date(data.get("publication_date")),
                self._format_date(data.get("bid_end_date")),
                self._format_date(data.get("consideration_date")),
                self._format_date(data.get("auction_date")),
                self._format_date(data.get("signing_date")),
                self._format_date(data.get("bg_deadline_date")),
                data.get("risk_warning"),
                1 if data.get("is_final") else 0
            )
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def get_timeline(self, procurement_id: int) -> List[Dict]:
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM procurement_timeline WHERE procurement_id = ? ORDER BY revision_number",
            (procurement_id,)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    async def get_final_timeline(self, procurement_id: int) -> Optional[Dict]:
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM procurement_timeline WHERE procurement_id = ? AND is_final = 1",
            (procurement_id,)
        )
        return self._row_to_dict(self.cursor.fetchone())

    async def set_final_timeline(self, procurement_id: int, revision_number: int):
        await self._ensure_connection()
        self.cursor.execute("UPDATE procurement_timeline SET is_final = 0 WHERE procurement_id = ?", (procurement_id,))
        self.cursor.execute(
            "UPDATE procurement_timeline SET is_final = 1 WHERE procurement_id = ? AND revision_number = ?",
            (procurement_id, revision_number)
        )
        self.conn.commit()

    async def get_next_revision(self, procurement_id: int) -> int:
        await self._ensure_connection()
        self.cursor.execute("SELECT MAX(revision_number) as max_rev FROM procurement_timeline WHERE procurement_id = ?",
                           (procurement_id,))
        row = self.cursor.fetchone()
        return (row["max_rev"] or 0) + 1

    async def save_pdf_path(self, procurement_id: int, pdf_path: str):
        await self._ensure_connection()
        self.cursor.execute(
            "UPDATE procurements SET final_pdf_path = ?, status = 'approved' WHERE id = ?",
            (pdf_path, procurement_id)
        )
        self.conn.commit()

    # ============================================================
    # KNOWLEDGE BASE (база знаний законов)
    # ============================================================

    async def get_rule(self, law_type: str, procedure_type: str, stage: str) -> Optional[Dict]:
        """Получает правило из базы знаний по типу закона, процедуре и этапу"""
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM knowledge_base WHERE law_type = ? AND procedure_type = ? AND stage = ?",
            (law_type, procedure_type, stage)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    async def get_all_rules_for_procedure(self, law_type: str, procedure_type: str) -> List[Dict]:
        """Получает все правила для конкретной процедуры (все этапы)"""
        await self._ensure_connection()
        self.cursor.execute(
            "SELECT * FROM knowledge_base WHERE law_type = ? AND procedure_type = ? ORDER BY id",
            (law_type, procedure_type)
        )
        return self._rows_to_dicts(self.cursor.fetchall())

    async def insert_rule(self, law_type: str, procedure_type: str, stage: str,
                          article: str, rule_text: str, calculation_type: str = None,
                          source: str = None) -> int:
        """Вставляет новое правило в базу знаний"""
        await self._ensure_connection()
        self.cursor.execute(
            """INSERT INTO knowledge_base 
               (law_type, procedure_type, stage, article, rule_text, calculation_type, source)
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (law_type, procedure_type, stage, article, rule_text, calculation_type, source)
        )
        row = self.cursor.fetchone()
        self.conn.commit()
        return row["id"]

    async def clear_knowledge_base(self):
        """Очищает таблицу knowledge_base (для перезаливки данных)"""
        await self._ensure_connection()
        self.cursor.execute("DELETE FROM knowledge_base")
        self.conn.commit()

    async def get_all_rules(self, law_type: str = None) -> List[Dict]:
        """Получает все правила из базы знаний (можно отфильтровать по типу закона)"""
        await self._ensure_connection()
        if law_type:
            self.cursor.execute("SELECT * FROM knowledge_base WHERE law_type = ?", (law_type,))
        else:
            self.cursor.execute("SELECT * FROM knowledge_base")
        return self._rows_to_dicts(self.cursor.fetchall())

    # ============================================================
    # ЗАКРЫТИЕ ПОДКЛЮЧЕНИЯ
    # ============================================================

    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None