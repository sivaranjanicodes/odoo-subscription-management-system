// --------------------
// Dashboard subscriptions
// --------------------
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


// --------------------
// Page navigation
// --------------------
const pageLinks = document.querySelectorAll(".sidebar nav a");

const pages = {
  "Dashboard": document.getElementById("dashboardPage"),
  "Products & Plans": document.getElementById("productsPage"),
  "Subscriptions": document.getElementById("subscriptionsPage")
};

const pageDescriptions = {
  "Dashboard": "Welcome back! Here's your business overview.",
  "Products & Plans": "Manage your products and subscription plans.",
  "Subscriptions": "View and manage customer subscriptions."
};

const pageTitle = document.getElementById("pageTitle");
const pageDescription = document.getElementById("pageDescription");

pageLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();

    const title = link.textContent.trim();
    const selectedPage = pages[title];

    // Ignore menu items whose pages are not built yet.
    if (!selectedPage) {
      return;
    }

    Object.values(pages).forEach((page) => {
      page.hidden = true;
    });

    selectedPage.hidden = false;

    pageLinks.forEach((item) => {
      item.classList.remove("active");
    });

    link.classList.add("active");
    pageTitle.textContent = title;
    pageDescription.textContent = pageDescriptions[title];
  });
});


// --------------------
// Run Billing Day button
// --------------------
document.getElementById("billingBtn").addEventListener("click", () => {
  alert("Billing API will be connected after backend integration.");
});


// --------------------
// Add products
// --------------------
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