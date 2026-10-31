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
const todayISO = () => new Date().toISOString().slice(0, 10);

let productsCache = [];

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
// Modal
// ------------------------------------------------------------
function openModal(htmlText) {
  $("modalBody").innerHTML = htmlText;
  $("modal").hidden = false;
}
function closeModal() {
  $("modal").hidden = true;
}
$("modalClose").addEventListener("click", closeModal);
$("modal").addEventListener("click", (e) => {
  if (e.target.id === "modal") closeModal();
});

// ------------------------------------------------------------
// Role-based UI and navigation
// ------------------------------------------------------------
document.querySelectorAll("[data-roles]").forEach((el) => {
  if (!el.dataset.roles.split(",").includes(userRole)) el.style.display = "none";
});
$("userInfo").textContent = `${localStorage.getItem("user_name") || ""} (${userRole})`;

const PAGES = {
  dashboardPage: ["Dashboard", "Welcome back! Here's your business overview.", () => loadDashboard()],
  productsPage: ["Products & Plans", "Manage products, variants, taxes and plans.", () => loadProducts()],
  templatesPage: ["Quotation Templates", "Ready-made offers with plan and product lines.", () => loadTemplates()],
  subscriptionsPage: ["Subscriptions", "Track every subscription from draft to closed.", () => loadSubscriptions()],
  invoicesPage: ["Invoices", "Confirm, send, print and collect payment.", () => loadInvoices()],
  paymentsPage: ["Payments", "All payments received.", () => loadPayments()],
  discountsPage: ["Discounts", "Rules that apply automatically on invoices.", () => loadDiscounts()],
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

    const summarize = (obj) =>
      Object.entries(obj || {}).map(([k, v]) => `${badge(k)} ${v}`).join(" &nbsp; ") || "—";
    $("subStatusSummary").innerHTML = summarize(s.subscriptions_by_status);
    $("invStatusSummary").innerHTML = summarize(s.invoices_by_status);

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
          (r) => `<tr><td>${esc(r.customer_email)}</td><td>${esc(r.plan_name)}</td>
                  <td>${esc(r.subscription_number)}</td><td>${badge(r.status)}</td></tr>`
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
// Product-line builder (used by templates and subscriptions)
// ------------------------------------------------------------
function makeLineBuilder(productId, variantId, qtyId, addBtnId, listId) {
  const lines = [];

  function fillVariants() {
    const prod = productsCache.find((p) => String(p.id) === $(productId).value);
    const variants = prod ? prod.variants : [];
    $(variantId).innerHTML =
      `<option value="">No variant</option>` +
      variants.map((v) => `<option value="${v.id}">${esc(v.variant_name)} (+${v.price_extra})</option>`).join("");
  }

  function render() {
    $(listId).innerHTML = lines
      .map((l, i) => `<li>${esc(l.label)} × ${l.quantity} <button type="button" class="btn-sm" data-remove="${i}">remove</button></li>`)
      .join("");
  }

  $(productId).addEventListener("change", fillVariants);
  $(addBtnId).addEventListener("click", () => {
    const prod = productsCache.find((p) => String(p.id) === $(productId).value);
    if (!prod) return toast("Select a product first.", true);
    const variant = prod.variants.find((v) => String(v.id) === $(variantId).value);
    lines.push({
      product_id: prod.id,
      variant_id: variant ? variant.id : null,
      quantity: parseInt($(qtyId).value) || 1,
      label: prod.name + (variant ? ` - ${variant.variant_name}` : ""),
    });
    render();
  });
  $(listId).addEventListener("click", (e) => {
    const idx = e.target.dataset.remove;
    if (idx !== undefined) {
      lines.splice(parseInt(idx), 1);
      render();
    }
  });

  return {
    lines,
    fillVariants,
    clear() {
      lines.length = 0;
      render();
    },
    payload: () => lines.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id, quantity })),
  };
}

