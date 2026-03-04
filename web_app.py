# web_app.py
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import sqlite3
from datetime import datetime
import requests
import logging
import re
import os

# Настройки бота
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8582185333:AAF7UK0lvUmgxTkVTQkiY0021jFOmHxK334")
ADMIN_ID = int(os.environ.get('ADMIN_ID', 1066867845))
DB_NAME = "cake_shop.db"

app = Flask(__name__)
# Используем секретный ключ из переменных окружения или генерируем случайный
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-it-2026')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Настройки для загрузки изображений
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папку для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/images', exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Функция для получения базового URL приложения
def get_base_url():
    if os.environ.get('BOTHOST_URL'):
        return os.environ.get('BOTHOST_URL')
    return request.host_url.rstrip('/') if request else 'http://localhost:5000'


@app.context_processor
def utility_processor():
    """Добавляет полезные функции в шаблоны"""
    return dict(
        now=datetime.now,
        base_url=get_base_url
    )


def get_db_connection():
    """Получить соединение с БД"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def get_available_cakes_web():
    """Получить все доступные торты для веб-приложения"""
    conn = get_db_connection()
    cakes = conn.execute(
        "SELECT id, name, price, weight, description, photo_id FROM cakes WHERE is_available = 1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    # Преобразуем в список словарей и добавляем photo_url
    cakes_list = []
    for cake in cakes:
        cake_dict = dict(cake)
        # Для Bothost используем прямой URL к файлу
        if cake_dict['photo_id'] and cake_dict['photo_id'].startswith(('http://', 'https://')):
            cake_dict['photo_url'] = cake_dict['photo_id']
        else:
            # Если нет фото, используем заглушку
            cake_dict['photo_url'] = url_for('static', filename='images/default-cake.jpg', _external=True)
        cakes_list.append(cake_dict)

    return cakes_list


def get_cake_by_id(cake_id):
    """Получить торт по ID"""
    conn = get_db_connection()
    cake = conn.execute(
        "SELECT id, name, price, weight, description, photo_id, is_available FROM cakes WHERE id = ?",
        (cake_id,)
    ).fetchone()
    conn.close()

    if cake:
        cake = dict(cake)
        if cake['photo_id'] and cake['photo_id'].startswith(('http://', 'https://')):
            cake['photo_url'] = cake['photo_id']
        else:
            cake['photo_url'] = url_for('static', filename='images/default-cake.jpg', _external=True)

    return cake


def validate_phone(phone):
    """Проверка формата телефона"""
    pattern = r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$'
    return re.match(pattern, phone) is not None


def send_telegram_notification(order_data):
    """Отправить уведомление в Telegram админу о новом заказе"""
    cakes_list = "\n".join(
        [f"🍰 {item['name']} - {item['price']} ₽ ({item['weight']} кг) x {item['quantity']}" for item in
         order_data['items']])

    message = (
        f"📩 **НОВЫЙ ЗАКАЗ ИЗ MINI APP**\n\n"
        f"🍰 **Торты:**\n{cakes_list}\n"
        f"💰 **Итого:** {order_data['total']} ₽\n\n"
        f"👤 **Имя:** {order_data['name']}\n"
        f"📱 **Телефон:** {order_data['phone']}\n"
        f"📅 **Дата доставки:** {order_data['delivery_date']}\n"
        f"⏰ **Время доставки:** {order_data['delivery_time']}\n"
        f"📍 **Адрес:** {order_data['address']}\n"
        f"📝 **Пожелания:** {order_data.get('wish', 'Нет')}\n"
        f"🆔 **ID заказа:** {order_data.get('order_id', 'Не указан')}\n"
        f"📅 **Дата заказа:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": ADMIN_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        logger.info(f"Telegram notification sent: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


@app.route('/')
def index():
    """Главная страница с каталогом тортов"""
    cakes = get_available_cakes_web()
    cart = session.get('cart', {})
    cart_count = sum(cart.values())

    return render_template('index.html', cakes=cakes, cart_count=cart_count)


@app.route('/add_to_cart/<int:cake_id>', methods=['POST'])
def add_to_cart(cake_id):
    """Добавить торт в корзину"""
    cake = get_cake_by_id(cake_id)
    if not cake:
        return jsonify({'success': False, 'error': 'Торт не найден'})

    if not cake['is_available']:
        return jsonify({'success': False, 'error': 'Торт временно недоступен'})

    cart = session.get('cart', {})
    cake_id_str = str(cake_id)
    cart[cake_id_str] = cart.get(cake_id_str, 0) + 1
    session['cart'] = cart
    session.modified = True

    cart_count = sum(cart.values())
    return jsonify({'success': True, 'cart_count': cart_count})


@app.route('/remove_from_cart/<int:cake_id>', methods=['POST'])
def remove_from_cart(cake_id):
    """Удалить один торт из корзины"""
    cart = session.get('cart', {})
    cake_id_str = str(cake_id)

    if cake_id_str in cart:
        if cart[cake_id_str] > 1:
            cart[cake_id_str] -= 1
        else:
            del cart[cake_id_str]

    session['cart'] = cart
    session.modified = True

    cart_count = sum(cart.values())
    return jsonify({'success': True, 'cart_count': cart_count})


@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    """Очистить корзину"""
    session['cart'] = {}
    session.modified = True
    return jsonify({'success': True})


@app.route('/cart')
def cart():
    """Страница корзины"""
    cart_data = session.get('cart', {})
    cart_items = []
    total = 0

    for cake_id_str, quantity in cart_data.items():
        cake = get_cake_by_id(int(cake_id_str))
        if cake and cake['is_available']:
            item_total = cake['price'] * quantity
            total += item_total
            cart_items.append({
                'id': cake['id'],
                'name': cake['name'],
                'price': cake['price'],
                'weight': cake['weight'],
                'photo_url': cake['photo_url'],
                'quantity': quantity,
                'total': item_total
            })

    cart_count = sum(cart_data.values())
    return render_template('cart.html', cart_items=cart_items, total=total, cart_count=cart_count)


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Оформление заказа"""
    cart_data = session.get('cart', {})
    if not cart_data:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Получаем данные формы
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        delivery_date = request.form.get('delivery_date', '').strip()
        delivery_time = request.form.get('delivery_time', '').strip()
        wish = request.form.get('wish', '').strip()

        # Валидация
        errors = []
        if not name or len(name) < 2:
            errors.append("Укажите корректное имя")

        if not phone or not validate_phone(phone):
            errors.append("Укажите корректный номер телефона")

        if not address or len(address) < 5:
            errors.append("Укажите корректный адрес доставки")

        if not delivery_date:
            errors.append("Укажите дату доставки")

        if not delivery_time:
            errors.append("Укажите время доставки")

        if errors:
            items = []
            total = 0
            for cake_id_str, quantity in cart_data.items():
                cake = get_cake_by_id(int(cake_id_str))
                if cake:
                    item_total = cake['price'] * quantity
                    total += item_total
                    items.append({
                        'name': cake['name'],
                        'price': cake['price'],
                        'weight': cake['weight'],
                        'quantity': quantity,
                        'total': item_total
                    })
            return render_template('checkout.html', items=items, total=total, error=", ".join(errors))

        # Получаем информацию о товарах в корзине
        items = []
        conn = get_db_connection()
        order_ids = []

        try:
            for cake_id_str, quantity in cart_data.items():
                cake = get_cake_by_id(int(cake_id_str))
                if cake and cake['is_available']:
                    for _ in range(quantity):
                        items.append({
                            'id': cake['id'],
                            'name': cake['name'],
                            'price': cake['price'],
                            'weight': cake['weight'],
                            'quantity': 1
                        })

                        # Помечаем торт как недоступный в БД
                        conn.execute(
                            "UPDATE cakes SET is_available = 0 WHERE id = ?",
                            (cake['id'],)
                        )

                        # Создаем запись в таблице orders
                        cursor = conn.execute(
                            """INSERT INTO orders 
                               (cake_id, customer_name, phone, address, delivery_date, delivery_time, wish) 
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (cake['id'], name, phone, address, delivery_date, delivery_time,
                             wish if wish else "Без пожеланий")
                        )
                        order_ids.append(cursor.lastrowid)

            conn.commit()

            # Группируем одинаковые торты для отображения
            grouped_items = {}
            for item in items:
                key = f"{item['id']}_{item['name']}"
                if key in grouped_items:
                    grouped_items[key]['quantity'] += 1
                    grouped_items[key]['total'] += item['price']
                else:
                    grouped_items[key] = {
                        'id': item['id'],
                        'name': item['name'],
                        'price': item['price'],
                        'weight': item['weight'],
                        'quantity': 1,
                        'total': item['price']
                    }

            items_list = list(grouped_items.values())
            total = sum(item['total'] for item in items_list)

            # Подготовка данных для уведомления
            order_data = {
                'items': items_list,
                'total': total,
                'name': name,
                'phone': phone,
                'address': address,
                'delivery_date': delivery_date,
                'delivery_time': delivery_time,
                'wish': wish if wish else "Без пожеланий",
                'order_id': ", ".join(map(str, order_ids))
            }

            # Отправляем уведомление в Telegram
            send_telegram_notification(order_data)

            # Очищаем корзину
            session['cart'] = {}
            session.modified = True

            return render_template('order_success.html', order_data=order_data)

        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating order: {e}")
            return render_template('checkout.html', items=items, total=total,
                                   error="Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте позже.")
        finally:
            conn.close()

    # GET запрос - показываем форму
    cart_data = session.get('cart', {})
    items = []
    total = 0

    for cake_id_str, quantity in cart_data.items():
        cake = get_cake_by_id(int(cake_id_str))
        if cake and cake['is_available']:
            item_total = cake['price'] * quantity
            total += item_total
            items.append({
                'name': cake['name'],
                'price': cake['price'],
                'weight': cake['weight'],
                'quantity': quantity,
                'total': item_total
            })

    return render_template('checkout.html', items=items, total=total)


@app.route('/api/cart/count')
def cart_count():
    """API для получения количества товаров в корзине"""
    cart = session.get('cart', {})
    count = sum(cart.values())
    return jsonify({'count': count})


@app.route('/health')
def health():
    """Endpoint для проверки здоровья приложения"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.errorhandler(404)
def page_not_found(e):
    """Обработка ошибки 404"""
    cart = session.get('cart', {})
    cart_count = sum(cart.values())
    return render_template('404.html', cart_count=cart_count), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Обработка ошибки 500"""
    cart = session.get('cart', {})
    cart_count = sum(cart.values())
    return render_template('500.html', cart_count=cart_count), 500


if __name__ == '__main__':
    # Для локального тестирования
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Для продакшена на Bothost
    logger.info("Starting Cake Shop Telegram Mini App on Bothost")