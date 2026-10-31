from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from database import get_db_connection, init_db

app = FastAPI(title="Brightloop Subscription Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "customer"

class UserLogin(BaseModel):
    email: str
    password: str

class ProductCreate(BaseModel):
    name: str
    type: str
    sales_price: float
    cost_price: float
    notes: Optional[str] = ""

class ProductVariantCreate(BaseModel):
    product_id: int
    variant_name: str
    price_extra: float = 0.0

class PlanCreate(BaseModel):
    name: str
    billing_period: str  # daily, weekly, monthly, yearly
    price: float
    min_quantity: int = 1
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    auto_close: bool = False
    allow_pause_renew: bool = True

class DiscountCreate(BaseModel):
    code: str
    type: str  # fixed, percentage
    value: float
    min_amount: float = 0.0
    min_quantity: int = 1
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_uses: Optional[int] = None
    product_id: Optional[int] = None

class SubscriptionLineItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1
    unit_price: float
    tax_rate: float = 0.18

class SubscriptionCreate(BaseModel):
    customer_id: int
    plan_id: int
    payment_terms: str
    start_date: str
    expiry_date: str
    discount_code: Optional[str] = None
    line_items: List[SubscriptionLineItem]

class PaymentRecord(BaseModel):
    method: str
    amount: float
    note: Optional[str] = "Payment processed"


# ==========================================
# SYSTEM & AUTH ENDPOINTS
# ==========================================

@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "Brightloop Subscription Engine"}

@app.post("/api/register")
def register(user: UserRegister):
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (user.email, user.password, user.role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"message": "User created successfully", "user_id": user_id}
    except Exception:
        raise HTTPException(status_code=400, detail="Email already registered.")
    finally:
        conn.close()

@app.post("/api/login")
def login(user: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT * FROM users WHERE email = ? AND password_hash = ?",
        (user.email, user.password)
    ).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"message": "Login successful", "user_id": row["id"], "role": row["role"]}


# ==========================================
# PRODUCTS, VARIANTS & PLANS
# ==========================================

@app.get("/api/products")
def get_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    variants = conn.execute("SELECT * FROM product_variants").fetchall()
    conn.close()
    
    prod_list = [dict(p) for p in products]
    var_list = [dict(v) for v in variants]
    
    for p in prod_list:
        p["variants"] = [v for v in var_list if v["product_id"] == p["id"]]
    return prod_list

@app.post("/api/products")
def create_product(product: ProductCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, type, sales_price, cost_price, notes) VALUES (?, ?, ?, ?, ?)",
        (product.name, product.type, product.sales_price, product.cost_price, product.notes)
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return {"message": "Product created", "product_id": pid}

@app.post("/api/product-variants")
def create_variant(variant: ProductVariantCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO product_variants (product_id, variant_name, price_extra) VALUES (?, ?, ?)",
        (variant.product_id, variant.variant_name, variant.price_extra)
    )
    conn.commit()
    vid = cursor.lastrowid
    conn.close()
    return {"message": "Product variant created", "variant_id": vid}

@app.get("/api/plans")
def get_plans():
    conn = get_db_connection()
    plans = conn.execute("SELECT * FROM plans").fetchall()
    conn.close()
    return [dict(p) for p in plans]

@app.post("/api/plans")
def create_plan(plan: PlanCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO plans (name, billing_period, price, min_quantity, start_date, end_date, auto_close, allow_pause_renew)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (plan.name, plan.billing_period, plan.price, plan.min_quantity, plan.start_date, plan.end_date, plan.auto_close, plan.allow_pause_renew))
    conn.commit()
    plan_id = cursor.lastrowid
    conn.close()
    return {"message": "Plan created successfully", "plan_id": plan_id}


# ==========================================
# DISCOUNTS ENGINE
# ==========================================

@app.get("/api/discounts")
def get_discounts():
    conn = get_db_connection()
    discounts = conn.execute("SELECT * FROM discount_rules").fetchall()
    conn.close()
    return [dict(d) for d in discounts]

