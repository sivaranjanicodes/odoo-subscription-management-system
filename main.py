import base64
import calendar
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import smtplib
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection, init_db

app = FastAPI(title="Brightloop Subscription Engine API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.environ.get("SECRET_KEY", "brightloop-dev-secret-change-me")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:8000")


# ==========================================
# HELPERS
# ==========================================

@contextmanager
def db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.on_event("startup")
def startup_event():
    init_db()
    with db() as conn:
        # safe migrations for databases created from an older schema.sql
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(subscriptions)").fetchall()]
        if "quote_valid_until" not in cols:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN quote_valid_until DATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS quotation_template_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL REFERENCES quotation_templates(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            variant_id INTEGER REFERENCES product_variants(id),
            quantity INTEGER DEFAULT 1)""")
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_inv_sub ON invoices(subscription_id)",
            "CREATE INDEX IF NOT EXISTS idx_invlines_inv ON invoice_lines(invoice_id)",
            "CREATE INDEX IF NOT EXISTS idx_sublines_sub ON subscription_lines(subscription_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        ):
            conn.execute(stmt)
        empty = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    if empty:
        from seed import seed_data
        seed_data()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Please enter a valid email address.")
    return email


def check_password_rules(pw: str):
    if len(pw or "") <= 8:
        raise HTTPException(400, "Password must be more than 8 characters long.")
    if not re.search(r"[A-Z]", pw):
        raise HTTPException(400, "Password must contain an uppercase letter.")
    if not re.search(r"[a-z]", pw):
        raise HTTPException(400, "Password must contain a lowercase letter.")
    if not re.search(r"[^A-Za-z0-9]", pw):
        raise HTTPException(400, "Password must contain a special character.")


def parse_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(400, f"{field} must be in YYYY-MM-DD format.")


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def period_end(start: date, billing: str) -> date:
    if billing == "daily":
        return start
    if billing == "weekly":
        return start + timedelta(days=6)
    if billing == "monthly":
        return add_months(start, 1) - timedelta(days=1)
    return add_months(start, 12) - timedelta(days=1)


def paging(page: int, page_size: int):
    page_size = max(1, min(page_size, 200))
    return page_size, (max(page, 1) - 1) * page_size


def send_email(to: str, subject: str, body: str):
    """Sends through SMTP if SMTP_HOST is set, otherwise prints to the terminal (demo mode)."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"\n--- EMAIL (demo mode) ---\nTo: {to}\nSubject: {subject}\n{body}\n-------------------------\n")
        return
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "no-reply@brightloop.com")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    except Exception as exc:
        print("Email failed:", exc)


# ---------- signed login tokens (no extra library needed) ----------

def make_token(user_id: int, hours: int = 12) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + hours * 3600}).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: str):
    try:
        body, sig = token.split(".")
        expected = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return data if data["exp"] > time.time() else None
    except Exception:
        return None


def get_current_user(authorization: Optional[str] = Header(None), token: Optional[str] = Query(None)):
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif token:
        raw = token
    data = read_token(raw) if raw else None
    if not data:
        raise HTTPException(401, "Please log in.")
    with db() as conn:
        row = conn.execute("SELECT id, name, email, role FROM users WHERE id = ?", (data["uid"],)).fetchone()
    if not row:
        raise HTTPException(401, "Please log in.")
    return dict(row)


def require_roles(*roles):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "You do not have permission to do this.")
        return user
    return checker


STAFF = ("admin", "staff")


# ==========================================
# SCHEMAS
# ==========================================

class UserRegister(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class StaffCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class ForgotPassword(BaseModel):
    email: str


class ResetPassword(BaseModel):
    token: str
    new_password: str


class TaxCreate(BaseModel):
    name: str
    rate: float  # percent, e.g. 18


class ProductCreate(BaseModel):
    name: str
    type: str
    sales_price: float
    cost_price: float
    notes: Optional[str] = ""
    tax_id: Optional[int] = None


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
    applies_to: str = "subscription"  # product | subscription
    product_id: Optional[int] = None
    subscription_id: Optional[int] = None  # empty = all subscriptions


class LineItem(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class SubscriptionCreate(BaseModel):
    customer_id: int
    plan_id: Optional[int] = None
    template_id: Optional[int] = None
    payment_terms: str = "Net 15"
    start_date: str
    expiry_date: str
    line_items: List[LineItem] = []


class TemplateCreate(BaseModel):
    name: str
    plan_id: int
    validity_days: int = 30
    lines: List[LineItem]


class PaymentRecord(BaseModel):
    method: str
    amount: float
    payment_date: Optional[str] = None
    note: Optional[str] = ""


# ==========================================
# AUTH
# ==========================================

@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "Brightloop Subscription Engine"}


@app.post("/api/register")
def register(u: UserRegister):
    """Public signup. Always creates a customer; the role cannot be chosen."""
    email = normalize_email(u.email)
    check_password_rules(u.password)
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(400, "An account with this email already exists.")
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'customer')",
                (u.name, email, generate_password_hash(u.password)),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(400, "An account with this email already exists.")
        return {"message": "Account created successfully", "user_id": cur.lastrowid}


