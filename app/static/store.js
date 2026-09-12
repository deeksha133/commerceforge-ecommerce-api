const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
const state = { token: localStorage.getItem("cf_token") || "", user: null, products: [], categories: [], cart: { items: [], total: 0 }, authMode: "login" };
const money = value => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value);

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(e => e.msg).join("; ") : data.detail;
    throw new Error(detail || "Something went wrong");
  }
  return data;
}

function toast(message, isError = false) {
  const el = $("#toast");
  $("p", el).textContent = message;
  $("span", el).textContent = isError ? "!" : "✓";
  el.style.background = isError ? "#fee2e2" : "#edf2e5";
  el.style.color = isError ? "#7f1d1d" : "#12150d";
  el.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove("show"), 2800);
}

function openLayer(id) {
  closeLayers(false); $("#scrim").classList.add("open"); const el = $(id); el.classList.add("open"); el.setAttribute("aria-hidden", "false"); document.body.style.overflow = "hidden";
}
function closeLayers(clear = true) {
  $$(".modal.open,.drawer.open").forEach(el => { el.classList.remove("open"); el.setAttribute("aria-hidden", "true"); });
  if (clear) { $("#scrim").classList.remove("open"); document.body.style.overflow = ""; }
}

function initials(name = "Guest") { return name.split(/\s+/).map(x => x[0]).join("").slice(0, 2).toUpperCase(); }
function updateAccount() {
  $("#accountText").textContent = state.user ? state.user.name.split(" ")[0] : "Sign in";
  $(".avatar").textContent = initials(state.user?.name);
  $("#ordersBtn").textContent = state.user?.role === "admin" ? "Admin" : "Orders";
}

async function restoreSession() {
  if (!state.token) return updateAccount();
  try { state.user = await api("/api/auth/me"); } catch { state.token = ""; localStorage.removeItem("cf_token"); }
  updateAccount();
}

async function loadCategories() {
  state.categories = await api("/api/categories");
  $("#categoryFilters").innerHTML = `<button class="active" data-category="">All</button>` + state.categories.map(c => `<button data-category="${c.slug}">${escapeHtml(c.name)}</button>`).join("");
  $("#adminCategory").innerHTML = state.categories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  $$('[data-category]').forEach(btn => btn.addEventListener("click", () => { $$('[data-category]').forEach(x => x.classList.remove("active")); btn.classList.add("active"); loadProducts(); }));
}

function escapeHtml(value = "") { const div = document.createElement("div"); div.textContent = value; return div.innerHTML; }
function productMonogram(product) { return product.name.split(/\s+/).slice(0, 2).map(x => x[0]).join("").toUpperCase(); }

async function loadProducts() {
  const search = $("#searchInput").value.trim();
  const category = $('[data-category].active')?.dataset.category || "";
  const params = new URLSearchParams(); if (search) params.set("search", search); if (category) params.set("category", category); if ($("#stockOnly").checked) params.set("in_stock", "true");
  $("#productGrid").innerHTML = `<div class="loader"><i></i><span>Loading collection</span></div>`;
  try { state.products = await api(`/api/products?${params}`); renderProducts(); } catch (error) { $("#productGrid").innerHTML = ""; toast(error.message, true); }
}

