welcome_text = 🚀 Приветствуем тебя в StoreDima, { $name }

    🛍️ StoreDima — официальный магазин техники Apple с лучшими ценами и быстрым сервисом.

    📋 В StoreDima собрано всё лучшее от Apple:
    • Оригинальная техника и фирменные аксессуары
    • Самые свежие новинки

    🛒 Готов к покупкам? Тогда давай, листай и выбирай

asort_button = 📦 Ассортимент
cart_button = 🛒 Корзина
manager_button = 👨‍💻 Менеджер
locale_button = 📍 Адрес
trans_button = 🚚 Доставка
reviews_button = ⭐ Отзывы
site_button = 🌐 Сайт

reviews_callback = ⭐ Тут список крутых отзывов!

locale_callback =
    🛍️ StoreDima 🛍️

    🕙 Открыты ежедневно: 10:00 – 21:00

    📍 Москва, ул. Барклая 8
    «Старая Горбушка», павильон 174

trans_callback = 🚚 Информация о доставке
    Мы бережно доставим ваш заказ в кратчайшие сроки. Стоимость услуги зависит от вашего местоположения:
    📍 В пределах МКАД
    Фиксированная стоимость — 1 500 ₽
    📍 За пределы МКАД
    Стоимость рассчитывается индивидуально в зависимости от удаленности — от 2 500 ₽
    Точную сумму и удобное время доставки наш менеджер согласует с вами сразу после оформления заказа. Мы работаем, чтобы вам было комфортно!

add_product_start =
    🛠️ <b>Добавление товара</b> 🛠️

    ➡️ Введите категорию товара.

    📋 <b>Существующие категории:</b>

    { $categories_list }

    💡 Можете выбрать из списка или ввести новую категорию.
add_product_no_categories = (категории пока не найдены в базе)
category_empty_error = Категория не может быть пустой. Введите значение ещё раз:
model_empty_error = Модель не может быть пустой. Введите значение ещё раз:
description_empty_error = Описание не может быть пустым. Введите значение ещё раз:
price_empty_error = Стоимость не может быть пустой. Введите значение ещё раз:
price_invalid_error = Введите цену в любом удобном формате

category_saved_next =
    ✅ Категория сохранена!

    ➡️ Теперь введите название модели товара.

    Пример: iPhone 16 Pro 256GB Black
model_saved_next =
    ✅ Название сохранено!

    ➡️ Введите описание товара.

    Можно подробно: характеристики, комплектация, особенности и т.д.
description_saved_next =
    ✅ Описание сохранено!

    ➡️ Введите цену товара (как удобно: число, диапазон или текст).

    Примеры:
    цена: от 10.000
    цена: 10.000 - 12.000
price_saved_next =
    ✅ Цена сохранена!

    ➡️ Отправьте одно фото товара.

    После отправки фото товар будет добавлен в базу.

product_added_success =
    ✅ Товар успешно добавлен в базу!

    🆔 ID: <code>{ $id }</code>
    📁 Категория: { $category }
    📱 Модель: { $model }
    💰 Цена: { $price }
product_added_error = ❌ Ошибка при добавлении товара.

delete_product_start =
    🗑️ <b>Удаление товара</b> 🗑️

    ➡️ Введите точное название модели товара, который нужно удалить.

    Пример:
    iPhone 16 Pro 256GB Black

    ⏳ После отправки бот сразу удалит товар из базы.
delete_model_empty_error = Название модели не может быть пустым. Введите значение ещё раз:
delete_model_error = Произошла ошибка при удалении модели из базы.
delete_success =
    ✅ Товар успешно удалён!

    ➡️ Модель «{ $model_name }» успешно удалена из базы данных StoreDima.

    ♻️ База обновлена. Можете продолжать работу с товарами.
delete_not_found = Модель { $model_name } не найдена в базе. Проверьте правильность написания

no_products_available = Пока нет товаров в наличии 😔
choose_category = Выберите категорию техники:
choose_model = 📁 Категория: <b>{ $category }</b>

    Выберите модель:
product_unavailable = Товар временно отсутствует 😔
unknown_product_name = Без названия
unknown_product_price = Цена отсутствует
unknown_product_description = Описание отсутствует
product_display_error = Ошибка при отображении товара
user_not_defined = Пользователь не определён
cart_add_failed = Не удалось добавить товар в корзину
cart_product_not_found = Товар не найден или отсутствует в наличии
invalid_product_price = Некорректная цена товара
cart_item_added = Товар добавлен в корзину ✅
cart_cleared = Корзина очищена
cart_index_error = Неверный индекс позиции
cart_remove_failed = Не удалось удалить позицию
cart_item_removed = Позиция удалена
cart_checkout_sent = Заказ отправлен менеджеру ✅
cart_checkout_error = Не удалось отправить заказ менеджеру
buy_request_sent = Запрос на покупку отправлен менеджеру ✅
buy_request_error = Не удалось отправить запрос менеджеру
manager_order_username_missing = без username
manager_order_text =
    🧾 <b>Новый заказ</b>

    👤 Клиент: { $full_name }
    🔗 Username: { $username }
    🆔 ID: <code>{ $user_id }</code>

    { $cart_items }
manager_product_request_text =
    🧾 <b>Новая заявка на товар</b>

    👤 Клиент: { $full_name }
    🔗 Username: { $username }
    🆔 ID: <code>{ $user_id }</code>

    📱 Модель: <b>{ $model_name }</b>
    💰 Цена: <code>{ $price }</code>

main_menu_button = ⬅️ Главное меню
to_categories_button = ⬅️ К категориям
buy_button = 💰 Купить
add_to_cart_button = 🛒 В корзину
back_button = ⬅️ Вернуться
cart_back_button = ⬅️ Назад
manager_chat_button = 💬 Перейти к менеджеру
cart_remove_button = ❌ Удалить #{ $index }
cart_clear_button = 🧹 Очистить корзину

cart_empty = 🛒 <b>Ваша корзина пуста</b>
cart_header = <b>🛒 Содержимое корзины:</b>
unknown_model = Неизвестно
cart_item_line = { $index }. { $icon } { $model_name } — <code>{ $price }</code>
cart_total = <b>💰 Итого к оплате: { $total_sum }</b>