@app.post("/api/staff")
def create_staff(u: StaffCreate, admin=Depends(require_roles("admin"))):
    """Only the admin can add a new member of staff."""
    email = normalize_email(u.email)
    check_password_rules(u.password)
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(400, "An account with this email already exists.")
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'staff')",
            (u.name, email, generate_password_hash(u.password)),
        )
        return {"message": "Staff member created", "user_id": cur.lastrowid}


@app.post("/api/login")
def login(u: UserLogin):
    email = (u.email or "").strip().lower()
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], u.password):
        raise HTTPException(401, "Invalid email or password.")
    return {
        "message": "Login successful",
        "token": make_token(row["id"]),
        "user_id": row["id"],
        "role": row["role"],
        "name": row["name"],
    }


@app.get("/api/me")
def me(user=Depends(get_current_user)):
    return user


@app.post("/api/forgot-password")
def forgot_password(body: ForgotPassword):
    email = (body.email or "").strip().lower()
    with db() as conn:
        user = conn.execute("SELECT id, email FROM users WHERE lower(email) = ?", (email,)).fetchone()
        if user:
            raw = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user["id"], sha(raw), expires),
            )
            link = f"{FRONTEND_URL}/login.html?reset_token={raw}"
            send_email(user["email"], "Reset your Brightloop password",
                       f"Click the link to reset your password (valid for 1 hour):\n{link}")
    # same answer whether or not the email exists
    return {"message": "If that email is registered, a reset link has been sent."}


@app.post("/api/reset-password")
def reset_password(body: ResetPassword):
    check_password_rules(body.new_password)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM password_resets WHERE token = ? AND used = 0 AND expires_at > ?",
            (sha(body.token), now),
        ).fetchone()
        if not row:
            raise HTTPException(400, "This reset link is invalid or has expired.")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (generate_password_hash(body.new_password), row["user_id"]))
        conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
    return {"message": "Password updated. You can now log in."}


@app.get("/api/users")
def list_users(role: Optional[str] = None, user=Depends(require_roles(*STAFF))):
    sql, params = "SELECT id, name, email, role, created_at FROM users", []
    if role:
        sql += " WHERE role = ?"
        params.append(role)
    with db() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY id", params).fetchall()]


# ==========================================
# TAXES, PRODUCTS, VARIANTS
# ==========================================

@app.get("/api/taxes")
def get_taxes(user=Depends(get_current_user)):
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM taxes").fetchall()]


@app.post("/api/taxes")
def create_tax(t: TaxCreate, user=Depends(require_roles("admin"))):
    with db() as conn:
        cur = conn.execute("INSERT INTO taxes (name, rate) VALUES (?, ?)", (t.name, t.rate))
        return {"message": "Tax created", "tax_id": cur.lastrowid}


@app.get("/api/products")
def get_products(user=Depends(get_current_user)):
    with db() as conn:
        products = conn.execute(
            "SELECT p.*, t.name AS tax_name, t.rate AS tax_rate FROM products p LEFT JOIN taxes t ON t.id = p.tax_id"
        ).fetchall()
        variants = [dict(v) for v in conn.execute("SELECT * FROM product_variants").fetchall()]
    out = [dict(p) for p in products]
    for p in out:
        p["variants"] = [v for v in variants if v["product_id"] == p["id"]]
    return out


@app.post("/api/products")
def create_product(p: ProductCreate, user=Depends(require_roles("admin"))):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, type, sales_price, cost_price, notes, tax_id) VALUES (?, ?, ?, ?, ?, ?)",
            (p.name, p.type, p.sales_price, p.cost_price, p.notes, p.tax_id),
        )
        return {"message": "Product created", "product_id": cur.lastrowid}


@app.post("/api/product-variants")
def create_variant(v: ProductVariantCreate, user=Depends(require_roles("admin"))):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM products WHERE id = ?", (v.product_id,)).fetchone():
            raise HTTPException(404, "Product not found")
        cur = conn.execute(
            "INSERT INTO product_variants (product_id, variant_name, price_extra) VALUES (?, ?, ?)",
            (v.product_id, v.variant_name, v.price_extra),
        )
        return {"message": "Product variant created", "variant_id": cur.lastrowid}


# ==========================================
# PLANS
# ==========================================

@app.get("/api/plans")
def get_plans(user=Depends(get_current_user)):
    with db() as conn:
        return [dict(p) for p in conn.execute("SELECT * FROM plans ORDER BY id").fetchall()]


@app.post("/api/plans")
def create_plan(p: PlanCreate, user=Depends(require_roles("admin"))):
    if p.billing_period not in ("daily", "weekly", "monthly", "yearly"):
        raise HTTPException(400, "billing_period must be daily, weekly, monthly or yearly.")
    if p.start_date and p.end_date and parse_date(p.end_date, "end_date") < parse_date(p.start_date, "start_date"):
        raise HTTPException(400, "end_date cannot be before start_date.")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO plans (name, billing_period, price, min_quantity, start_date, end_date,
                                  auto_close, allow_pause_renew)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.name, p.billing_period, p.price, p.min_quantity, p.start_date, p.end_date,
             int(p.auto_close), int(p.allow_pause_renew)),
        )
        return {"message": "Plan created successfully", "plan_id": cur.lastrowid}


