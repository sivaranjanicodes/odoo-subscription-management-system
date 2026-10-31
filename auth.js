const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");

if (registerForm) {
  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const name = document.getElementById("registerName").value.trim();
    const email = document.getElementById("registerEmail").value.trim();
    const password = document.getElementById("registerPassword").value;

    const validPassword =
      password.length >= 9 &&
      /[A-Z]/.test(password) &&
      /[a-z]/.test(password) &&
      /[^A-Za-z0-9]/.test(password);

    const message = document.getElementById("registerMessage");

    if (!validPassword) {
      message.textContent =
        "Use at least 9 characters with uppercase, lowercase, and a special character.";
      return;
    }

    message.textContent =
      `Registration form checked for ${name} (${email}). Backend connection is still needed.`;
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();

    document.getElementById("loginMessage").textContent =
      "Login form checked. Backend connection is still needed.";
  });
}