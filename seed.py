from database import get_db_connection
from werkzeug.security import generate_password_hash


def seed_data():
    conn = get_db_connection()
    cur = conn.cursor()

    # ---------- Users (passwords meet the rules: 8+ chars, upper, lower, special) ----------
    users = [
        (1, 'Admin', 'admin@brightloop.com', generate_password_hash('Admin@12345'), 'admin'),
        (2, 'Staff One', 'staff1@brightloop.com', generate_password_hash('Staff@12345'), 'staff'),
        (3, 'Customer One', 'customer1@gmail.com', generate_password_hash('Customer@123'), 'customer'),
        (4, 'Customer Two', 'customer2@gmail.com', generate_password_hash('Customer@123'), 'customer'),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO users (id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        users,
    )

    # ---------- Taxes ----------
    cur.executemany(
        "INSERT OR IGNORE INTO taxes (id, name, rate) VALUES (?, ?, ?)",
        [(1, 'GST 18%', 18.0), (2, 'GST 5%', 5.0)],
    )

    # ---------- Products ----------
    cur.executemany(
        """INSERT OR IGNORE INTO products
           (id, name, type, sales_price, cost_price, notes, tax_id) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 'Brightloop ERP Core', 'Software', 1500.0, 500.0, 'Main ERP product', 1),
            (2, 'Odoo Integration Module', 'Add-on', 500.0, 100.0, 'Optional add-on', 1),
        ],
    )

    # ---------- Variants (e.g. choosing the Odoo brand adds 560) ----------
    cur.executemany(
        "INSERT OR IGNORE INTO product_variants (id, product_id, variant_name, price_extra) VALUES (?, ?, ?, ?)",
        [
            (1, 1, 'Brand: Odoo', 560.0),
            (2, 1, 'Brand: SAP', 800.0),
            (3, 1, 'Brand: Standard', 0.0),
        ],
    )

    # ---------- Plans ----------
    cur.executemany(
        """INSERT OR IGNORE INTO plans
           (id, name, billing_period, price, min_quantity, start_date, end_date,
            auto_close, allow_pause_renew, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 'Monthly Pro Plan', 'monthly', 1500.0, 1, '2026-01-01', '2027-12-31', 0, 1, 'Active'),
            (2, 'Yearly Enterprise Plan', 'yearly', 15000.0, 5, '2026-01-01', '2027-12-31', 1, 0, 'Active'),
        ],
    )

    # ---------- Quotation template ----------
    cur.execute(
        "INSERT OR IGNORE INTO quotation_templates (id, name, plan_id, validity_days) VALUES (1, 'Standard Monthly Offer', 1, 30)"
    )

    # ---------- Subscriptions ----------
    cur.executemany(
        """INSERT OR IGNORE INTO subscriptions
           (id, subscription_number, customer_id, plan_id, template_id,
            start_date, expiry_date, payment_terms, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 'SUB-0001', 3, 1, 1, '2026-08-01', '2027-07-31', 'Net 10', 'Active'),
            (2, 'SUB-0002', 4, 2, None, '2026-10-01', '2027-09-30', 'Net 30', 'Draft'),
        ],
    )

    # ---------- Subscription lines (unit_price already includes the variant extra) ----------
    cur.executemany(
        """INSERT OR IGNORE INTO subscription_lines
           (id, subscription_id, product_id, variant_id, quantity, unit_price, tax_rate, total_amount)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 1, 1, 1, 2, 2060.0, 18.0, 4120.0),   # 1500 + 560 (Odoo) x 2
            (2, 1, 2, None, 1, 500.0, 18.0, 500.0),
            (3, 2, 1, 3, 5, 1500.0, 18.0, 7500.0),
        ],
    )

    # ---------- Discount rule ----------
    cur.execute(
        """INSERT OR IGNORE INTO discount_rules
           (id, code, type, value, min_amount, min_quantity, start_date, end_date,
            max_uses, used_count, applies_to, product_id, subscription_id)
           VALUES (1, 'SEATS10', 'percentage', 10.0, 0, 5, '2026-10-01', '2026-12-31',
                   100, 0, 'subscription', NULL, NULL)"""
    )

    # ---------- Sample invoices (one paid, one overdue) so the dashboard has data ----------
    cur.executemany(
        """INSERT OR IGNORE INTO invoices
           (id, invoice_number, subscription_id, customer_id, period_start, period_end,
            invoice_date, due_date, subtotal, tax_amount, discount_amount, total, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 'INV-0001', 1, 3, '2026-08-01', '2026-08-31', '2026-08-01', '2026-08-11',
             4620.0, 831.6, 0.0, 5451.6, 'Paid'),
            (2, 'INV-0002', 1, 3, '2026-09-01', '2026-09-30', '2026-09-01', '2026-09-11',
             4620.0, 831.6, 0.0, 5451.6, 'Confirmed'),  # unpaid and past due = overdue
        ],
    )

    cur.executemany(
        """INSERT OR IGNORE INTO invoice_lines
           (id, invoice_id, product_id, description, quantity, unit_price, tax_rate, amount)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 1, 1, 'Brightloop ERP Core (Brand: Odoo)', 2, 2060.0, 18.0, 4120.0),
            (2, 1, 2, 'Odoo Integration Module', 1, 500.0, 18.0, 500.0),
            (3, 2, 1, 'Brightloop ERP Core (Brand: Odoo)', 2, 2060.0, 18.0, 4120.0),
            (4, 2, 2, 'Odoo Integration Module', 1, 500.0, 18.0, 500.0),
        ],
    )

    cur.execute(
        """INSERT OR IGNORE INTO invoice_payments
           (id, invoice_id, method, amount, payment_date, note)
           VALUES (1, 1, 'UPI', 5451.6, '2026-08-09', 'Paid on time')"""
    )

    conn.commit()
    conn.close()
    print("Sample data populated successfully into brightloop.db!")


if __name__ == "__main__":
    seed_data()