const API = "/api/v1";
const state = {
  token: localStorage.getItem("stockflow_token"),
  user: JSON.parse(localStorage.getItem("stockflow_user") || "null"),
  products: [],
  availability: [],
  cart: [],
  warehouses: [],
  inventory: [],
  adminOrders: [],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const money = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));
const shortId = (value) => value.slice(0, 8).toUpperCase();

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(`${API}${path}`, { ...options, headers });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(formatDetail(body?.detail) || `Request failed (${response.status})`);
  return body;
}

function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg || JSON.stringify(item)).join("; ");
  if (detail && typeof detail === "object") return detail.message || JSON.stringify(detail);
  return "";
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show${error ? " error" : ""}`;
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => element.className = "toast", 3200);
}

function setSession(payload) {
  state.token = payload?.access_token || null;
  state.user = payload?.user || null;
  if (state.token) {
    localStorage.setItem("stockflow_token", state.token);
    localStorage.setItem("stockflow_user", JSON.stringify(state.user));
  } else {
    localStorage.removeItem("stockflow_token");
    localStorage.removeItem("stockflow_user");
  }
  updateSessionUI();
}

function updateSessionUI() {
  const loggedIn = Boolean(state.user);
  const admin = state.user?.role === "admin";
  $$(".auth-only").forEach(el => el.classList.toggle("hidden", !loggedIn));
  $$(".admin-only").forEach(el => el.classList.toggle("hidden", !admin));
  $("#user-chip").classList.toggle("hidden", !loggedIn);
  $("#user-chip").textContent = loggedIn ? `${state.user.full_name} · ${state.user.role}` : "";
  $("#auth-button").textContent = loggedIn ? "Sign out" : "Sign in";
}

function showView(name) {
  $$(".view").forEach(el => el.classList.toggle("active", el.id === `${name}-view`));
  $$(".nav-link").forEach(el => el.classList.toggle("active", el.dataset.view === name));
  if (name === "orders") loadOrders();
  if (name === "admin") loadAdmin();
}

async function loadProducts() {
  try {
    [state.products, state.availability] = await Promise.all([
      request("/catalog/products"),
      request("/catalog/availability"),
    ]);
    renderProducts();
  } catch (error) {
    $("#product-grid").innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

function renderProducts() {
  if (!state.products.length) {
    $("#product-grid").innerHTML = `<div class="empty">No products yet. Sign in as the demo administrator and add your first product and stock.</div>`;
    return;
  }
  $("#product-grid").innerHTML = state.products.map(product => {
    const locations = state.availability.filter(item => item.product_id === product.id);
    const best = locations[0];
    return `
      <article class="product-card">
        <span class="sku">${product.sku}</span>
        <h3>${escapeHtml(product.name)}</h3>
        <p>${escapeHtml(product.description || "A StockFlow catalogue product.")}</p>
        <div class="product-meta">
          <div><strong>${money(product.price)}</strong><div class="stock-label">${product.available_quantity} available</div></div>
          <button class="button primary add-cart" data-product="${product.id}" data-warehouse="${best?.warehouse_id || ""}" ${best ? "" : "disabled"}>${best ? "Add to cart" : "Out of stock"}</button>
        </div>
      </article>`;
  }).join("");
  $$(".add-cart").forEach(button => button.addEventListener("click", () => addToCart(button.dataset.product, button.dataset.warehouse)));
}

function addToCart(productId, warehouseId) {
  const product = state.products.find(item => item.id === productId);
  const stock = state.availability.find(item => item.product_id === productId && item.warehouse_id === warehouseId);
  const existing = state.cart.find(item => item.productId === productId && item.warehouseId === warehouseId);
  if (existing) {
    if (existing.quantity >= stock.available_quantity) return toast("No more stock is currently available", true);
    existing.quantity += 1;
  } else {
    state.cart.push({ productId, warehouseId, product, stock, quantity: 1 });
  }
  renderCart();
  $("#cart-drawer").classList.add("open");
}

function renderCart() {
  $("#cart-count").textContent = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  $("#cart-total").textContent = money(state.cart.reduce((sum, item) => sum + Number(item.product.price) * item.quantity, 0));
  $("#cart-items").innerHTML = state.cart.length ? state.cart.map((item, index) => `
    <div class="cart-row">
      <div><strong>${escapeHtml(item.product.name)}</strong><small>${item.stock.warehouse_name} · Qty ${item.quantity}</small></div>
      <button data-remove="${index}">Remove</button>
    </div>`).join("") : `<div class="empty">Your cart is empty.</div>`;
  $$("[data-remove]").forEach(button => button.addEventListener("click", () => {
    state.cart.splice(Number(button.dataset.remove), 1);
    renderCart();
  }));
}

async function checkout() {
  if (!state.user) return openAuth();
  if (!state.cart.length) return toast("Add a product before reserving inventory", true);
  const payload = {
    items: state.cart.map(item => ({
      product_id: item.productId,
      warehouse_id: item.warehouseId,
      quantity: item.quantity,
    })),
  };
  try {
    const key = crypto.randomUUID();
    const order = await request("/orders", {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify(payload),
    });
    state.cart = [];
    renderCart();
    $("#cart-drawer").classList.remove("open");
    toast(`Order ${shortId(order.id)} reserved for 15 minutes`);
    await loadProducts();
    showView("orders");
  } catch (error) { toast(error.message, true); }
}

async function loadOrders() {
  if (!state.user) return;
  try {
    const orders = await request("/orders");
    $("#orders-list").innerHTML = orders.length ? orders.map(orderCard).join("") : `<div class="empty">You have not placed an order yet.</div>`;
    bindOrderActions();
  } catch (error) { toast(error.message, true); }
}

function orderCard(order, admin = false) {
  const actions = [];
  if (order.status === "reserved" && !admin) {
    actions.push(`<button class="button primary pay-order" data-id="${order.id}" data-result="success">Pay successfully</button>`);
    actions.push(`<button class="button ghost pay-order" data-id="${order.id}" data-result="failure">Simulate failure</button>`);
    actions.push(`<button class="button ghost cancel-order" data-id="${order.id}">Cancel</button>`);
  }
  if (order.status === "paid" && admin) actions.push(`<button class="button primary fulfil-order" data-id="${order.id}">Mark fulfilled</button>`);
  return `<article class="order-card">
    <div><span class="status">${order.status}</span><h3>Order ${shortId(order.id)}</h3><p>${order.items.length} line(s) · ${money(order.total_amount)} · ${new Date(order.created_at).toLocaleString()}</p></div>
    <div class="order-actions">${actions.join("")}</div>
  </article>`;
}

function bindOrderActions() {
  $$(".pay-order").forEach(button => button.addEventListener("click", async () => {
    try {
      await request(`/orders/${button.dataset.id}/payment`, { method: "POST", body: JSON.stringify({ result: button.dataset.result }) });
      toast(button.dataset.result === "success" ? "Payment accepted" : "Payment failed; stock released");
      await Promise.all([loadOrders(), loadProducts()]);
    } catch (error) { toast(error.message, true); }
  }));
  $$(".cancel-order").forEach(button => button.addEventListener("click", async () => {
    try {
      await request(`/orders/${button.dataset.id}/cancel`, { method: "POST" });
      toast("Order cancelled and stock released");
      await Promise.all([loadOrders(), loadProducts()]);
    } catch (error) { toast(error.message, true); }
  }));
  $$(".fulfil-order").forEach(button => button.addEventListener("click", async () => {
    try {
      await request(`/admin/orders/${button.dataset.id}/fulfil`, { method: "POST" });
      toast("Order fulfilled; reserved stock left the warehouse");
      await loadAdmin();
    } catch (error) { toast(error.message, true); }
  }));
}

async function loadAdmin() {
  if (state.user?.role !== "admin") return;
  try {
    const [products, warehouses, inventory, orders, ledger] = await Promise.all([
      request("/catalog/products"), request("/admin/warehouses"), request("/admin/inventory"),
      request("/admin/orders"), request("/admin/inventory/movements?limit=30"),
    ]);
    state.products = products; state.warehouses = warehouses; state.inventory = inventory; state.adminOrders = orders;
    $("#metric-products").textContent = products.length;
    $("#metric-available").textContent = inventory.reduce((sum, item) => sum + item.available_quantity, 0);
    $("#metric-reserved").textContent = inventory.reduce((sum, item) => sum + item.reserved_quantity, 0);
    $("#metric-orders").textContent = orders.length;
    $("#stock-product").innerHTML = products.map(item => `<option value="${item.id}">${escapeHtml(item.name)} (${item.sku})</option>`).join("");
    $("#stock-warehouse").innerHTML = warehouses.map(item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
    $("#inventory-list").innerHTML = inventory.length ? inventory.map(item => `<div class="table-row"><div><strong>${escapeHtml(item.product_name)}</strong><small>${escapeHtml(item.warehouse_name)}</small></div><strong>${item.available_quantity} / ${item.reserved_quantity}</strong></div>`).join("") : `<div class="empty">No inventory records.</div>`;
    $("#admin-orders-list").innerHTML = orders.length ? orders.map(order => orderCard(order, true)).join("") : `<div class="empty">No orders yet.</div>`;
    $("#ledger-list").innerHTML = ledger.length ? ledger.map(item => `<div class="table-row"><div><strong>${item.movement_type.replaceAll("_", " ")}</strong><small>${new Date(item.created_at).toLocaleString()} · ${item.reason || "No reason"}</small></div><strong>${item.available_delta >= 0 ? "+" : ""}${item.available_delta} available</strong></div>`).join("") : `<div class="empty">No stock movements yet.</div>`;
    bindOrderActions();
  } catch (error) { toast(error.message, true); }
}

function formData(form) { return Object.fromEntries(new FormData(form).entries()); }
function bindAdminForms() {
  $("#product-form").addEventListener("submit", async event => {
    event.preventDefault();
    const data = formData(event.target);
    try { await request("/admin/products", { method: "POST", body: JSON.stringify(data) }); event.target.reset(); toast("Product created"); await loadAdmin(); await loadProducts(); }
    catch (error) { toast(error.message, true); }
  });
  $("#warehouse-form").addEventListener("submit", async event => {
    event.preventDefault();
    try { await request("/admin/warehouses", { method: "POST", body: JSON.stringify(formData(event.target)) }); event.target.reset(); toast("Warehouse created"); await loadAdmin(); }
    catch (error) { toast(error.message, true); }
  });
  $("#stock-form").addEventListener("submit", async event => {
    event.preventDefault();
    const data = formData(event.target); data.quantity_delta = Number(data.quantity_delta);
    try { await request("/admin/inventory/adjust", { method: "POST", body: JSON.stringify(data) }); event.target.reset(); toast("Inventory adjusted and ledger updated"); await loadAdmin(); await loadProducts(); }
    catch (error) { toast(error.message, true); }
  });
}

function openAuth() { $("#auth-modal").classList.add("open"); }
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = value; return div.innerHTML; }

function bindEvents() {
  $$("[data-view]").forEach(button => button.addEventListener("click", event => { event.preventDefault(); showView(button.dataset.view); }));
  $("#auth-button").addEventListener("click", () => state.user ? (setSession(null), showView("store"), toast("Signed out")) : openAuth());
  $("#close-auth").addEventListener("click", () => $("#auth-modal").classList.remove("open"));
  $("#toggle-auth").addEventListener("click", () => {
    const registering = !$("#register-form").classList.contains("hidden");
    $("#register-form").classList.toggle("hidden", registering);
    $("#login-form").classList.toggle("hidden", !registering);
    $("#auth-title").textContent = registering ? "Sign in to StockFlow" : "Create your account";
    $("#toggle-auth").textContent = registering ? "Need an account? Register" : "Already registered? Sign in";
  });
  $("#login-form").addEventListener("submit", async event => {
    event.preventDefault();
    try { const session = await request("/auth/login", { method: "POST", body: JSON.stringify(formData(event.target)) }); setSession(session); $("#auth-modal").classList.remove("open"); toast(`Welcome back, ${session.user.full_name}`); if (session.user.role === "admin") showView("admin"); }
    catch (error) { toast(error.message, true); }
  });
  $("#register-form").addEventListener("submit", async event => {
    event.preventDefault();
    const data = formData(event.target);
    try { await request("/auth/register", { method: "POST", body: JSON.stringify(data) }); const session = await request("/auth/login", { method: "POST", body: JSON.stringify({ email: data.email, password: data.password }) }); setSession(session); $("#auth-modal").classList.remove("open"); toast("Account created"); }
    catch (error) { toast(error.message, true); }
  });
  $("#cart-button").addEventListener("click", () => $("#cart-drawer").classList.add("open"));
  $("#close-cart").addEventListener("click", () => $("#cart-drawer").classList.remove("open"));
  $("#checkout-button").addEventListener("click", checkout);
  $("#refresh-products").addEventListener("click", loadProducts);
  $("#refresh-orders").addEventListener("click", loadOrders);
  $("#refresh-admin").addEventListener("click", loadAdmin);
}

bindEvents();
bindAdminForms();
updateSessionUI();
renderCart();
loadProducts();