@app.put("/api/plans/{plan_id}/status")
def set_plan_status(plan_id: int, status: str, new_end_date: Optional[str] = None,
                    user=Depends(require_roles("admin"))):
    """Close early, pause, or renew (status=Active, optionally with a new end date)."""
    if status not in ("Active", "Paused", "Closed"):
        raise HTTPException(400, "status must be Active, Paused or Closed.")
    with db() as conn:
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan:
            raise HTTPException(404, "Plan not found")
        if not plan["allow_pause_renew"]:
            raise HTTPException(400, "This plan cannot be paused, renewed or closed early.")
        if new_end_date:
            parse_date(new_end_date, "new_end_date")
            conn.execute("UPDATE plans SET end_date = ? WHERE id = ?", (new_end_date, plan_id))
        conn.execute("UPDATE plans SET status = ? WHERE id = ?", (status, plan_id))
        return {"message": f"Plan is now {status}"}


# ==========================================
# QUOTATION TEMPLATES
# ==========================================

@app.get("/api/quotation-templates")
def get_templates(user=Depends(require_roles(*STAFF))):
    with db() as conn:
        tpls = [dict(t) for t in conn.execute(
            "SELECT t.*, p.name AS plan_name FROM quotation_templates t JOIN plans p ON p.id = t.plan_id").fetchall()]
        lines = [dict(l) for l in conn.execute(
            """SELECT l.*, p.name AS product_name, v.variant_name
               FROM quotation_template_lines l
               JOIN products p ON p.id = l.product_id
               LEFT JOIN product_variants v ON v.id = l.variant_id""").fetchall()]
    for t in tpls:
        t["lines"] = [l for l in lines if l["template_id"] == t["id"]]
    return tpls


@app.post("/api/quotation-templates")
def create_template(t: TemplateCreate, user=Depends(require_roles(*STAFF))):
    if not t.lines:
        raise HTTPException(400, "Add at least one product line to the template.")
    if t.validity_days < 1:
        raise HTTPException(400, "Validity must be at least 1 day.")
    with db() as conn:
        if not conn.execute("SELECT 1 FROM plans WHERE id = ?", (t.plan_id,)).fetchone():
            raise HTTPException(404, "Plan not found")
        cur = conn.execute(
            "INSERT INTO quotation_templates (name, plan_id, validity_days) VALUES (?, ?, ?)",
            (t.name, t.plan_id, t.validity_days),
        )
        for l in t.lines:
            conn.execute(
                "INSERT INTO quotation_template_lines (template_id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?)",
                (cur.lastrowid, l.product_id, l.variant_id, l.quantity),
            )
        return {"message": "Template created", "template_id": cur.lastrowid}


# ==========================================
# DISCOUNTS (admin only to create)
# ==========================================

@app.get("/api/discounts")
def get_discounts(user=Depends(require_roles(*STAFF))):
    with db() as conn:
        return [dict(d) for d in conn.execute("SELECT * FROM discount_rules ORDER BY id DESC").fetchall()]


