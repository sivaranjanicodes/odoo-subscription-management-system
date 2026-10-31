// --------------------
// Sample subscription data
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


// --------------------
// Dashboard subscriptions table
// --------------------
const subscriptionTable = document.getElementById("subscriptionTable");

function renderDashboardSubscriptions() {
  if (!subscriptionTable) return;

  subscriptionTable.innerHTML = subscriptions.map((subscription) => `
    <tr>
      <td>${subscription.customer}</td>
      <td>${subscription.plan}</td>
      <td>₹${subscription.amount.toLocaleString("en-IN")}</td>
      <td><span class="status">${subscription.status}</span></td>
    </tr>
  `).join("");
}

renderDashboardSubscriptions();


// --------------------
// Page navigation
// --------------------
const pageLinks = document.querySelectorAll(".sidebar nav a");

const pages = {
  "Dashboard": document.getElementById("dashboardPage"),
  "Products & Plans": document.getElementById("productsPage"),
  "Subscriptions": document.getElementById("subscriptionsPage"),
  "Invoices": document.getElementById("invoicesPage"),
  "Payments": document.getElementById("paymentsPage")
};

const pageDescriptions = {
  "Dashboard": "Welcome back! Here's your business overview.",
  "Products & Plans": "Manage your products and subscription plans.",
  "Subscriptions": "View and manage customer subscriptions.",
  "Invoices": "View customer invoices and payment status.",
  "Payments": "View customer payment records and status."
};

const pageTitle = document.getElementById("pageTitle");
const pageDescription = document.getElementById("pageDescription");

pageLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();

    const title = link.textContent.trim();
    const selectedPage = pages[title];

    // Ignore menu items whose pages are not built yet.
    if (!selectedPage) return;

    Object.values(pages).forEach((page) => {
      if (page) page.hidden = true;
    });

    selectedPage.hidden = false;

    pageLinks.forEach((item) => item.classList.remove("active"));
    link.classList.add("active");

    if (pageTitle) pageTitle.textContent = title;
    if (pageDescription) {
      pageDescription.textContent = pageDescriptions[title];
    }
  });
});


// --------------------
// Run Billing Day button
// --------------------
const billingButton = document.getElementById("billingBtn");

if (billingButton) {
  billingButton.addEventListener("click", () => {
    alert("Billing API will be connected after backend integration.");
  });
}


// --------------------
// Add products
// --------------------
const products = [];

const productForm = document.getElementById("productForm");
const productTable = document.getElementById("productTable");

if (productForm && productTable) {
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
}


// --------------------
// Subscriptions page
// --------------------
const subscriptionForm = document.getElementById("subscriptionForm");
const allSubscriptionsTable = document.getElementById("allSubscriptionsTable");

function renderAllSubscriptions() {
  if (!allSubscriptionsTable) return;

  allSubscriptionsTable.innerHTML = subscriptions.map((subscription) => `
    <tr>
      <td>${subscription.customer}</td>
      <td>${subscription.plan}</td>
      <td>₹${subscription.amount.toLocaleString("en-IN")}</td>
      <td><span class="status">${subscription.status}</span></td>
    </tr>
  `).join("");
}

renderAllSubscriptions();

if (subscriptionForm) {
  subscriptionForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const newSubscription = {
      customer: document.getElementById("customerName").value.trim(),
      plan: document.getElementById("subscriptionPlan").value.trim(),
      amount: Number(document.getElementById("subscriptionAmount").value),
      status: "Active"
    };

    subscriptions.push(newSubscription);

    renderAllSubscriptions();
    renderDashboardSubscriptions();
    subscriptionForm.reset();
  });
}


// --------------------
// Invoices sample data
// --------------------
const invoices = [
  {
    id: "INV-001",
    customer: "ABC Technologies",
    amount: 5000,
    dueDate: "2026-11-15",
    status: "Paid"
  },
  {
    id: "INV-002",
    customer: "Green Store",
    amount: 1000,
    dueDate: "2026-11-20",
    status: "Pending"
  }
];

const invoiceTable = document.getElementById("invoiceTable");

if (invoiceTable) {
  invoiceTable.innerHTML = invoices.map((invoice) => `
    <tr>
      <td>${invoice.id}</td>
      <td>${invoice.customer}</td>
      <td>₹${invoice.amount.toLocaleString("en-IN")}</td>
      <td>${invoice.dueDate}</td>
      <td>${invoice.status}</td>
    </tr>
  `).join("");
}


// --------------------
// Payments sample data
// --------------------
const payments = [
  {
    id: "PAY-001",
    customer: "ABC Technologies",
    amount: 5000,
    date: "2026-10-25",
    method: "UPI",
    status: "Successful"
  },
  {
    id: "PAY-002",
    customer: "Green Store",
    amount: 1000,
    date: "2026-10-26",
    method: "Card",
    status: "Pending"
  },
  {
    id: "PAY-003",
    customer: "Tech Solutions",
    amount: 2500,
    date: "2026-10-27",
    method: "Bank Transfer",
    status: "Failed"
  }
];

const paymentTable = document.getElementById("paymentTable");

if (paymentTable) {
  paymentTable.innerHTML = payments.map((payment) => `
    <tr>
      <td>${payment.id}</td>
      <td>${payment.customer}</td>
      <td>₹${payment.amount.toLocaleString("en-IN")}</td>
      <td>${payment.date}</td>
      <td>${payment.method}</td>
      <td>${payment.status}</td>
    </tr>
  `).join("");
}