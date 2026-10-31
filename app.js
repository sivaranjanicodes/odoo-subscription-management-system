const subscriptions = [
  {
    customer: "ABC Technologies",
    plan: "Enterprise",
    amount: 5000,
    status: "Active"
  },
  {
    customer: "Green Store",
    plan: "Basic",
    amount: 1000,
    status: "Active"
  },
  {
    customer: "Tech Solutions",
    plan: "Premium",
    amount: 2500,
    status: "Active"
  }
];

// Fill the Recent Subscriptions table
const subscriptionTable = document.getElementById("subscriptionTable");

subscriptions.forEach((subscription) => {
  const row = document.createElement("tr");

  row.innerHTML = `
    <td>${subscription.customer}</td>
    <td>${subscription.plan}</td>
    <td>₹${subscription.amount.toLocaleString("en-IN")}</td>
    <td><span class="status">${subscription.status}</span></td>
  `;

  subscriptionTable.appendChild(row);
});

// Dashboard / Products & Plans navigation
const pageLinks = document.querySelectorAll(".sidebar nav a");
const dashboardPage = document.getElementById("dashboardPage");
const productsPage = document.getElementById("productsPage");
const pageTitle = document.getElementById("pageTitle");
const pageDescription = document.getElementById("pageDescription");

pageLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();

    const page = link.dataset.page;

    // These two pages are implemented; other menu items are placeholders.
    if (page !== "dashboardPage" && page !== "productsPage") {
      return;
    }

    dashboardPage.hidden = page !== "dashboardPage";
    productsPage.hidden = page !== "productsPage";

    pageLinks.forEach((item) => item.classList.remove("active"));
    link.classList.add("active");

    if (page === "productsPage") {
      pageTitle.textContent = "Products & Plans";
      pageDescription.textContent =
        "Manage your products and subscription plans.";
    } else {
      pageTitle.textContent = "Dashboard";
      pageDescription.textContent =
        "Welcome back! Here's your business overview.";
    }
  });
});

// Demo billing button
document.getElementById("billingBtn").addEventListener("click", () => {
  alert("Billing API will be connected after backend integration.");
});

// Add products to the table (temporary browser-only data)
const products = [];
const productForm = document.getElementById("productForm");
const productTable = document.getElementById("productTable");

productForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const product = {
    name: document.getElementById("productName").value.trim(),
    price: Number(document.getElementById("productPrice").value),
    type: document.getElementById("productType").value
  };

  products.push(product);

  productTable.innerHTML = products.map((item) => `
    <tr>
      <td>${item.name}</td>
      <td>${item.type}</td>
      <td>₹${item.price.toLocaleString("en-IN")}</td>
    </tr>
  `).join("");

  productForm.reset();
});