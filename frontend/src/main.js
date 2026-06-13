// Empty string = same-origin (nginx proxies /api → backend in Docker).
const API_BASE = import.meta.env.VITE_API_URL ?? "";
const DEFAULT_API_KEY = import.meta.env.VITE_API_SECRET_KEY ?? "";

const PAYMENT_LABELS = {
  card: "Банковская карта",
  sbp: "СБП (перевод)",
  cash: "Наличные при получении",
  crypto: "Криптовалюта",
  installment: "Рассрочка",
};

const STATUS_LABELS = {
  pending: "Ожидает",
  confirmed: "Подтверждён",
  completed: "Выполнен",
  cancelled: "Отменён",
};

const state = {
  products: [],
  categories: [],
  orders: [],
  editingModel: null,
};

const els = {
  apiKey: document.getElementById("apiKey"),
  pageTitle: document.getElementById("pageTitle"),
  refreshBtn: document.getElementById("refreshBtn"),
  dashboardView: document.getElementById("dashboardView"),
  ordersView: document.getElementById("ordersView"),
  productsView: document.getElementById("productsView"),
  categoriesView: document.getElementById("categoriesView"),
  statProducts: document.getElementById("statProducts"),
  statOrders: document.getElementById("statOrders"),
  statCategories: document.getElementById("statCategories"),
  dashboardOrdersTable: document.getElementById("dashboardOrdersTable"),
  ordersTable: document.getElementById("ordersTable"),
  productsTable: document.getElementById("productsTable"),
  categoriesGrid: document.getElementById("categoriesGrid"),
  productSearch: document.getElementById("productSearch"),
  addProductBtn: document.getElementById("addProductBtn"),
  productModal: document.getElementById("productModal"),
  productForm: document.getElementById("productForm"),
  modalTitle: document.getElementById("modalTitle"),
  editModelOriginal: document.getElementById("editModelOriginal"),
  fieldCategory: document.getElementById("fieldCategory"),
  fieldModel: document.getElementById("fieldModel"),
  fieldDescription: document.getElementById("fieldDescription"),
  fieldPrice: document.getElementById("fieldPrice"),
  fieldPhoto: document.getElementById("fieldPhoto"),
  fieldStock: document.getElementById("fieldStock"),
  cancelModal: document.getElementById("cancelModal"),
  toast: document.getElementById("toast"),
};

els.apiKey.value = localStorage.getItem("shop_admin_api_key") || DEFAULT_API_KEY;

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.borderColor = isError ? "rgba(239,68,68,0.5)" : "rgba(34,197,94,0.5)";
  els.toast.classList.remove("hidden");
  setTimeout(() => els.toast.classList.add("hidden"), 3200);
}

function getApiKey() {
  const key = els.apiKey.value.trim();
  localStorage.setItem("shop_admin_api_key", key);
  return key;
}

async function api(path, options = {}) {
  const apiKey = getApiKey();
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${apiKey}`,
    "X-API-Key": apiKey,
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function switchView(view) {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  els.dashboardView.classList.toggle("active", view === "dashboard");
  els.ordersView.classList.toggle("active", view === "orders");
  els.productsView.classList.toggle("active", view === "products");
  els.categoriesView.classList.toggle("active", view === "categories");

  const titles = {
    dashboard: "Дашборд",
    orders: "Заказы",
    products: "Товары",
    categories: "Категории",
  };
  els.pageTitle.textContent = titles[view] || "Панель управления";
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function paymentLabel(method) {
  return PAYMENT_LABELS[method] || method || "—";
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "—";
}

function renderItemsCell(items) {
  if (!items?.length) return "<span class='muted'>—</span>";
  return items
    .map(
      (item) => `
      <div class="order-item-line">
        <strong>${escapeHtml(item.category_name || "—")}</strong> /
        ${escapeHtml(item.model_name)}
        × ${item.quantity ?? 1}
        — <code>${escapeHtml(item.price)}</code>
      </div>`
    )
    .join("");
}

function renderOrdersTable(container, orders) {
  if (!container) return;

  if (!orders?.length) {
    container.innerHTML = `<p class="empty-msg">Заказов пока нет</p>`;
    return;
  }

  container.innerHTML = `
    <table class="orders-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Дата</th>
          <th>Покупатель</th>
          <th>Товары</th>
          <th>Сумма</th>
          <th>Адрес доставки</th>
          <th>Оплата</th>
          <th>Статус</th>
        </tr>
      </thead>
      <tbody>
        ${orders
          .map(
            (order) => `
          <tr>
            <td><code>#${order.id}</code></td>
            <td>${formatDate(order.created_at)}</td>
            <td>
              <div>ID: <code>${order.user_id}</code></div>
              <div class="muted">${escapeHtml(order.username || "без username")}</div>
            </td>
            <td class="items-cell">${renderItemsCell(order.items)}</td>
            <td>
              <div><strong>${escapeHtml(order.total_amount || "—")}</strong></div>
              ${
                order.delivery_fee
                  ? `<div class="muted">Доставка: ${escapeHtml(order.delivery_fee)}</div>`
                  : ""
              }
            </td>
            <td>${escapeHtml(order.delivery_address || "—")}</td>
            <td>${escapeHtml(paymentLabel(order.payment_method))}</td>
            <td><span class="status-badge status-${escapeHtml(order.status)}">${escapeHtml(statusLabel(order.status))}</span></td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderProductsTable(filter = "") {
  const query = filter.trim().toLowerCase();
  const rows = state.products.filter((product) => {
    if (!query) return true;
    return (
      product.model.toLowerCase().includes(query) ||
      product.category.toLowerCase().includes(query)
    );
  });

  if (!rows.length) {
    els.productsTable.innerHTML = `<p class="empty-msg">Товары не найдены</p>`;
    return;
  }

  els.productsTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Название</th>
          <th>Категория</th>
          <th>Цена</th>
          <th>Остаток</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map(
            (product) => `
          <tr>
            <td><strong>${escapeHtml(product.model)}</strong><br><small>${escapeHtml(product.description).slice(0, 80)}...</small></td>
            <td>${escapeHtml(product.category)}</td>
            <td>${escapeHtml(product.price)}</td>
            <td>${product.stock}</td>
            <td>
              <div class="actions">
                <button class="btn secondary" data-edit="${escapeAttr(product.model)}">✏️</button>
                <button class="btn danger" data-delete="${escapeAttr(product.model)}">🗑</button>
              </div>
            </td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;

  els.productsTable.querySelectorAll("[data-edit]").forEach((btn) => {
    btn.addEventListener("click", () => openEditModal(btn.dataset.edit));
  });
  els.productsTable.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", () => deleteProduct(btn.dataset.delete));
  });
}

