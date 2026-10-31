// ============================================================
// Brightloop dashboard. Uses api() and API_BASE from auth.js
// ============================================================
const userRole = localStorage.getItem("role") || "customer";
const $ = (id) => document.getElementById(id);
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const emptyRow = (cols, text = "Nothing to show yet.") =>
  `<tr><td colspan="${cols}" style="text-align:center;color:#888">${text}</td></tr>`;
const badge = (s) => `<span class="badge badge-${String(s).toLowerCase()}">${esc(s)}</span>`;

function toast(message, isError = false) {
  const t = $("toast");
  t.textContent = message;
  t.className = "show" + (isError ? " error" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.className = ""), 3500);
}

function fillSelect(id, items, labelFn, firstLabel, valueKey = "id") {
  const el = $(id);
  if (!el) return;
  const prev = el.value;
  el.innerHTML =
    `<option value="">${esc(firstLabel)}</option>` +
    items.map((i) => `<option value="${i[valueKey]}">${esc(labelFn(i))}</option>`).join("");
  el.value = prev;
}

function debounce(fn, ms = 300) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

// ------------------------------------------------------------
// Role-based UI and navigation
// ------------------------------------------------------------
document.querySelectorAll("[data-roles]").forEach((el) => {
  if (!el.dataset.roles.split(",").includes(userRole)) el.style.display = "none";
});
$("userInfo").textContent = `${localStorage.getItem("user_name") || ""} (${userRole})`;

const PAGES = {
  dashboardPage: ["Dashboard", "Welcome back! Here's your business overview.", loadDashboard],
  productsPage: ["Products & Plans", "Manage products, variants, taxes and plans.", loadProducts],
  subscriptionsPage: ["Subscriptions", "Track every subscription from draft to closed.", loadSubscriptions],
  invoicesPage: ["Invoices", "Confirm, send, print and collect payment.", loadInvoices],
  paymentsPage: ["Payments", "All payments received.", loadPayments],
  discountsPage: ["Discounts", "Rules that apply automatically on invoices.", loadDiscounts],
  staffPage: ["Team", "Only the admin can add staff.", () => {}],
};

function showPage(pageId) {
  Object.keys(PAGES).forEach((id) => {
    const sec = $(id);
    if (sec) sec.hidden = id !== pageId;
  });
  document.querySelectorAll("#mainNav a").forEach((a) => a.classList.toggle("active", a.dataset.page === pageId));
  $("pageTitle").textContent = PAGES[pageId][0];
  $("pageDescription").textContent = PAGES[pageId][1];
  PAGES[pageId][2]();
}

document.querySelectorAll("#mainNav a").forEach((a) =>
  a.addEventListener("click", (e) => {
    e.preventDefault();
    showPage(a.dataset.page);
  })
);

// ------------------------------------------------------------
// Dashboard
// ------------------------------------------------------------
async function loadDashboard() {
  if (userRole === "customer") return;
  try {
    const qs = new URLSearchParams();
    if ($("dashFrom").value) qs.set("date_from", $("dashFrom").value);
    if ($("dashTo").value) qs.set("date_to", $("dashTo").value);
    const [s, recent, overdue] = await Promise.all([
      api("/dashboard/summary?" + qs),
      api("/subscriptions?page_size=5"),
      api("/invoices?overdue=true&page_size=10"),
    ]);
    $("activeCount").textContent = s.active_subscriptions;
    $("revenue").textContent = money(s.mrr);
    $("paymentsReceived").textContent = money(s.revenue_collected);
    $("outstandingAmount").textContent = money(s.outstanding_amount);
    $("overdueCount").textContent = s.overdue_invoices;

    $("overdueTable").innerHTML =
      overdue
        .map(
          (i) => `<tr><td>${esc(i.invoice_number)}</td><td>${esc(i.customer_email)}</td>
                  <td>${esc(i.due_date)}</td><td>${money(i.outstanding)}</td></tr>`
        )
        .join("") || emptyRow(4, "No overdue invoices 🎉");

    $("subscriptionTable").innerHTML =
      recent
        .map(
          (s) => `<tr><td>${esc(s.customer_email)}</td><td>${esc(s.plan_name)}</td>
                  <td>${esc(s.subscription_number)}</td><td>${badge(s.status)}</td></tr>`
        )
        .join("") || emptyRow(4);
  } catch (err) {
    toast(err.message, true);
  }
}
$("dashFilterForm").addEventListener("submit", (e) => {
  e.preventDefault();
  loadDashboard();
});

