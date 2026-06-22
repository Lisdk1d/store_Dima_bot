// Empty string = same-origin (nginx proxies /api → backend in Docker).
const API_BASE = import.meta.env.VITE_API_URL ?? "";

// Telegram WebApp: signed initData is the credential. No secret is baked in.
const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const PAYMENT_LABELS = {
  card: "Банковская карта",
  sbp: "СБП (перевод)",
  cash: "Наличные при получении",
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
  editingOrderId: null,
  orderSaving: false,
  orderDeleting: false,
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
  orderSearch: document.getElementById("orderSearch"),
  orderStatusFilter: document.getElementById("orderStatusFilter"),
  orderModal: document.getElementById("orderModal"),
  orderForm: document.getElementById("orderForm"),
  orderModalTitle: document.getElementById("orderModalTitle"),
  fieldOrderStatus: document.getElementById("fieldOrderStatus"),
  fieldOrderDelivery: document.getElementById("fieldOrderDelivery"),
  fieldOrderDeliveryFee: document.getElementById("fieldOrderDeliveryFee"),
  fieldOrderComment: document.getElementById("fieldOrderComment"),
  fieldOrderTotal: document.getElementById("fieldOrderTotal"),
  fieldOrderPayment: document.getElementById("fieldOrderPayment"),
  fieldOrderItems: document.getElementById("fieldOrderItems"),
  cancelOrderModal: document.getElementById("cancelOrderModal"),
  deleteOrderDialog: document.getElementById("deleteOrderDialog"),
  deleteOrderConfirm: document.getElementById("deleteOrderConfirm"),
  cancelDeleteOrder: document.getElementById("cancelDeleteOrder"),
  deleteOrderMessage: document.getElementById("deleteOrderMessage"),
};

els.apiKey.value = localStorage.getItem("shop_admin_dev_key") || "";

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.borderColor = isError ? "rgba(239,68,68,0.5)" : "rgba(34,197,94,0.5)";
  els.toast.classList.remove("hidden");
  setTimeout(() => els.toast.classList.add("hidden"), 3200);
}

function getDevKey() {
  const key = els.apiKey.value.trim();
  localStorage.setItem("shop_admin_dev_key", key);
  return key;
}