function renderProducts() {
  $("#productCount").textContent = state.products.length;
  $("#emptyState").classList.toggle("hidden", state.products.length > 0);
  $("#productGrid").innerHTML = state.products.map(p => `<article class="product-card">
    <div class="product-visual ${p.category.slug === "lifestyle" ? "lifestyle" : ""}" data-view="${p.id}" role="button" tabindex="0"><span class="stock-badge">${p.stock ? `${p.stock} IN STOCK` : "SOLD OUT"}</span><div class="product-icon">${productMonogram(p)}</div></div>
    <div class="product-info"><div class="product-meta"><small>${escapeHtml(p.category.name)}</small><small>#${String(p.id).padStart(3,"0")}</small></div><h3 data-view="${p.id}" role="button" tabindex="0">${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description)}</p><div class="product-bottom"><span class="price">${money(p.price)}</span><button class="add-btn" data-add="${p.id}" ${!p.stock ? "disabled" : ""} aria-label="Add ${escapeHtml(p.name)} to bag">+</button></div></div>
  </article>`).join("");
  $$('[data-add]').forEach(btn => btn.addEventListener("click", () => addToCart(Number(btn.dataset.add))));
  $$('[data-view]').forEach(el => { el.addEventListener("click", () => openProduct(Number(el.dataset.view))); el.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") openProduct(Number(el.dataset.view)); }); });
}

function openProduct(productId) {
  const product = state.products.find(item => item.id === productId); if (!product) return;
  $("#detailMonogram").textContent = productMonogram(product); $("#detailCategory").textContent = product.category.name.toUpperCase(); $("#detailName").textContent = product.name; $("#detailDescription").textContent = product.description; $("#detailPrice").textContent = money(product.price); $("#detailStock").textContent = product.stock ? `${product.stock} ready to ship` : "Sold out";
  const addButton = $("#detailAdd"); addButton.disabled = !product.stock; addButton.dataset.productId = product.id; addButton.firstChild.textContent = product.stock ? "Add to bag " : "Currently unavailable "; openLayer("#productModal");
}

const promiseContent = {
  security: { mark: "01", title: "Secure by design", copy: "Passwords are protected using PBKDF2-SHA256 hashing, private requests require expiring JWT access tokens, and administrator operations are isolated with role-based authorization." },
  inventory: { mark: "02", title: "Inventory in real time", copy: "Stock is validated when an item enters the bag and checked again during checkout. Each confirmed order updates inventory in the same database transaction." },
  pricing: { mark: "03", title: "Transparent totals", copy: "The bag shows every line total, checkout calculates discounts explicitly, and each order stores an immutable price snapshot so purchase history remains accurate." }
};
function openPromise(key) { const item = promiseContent[key]; if (!item) return; $("#promiseMark").textContent = item.mark; $("#promiseTitle").textContent = item.title; $("#promiseCopy").textContent = item.copy; openLayer("#promiseModal"); }

async function loadCart() {
  if (!state.user) { state.cart = { items: [], total: 0 }; renderCart(); return; }
  try { state.cart = await api("/api/cart"); renderCart(); } catch (error) { toast(error.message, true); }
}
function renderCart() {
  $("#cartCount").textContent = state.cart.items.reduce((sum, item) => sum + item.quantity, 0);
  $("#cartItems").innerHTML = state.cart.items.map(item => `<div class="cart-row"><div class="cart-thumb">${escapeHtml(item.product_name.split(/\s+/).slice(0,2).map(x=>x[0]).join(""))}</div><div><h4>${escapeHtml(item.product_name)}</h4><small>${item.quantity} × ${money(item.unit_price)} · ${money(item.line_total)}</small></div><button class="remove-btn" data-remove="${item.product_id}" aria-label="Remove item">×</button></div>`).join("");
  $("#cartEmpty").classList.toggle("hidden", state.cart.items.length > 0); $("#cartSummary").classList.toggle("hidden", !state.cart.items.length); $("#cartTotal").textContent = money(state.cart.total); $("#checkoutTotal").textContent = money(state.cart.total);
  $$('[data-remove]').forEach(btn => btn.addEventListener("click", async () => { try { state.cart = await api(`/api/cart/items/${btn.dataset.remove}`, { method: "DELETE" }); renderCart(); toast("Item removed"); } catch (e) { toast(e.message, true); } }));
}
async function addToCart(productId) {
  if (!state.user) { openAuth("login"); return toast("Sign in to add items to your bag"); }
  const existing = state.cart.items.find(item => item.product_id === productId);
  try { state.cart = await api("/api/cart/items", { method: "POST", body: JSON.stringify({ product_id: productId, quantity: (existing?.quantity || 0) + 1 }) }); renderCart(); toast("Added to your bag"); } catch (e) { toast(e.message, true); }
}

function openAuth(mode = "login") { setAuthMode(mode); openLayer("#authModal"); }
function setAuthMode(mode) {
  state.authMode = mode; $$('[data-auth-tab]').forEach(b => b.classList.toggle("active", b.dataset.authTab === mode));
  $(".name-field").classList.toggle("hidden", mode === "login"); $("#authTitle").textContent = mode === "login" ? "Sign in to continue" : "Create your account"; $("#authSubtitle").textContent = mode === "login" ? "Access your bag, orders, and saved account." : "Join for a faster, safer shopping experience."; $("#authSubmit").innerHTML = `${mode === "login" ? "Sign in" : "Create account"} <span>→</span>`; $("#authError").textContent = "";
}
async function submitAuth(event) {
  event.preventDefault(); const form = new FormData(event.currentTarget); const payload = { email: form.get("email"), password: form.get("password") }; if (state.authMode === "register") payload.name = form.get("name");
  try { const result = await api(`/api/auth/${state.authMode === "login" ? "login" : "register"}`, { method: "POST", body: JSON.stringify(payload) }); state.token = result.access_token; state.user = result.user; localStorage.setItem("cf_token", state.token); updateAccount(); await loadCart(); closeLayers(); event.currentTarget.reset(); toast(`Welcome, ${state.user.name.split(" ")[0]}`); } catch (e) { $("#authError").textContent = e.message; }
}
function signOut() { state.token = ""; state.user = null; state.cart = { items: [], total: 0 }; localStorage.removeItem("cf_token"); updateAccount(); renderCart(); toast("Signed out securely"); }

async function showOrders() {
  if (!state.user) return openAuth("login");
  if (state.user.role === "admin") return showAdmin();
  openLayer("#ordersModal"); $("#ordersList").innerHTML = `<div class="loader"><i></i></div>`;
  try { renderOrders(await api("/api/orders"), $("#ordersList")); } catch (e) { $("#ordersList").innerHTML = `<p>${escapeHtml(e.message)}</p>`; }
}
function renderOrders(orders, root, admin = false) {
  if (!orders.length) { root.innerHTML = `<div class="empty"><strong>No orders yet</strong><p>Your completed purchases will appear here.</p></div>`; return; }
  root.innerHTML = orders.map(order => `<article class="order-card"><div class="order-top"><div><h4>Order #${String(order.id).padStart(4,"0")}</h4><small>${new Date(order.created_at).toLocaleString()}</small></div><span class="order-status">${order.status}</span></div><div class="order-lines">${order.items.map(i => `<div><span>${i.quantity} × ${escapeHtml(i.product_name)}</span><b>${money(i.quantity * i.unit_price)}</b></div>`).join("")}<div><strong>Total</strong><strong>${money(order.total)}</strong></div></div>${admin ? `<div class="admin-order-actions"><select data-status-for="${order.id}">${["placed","paid","shipped","delivered","cancelled"].map(s=>`<option ${s===order.status?"selected":""}>${s}</option>`).join("")}</select><button class="primary" data-update-order="${order.id}">Update</button></div>` : ""}</article>`).join("");
  if (admin) $$('[data-update-order]',root).forEach(btn => btn.addEventListener("click", () => updateOrder(btn.dataset.updateOrder)));
}
async function checkout(event) {
  event.preventDefault(); const form = new FormData(event.currentTarget); $("#checkoutError").textContent = "";
  try { const order = await api("/api/orders/checkout", { method: "POST", body: JSON.stringify({ shipping_address: form.get("shipping_address"), coupon_code: form.get("coupon_code") || null }) }); event.currentTarget.reset(); await Promise.all([loadCart(), loadProducts()]); closeLayers(); toast(`Order #${order.id} placed successfully`); } catch (e) { $("#checkoutError").textContent = e.message; }
}

async function showAdmin() {
  openLayer("#adminModal"); showAdminTab("products");
}
async function showAdminTab(tab) {
  $$('[data-admin-tab]').forEach(b => b.classList.toggle("active", b.dataset.adminTab === tab)); $("#productForm").classList.toggle("hidden", tab !== "products"); $("#adminOrders").classList.toggle("hidden", tab !== "orders");
  if (tab === "orders") { $("#adminOrders").innerHTML = `<div class="loader"><i></i></div>`; try { renderOrders(await api("/api/admin/orders"), $("#adminOrders"), true); } catch (e) { toast(e.message,true); } }
}
async function createProduct(event) {
  event.preventDefault(); const form = new FormData(event.currentTarget); const payload = { name: form.get("name"), category_id: Number(form.get("category_id")), description: form.get("description"), price: Number(form.get("price")), stock: Number(form.get("stock")) };
  try { await api("/api/products", { method: "POST", body: JSON.stringify(payload) }); event.currentTarget.reset(); await loadProducts(); closeLayers(); toast("Product published to the collection"); } catch (e) { $("#adminError").textContent = e.message; }
}
async function updateOrder(id) { const status = $(`[data-status-for="${id}"]`).value; try { await api(`/api/admin/orders/${id}/status?order_status=${status}`, { method: "PATCH" }); toast("Order status updated"); showAdminTab("orders"); } catch (e) { toast(e.message,true); } }

function accountAction() { if (!state.user) return openAuth("login"); if (confirm(`Signed in as ${state.user.email}. Sign out?`)) signOut(); }
function debounce(fn, wait=300){ let timer; return (...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),wait)}; }

