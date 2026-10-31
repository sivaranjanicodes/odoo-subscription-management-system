CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT CHECK(role IN ('admin', 'staff', 'customer')) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    token TEXT UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS taxes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rate REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    sales_price REAL NOT NULL,
    cost_price REAL NOT NULL,
    notes TEXT,
    tax_id INTEGER REFERENCES taxes(id)
);

CREATE TABLE IF NOT EXISTS product_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_name TEXT NOT NULL,
    price_extra REAL DEFAULT 0.00
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    billing_period TEXT CHECK(billing_period IN ('daily', 'weekly', 'monthly', 'yearly')) NOT NULL,
    price REAL NOT NULL,
    min_quantity INTEGER DEFAULT 1,
    start_date DATE,
    end_date DATE,
    auto_close BOOLEAN DEFAULT 0,
    allow_pause_renew BOOLEAN DEFAULT 1,
    status TEXT CHECK(status IN ('Active', 'Paused', 'Closed')) DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS quotation_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    plan_id INTEGER REFERENCES plans(id),
    validity_days INTEGER DEFAULT 30
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES users(id),
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    template_id INTEGER REFERENCES quotation_templates(id),
    start_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    payment_terms TEXT NOT NULL,
    status TEXT CHECK(status IN ('Draft', 'Quotation', 'Confirmed', 'Active', 'Closed')) DEFAULT 'Draft'
);

CREATE TABLE IF NOT EXISTS subscription_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER REFERENCES product_variants(id),
    quantity INTEGER DEFAULT 1,
    unit_price REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    total_amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS discount_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    type TEXT CHECK(type IN ('fixed', 'percentage')) NOT NULL,
    value REAL NOT NULL,
    min_amount REAL DEFAULT 0.0,
    min_quantity INTEGER DEFAULT 1,
    start_date DATE,
    end_date DATE,
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    applies_to TEXT CHECK(applies_to IN ('product', 'subscription')) DEFAULT 'subscription',
    product_id INTEGER REFERENCES products(id),
    subscription_id INTEGER REFERENCES subscriptions(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id),
    customer_id INTEGER NOT NULL REFERENCES users(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    invoice_date DATE DEFAULT CURRENT_DATE,
    due_date DATE NOT NULL,
    subtotal REAL NOT NULL,
    tax_amount REAL NOT NULL,
    discount_amount REAL DEFAULT 0.0,
    total REAL NOT NULL,
    status TEXT CHECK(status IN ('Draft', 'Confirmed', 'Paid', 'Cancelled')) DEFAULT 'Draft',
    UNIQUE(subscription_id, period_start)
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    product_id INTEGER REFERENCES products(id),
    description TEXT,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    tax_rate REAL DEFAULT 0.0,
    amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    method TEXT NOT NULL,
    amount REAL NOT NULL,
    payment_date DATE NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_sub_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_sub_customer ON subscriptions(customer_id);
CREATE INDEX IF NOT EXISTS idx_inv_status_due ON invoices(status, due_date);
CREATE INDEX IF NOT EXISTS idx_inv_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_pay_invoice ON invoice_payments(invoice_id);