const subLines = makeLineBuilder("lineProduct", "lineVariant", "lineQty", "addLineBtn", "pendingLines");
const tplLines = makeLineBuilder("tplProduct", "tplVariant", "tplQty", "tplAddLineBtn", "tplPendingLines");

// ------------------------------------------------------------
// Quotation templates
// ------------------------------------------------------------
async function loadTemplates() {
  try {
    const [templates, plans, products] = await Promise.all([
      api("/quotation-templates"),
      api("/plans"),
      api("/products"),
    ]);
    productsCache = products;
    fillSelect("tplPlan", plans.filter((p) => p.status === "Active"), (p) => `${p.name} - ${p.billing_period}`, "Select plan");
    fillSelect("tplProduct", products, (p) => `${p.name} (${money(p.sales_price)})`, "Select product");
    tplLines.fillVariants();

    $("templateTable").innerHTML =
      templates
        .map(
          (t) => `<tr><td>${esc(t.name)}</td><td>${esc(t.plan_name)}</td><td>${t.validity_days} days</td>
            <td>${t.lines.map((l) => `${esc(l.product_name)}${l.variant_name ? " (" + esc(l.variant_name) + ")" : ""} × ${l.quantity}`).join("<br>")}</td></tr>`
        )
        .join("") || emptyRow(4);
  } catch (err) {
    toast(err.message, true);
  }
}

$("templateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/quotation-templates", "POST", {
      name: $("tplName").value.trim(),
      plan_id: parseInt($("tplPlan").value),
      validity_days: parseInt($("tplValidity").value) || 30,
      lines: tplLines.payload(),
    });
    e.target.reset();
    $("tplValidity").value = 30;
    tplLines.clear();
    toast("Template saved");
    loadTemplates();
  } catch (err) {
    toast(err.message, true);
  }
});

// ------------------------------------------------------------
// Subscriptions
// ------------------------------------------------------------
const NEXT_STATUS = {
  Draft: ["Quotation", "Send quotation"],
  Quotation: ["Confirmed", "Confirm"],
  Confirmed: ["Active", "Activate"],
};

async function loadSubscriptions() {
  try {
    const qs = new URLSearchParams();
    if ($("subStatusFilter").value) qs.set("status", $("subStatusFilter").value);
    if ($("subSearch").value.trim()) qs.set("q", $("subSearch").value.trim());
    const subs = await api("/subscriptions?" + qs);

    $("allSubscriptionsTable").innerHTML =
      subs
        .map((s) => {
          let actions = `<button class="btn-sm" data-act="view" data-id="${s.id}">View</button> `;
          if (userRole !== "customer" && NEXT_STATUS[s.status]) {
            const [to, label] = NEXT_STATUS[s.status];
            actions += `<button class="btn-sm" data-act="sub" data-id="${s.id}" data-status="${to}">${label}</button> `;
          }
          if (s.status !== "Closed")
            actions += `<button class="btn-sm" data-act="sub" data-id="${s.id}" data-status="Closed">Close</button>`;
          let valid = "";
          if (s.quote_valid_until && (s.status === "Draft" || s.status === "Quotation")) {
            const expired = s.quote_valid_until < todayISO();
            valid = `<br><small>${expired ? "Quote expired" : "Quote valid until"} ${esc(s.quote_valid_until)}</small>`;
          }
          return `<tr><td>${esc(s.subscription_number)}</td><td>${esc(s.customer_email)}</td>
            <td>${esc(s.plan_name)} (${esc(s.billing_period)})<br><small>${esc(s.payment_terms)}</small></td>
            <td>${esc(s.start_date)} → ${esc(s.expiry_date)}</td><td>${badge(s.status)}${valid}</td><td>${actions}</td></tr>`;
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
  fillSelect("subPlan", plans.filter((p) => p.status === "Active"), (p) => `${p.name} - ${p.billing_period}`, "Plan (or from template)");
  fillSelect("lineProduct", products, (p) => `${p.name} (${money(p.sales_price)})`, "Select product");
  subLines.fillVariants();
}

async function viewSubscription(id) {
  const s = await api(`/subscriptions/${id}`);
  let subtotal = 0, tax = 0;
  const rows = s.lines
    .map((l) => {
      subtotal += l.total_amount;
      tax += (l.total_amount * (l.tax_rate || 0)) / 100;
      return `<tr><td>${esc(l.product_name)}${l.variant_name ? " (" + esc(l.variant_name) + ")" : ""}</td>
        <td>${l.quantity}</td><td>${money(l.unit_price)}</td><td>${l.tax_rate}%</td><td>${money(l.total_amount)}</td></tr>`;
    })
    .join("");
  openModal(`
    <h3>${esc(s.subscription_number)} ${badge(s.status)}</h3>
    <p>Customer: ${esc(s.customer_email)}<br>Plan: ${esc(s.plan_name)} (${esc(s.billing_period)})<br>
    ${esc(s.start_date)} → ${esc(s.expiry_date)} · ${esc(s.payment_terms)}
    ${s.quote_valid_until ? "<br>Quotation valid until " + esc(s.quote_valid_until) : ""}</p>
    <table><thead><tr><th>Product</th><th>Qty</th><th>Unit price</th><th>Tax</th><th>Amount</th></tr></thead>
    <tbody>${rows || emptyRow(5, "No lines")}</tbody></table>
    <p>Subtotal: ${money(subtotal)}<br>Tax: ${money(tax)}<br><strong>Total per period: ${money(subtotal + tax)}</strong></p>`);
}

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
      line_items: subLines.payload(),
    });
    subLines.clear();
    e.target.reset();
    $("subTerms").value = "Net 15";
    $("subStart").value = todayISO();
    toast(`Created ${res.subscription_number} (Draft)`);
    loadSubscriptions();
  } catch (err) {
    toast(err.message, true);
  }
});

