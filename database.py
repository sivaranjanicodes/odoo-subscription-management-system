import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "brightloop.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError("schema.sql file not found in directory!")

    conn = get_db_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Brightloop Database initialized successfully.")


if __name__ == "__main__":
    init_db()