@app.post("/api/discounts")
def create_discount(d: DiscountCreate, user=Depends(require_roles("admin"))):
    if d.type not in ("fixed", "percentage"):
        raise HTTPException(400, "type must be fixed or percentage.")
    if d.value <= 0 or (d.type == "percentage" and d.value > 100):
        raise HTTPException(400, "Discount value is not valid.")
    if d.applies_to not in ("product", "subscription"):
        raise HTTPException(400, "applies_to must be product or subscription.")
    if d.applies_to == "product" and not d.product_id:
        raise HTTPException(400, "Choose a product for a product discount.")
    if d.start_date and d.end_date and parse_date(d.end_date, "end_date") < parse_date(d.start_date, "start_date"):
        raise HTTPException(400, "end_date cannot be before start_date.")
    with db() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO discount_rules (code, type, value, min_amount, min_quantity, start_date, end_date,
                                               max_uses, applies_to, product_id, subscription_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (d.code.strip().upper(), d.type, d.value, d.min_amount, d.min_quantity, d.start_date, d.end_date,
                 d.max_uses, d.applies_to, d.product_id, d.subscription_id),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Discount code already exists.")
        return {"message": "Discount rule created", "discount_id": cur.lastrowid}


def find_discount(conn, sub_id: int, lines: list, subtotal: float, total_qty: int, today: date):
    """Best applicable discount for one invoice. Returns (rule or None, amount)."""
    iso = today.isoformat()
    rules = conn.execute(
        """SELECT * FROM discount_rules
           WHERE (start_date IS NULL OR start_date <= ?)
             AND (end_date IS NULL OR end_date >= ?)
             AND (max_uses IS NULL OR used_count < max_uses)""",
        (iso, iso),
    ).fetchall()
    best, best_amt = None, 0.0
    for r in rules:
        if total_qty < (r["min_quantity"] or 1) or subtotal < (r["min_amount"] or 0):
            continue
        if r["applies_to"] == "product":
            if r["product_id"] is None:
                continue
            base = sum(l["amount"] for l in lines if l["product_id"] == r["product_id"])
        else:
            if r["subscription_id"] not in (None, sub_id):
                continue
            base = subtotal
        if base <= 0:
            continue
        amt = min(r["value"], base) if r["type"] == "fixed" else base * r["value"] / 100.0
        if amt > best_amt:
            best, best_amt = r, amt
    return best, round(best_amt, 2)


# ==========================================
# SUBSCRIPTIONS
# ==========================================

SUB_FLOW = {
    "Draft": ["Quotation", "Closed"],
    "Quotation": ["Draft", "Confirmed", "Closed"],
    "Confirmed": ["Active", "Closed"],
    "Active": ["Closed"],
    "Closed": [],
}


@app.get("/api/subscriptions")
def get_subscriptions(status: Optional[str] = None, customer_id: Optional[int] = None,
                      q: Optional[str] = None, page: int = 1, page_size: int = 100,
                      user=Depends(get_current_user)):
    where, params = [], []
    if user["role"] == "customer":
        where.append("s.customer_id = ?")
        params.append(user["id"])
    elif customer_id:
        where.append("s.customer_id = ?")
        params.append(customer_id)
    if status:
        where.append("s.status = ?")
        params.append(status)
    if q:
        where.append("(s.subscription_number LIKE ? OR u.email LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    size, offset = paging(page, page_size)
    sql = f"""SELECT s.*, u.email AS customer_email, u.name AS customer_name,
                     p.name AS plan_name, p.billing_period
              FROM subscriptions s
              JOIN users u ON s.customer_id = u.id
              JOIN plans p ON s.plan_id = p.id
              {"WHERE " + " AND ".join(where) if where else ""}
              ORDER BY s.id DESC LIMIT ? OFFSET ?"""
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params + [size, offset]).fetchall()]


@app.get("/api/subscriptions/{subscription_id}")
def get_subscription_details(subscription_id: int, user=Depends(get_current_user)):
    with db() as conn:
        sub = conn.execute(
            """SELECT s.*, u.email AS customer_email, u.name AS customer_name,
                      p.name AS plan_name, p.billing_period, p.price AS plan_price
               FROM subscriptions s
               JOIN users u ON s.customer_id = u.id
               JOIN plans p ON s.plan_id = p.id
               WHERE s.id = ?""", (subscription_id,)).fetchone()
        if not sub or (user["role"] == "customer" and sub["customer_id"] != user["id"]):
            raise HTTPException(404, "Subscription not found")
        lines = conn.execute(
            """SELECT sl.*, p.name AS product_name, pv.variant_name
               FROM subscription_lines sl
               JOIN products p ON sl.product_id = p.id
               LEFT JOIN product_variants pv ON sl.variant_id = pv.id
               WHERE sl.subscription_id = ?""", (subscription_id,)).fetchall()
    result = dict(sub)
    result["lines"] = [dict(l) for l in lines]
    return result