async function api(path, options = {}) {
  const initData = tg?.initData || "";
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (initData) {
    // Inside Telegram: authenticate with the signed initData payload.
    headers.Authorization = `tma ${initData}`;
    headers["X-Telegram-Init-Data"] = initData;
  } else {
    // Outside Telegram (local dev): fall back to a manually entered key.
    const devKey = getDevKey();
    if (devKey) headers["X-API-Key"] = devKey;
  }

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

function renderOrdersTable(container, orders, { withActions = false } = {}) {
  if (!container) return;

  if (!orders?.length) {
    container.innerHTML = `<p class="empty-msg">Заказов пока нет</p>`;
    return;
  }

  const actionsHeader = withActions ? "<th>Действия</th>" : "";

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
          ${actionsHeader}
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
            ${
              withActions
                ? `<td>
              <div class="actions">
                <button class="btn secondary" data-edit-order="${order.id}">✏️</button>
                <button class="btn danger" data-delete-order="${order.id}">🗑</button>
              </div>
            </td>`
                : ""
            }
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;

  if (withActions) {
    container.querySelectorAll("[data-edit-order]").forEach((btn) => {
      btn.addEventListener("click", () => openOrderModal(Number(btn.dataset.editOrder)));
    });
    container.querySelectorAll("[data-delete-order]").forEach((btn) => {
      btn.addEventListener("click", () => openDeleteOrderDialog(Number(btn.dataset.deleteOrder)));
    });
  }
}

function getFilteredOrders() {
  const query = (els.orderSearch?.value || "").trim().toLowerCase();
  const status = els.orderStatusFilter?.value || "";

  return state.orders.filter((order) => {
    if (status && order.status !== status) return false;
    if (!query) return true;
    const idMatch = String(order.id).includes(query);
    const userMatch =
      String(order.user_id).includes(query) ||
      (order.username || "").toLowerCase().includes(query);
    return idMatch || userMatch;
  });
}

function renderOrdersView() {
  renderOrdersTable(els.ordersTable, getFilteredOrders(), { withActions: true });
}

function serializeOrderItems(rawText) {
  const lines = rawText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.map((line) => {
    const parts = line.split("|").map((part) => part.trim());
    return {
      model_name: parts[0] || "",
      price: parts[1] || "",
      category_name: parts[2] || null,
      quantity: Number(parts[3] || 1),
    };
  });
}

function formatOrderItemsForEdit(items) {
  if (!items?.length) return "";
  return items
    .map(
      (item) =>
        `${item.model_name} | ${item.price} | ${item.category_name || ""} | ${item.quantity ?? 1}`
    )
    .join("\n");
}

function openOrderModal(orderId) {
  const order = state.orders.find((item) => item.id === orderId);
  if (!order) return;

  state.editingOrderId = orderId;
  els.orderModalTitle.textContent = `Редактировать заказ #${orderId}`;
  els.fieldOrderStatus.value = order.status || "pending";
  els.fieldOrderDelivery.value = order.delivery_address || "";
  els.fieldOrderDeliveryFee.value = order.delivery_fee || "";
  els.fieldOrderComment.value = order.comment || "";
  els.fieldOrderTotal.value = order.total_amount || "";
  els.fieldOrderPayment.value = order.payment_method || "";
  els.fieldOrderItems.value = formatOrderItemsForEdit(order.items);
  els.orderModal.showModal();
}

function openDeleteOrderDialog(orderId) {
  state.editingOrderId = orderId;
  els.deleteOrderMessage.textContent = `Удалить заказ #${orderId}? Это действие нельзя отменить.`;
  els.deleteOrderDialog.showModal();
}

async function saveOrder(event) {
  event.preventDefault();
  if (state.orderSaving || state.editingOrderId == null) return;

  const items = serializeOrderItems(els.fieldOrderItems.value);
  if (!items.length || items.some((item) => !item.model_name || !item.price)) {
    showToast("Укажите товары в формате: название | цена | категория | кол-во", true);
    return;
  }

  const payload = {
    status: els.fieldOrderStatus.value,
    delivery_address: els.fieldOrderDelivery.value.trim() || null,
    delivery_fee: els.fieldOrderDeliveryFee.value.trim() || null,
    comment: els.fieldOrderComment.value.trim() || null,
    total_amount: els.fieldOrderTotal.value.trim() || null,
    payment_method: els.fieldOrderPayment.value || null,
    items,
  };

  state.orderSaving = true;
  const submitBtn = els.orderForm.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.disabled = true;

  try {
    await api(`/api/orders/${state.editingOrderId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    els.orderModal.close();
    showToast("Заказ обновлён");
    await loadOrders();
    renderOrdersView();
  } catch (error) {
    showToast(`Ошибка: ${error.message}`, true);
  } finally {
    state.orderSaving = false;
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function confirmDeleteOrder() {
  if (state.orderDeleting || state.editingOrderId == null) return;

  state.orderDeleting = true;
  els.deleteOrderConfirm.disabled = true;

  try {
    await api(`/api/orders/${state.editingOrderId}`, { method: "DELETE" });
    els.deleteOrderDialog.close();
    showToast("Заказ удалён");
    state.editingOrderId = null;
    await refreshAll();
  } catch (error) {
    showToast(`Ошибка: ${error.message}`, true);
  } finally {
    state.orderDeleting = false;
    els.deleteOrderConfirm.disabled = false;
  }
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
            <td><strong>${escapeHtml(product.model)}</strong><br><small>${escapeHtml(truncate(product.description, 80))}</small></td>
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
  renderOrdersView();
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

function truncate(value, max) {
  const text = String(value ?? "").trim();
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

els.refreshBtn.addEventListener("click", refreshAll);
els.productSearch.addEventListener("input", () => renderProductsTable(els.productSearch.value));
els.orderSearch?.addEventListener("input", renderOrdersView);
els.orderStatusFilter?.addEventListener("change", renderOrdersView);
els.addProductBtn.addEventListener("click", openCreateModal);
els.cancelModal.addEventListener("click", () => els.productModal.close());
els.cancelOrderModal?.addEventListener("click", () => els.orderModal.close());
els.orderForm?.addEventListener("submit", saveOrder);
els.deleteOrderConfirm?.addEventListener("click", confirmDeleteOrder);
els.cancelDeleteOrder?.addEventListener("click", () => els.deleteOrderDialog.close());

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
