# db_cakes.py
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_NAME = "cake_shop.db"


def now():
    """Возвращает текущую дату и время для использования в шаблонах"""
    return datetime.now()


async def init_db():
    """Инициализация базы данных для магазина тортов"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица тортов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            weight REAL NOT NULL,
            description TEXT,
            photo_id TEXT NOT NULL,
            is_available INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cake_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            delivery_date TEXT NOT NULL,
            delivery_time TEXT NOT NULL,
            wish TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            status TEXT DEFAULT 'active',
            cancellation_reason TEXT,
            FOREIGN KEY (cake_id) REFERENCES cakes (id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Cake shop database initialized")


async def get_cake(cake_id: int):
    """Получить информацию о конкретном торте"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price, weight, description, photo_id, is_available FROM cakes WHERE id = ?",
        (cake_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result


async def get_available_cakes():
    """Получить все доступные торты"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price, weight, description, photo_id FROM cakes WHERE is_available = 1 ORDER BY created_at DESC"
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def get_all_cakes_for_admin():
    """Получить все торты для админа (включая недоступные)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price, weight, description, photo_id, is_available FROM cakes ORDER BY created_at DESC"
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def get_cake_info(cake_id: int):
    """Получить детальную информацию о торте"""
    return await get_cake(cake_id)


async def get_cakes_by_ids(cake_ids: list):
    """Получить информацию о нескольких тортах по их ID"""
    if not cake_ids:
        return []

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(cake_ids))
    cursor.execute(
        f"SELECT id, name, price, weight, description, photo_id, is_available FROM cakes WHERE id IN ({placeholders})",
        cake_ids
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def add_cake(name: str, price: int, weight: float, description: str, photo_id: str):
    """Добавить новый торт"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cakes (name, price, weight, description, photo_id) VALUES (?, ?, ?, ?, ?)",
        (name, price, weight, description, photo_id)
    )
    conn.commit()
    conn.close()
    logger.info(f"Cake added: {name}")


async def update_cake(cake_id: int, name=None, price=None, weight=None, description=None, photo_id=None):
    """Обновить информацию о торте"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    updates = []
    params = []

    if name:
        updates.append("name = ?")
        params.append(name)
    if price:
        updates.append("price = ?")
        params.append(price)
    if weight:
        updates.append("weight = ?")
        params.append(weight)
    if description:
        updates.append("description = ?")
        params.append(description)
    if photo_id:
        updates.append("photo_id = ?")
        params.append(photo_id)

    if updates:
        query = f"UPDATE cakes SET {', '.join(updates)} WHERE id = ?"
        params.append(cake_id)
        cursor.execute(query, params)
        conn.commit()

    conn.close()
    logger.info(f"Cake {cake_id} updated")


async def delete_cake(cake_id: int):
    """Удалить торт"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cakes WHERE id = ?", (cake_id,))
    conn.commit()
    conn.close()
    logger.info(f"Cake {cake_id} deleted")


async def create_order(cake_id: int, customer_name: str, phone: str, delivery_info: str, wish: str = "Без пожеланий"):
    """Создать новый заказ и пометить торт как недоступный"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Помечаем торт как недоступный
    cursor.execute(
        "UPDATE cakes SET is_available = 0 WHERE id = ?",
        (cake_id,)
    )

    # Разбираем delivery_info (формат: "Дата: {date}, Время: {time}, Адрес: {address}")
    import re
    date_match = re.search(r'Дата: (.*?),', delivery_info)
    time_match = re.search(r'Время: (.*?),', delivery_info)
    address_match = re.search(r'Адрес: (.*?)$', delivery_info)

    delivery_date = date_match.group(1) if date_match else "Не указана"
    delivery_time = time_match.group(1) if time_match else "Не указано"
    address = address_match.group(1) if address_match else delivery_info

    # Создаем заказ
    cursor.execute(
        "INSERT INTO orders (cake_id, customer_name, phone, address, delivery_date, delivery_time, wish) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cake_id, customer_name, phone, address, delivery_date, delivery_time, wish)
    )
    order_id = cursor.lastrowid

    conn.commit()
    conn.close()
    logger.info(f"Order {order_id} created for cake {cake_id}")
    return order_id


async def get_active_orders():
    """Получить активные заказы"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, cake_id, customer_name, phone, address, delivery_date, delivery_time, wish, created_at, status FROM orders WHERE status = 'active' ORDER BY created_at DESC"
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def get_completed_orders():
    """Получить выполненные заказы"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, cake_id, customer_name, phone, address, delivery_date, delivery_time, wish, created_at, completed_at, status FROM orders WHERE status = 'completed' ORDER BY completed_at DESC"
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def get_cancelled_orders():
    """Получить отмененные заказы"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, cake_id, customer_name, phone, address, delivery_date, delivery_time, wish, created_at, cancelled_at, status, cancellation_reason FROM orders WHERE status = 'cancelled' ORDER BY cancelled_at DESC"
    )
    results = cursor.fetchall()
    conn.close()
    return results


async def complete_order(order_id: int):
    """Отметить заказ как выполненный"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,)
    )
    conn.commit()
    conn.close()
    logger.info(f"Order {order_id} completed")


async def cancel_order(order_id: int, reason: str = "Отменен администратором"):
    """Отменить заказ и вернуть торт в доступные"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Получаем cake_id из заказа
    cursor.execute("SELECT cake_id FROM orders WHERE id = ?", (order_id,))
    result = cursor.fetchone()

    if result:
        cake_id = result[0]
        # Возвращаем торт в доступные
        cursor.execute(
            "UPDATE cakes SET is_available = 1 WHERE id = ?",
            (cake_id,)
        )

    # Отмечаем заказ как отмененный
    cursor.execute(
        "UPDATE orders SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = ? WHERE id = ?",
        (reason, order_id)
    )

    conn.commit()
    conn.close()
    logger.info(f"Order {order_id} cancelled, cake {cake_id} restored")


async def mark_cake_as_unavailable(cake_id: int):
    """Отметить торт как недоступный"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE cakes SET is_available = 0 WHERE id = ?",
        (cake_id,)
    )
    conn.commit()
    conn.close()
    logger.info(f"Cake {cake_id} marked as unavailable")


async def mark_cake_as_available(cake_id: int):
    """Отметить торт как доступный"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE cakes SET is_available = 1 WHERE id = ?",
        (cake_id,)
    )
    conn.commit()
    conn.close()
    logger.info(f"Cake {cake_id} marked as available")


async def restore_all_cakes():
    """Восстановить все торты (сделать доступными)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE cakes SET is_available = 1")
    conn.commit()
    conn.close()
    logger.info("All cakes restored")