@app.post("/api/subscriptions")
def create_subscription(sub: SubscriptionCreate, user=Depends(require_roles(*STAFF))):
    start = parse_date(sub.start_date, "start_date")
    expiry = parse_date(sub.expiry_date, "expiry_date")
    if expiry <= start:
        raise HTTPException(400, "expiry_date must be after start_date.")

    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id = ? AND role = 'customer'", (sub.customer_id,)).fetchone():
            raise HTTPException(400, "Customer not found.")

        plan_id = sub.plan_id
        items = [i.dict() for i in sub.line_items]
        quote_valid_until = None

        if sub.template_id:
            tpl = conn.execute("SELECT * FROM quotation_templates WHERE id = ?", (sub.template_id,)).fetchone()
            if not tpl:
                raise HTTPException(404, "Template not found.")
            plan_id = plan_id or tpl["plan_id"]
            quote_valid_until = (date.today() + timedelta(days=tpl["validity_days"])).isoformat()
            if not items:
                items = [dict(product_id=l["product_id"], variant_id=l["variant_id"], quantity=l["quantity"])
                         for l in conn.execute(
                             "SELECT * FROM quotation_template_lines WHERE template_id = ?", (tpl["id"],)).fetchall()]

        if not plan_id:
            raise HTTPException(400, "A plan is required.")
        plan = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if not plan or plan["status"] != "Active":
            raise HTTPException(400, "This plan is not available.")
        if (plan["start_date"] and start < parse_date(plan["start_date"], "plan start")) or \
           (plan["end_date"] and start > parse_date(plan["end_date"], "plan end")):
            raise HTTPException(400, "This plan is not available on the chosen start date.")
        if not items:
            raise HTTPException(400, "Add at least one product line.")
        if sum(i["quantity"] for i in items) < plan["min_quantity"]:
            raise HTTPException(400, f"Minimum quantity for this plan is {plan['min_quantity']}.")

        cur = conn.execute(
            """INSERT INTO subscriptions (subscription_number, customer_id, plan_id, template_id,
                                          start_date, expiry_date, payment_terms, status, quote_valid_until)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', ?)""",
            (f"TMP-{uuid.uuid4().hex}", sub.customer_id, plan_id, sub.template_id,
             sub.start_date, sub.expiry_date, sub.payment_terms, quote_valid_until),
        )
        sub_id = cur.lastrowid
        sub_number = f"SUB-{sub_id:04d}"
        conn.execute("UPDATE subscriptions SET subscription_number = ? WHERE id = ?", (sub_number, sub_id))

        for it in items:
            prod = conn.execute(
                """SELECT p.*, COALESCE(t.rate, 0) AS tax_rate FROM products p
                   LEFT JOIN taxes t ON t.id = p.tax_id WHERE p.id = ?""", (it["product_id"],)).fetchone()
            if not prod:
                raise HTTPException(400, f"Product {it['product_id']} not found.")
            if it["quantity"] < 1:
                raise HTTPException(400, "Quantity must be at least 1.")
            price = prod["sales_price"]
            if it.get("variant_id"):
                var = conn.execute("SELECT * FROM product_variants WHERE id = ? AND product_id = ?",
                                   (it["variant_id"], it["product_id"])).fetchone()
                if not var:
                    raise HTTPException(400, "Variant does not belong to that product.")
                price += var["price_extra"]
            conn.execute(
                """INSERT INTO subscription_lines (subscription_id, product_id, variant_id, quantity,
                                                   unit_price, tax_rate, total_amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sub_id, it["product_id"], it.get("variant_id"), it["quantity"], price,
                 prod["tax_rate"], round(price * it["quantity"], 2)),
            )
    return {"message": "Subscription created in Draft status", "subscription_id": sub_id,
            "subscription_number": sub_number, "quotation_valid_until": quote_valid_until}


@app.put("/api/subscriptions/{subscription_id}/status")
def update_subscription_status(subscription_id: int, status: str, user=Depends(get_current_user)):
    if status not in SUB_FLOW:
        raise HTTPException(400, "Invalid status.")
    with db() as conn:
        sub = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone()
        if not sub:
            raise HTTPException(404, "Subscription not found")
        if user["role"] == "customer":
            if sub["customer_id"] != user["id"] or status != "Closed":
                raise HTTPException(403, "Customers can only close their own subscription.")
        if status not in SUB_FLOW[sub["status"]]:
            raise HTTPException(400, f"Cannot move from {sub['status']} to {status}. "
                                     f"Allowed: {', '.join(SUB_FLOW[sub['status']]) or 'none'}.")
        if (sub["status"] == "Quotation" and status == "Confirmed" and sub["quote_valid_until"]
                and sub["quote_valid_until"] < date.today().isoformat()):
            raise HTTPException(400, f"This quotation expired on {sub['quote_valid_until']}. Create a new one.")
        conn.execute("UPDATE subscriptions SET status = ? WHERE id = ?", (status, subscription_id))
    return {"message": f"Subscription status updated to {status}"}


# ==========================================
# INVOICES & BILLING ENGINE
# ==========================================

INVOICE_SELECT = """
    SELECT i.*, u.email AS customer_email, u.name AS customer_name, s.subscription_number,
           COALESCE(pp.paid, 0) AS paid_amount,
           ROUND(i.total - COALESCE(pp.paid, 0), 2) AS outstanding,
           CASE WHEN i.status = 'Confirmed' AND i.due_date < ? AND i.total - COALESCE(pp.paid, 0) > 0.005
                THEN 1 ELSE 0 END AS is_overdue
    FROM invoices i
    JOIN users u ON i.customer_id = u.id
    JOIN subscriptions s ON i.subscription_id = s.id
    LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM invoice_payments GROUP BY invoice_id) pp
           ON pp.invoice_id = i.id