@app.post("/api/discounts")
def create_discount(discount: DiscountCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO discount_rules (code, type, value, min_amount, min_quantity, start_date, end_date, max_uses, product_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (discount.code, discount.type, discount.value, discount.min_amount, discount.min_quantity, discount.start_date, discount.end_date, discount.max_uses, discount.product_id))
        conn.commit()
        did = cursor.lastrowid
        return {"message": "Discount rule created", "discount_id": did}
    except Exception:
        raise HTTPException(status_code=400, detail="Discount code already exists.")
    finally:
        conn.close()


# ==========================================
# SUBSCRIPTION LIFECYCLE MANAGEMENT
# ==========================================

@app.get("/api/subscriptions")
def get_subscriptions():
    conn = get_db_connection()
    subs = conn.execute("""
        SELECT s.*, u.email as customer_email, p.name as plan_name, p.billing_period
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        ORDER BY s.id DESC
    """).fetchall()
    conn.close()
    return [dict(s) for s in subs]

@app.get("/api/subscriptions/{subscription_id}")
def get_subscription_details(subscription_id: int):
    conn = get_db_connection()
    sub = conn.execute("""
        SELECT s.*, u.email as customer_email, p.name as plan_name, p.billing_period, p.price as plan_price
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.id = ?
    """, (subscription_id,)).fetchone()
    
    if not sub:
        conn.close()
        raise HTTPException(status_code=404, detail="Subscription not found")
        
    lines = conn.execute("""
        SELECT sl.*, p.name as product_name, pv.variant_name
        FROM subscription_lines sl
        JOIN products p ON sl.product_id = p.id
        LEFT JOIN product_variants pv ON sl.variant_id = pv.id
        WHERE sl.subscription_id = ?
    """, (subscription_id,)).fetchall()
    
    conn.close()
    result = dict(sub)
    result["lines"] = [dict(l) for l in lines]
    return result

@app.post("/api/subscriptions")
def create_subscription(sub: SubscriptionCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sub_number = f"SUB-BL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    cursor.execute("""
        INSERT INTO subscriptions (subscription_number, customer_id, plan_id, start_date, expiry_date, payment_terms, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Draft')
    """, (sub_number, sub.customer_id, sub.plan_id, sub.start_date, sub.expiry_date, sub.payment_terms))
    
    sub_id = cursor.lastrowid
    
    for item in sub.line_items:
        tot_amount = item.quantity * item.unit_price * (1 + item.tax_rate)
        cursor.execute("""
            INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity, unit_price, tax_rate, total_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sub_id, item.product_id, item.variant_id, item.quantity, item.unit_price, item.tax_rate, tot_amount))
        
    conn.commit()
    conn.close()
    return {"message": "Subscription created in Draft status", "subscription_id": sub_id, "subscription_number": sub_number}

@app.put("/api/subscriptions/{subscription_id}/status")
def update_subscription_status(subscription_id: int, status: str):
    valid_statuses = ['Draft', 'Quotation', 'Confirmed', 'Active', 'Closed']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status transition.")
    
    conn = get_db_connection()
    conn.execute("UPDATE subscriptions SET status = ? WHERE id = ?", (status, subscription_id))
    conn.commit()
    conn.close()
    return {"message": f"Subscription status updated to {status}"}


# ==========================================
# INVOICING & AUTOMATED BILLING ENGINE
# ==========================================

@app.get("/api/invoices")
def get_invoices():
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT i.*, u.email as customer_email, s.subscription_number
        FROM invoices i
        JOIN users u ON i.customer_id = u.id
        JOIN subscriptions s ON i.subscription_id = s.id
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return [dict(inv) for inv in invoices]

@app.post("/api/billing/run")
def run_billing_cycle():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    active_subs = cursor.execute("""
        SELECT s.id as subscription_id, s.customer_id, p.price, s.subscription_number
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.status = 'Active'
    """).fetchall()
    
    generated_count = 0
    total_billed = 0.0
    due_date_str = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    
    for sub in active_subs:
        sub_id = sub["subscription_id"]
        cust_id = sub["customer_id"]
        subtotal = float(sub["price"])
        
        existing = cursor.execute("""
            SELECT id FROM invoices 
            WHERE subscription_id = ? AND due_date = ?
        """, (sub_id, due_date_str)).fetchone()
        
        if existing:
            continue
            
        tax_amount = round(subtotal * 0.18, 2)
        total = subtotal + tax_amount
        inv_number = f"INV-{sub['subscription_number']}-{datetime.now().strftime('%M%S')}"
        
        cursor.execute("""
            INSERT INTO invoices 
            (invoice_number, subscription_id, customer_id, due_date, subtotal, tax_amount, discount_amount, total, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed')
        """, (inv_number, sub_id, cust_id, due_date_str, subtotal, tax_amount, 0.0, total))
        
        generated_count += 1
        total_billed += total

    conn.commit()
    conn.close()
    
    return {
        "message": "Billing cycle processed successfully.",
        "invoices_generated": generated_count,
        "total_amount_billed": total_billed
    }

@app.post("/api/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, payment: PaymentRecord):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inv = cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    cursor.execute("""
        INSERT INTO invoice_payments (invoice_id, method, amount, payment_date, note)
        VALUES (?, ?, ?, ?, ?)
    """, (invoice_id, payment.method, payment.amount, datetime.now().strftime("%Y-%m-%d"), payment.note))
    
    cursor.execute("UPDATE invoices SET status = 'Paid' WHERE id = ?", (invoice_id,))
    cursor.execute("UPDATE subscriptions SET status = 'Active' WHERE id = ?", (inv["subscription_id"],))
    
    conn.commit()
    conn.close()
    return {"message": f"Invoice {inv['invoice_number']} paid successfully. Subscription is now Active."}


# ==========================================
# DASHBOARD & FINANCIAL ANALYTICS
# ==========================================

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    conn = get_db_connection()
    
    active_count = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'Active'").fetchone()[0]
    total_mrr = conn.execute("""
        SELECT COALESCE(SUM(p.price), 0.0) 
        FROM subscriptions s 
        JOIN plans p ON s.plan_id = p.id 
        WHERE s.status = 'Active'
    """).fetchone()[0]
    
    unpaid_invoices = conn.execute("SELECT COUNT(*) FROM invoices WHERE status != 'Paid'").fetchone()[0]
    closed_count = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'Closed'").fetchone()[0]
    
    conn.close()
    return {
        "active_subscriptions": active_count,
        "mrr": total_mrr,
        "unpaid_invoices": unpaid_invoices,
        "closed_subscriptions": closed_count
    }