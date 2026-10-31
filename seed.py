import sqlite3
from database import get_db_connection

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert Sample Users
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES
        (1, 'admin@brightloop.com', 'admin123', 'admin'),
        (2, 'customer1@gmail.com', 'cust123', 'customer')
    """)

    # Insert Sample Products
    cursor.execute("""
        INSERT OR IGNORE INTO products (id, name, type, sales_price, cost_price) VALUES
        (1, 'Brightloop ERP Core', 'Software', 1500.0, 500.0),
        (2, 'Odoo Integration Module', 'Add-on', 500.0, 100.0)
    """)

    # Insert Sample Billing Plans
    cursor.execute("""
        INSERT OR IGNORE INTO plans (id, name, billing_period, price) VALUES
        (1, 'Monthly Pro Plan', 'monthly', 1500.0),
        (2, 'Yearly Enterprise Plan', 'yearly', 15000.0)
    """)

    conn.commit()
    conn.close()
    print("Sample data populated successfully into brightloop.db!")

if __name__ == "__main__":
    seed_data()