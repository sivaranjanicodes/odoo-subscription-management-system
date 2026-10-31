import sqlite3
import os

DB_NAME = "brightloop.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists("schema.sql"):
        raise FileNotFoundError("schema.sql file not found in directory!")
    
    conn = get_db_connection()
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema_script = f.read()
    
    conn.executescript(schema_script)
    conn.commit()
    conn.close()
    print("Brightloop Database initialized successfully.")

if __name__ == "__main__":
    init_db()