function renderCategories() {
  const counts = state.products.reduce((acc, product) => {
    acc[product.category] = (acc[product.category] || 0) + 1;
    return acc;
  }, {});

  const categories = Object.keys(counts).sort((a, b) => a.localeCompare(b, "ru"));
  if (!categories.length) {
    els.categoriesGrid.innerHTML = `<p class="empty-msg">Категории пока отсутствуют</p>`;
    return;
  }

  els.categoriesGrid.innerHTML = categories
    .map(
      (category) => `
      <article class="category-card">
        <div>
          <strong>${escapeHtml(category)}</strong>
          <div class="muted">${counts[category]} товар(ов)</div>
        </div>
        <button class="btn danger" data-del-cat="${escapeAttr(category)}">Удалить</button>
      </article>`
    )
    .join("");

  els.categoriesGrid.querySelectorAll("[data-del-cat]").forEach((btn) => {
    btn.addEventListener("click", () => deleteCategory(btn.dataset.delCat));
  });
}

function openCreateModal() {
  state.editingModel = null;
  els.modalTitle.textContent = "Новый товар";
  els.editModelOriginal.value = "";
  els.productForm.reset();
  els.fieldStock.value = "1";
  els.productModal.showModal();
}

function openEditModal(model) {
  const product = state.products.find((item) => item.model === model);
  if (!product) return;
  state.editingModel = model;
  els.modalTitle.textContent = "Редактировать товар";
  els.editModelOriginal.value = model;
  els.fieldCategory.value = product.category;
  els.fieldModel.value = product.model;
  els.fieldDescription.value = product.description;
  els.fieldPrice.value = product.price;
  els.fieldPhoto.value = product.photo_id || "";
  els.fieldStock.value = product.stock;
  els.productModal.showModal();
}

async function loadDashboard() {
  const stats = await api("/api/stats");
  els.statProducts.textContent = stats.products_count;
  els.statOrders.textContent = stats.orders_count;
  els.statCategories.textContent = stats.categories_count;
}

async function loadOrders() {
  state.orders = await api("/api/orders");
  renderOrdersTable(els.dashboardOrdersTable, state.orders.slice(0, 10));
  renderOrdersTable(els.ordersTable, state.orders);
}

async function loadProducts() {
  state.products = await api("/api/products");
  renderProductsTable(els.productSearch.value);
  renderCategories();
}

async function refreshAll() {
  try {
    await Promise.all([loadDashboard(), loadOrders(), loadProducts()]);
    showToast("Данные обновлены");
  } catch (error) {
    showToast(`Ошибка: ${error.message}`, true);
  }
}

async function deleteProduct(model) {
  if (!confirm(`Удалить товар «${model}»?`)) return;
  try {
    await api(`/api/products/${encodeURIComponent(model)}`, { method: "DELETE" });
    showToast("Товар удалён");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function deleteCategory(category) {
  if (!confirm(`Удалить категорию «${category}» и все товары в ней?`)) return;
  try {
    const result = await api(`/api/categories/${encodeURIComponent(category)}`, { method: "DELETE" });
    showToast(`Удалено товаров: ${result.deleted_count}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

els.refreshBtn.addEventListener("click", refreshAll);
els.productSearch.addEventListener("input", () => renderProductsTable(els.productSearch.value));
els.addProductBtn.addEventListener("click", openCreateModal);
els.cancelModal.addEventListener("click", () => els.productModal.close());

els.productForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    category: els.fieldCategory.value.trim(),
    model: els.fieldModel.value.trim(),
    description: els.fieldDescription.value.trim(),
    price: els.fieldPrice.value.trim(),
    photo_id: els.fieldPhoto.value.trim(),
    stock: Number(els.fieldStock.value || 1),
  };

  try {
    if (state.editingModel) {
      await api(`/api/products/${encodeURIComponent(state.editingModel)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      showToast("Товар обновлён");
    } else {
      await api("/api/products", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Товар создан");
    }
    els.productModal.close();
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

refreshAll();
