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

const table = document.getElementById("subscriptionTable");

subscriptions.forEach(subscription => {
    const row = document.createElement("tr");

    row.innerHTML = `
        <td>${subscription.customer}</td>
        <td>${subscription.plan}</td>
        <td>₹${subscription.amount.toLocaleString("en-IN")}</td>
        <td><span class="status">${subscription.status}</span></td>
    `;

    table.appendChild(row);
});

document.getElementById("billingBtn").addEventListener("click", () => {
    alert("Billing API will be connected after backend integration.");
});