// ------------------------------------------------------------
// Products, variants, taxes, plans
// ------------------------------------------------------------
let productsCache = [];

async function loadProducts() {
  try {
    const [products, plans, taxes] = await Promise.all([api("/products"), api("/plans"), api("/taxes")]);
    productsCache = products;
    $("productTable").innerHTML =
      products
        .map(
          (p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.type)}</td><td>${money(p.sales_price)}</td>
            <td>${money(p.cost_price)}</td><td>${esc(p.tax_name || "-")}</td>
            <td>${p.variants.map((v) => `${esc(v.variant_name)} (+${v.price_extra})`).join(", ") || "-"}</td></tr>`
        )
        .join("") || emptyRow(6);

    fillSelect("productTax", taxes, (t) => `${t.name} (${t.rate}%)`, "No tax");
    fillSelect("variantProduct", products, (p) => p.name, "Select product");

    $("planTable").innerHTML =
      plans
        .map((p) => {
          let actions = "";
          if (userRole === "admin") {
            if (!p.allow_pause_renew) actions = "<small>Locked</small>";
            else if (p.status === "Active")
              actions = `<button class="btn-sm" data-act="plan" data-id="${p.id}" data-status="Paused">Pause</button>
                         <button class="btn-sm" data-act="plan" data-id="${p.id}" data-status="Closed">Close</button>`;
            else if (p.status === "Paused")
              actions = `<button class="btn-sm" data-act="plan" data-id="${p.id}" data-status="Active">Resume</button>
                         <button class="btn-sm" data-act="plan" data-id="${p.id}" data-status="Closed">Close</button>`;
            else
              actions = `<button class="btn-sm" data-act="plan" data-id="${p.id}" data-status="Active" data-renew="1">Renew</button>`;
          }
          return `<tr><td>${esc(p.name)}</td><td>${esc(p.billing_period)}</td><td>${money(p.price)}</td>
            <td>${p.min_quantity}</td><td>${esc(p.start_date || "—")} → ${esc(p.end_date || "—")}</td>
            <td>${badge(p.status)}</td><td>${actions}</td></tr>`;
        })
        .join("") || emptyRow(7);
  } catch (err) {
    toast(err.message, true);
  }
}

$("planTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act='plan']");
  if (!btn) return;
  try {
    let url = `/plans/${btn.dataset.id}/status?status=${btn.dataset.status}`;
    if (btn.dataset.renew) {
      const end = prompt("New end date (YYYY-MM-DD):");
      if (!end) return;
      url += `&new_end_date=${encodeURIComponent(end)}`;
    }
    await api(url, "PUT");
    toast("Plan updated");
    loadProducts();
  } catch (err) {
    toast(err.message, true);
  }
});

$("taxForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/taxes", "POST", { name: $("taxName").value.trim(), rate: parseFloat($("taxRate").value) });
    e.target.reset();
    toast("Tax added");
    loadProducts();
  } catch (err) {
    toast(err.message, true);
  }
});

$("productForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/products", "POST", {
      name: $("productName").value.trim(),
      type: $("productType").value,
      sales_price: parseFloat($("productPrice").value),
      cost_price: parseFloat($("productCost").value),
      notes: $("productNotes").value.trim(),
      tax_id: $("productTax").value ? parseInt($("productTax").value) : null,
    });
    e.target.reset();
    toast("Product added");
    loadProducts();
  } catch (err) {
    toast(err.message, true);
  }
});

$("variantForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/product-variants", "POST", {
      product_id: parseInt($("variantProduct").value),
      variant_name: $("variantName").value.trim(),
      price_extra: parseFloat($("variantExtra").value),
    });
    e.target.reset();
    toast("Variant added");
    loadProducts();
  } catch (err) {
    toast(err.message, true);
  }
});

$("planForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/plans", "POST", {
      name: $("planName").value.trim(),
      billing_period: $("planPeriod").value,
      price: parseFloat($("planPrice").value),
      min_quantity: parseInt($("planMinQty").value) || 1,
      start_date: $("planStart").value || null,
      end_date: $("planEnd").value || null,
      auto_close: $("planAutoClose").checked,
      allow_pause_renew: $("planAllowPause").checked,
    });
    e.target.reset();
    toast("Plan added");
    loadProducts();
  } catch (err) {
    toast(err.message, true);
  }
});

// ------------------------------------------------------------
// Subscriptions
// ------------------------------------------------------------
let pendingLines = [];
const NEXT_STATUS = { Draft: ["Quotation", "Send quotation"], Quotation: ["Confirmed", "Confirm"], Confirmed: ["Active", "Activate"] };

async function loadSubscriptions() {
  try {
    const qs = new URLSearchParams();
    if ($("subStatusFilter").value) qs.set("status", $("subStatusFilter").value);
    if ($("subSearch").value.trim()) qs.set("q", $("subSearch").value.trim());
    const subs = await api("/subscriptions?" + qs);

    $("allSubscriptionsTable").innerHTML =
      subs
        .map((s) => {
          let actions = "";
          if (userRole !== "customer" && NEXT_STATUS[s.status]) {
            const [to, label] = NEXT_STATUS[s.status];
            actions += `<button class="btn-sm" data-act="sub" data-id="${s.id}" data-status="${to}">${label}</button> `;
          }
          if (s.status !== "Closed")
            actions += `<button class="btn-sm" data-act="sub" data-id="${s.id}" data-status="Closed">Close</button>`;
          return `<tr><td>${esc(s.subscription_number)}</td><td>${esc(s.customer_email)}</td>
            <td>${esc(s.plan_name)} (${esc(s.billing_period)})</td>
            <td>${esc(s.start_date)} → ${esc(s.expiry_date)}</td><td>${badge(s.status)}</td><td>${actions}</td></tr>`;
        })
        .join("") || emptyRow(6);

    if (userRole !== "customer") await loadSubscriptionFormData();
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadSubscriptionFormData() {
  const [customers, plans, products, templates] = await Promise.all([
    api("/users?role=customer"),
    api("/plans"),
    api("/products"),
    api("/quotation-templates"),
  ]);
  productsCache = products;
  fillSelect("subCustomer", customers, (c) => `${c.name || ""} ${c.email}`.trim(), "Select customer");
  fillSelect("subTemplate", templates, (t) => `${t.name} (valid ${t.validity_days} days)`, "No template");
  fillSelect("subPlan", plans.filter((p) => p.status === "Active"), (p) => `${p.name} - ${p.billing_period}`, "Select plan");
  fillSelect("lineProduct", products, (p) => `${p.name} (${money(p.sales_price)})`, "Select product");
  fillVariants();
}

function fillVariants() {
  const prod = productsCache.find((p) => String(p.id) === $("lineProduct").value);
  const variants = prod ? prod.variants : [];
  $("lineVariant").innerHTML =
    `<option value="">No variant</option>` +
    variants.map((v) => `<option value="${v.id}">${esc(v.variant_name)} (+${v.price_extra})</option>`).join("");
}
$("lineProduct").addEventListener("change", fillVariants);

function renderPendingLines() {
  $("pendingLines").innerHTML = pendingLines
    .map((l, i) => `<li>${esc(l.label)} × ${l.quantity} <button type="button" class="btn-sm" data-remove="${i}">remove</button></li>`)
    .join("");
}

$("addLineBtn").addEventListener("click", () => {
  const prod = productsCache.find((p) => String(p.id) === $("lineProduct").value);
  if (!prod) return toast("Select a product first.", true);
  const variantId = $("lineVariant").value;
  const variant = prod.variants.find((v) => String(v.id) === variantId);
  pendingLines.push({
    product_id: prod.id,
    variant_id: variant ? variant.id : null,
    quantity: parseInt($("lineQty").value) || 1,
    label: prod.name + (variant ? ` - ${variant.variant_name}` : ""),
  });
  renderPendingLines();
});

$("pendingLines").addEventListener("click", (e) => {
  const idx = e.target.dataset.remove;
  if (idx !== undefined) {
    pendingLines.splice(parseInt(idx), 1);
    renderPendingLines();
  }
});

$("subscriptionForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await api("/subscriptions", "POST", {
      customer_id: parseInt($("subCustomer").value),
      plan_id: $("subPlan").value ? parseInt($("subPlan").value) : null,
      template_id: $("subTemplate").value ? parseInt($("subTemplate").value) : null,
      payment_terms: $("subTerms").value.trim(),
      start_date: $("subStart").value,
      expiry_date: $("subExpiry").value,
      line_items: pendingLines.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id, quantity })),
    });
    pendingLines = [];
    renderPendingLines();
    e.target.reset();
    $("subTerms").value = "Net 15";
    toast(`Created ${res.subscription_number} (Draft)`);
    loadSubscriptions();
  } catch (err) {
    toast(err.message, true);
  }
});

$("allSubscriptionsTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act='sub']");
  if (!btn) return;
  try {
    await api(`/subscriptions/${btn.dataset.id}/status?status=${btn.dataset.status}`, "PUT");
    toast(`Subscription is now ${btn.dataset.status}`);
    loadSubscriptions();
  } catch (err) {
    toast(err.message, true);
  }
});
$("subStatusFilter").addEventListener("change", loadSubscriptions);
$("subSearch").addEventListener("input", debounce(loadSubscriptions));

// ------------------------------------------------------------
// Invoices
// ------------------------------------------------------------
async function loadInvoices() {
  try {
    const qs = new URLSearchParams();
    if ($("invStatusFilter").value) qs.set("status", $("invStatusFilter").value);
    if ($("invOverdueOnly").checked) qs.set("overdue", "true");
    if ($("invSearch").value.trim()) qs.set("q", $("invSearch").value.trim());
    const invoices = await api("/invoices?" + qs);

    $("invoiceTable").innerHTML =
      invoices
        .map((i) => {
          let actions = `<button class="btn-sm" data-act="print" data-id="${i.id}">Print</button> `;
          if (userRole !== "customer") {
            if (i.status === "Draft")
              actions += `<button class="btn-sm" data-act="confirm" data-id="${i.id}">Confirm</button> `;
            if (i.status === "Confirmed")
              actions += `<button class="btn-sm" data-act="pay" data-id="${i.id}" data-out="${i.outstanding}">Record payment</button> `;
            if (i.status !== "Cancelled")
              actions += `<button class="btn-sm" data-act="send" data-id="${i.id}">Send</button> `;
            if (i.status === "Draft" || i.status === "Confirmed")
              actions += `<button class="btn-sm" data-act="cancel" data-id="${i.id}">Cancel</button>`;
          }
          const overdue = i.is_overdue ? ' <span class="badge badge-overdue">Overdue</span>' : "";
          return `<tr><td>${esc(i.invoice_number)}</td><td>${esc(i.customer_email)}</td>
            <td>${esc(i.period_start)} → ${esc(i.period_end)}</td><td>${money(i.total)}</td>
            <td>${money(i.outstanding)}</td><td>${esc(i.due_date)}</td>
            <td>${badge(i.status)}${overdue}</td><td>${actions}</td></tr>`;
        })
        .join("") || emptyRow(8);
  } catch (err) {
    toast(err.message, true);
  }
}

$("invoiceTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = btn.dataset.id;
  try {
    switch (btn.dataset.act) {
      case "print":
        window.open(`${API_BASE}/invoices/${id}/print?token=${localStorage.getItem("token")}`, "_blank");
        return;
      case "confirm":
        await api(`/invoices/${id}/confirm`, "POST");
        toast("Invoice confirmed");
        break;
      case "cancel":
        if (!confirm("Cancel this invoice?")) return;
        await api(`/invoices/${id}/cancel`, "POST");
        toast("Invoice cancelled");
        break;
      case "send": {
        const r = await api(`/invoices/${id}/send`, "POST");
        toast(r.message);
        return;
      }
      case "pay": {
        const method = prompt("Payment method (UPI / Card / Bank Transfer / Cash):", "UPI");
        if (!method) return;
        const amount = parseFloat(prompt("Amount:", btn.dataset.out));
        if (!amount) return;
        const note = prompt("Note (optional):", "") || "";
        const r = await api(`/invoices/${id}/payments`, "POST", { method, amount, note });
        toast(r.message);
        break;
      }
    }
    loadInvoices();
  } catch (err) {
    toast(err.message, true);
  }
});
$("invStatusFilter").addEventListener("change", loadInvoices);
$("invOverdueOnly").addEventListener("change", loadInvoices);
$("invSearch").addEventListener("input", debounce(loadInvoices));

// ------------------------------------------------------------
// Payments
// ------------------------------------------------------------
async function loadPayments() {
  try {
    const pays = await api("/payments");
    $("paymentTable").innerHTML =
      pays
        .map(
          (p) => `<tr><td>PAY-${String(p.id).padStart(4, "0")}</td><td>${esc(p.invoice_number)}</td>
            <td>${esc(p.customer_email)}</td><td>${money(p.amount)}</td><td>${esc(p.payment_date)}</td>
            <td>${esc(p.method)}</td><td>${esc(p.note || "")}</td></tr>`
        )
        .join("") || emptyRow(7);
  } catch (err) {
    toast(err.message, true);
  }
}

// ------------------------------------------------------------
// Discounts
// ------------------------------------------------------------
async function loadDiscounts() {
  try {
    const [discounts, products] = await Promise.all([api("/discounts"), api("/products")]);
    fillSelect("discProduct", products, (p) => p.name, "Select product (for product discounts)");
    $("discountTable").innerHTML =
      discounts
        .map((d) => {
          const value = d.type === "percentage" ? `${d.value}%` : money(d.value);
          const target =
            d.applies_to === "product"
              ? "Product: " + esc((products.find((p) => p.id === d.product_id) || {}).name || d.product_id)
              : "Whole subscriptions";
          return `<tr><td>${esc(d.code)}</td><td>${value}</td>
            <td>Qty ${d.min_quantity}, ${money(d.min_amount)}</td>
            <td>${esc(d.start_date || "—")} → ${esc(d.end_date || "—")}</td>
            <td>${d.used_count}${d.max_uses ? " / " + d.max_uses : ""}</td><td>${target}</td></tr>`;
        })
        .join("") || emptyRow(6);
  } catch (err) {
    toast(err.message, true);
  }
}

$("discountForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const appliesTo = $("discAppliesTo").value;
    await api("/discounts", "POST", {
      code: $("discCode").value.trim(),
      type: $("discType").value,
      value: parseFloat($("discValue").value),
      min_amount: parseFloat($("discMinAmount").value) || 0,
      min_quantity: parseInt($("discMinQty").value) || 1,
      start_date: $("discStart").value || null,
      end_date: $("discEnd").value || null,
      max_uses: $("discMaxUses").value ? parseInt($("discMaxUses").value) : null,
      applies_to: appliesTo,
      product_id: appliesTo === "product" && $("discProduct").value ? parseInt($("discProduct").value) : null,
    });
    e.target.reset();
    toast("Discount rule created");
    loadDiscounts();
  } catch (err) {
    toast(err.message, true);
  }
});

// ------------------------------------------------------------
// Team (admin only)
// ------------------------------------------------------------
$("staffForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/staff", "POST", {
      name: $("staffName").value.trim(),
      email: $("staffEmail").value.trim(),
      password: $("staffPassword").value,
    });
    e.target.reset();
    toast("Staff member added");
  } catch (err) {
    toast(err.message, true);
  }
});

// ------------------------------------------------------------
// Start
// ------------------------------------------------------------
$("subStart").value = new Date().toISOString().slice(0, 10);
showPage(userRole === "customer" ? "subscriptionsPage" : "dashboardPage");