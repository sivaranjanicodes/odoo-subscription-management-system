// ============================================================
// Brightloop frontend: auth + shared API helper
// Load this file BEFORE app.js on every page.
// ============================================================
// Works from the website (same server) and from Go Live (port 5500/5501)
const API_BASE = ["5500", "5501"].includes(window.location.port)
  ? "http://127.0.0.1:8000/api"
  : "/api";
const DEMO_LOGGED_IN_KEY = "brightloopDemoLoggedIn";

async function api(path, method = "GET", body = null) {
  const token = localStorage.getItem("token");
  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : null,
    });
  } catch (err) {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  const data = await res.json().catch(() => ({}));

  if (res.status === 401 && token) {
    clearSession();
    window.location.href = "login.html";
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join(", ");
    throw new Error(msg || "Something went wrong.");
  }
  return data;
}

function clearSession() {
  ["token", "role", "user_id", "user_name", DEMO_LOGGED_IN_KEY].forEach((k) =>
    localStorage.removeItem(k)
  );
}

function setMessage(elementId, message, isError = true) {
  const element = document.getElementById(elementId);
  if (element) {
    element.textContent = message;
    element.style.color = isError ? "#b42318" : "#197344";
  }
}

function isStrongPassword(password) {
  return (
    password.length >= 9 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /[^A-Za-z0-9]/.test(password)
  );
}

// ------------------------------------------------------------
// Page guard: every page except login/register needs a token
// ------------------------------------------------------------
const currentPage = window.location.pathname.split("/").pop() || "index.html";
const publicPages = ["login.html", "register.html"];

if (!publicPages.includes(currentPage) && !localStorage.getItem("token")) {
  window.location.href = "login.html";
}

// ------------------------------------------------------------
// Register (real backend; role is always "customer")
// ------------------------------------------------------------
const registerForm = document.getElementById("registerForm");

if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const fullName = document.getElementById("fullName").value.trim();
    const companyName = document.getElementById("companyName").value.trim();
    const email = document.getElementById("registerEmail").value.trim().toLowerCase();
    const password = document.getElementById("registerPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;
    const termsAccepted = document.getElementById("terms").checked;

    if (!fullName || !companyName || !email) {
      setMessage("registerMessage", "Please fill in all required fields.");
      return;
    }
    if (!isStrongPassword(password)) {
      setMessage(
        "registerMessage",
        "Password must be at least 9 characters and include uppercase, lowercase, and a special character."
      );
      return;
    }
    if (password !== confirmPassword) {
      setMessage("registerMessage", "Passwords do not match.");
      return;
    }
    if (!termsAccepted) {
      setMessage("registerMessage", "Please accept the terms and conditions.");
      return;
    }

    try {
      await api("/register", "POST", { name: fullName, email, password });
      setMessage("registerMessage", "Account created. Redirecting to login…", false);
      setTimeout(() => (window.location.href = "login.html"), 800);
    } catch (err) {
      setMessage("registerMessage", err.message);
    }
  });
}

// ------------------------------------------------------------
// Login (real backend)
// ------------------------------------------------------------
const loginForm = document.getElementById("loginForm");

if (loginForm) {
  clearSession();

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("loginEmail").value.trim().toLowerCase();
    const password = document.getElementById("loginPassword").value;

    try {
      const data = await api("/login", "POST", { email, password });
      localStorage.setItem("token", data.token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("user_id", data.user_id);
      localStorage.setItem("user_name", data.name || email);
      localStorage.setItem(DEMO_LOGGED_IN_KEY, "true");
      window.location.href = "index.html";
    } catch (err) {
      setMessage("loginMessage", err.message);
    }
  });
}

// ------------------------------------------------------------
// Forgot password
// ------------------------------------------------------------
const forgotLink = document.getElementById("forgotPasswordLink");

if (forgotLink) {
  forgotLink.addEventListener("click", async (event) => {
    event.preventDefault();
    const typed = document.getElementById("loginEmail");
    const email = (prompt("Enter your registered email:", typed ? typed.value : "") || "").trim();
    if (!email) return;
    try {
      const data = await api("/forgot-password", "POST", { email });
      setMessage("loginMessage", data.message, false);
    } catch (err) {
      setMessage("loginMessage", err.message);
    }
  });
}

// ------------------------------------------------------------
// Reset password (page opened from the emailed link: login.html?reset_token=XXXX)
// ------------------------------------------------------------
const resetForm = document.getElementById("resetForm");

if (resetForm) {
  const resetToken = new URLSearchParams(window.location.search).get("reset_token");
  if (resetToken) {
    resetForm.style.display = "block";
    if (loginForm) loginForm.style.display = "none";
  }

  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const newPassword = document.getElementById("newPassword").value;
    const confirmNew = document.getElementById("confirmNewPassword").value;

    if (!isStrongPassword(newPassword)) {
      setMessage("resetMessage", "Password must be at least 9 characters and include uppercase, lowercase, and a special character.");
      return;
    }
    if (newPassword !== confirmNew) {
      setMessage("resetMessage", "Passwords do not match.");
      return;
    }
    try {
      const data = await api("/reset-password", "POST", { token: resetToken, new_password: newPassword });
      setMessage("resetMessage", data.message, false);
      setTimeout(() => (window.location.href = "login.html"), 1200);
    } catch (err) {
      setMessage("resetMessage", err.message);
    }
  });
}

// ------------------------------------------------------------
// Logout
// ------------------------------------------------------------
const logoutBtn = document.getElementById("logoutBtn");

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    clearSession();
    window.location.href = "login.html";
  });
}

// ------------------------------------------------------------
// Run billing button (admin/staff only)
// ------------------------------------------------------------
const runBillingBtn = document.getElementById("runBillingBtn");

if (runBillingBtn) {
  if (localStorage.getItem("role") === "customer") {
    runBillingBtn.style.display = "none";
  }

  runBillingBtn.addEventListener("click", async () => {
    runBillingBtn.disabled = true;
    try {
      const data = await api("/billing/run?auto_confirm=true", "POST");
      alert(`${data.message}\nInvoices generated: ${data.invoices_generated}\nTotal billed: ${data.total_amount_billed}`);
      if (typeof loadDashboard === "function") loadDashboard();
    } catch (err) {
      alert(err.message);
    } finally {
      runBillingBtn.disabled = false;
    }
  });
}