document.addEventListener("DOMContentLoaded", async () => {
  $("#scrim").addEventListener("click", () => closeLayers()); $$('[data-close]').forEach(b => b.addEventListener("click", () => closeLayers())); document.addEventListener("keydown", e => { if(e.key === "Escape") closeLayers(); });
  $("#accountBtn").addEventListener("click", accountAction); $("#cartBtn").addEventListener("click", () => openLayer("#cartDrawer")); $("#ordersBtn").addEventListener("click", showOrders); $("#authForm").addEventListener("submit", submitAuth); $("#checkoutForm").addEventListener("submit", checkout); $("#productForm").addEventListener("submit", createProduct); $("#checkoutBtn").addEventListener("click", () => { closeLayers(); openLayer("#checkoutModal"); });
  $$('[data-auth-tab]').forEach(b => b.addEventListener("click", () => setAuthMode(b.dataset.authTab))); $$('[data-admin-tab]').forEach(b => b.addEventListener("click", () => showAdminTab(b.dataset.adminTab)));
  $("#demoBtn").addEventListener("click", () => { openAuth("login"); }); $("#searchInput").addEventListener("input", debounce(loadProducts)); $("#stockOnly").addEventListener("change", loadProducts);
  $("#detailAdd").addEventListener("click", async event => { const id = Number(event.currentTarget.dataset.productId); closeLayers(); await addToCart(id); }); $$('[data-promise]').forEach(card => card.addEventListener("click", () => openPromise(card.dataset.promise)));
  $("#themeBtn").addEventListener("click", () => { document.body.classList.toggle("light"); localStorage.setItem("cf_theme", document.body.classList.contains("light") ? "light" : "dark"); }); if (localStorage.getItem("cf_theme") === "light") document.body.classList.add("light");
  try { await restoreSession(); await Promise.all([loadCategories(), loadCart()]); await loadProducts(); } catch (e) { toast(e.message, true); }
});