$("allSubscriptionsTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  try {
    if (btn.dataset.act === "view") return await viewSubscription(btn.dataset.id);
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
          let actions =
            `<button class="btn-sm" data-act="view" data-id="${i.id}">View</button> ` +
            `<button class="btn-sm" data-act="print" data-id="${i.id}">Print</button> `;
          if (userRole !== "customer") {
            if (i.status === "Draft")
              actions += `<button class="btn-sm" data-act="confirm" data-id="${i.id}">Confirm</button> `;
            if (i.status === "Confirmed")
              actions += `<button class="btn-sm" data-act="pay" data-id="${i.id}" data-num="${esc(i.invoice_number)}" data-out="${i.outstanding}">Record payment</button> `;
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

async function viewInvoice(id) {
  const i = await api(`/invoices/${id}`);
  const lines = i.lines
    .map(
      (l) => `<tr><td>${esc(l.description)}</td><td>${l.quantity}</td><td>${money(l.unit_price)}</td>
        <td>${l.tax_rate}%</td><td>${money(l.amount)}</td></tr>`
    )
    .join("");
  const pays = i.payments
    .map((p) => `<tr><td>${esc(p.payment_date)}</td><td>${esc(p.method)}</td><td>${money(p.amount)}</td><td>${esc(p.note || "")}</td></tr>`)
    .join("");
  openModal(`
    <h3>${esc(i.invoice_number)} ${badge(i.status)}${i.is_overdue ? ' <span class="badge badge-overdue">Overdue</span>' : ""}</h3>
    <p>${esc(i.customer_email)} · ${esc(i.subscription_number)}<br>
    Period ${esc(i.period_start)} → ${esc(i.period_end)} · Due ${esc(i.due_date)}</p>
    <table><thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Tax</th><th>Amount</th></tr></thead>
    <tbody>${lines}</tbody></table>
    <p>Subtotal: ${money(i.subtotal)}<br>Discount: -${money(i.discount_amount)}<br>Tax: ${money(i.tax_amount)}<br>
    <strong>Total: ${money(i.total)}</strong><br>Paid: ${money(i.paid_amount)}<br>
    <strong>Outstanding: ${money(i.outstanding)}</strong></p>
    <h4>Payments</h4>
    <table><thead><tr><th>Date</th><th>Method</th><th>Amount</th><th>Note</th></tr></thead>
    <tbody>${pays || emptyRow(4, "No payments yet")}</tbody></table>`);
}

function openPayModal(id, number, outstanding) {
  openModal(`
    <h3>Record payment · ${esc(number)}</h3>
    <form id="payForm" data-id="${id}">
      <label>Method
        <select id="payMethod">
          <option>UPI</option><option>Card</option><option>Bank Transfer</option><option>Cash</option><option>Cheque</option>
        </select>
      </label>
      <label>Amount <input id="payAmount" type="number" step="0.01" min="0.01" value="${outstanding}" required /></label>
      <label>Date <input id="payDate" type="date" value="${todayISO()}" required /></label>
      <label>Note <input id="payNote" type="text" placeholder="Optional note" /></label>
      <button type="submit">Save payment</button>
    </form>`);
}

$("modalBody").addEventListener("submit", async (e) => {
  if (e.target.id !== "payForm") return;
  e.preventDefault();
  try {
    const r = await api(`/invoices/${e.target.dataset.id}/payments`, "POST", {
      method: $("payMethod").value,
      amount: parseFloat($("payAmount").value),
      payment_date: $("payDate").value,
      note: $("payNote").value.trim(),
    });
    closeModal();
    toast(r.message);
    loadInvoices();
  } catch (err) {
    toast(err.message, true);
  }
});

$("invoiceTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = btn.dataset.id;
  try {
    switch (btn.dataset.act) {
      case "view":
        return await viewInvoice(id);
      case "print":
        window.open(`${API_BASE}/invoices/${id}/print?token=${localStorage.getItem("token")}`, "_blank");
        return;
      case "pay":
        return openPayModal(id, btn.dataset.num, btn.dataset.out);
      case "send": {
        const r = await api(`/invoices/${id}/send`, "POST");
        toast(r.message);
        return;
      }
      case "confirm":
        await api(`/invoices/${id}/confirm`, "POST");
        toast("Invoice confirmed");
        break;
      case "cancel":
        if (!confirm("Cancel this invoice?")) return;
        await api(`/invoices/${id}/cancel`, "POST");
        toast("Invoice cancelled");
        break;
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
    const qs = new URLSearchParams();
    if ($("payFrom").value) qs.set("date_from", $("payFrom").value);
    if ($("payTo").value) qs.set("date_to", $("payTo").value);
    const pays = await api("/payments?" + qs);
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
$("payFrom").addEventListener("change", loadPayments);
$("payTo").addEventListener("change", loadPayments);

// ------------------------------------------------------------
// Discounts
// ------------------------------------------------------------
async function loadDiscounts() {
  try {
    const [discounts, products, subs] = await Promise.all([
      api("/discounts"),
      api("/products"),
      api("/subscriptions?page_size=200"),
    ]);
    fillSelect("discProduct", products, (p) => p.name, "Select product (for product discounts)");
    fillSelect("discSubscription", subs, (s) => `${s.subscription_number} - ${s.customer_email}`, "All subscriptions");
    $("discountTable").innerHTML =
      discounts
        .map((d) => {
          const value = d.type === "percentage" ? `${d.value}%` : money(d.value);
          let target;
          if (d.applies_to === "product")
            target = "Product: " + esc((products.find((p) => p.id === d.product_id) || {}).name || d.product_id);
          else if (d.subscription_id)
            target = "Subscription: " + esc((subs.find((s) => s.id === d.subscription_id) || {}).subscription_number || d.subscription_id);
          else target = "All subscriptions";
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
      subscription_id:
        appliesTo === "subscription" && $("discSubscription").value ? parseInt($("discSubscription").value) : null,
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
$("subStart").value = todayISO();
showPage(userRole === "customer" ? "subscriptionsPage" : "dashboardPage");