"""


def load_invoice(conn, invoice_id: int, user: dict):
    inv = conn.execute(INVOICE_SELECT + " WHERE i.id = ?", (date.today().isoformat(), invoice_id)).fetchone()
    if not inv or (user["role"] == "customer" and inv["customer_id"] != user["id"]):
        raise HTTPException(404, "Invoice not found")
    return inv


@app.get("/api/invoices")
def get_invoices(status: Optional[str] = None, overdue: Optional[bool] = None,
                 customer_id: Optional[int] = None, q: Optional[str] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                 page: int = 1, page_size: int = 100, user=Depends(get_current_user)):
    today = date.today().isoformat()
    where, params = [], [today]
    if user["role"] == "customer":
        where.append("i.customer_id = ?")
        params.append(user["id"])
    elif customer_id:
        where.append("i.customer_id = ?")
        params.append(customer_id)
    if status:
        where.append("i.status = ?")
        params.append(status)
    if overdue:
        where.append("i.status = 'Confirmed' AND i.due_date < ? AND i.total - COALESCE(pp.paid, 0) > 0.005")
        params.append(today)
    if q:
        where.append("(i.invoice_number LIKE ? OR u.email LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if date_from:
        where.append("i.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("i.invoice_date <= ?")
        params.append(date_to)
    size, offset = paging(page, page_size)
    sql = INVOICE_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY i.id DESC LIMIT ? OFFSET ?"
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params + [size, offset]).fetchall()]


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, user=Depends(get_current_user)):
    with db() as conn:
        inv = load_invoice(conn, invoice_id, user)
        lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (invoice_id,)).fetchall()
        pays = conn.execute("SELECT * FROM invoice_payments WHERE invoice_id = ? ORDER BY payment_date",
                            (invoice_id,)).fetchall()
    result = dict(inv)
    result["lines"] = [dict(l) for l in lines]
    result["payments"] = [dict(p) for p in pays]
    return result


def create_invoice_for_period(conn, sub, start: date, end: date, today: date, status: str):
    """Builds one invoice from a subscription. Returns the total, or None if the period was already billed."""
    lines = []
    for l in conn.execute(
        """SELECT sl.*, p.name AS product_name, pv.variant_name FROM subscription_lines sl
           JOIN products p ON p.id = sl.product_id
           LEFT JOIN product_variants pv ON pv.id = sl.variant_id
           WHERE sl.subscription_id = ?""", (sub["id"],)).fetchall():
        amount = round(l["quantity"] * l["unit_price"], 2)
        name = l["product_name"] + (f" ({l['variant_name']})" if l["variant_name"] else "")
        lines.append(dict(product_id=l["product_id"], description=name, quantity=l["quantity"],
                          unit_price=l["unit_price"], tax_rate=l["tax_rate"] or 0, amount=amount))
    if not lines:  # no product lines: bill the plan price
        lines.append(dict(product_id=None, description=sub["plan_name"], quantity=1,
                          unit_price=sub["plan_price"], tax_rate=0, amount=sub["plan_price"]))

    subtotal = round(sum(l["amount"] for l in lines), 2)
    tax_total = sum(l["amount"] * l["tax_rate"] / 100.0 for l in lines)
    total_qty = sum(l["quantity"] for l in lines)

    rule, discount = find_discount(conn, sub["id"], lines, subtotal, total_qty, today)
    if discount and subtotal > 0:
        tax_total *= (1 - discount / subtotal)
    tax_total = round(tax_total, 2)
    total = round(subtotal - discount + tax_total, 2)

    match = re.search(r"\d+", sub["payment_terms"] or "")
    due = today + timedelta(days=int(match.group()) if match else 15)

    try:
        cur = conn.execute(
            """INSERT INTO invoices (invoice_number, subscription_id, customer_id, period_start, period_end,
                                     invoice_date, due_date, subtotal, tax_amount, discount_amount, total, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"TMP-{uuid.uuid4().hex}", sub["id"], sub["customer_id"], start.isoformat(), end.isoformat(),
             today.isoformat(), due.isoformat(), subtotal, tax_total, discount, total, status),
        )
    except sqlite3.IntegrityError:
        return None  # UNIQUE(subscription_id, period_start): already billed

    inv_id = cur.lastrowid
    conn.execute("UPDATE invoices SET invoice_number = ? WHERE id = ?", (f"INV-{inv_id:05d}", inv_id))
    for l in lines:
        conn.execute(
            """INSERT INTO invoice_lines (invoice_id, product_id, description, quantity, unit_price, tax_rate, amount)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (inv_id, l["product_id"], l["description"], l["quantity"], l["unit_price"], l["tax_rate"], l["amount"]),
        )
    if rule and discount:
        conn.execute("UPDATE discount_rules SET used_count = used_count + 1 WHERE id = ?", (rule["id"],))
    return total


@app.post("/api/billing/run")
def run_billing_cycle(auto_confirm: bool = False, user=Depends(require_roles(*STAFF))):
    """Creates every invoice that is due. Safe to run repeatedly: a period is never billed twice or skipped."""
    today = date.today()
    generated, total_billed = 0, 0.0
    with db() as conn:
        subs = conn.execute(
            """SELECT s.*, p.name AS plan_name, p.price AS plan_price, p.billing_period
               FROM subscriptions s JOIN plans p ON p.id = s.plan_id
               WHERE s.status = 'Active' AND p.status = 'Active'""").fetchall()
        for sub in subs:
            last = conn.execute("SELECT MAX(period_end) FROM invoices WHERE subscription_id = ?",
                                (sub["id"],)).fetchone()[0]
            start = parse_date(last, "period_end") + timedelta(days=1) if last else parse_date(sub["start_date"], "start")
            expiry = parse_date(sub["expiry_date"], "expiry")
            guard = 0
            while start <= today and start <= expiry and guard < 36:
                end = period_end(start, sub["billing_period"])
                total = create_invoice_for_period(conn, sub, start, end, today,
                                                  "Confirmed" if auto_confirm else "Draft")
                if total is not None:
                    generated += 1
                    total_billed += total
                start = end + timedelta(days=1)
                guard += 1

        # automatic closing
        iso = today.isoformat()
        conn.execute("UPDATE plans SET status = 'Closed' WHERE auto_close = 1 AND end_date IS NOT NULL "
                     "AND end_date < ? AND status != 'Closed'", (iso,))
        conn.execute("UPDATE subscriptions SET status = 'Closed' WHERE status = 'Active' AND expiry_date < ?", (iso,))

    return {"message": "Billing cycle processed successfully.",
            "invoices_generated": generated, "total_amount_billed": round(total_billed, 2)}


@app.post("/api/invoices/{invoice_id}/confirm")
def confirm_invoice(invoice_id: int, user=Depends(require_roles(*STAFF))):
    with db() as conn:
        inv = load_invoice(conn, invoice_id, user)
        if inv["status"] != "Draft":
            raise HTTPException(400, "Only a Draft invoice can be confirmed.")
        conn.execute("UPDATE invoices SET status = 'Confirmed' WHERE id = ?", (invoice_id,))
    return {"message": f"Invoice {inv['invoice_number']} confirmed."}


@app.post("/api/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, user=Depends(require_roles(*STAFF))):
    with db() as conn:
        inv = load_invoice(conn, invoice_id, user)
        if inv["status"] not in ("Draft", "Confirmed") or inv["paid_amount"] > 0:
            raise HTTPException(400, "This invoice cannot be cancelled.")
        conn.execute("UPDATE invoices SET status = 'Cancelled' WHERE id = ?", (invoice_id,))
    return {"message": f"Invoice {inv['invoice_number']} cancelled."}


@app.post("/api/invoices/{invoice_id}/send")
def send_invoice(invoice_id: int, user=Depends(require_roles(*STAFF))):
    with db() as conn:
        inv = load_invoice(conn, invoice_id, user)
        if inv["status"] == "Cancelled":
            raise HTTPException(400, "A cancelled invoice cannot be sent.")
    send_email(inv["customer_email"], f"Invoice {inv['invoice_number']} from Brightloop",
               f"Hello,\n\nYour invoice {inv['invoice_number']} for {inv['total']} is due on {inv['due_date']}.\n"
               f"Period: {inv['period_start']} to {inv['period_end']}.\n\nThank you,\nBrightloop Software")
    return {"message": f"Invoice {inv['invoice_number']} sent to {inv['customer_email']}."}


@app.get("/api/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice(invoice_id: int, user=Depends(get_current_user)):
    """Open as /api/invoices/ID/print?token=YOUR_TOKEN in a new tab."""
    with db() as conn:
        inv = load_invoice(conn, invoice_id, user)
        lines = conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?", (invoice_id,)).fetchall()
    rows = "".join(
        f"<tr><td>{html.escape(l['description'] or '')}</td><td>{l['quantity']}</td>"
        f"<td>{l['unit_price']:.2f}</td><td>{l['tax_rate']}%</td><td>{l['amount']:.2f}</td></tr>" for l in lines)
    return f"""<html><head><title>{inv['invoice_number']}</title>
    <style>body{{font-family:Arial;margin:40px}}table{{width:100%;border-collapse:collapse}}
    td,th{{border:1px solid #ccc;padding:8px;text-align:left}}.r{{text-align:right}}</style></head><body>
    <h1>Brightloop Software</h1><h2>Invoice {inv['invoice_number']}</h2>
    <p>Customer: {html.escape(inv['customer_email'])}<br>Subscription: {inv['subscription_number']}<br>
    Period: {inv['period_start']} to {inv['period_end']}<br>Due date: {inv['due_date']}<br>Status: {inv['status']}</p>
    <table><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Tax</th><th>Amount</th></tr>{rows}</table>
    <p class="r">Subtotal: {inv['subtotal']:.2f}<br>Discount: -{inv['discount_amount']:.2f}<br>
    Tax: {inv['tax_amount']:.2f}<br><b>Total: {inv['total']:.2f}</b><br>
    Paid: {inv['paid_amount']:.2f}<br><b>Outstanding: {inv['outstanding']:.2f}</b></p>
    <script>window.print()</script></body></html>"""


# ==========================================
# PAYMENTS
# ==========================================

def record_payment(invoice_id: int, p: PaymentRecord):
    if p.amount <= 0:
        raise HTTPException(400, "Amount must be greater than zero.")
    pay_date = parse_date(p.payment_date, "payment_date") if p.payment_date else date.today()
    with db() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if inv["status"] != "Confirmed":
            raise HTTPException(400, "Payments can only be recorded against a Confirmed invoice.")
        paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM invoice_payments WHERE invoice_id = ?",
                            (invoice_id,)).fetchone()[0]
        outstanding = round(inv["total"] - paid, 2)
        if p.amount > outstanding + 0.005:
            raise HTTPException(400, f"Amount is more than the outstanding balance ({outstanding}).")
        conn.execute(
            "INSERT INTO invoice_payments (invoice_id, method, amount, payment_date, note) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, p.method, p.amount, pay_date.isoformat(), p.note),
        )
        remaining = round(outstanding - p.amount, 2)
        if remaining <= 0.005:
            conn.execute("UPDATE invoices SET status = 'Paid' WHERE id = ?", (invoice_id,))
        conn.execute("UPDATE subscriptions SET status = 'Active' WHERE id = ? AND status = 'Confirmed'",
                     (inv["subscription_id"],))
    return {"message": f"Payment recorded for {inv['invoice_number']}.",
            "outstanding": max(remaining, 0), "invoice_status": "Paid" if remaining <= 0.005 else "Confirmed"}


@app.post("/api/invoices/{invoice_id}/payments")
def add_payment(invoice_id: int, payment: PaymentRecord, user=Depends(require_roles(*STAFF))):
    return record_payment(invoice_id, payment)


@app.post("/api/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, payment: PaymentRecord, user=Depends(require_roles(*STAFF))):
    return record_payment(invoice_id, payment)


@app.get("/api/payments")
def list_payments(date_from: Optional[str] = None, date_to: Optional[str] = None,
                  method: Optional[str] = None, page: int = 1, page_size: int = 100,
                  user=Depends(require_roles(*STAFF))):
    where, params = [], []
    if date_from:
        where.append("p.payment_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("p.payment_date <= ?")
        params.append(date_to)
    if method:
        where.append("p.method = ?")
        params.append(method)
    size, offset = paging(page, page_size)
    sql = f"""SELECT p.*, i.invoice_number, u.email AS customer_email
              FROM invoice_payments p JOIN invoices i ON i.id = p.invoice_id JOIN users u ON u.id = i.customer_id
              {"WHERE " + " AND ".join(where) if where else ""}
              ORDER BY p.payment_date DESC, p.id DESC LIMIT ? OFFSET ?"""
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params + [size, offset]).fetchall()]


# ==========================================
# DASHBOARD
# ==========================================

@app.get("/api/dashboard/summary")
def get_dashboard_summary(date_from: Optional[str] = None, date_to: Optional[str] = None,
                          user=Depends(require_roles(*STAFF))):
    today = date.today().isoformat()
    with db() as conn:
        by_sub = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) AS c FROM subscriptions GROUP BY status").fetchall()}
        by_inv = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) AS c FROM invoices GROUP BY status").fetchall()}

        mrr = conn.execute(
            """SELECT COALESCE(SUM(CASE p.billing_period
                        WHEN 'monthly' THEN COALESCE(x.amt, p.price)
                        WHEN 'yearly'  THEN COALESCE(x.amt, p.price) / 12.0
                        WHEN 'weekly'  THEN COALESCE(x.amt, p.price) * 52 / 12.0
                        ELSE COALESCE(x.amt, p.price) * 30 END), 0)
               FROM subscriptions s
               JOIN plans p ON p.id = s.plan_id
               LEFT JOIN (SELECT subscription_id, SUM(total_amount) AS amt
                          FROM subscription_lines GROUP BY subscription_id) x ON x.subscription_id = s.id
               WHERE s.status = 'Active'""").fetchone()[0]

        pay_sql, pay_params = "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM invoice_payments WHERE 1=1", []
        if date_from:
            pay_sql += " AND payment_date >= ?"
            pay_params.append(date_from)
        if date_to:
            pay_sql += " AND payment_date <= ?"
            pay_params.append(date_to)
        revenue, payment_count = conn.execute(pay_sql, pay_params).fetchone()

        out = conn.execute(
            """WITH inv AS (
                   SELECT i.due_date,
                          i.total - COALESCE((SELECT SUM(amount) FROM invoice_payments p
                                              WHERE p.invoice_id = i.id), 0) AS due
                   FROM invoices i WHERE i.status = 'Confirmed')
               SELECT COALESCE(SUM(due), 0), COUNT(*),
                      COALESCE(SUM(CASE WHEN due_date < ? THEN due ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN due_date < ? THEN 1 ELSE 0 END), 0)
               FROM inv WHERE due > 0.005""", (today, today)).fetchone()

    return {
        "active_subscriptions": by_sub.get("Active", 0),
        "closed_subscriptions": by_sub.get("Closed", 0),
        "subscriptions_by_status": by_sub,
        "invoices_by_status": by_inv,
        "mrr": round(mrr, 2),
        "revenue_collected": round(revenue, 2),
        "payments_count": payment_count,
        "outstanding_amount": round(out[0], 2),
        "outstanding_invoices": out[1],
        "overdue_amount": round(out[2], 2),
        "overdue_invoices": out[3],
        "unpaid_invoices": out[1],
    }


# ==========================================
# SERVE THE WEBSITE (keep this at the very bottom)
# ==========================================

FRONTEND_FILES = {"index.html", "login.html", "register.html", "app.js", "auth.js", "styles.css"}


@app.get("/", include_in_schema=False)
def site_home():
    return RedirectResponse("/login.html")


@app.get("/{filename}", include_in_schema=False)
def site_file(filename: str):
    if filename in FRONTEND_FILES:
        return FileResponse(os.path.join(BASE_DIR, filename))
    raise HTTPException(404, "Not found")