const DEMO_USER_KEY = "brightloopDemoUser";
const DEMO_PASSWORD_KEY = "brightloopDemoPassword";
const DEMO_LOGGED_IN_KEY = "brightloopDemoLoggedIn";

function getDemoUser() {
  try {
    return JSON.parse(localStorage.getItem(DEMO_USER_KEY));
  } catch {
    return null;
  }
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

// Registration demo: keeps the register page working.
const registerForm = document.getElementById("registerForm");

if (registerForm) {
  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const fullName = document.getElementById("fullName").value.trim();
    const companyName = document.getElementById("companyName").value.trim();
    const email = document.getElementById("registerEmail").value.trim().toLowerCase();
    const phone = document.getElementById("phone").value.trim();
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

    const existingUser = getDemoUser();

    if (existingUser && existingUser.email === email) {
      setMessage("registerMessage", "This email is already registered. Please log in.");
      return;
    }

    const user = { fullName, companyName, email, phone };

    localStorage.setItem(DEMO_USER_KEY, JSON.stringify(user));
    localStorage.setItem(DEMO_PASSWORD_KEY, password);

    setMessage("registerMessage", "Account created. Redirecting to login…", false);

    window.setTimeout(() => {
      window.location.href = "login.html";
    }, 800);
  });
}

// Login demo: sets the same login key used by the dashboard.
const loginForm = document.getElementById("loginForm");

if (loginForm) {
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const email = document.getElementById("loginEmail").value.trim().toLowerCase();
    const password = document.getElementById("loginPassword").value;
    const user = getDemoUser();
    const savedPassword = localStorage.getItem(DEMO_PASSWORD_KEY);

    if (!user || user.email !== email || savedPassword !== password) {
      setMessage("loginMessage", "Email or password is incorrect, or no demo account exists.");
      return;
    }

    localStorage.setItem(DEMO_LOGGED_IN_KEY, "true");
    window.location.href = "index.html";
  });
}

// Logout
const logoutBtn = document.getElementById("logoutBtn");

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem(DEMO_LOGGED_IN_KEY);
    window.location.href = "login.html";
  });
}

// Demo billing button
const runBillingBtn = document.getElementById("runBillingBtn");

if (runBillingBtn) {
  runBillingBtn.addEventListener("click", () => {
    alert("Demo only: connect this button to the backend billing API.");
  });
}