from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from database import get_db_connection, init_db

app = FastAPI(title="Brightloop Subscription Engine API", version="1.0.0")

# Enable CORS for local frontend communication
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

# --- Data Models ---
class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "customer"

class UserLogin(BaseModel):
    email: str
    password: str

class SubscriptionCreate(BaseModel):
    customer_id: int
    plan_id: int
    start_date: str
    expiry_date: str
    payment_terms: str
    product_ids: List[int]

# --- Core API Endpoints ---

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
    except Exception as e:
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

@app.get("/api/products")
def get_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return [dict(p) for p in products]

@app.get("/api/plans")
def get_plans():
    conn = get_db_connection()
    plans = conn.execute("SELECT * FROM plans").fetchall()
    conn.close()
    return [dict(p) for p in plans]

@app.get("/api/subscriptions")
def get_subscriptions():
    conn = get_db_connection()
    subs = conn.execute("""
        SELECT s.*, u.email as customer_email, p.name as plan_name 
        FROM subscriptions s
        JOIN users u ON s.customer_id = u.id
        JOIN plans p ON s.plan_id = p.id
    """).fetchall()
    conn.close()
    return [dict(s) for s in subs]

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
    
    conn.close()
    return {
        "active_subscriptions": active_count,
        "mrr": total_mrr,
        "unpaid_invoices": unpaid_invoices
    }