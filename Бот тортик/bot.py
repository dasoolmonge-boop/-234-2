# bot_cakes.py
import asyncio
import logging
import re
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, CallbackQuery
)
from db_cakes import (
    init_db, get_available_cakes, get_cake_info,
    add_cake, update_cake, delete_cake,
    get_all_cakes_for_admin, create_order,
    get_active_orders, get_completed_orders, complete_order,
    get_cakes_by_ids, get_cake, cancel_order,
    get_cancelled_orders, mark_cake_as_available
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------- Настройки ----------------------
TOKEN = "8710895907:AAHAVyf_k2WjkKpbpIYYHMB16HoyFsZ8tfU"
ADMIN_ID = 1066867845  # Замените на ваш ID

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "cake_shop.db"


# ---------------------- Состояния ----------------------
class AddCake(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name_price = State()
    waiting_for_description = State()
    waiting_for_weight = State()  # Добавляем вес торта


class EditCake(StatesGroup):
    choosing_cake = State()
    choosing_field = State()
    waiting_for_new_name = State()
    waiting_for_new_price = State()
    waiting_for_new_description = State()
    waiting_for_new_weight = State()
    waiting_for_new_photo = State()


class DeleteCake(StatesGroup):
    confirming = State()


class OrderStates(StatesGroup):
    in_cart = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()
    waiting_for_delivery_date = State()  # Дата доставки
    waiting_for_delivery_time = State()  # Время доставки
    waiting_for_wish = State()  # Пожелания к торту


# ---------------------- Клавиатуры ----------------------
def get_user_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎂 Наши торты"), KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="⭐ Акции")]
        ],
        resize_keyboard=True
    )


def get_admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎂 Наши торты"), KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="⚙️ Админ-панель")]
        ],
        resize_keyboard=True
    )


def get_admin_panel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить торт"), KeyboardButton(text="✏️ Редактировать торт")],
            [KeyboardButton(text="🗑 Удалить торт"), KeyboardButton(text="📋 Активные заказы")],
            [KeyboardButton(text="✅ Выполненные заказы"), KeyboardButton(text="❌ Отмененные заказы")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔙 Назад в меню")]
        ],
        resize_keyboard=True
    )


def get_cart_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Оформить заказ", callback_data="checkout")],
            [InlineKeyboardButton(text="🔄 Обновить корзину", callback_data="refresh_cart")],
            [InlineKeyboardButton(text="🧹 Очистить корзину", callback_data="clear_cart")]
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def validate_phone(phone: str) -> bool:
    pattern = r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$'
    return re.match(pattern, phone) is not None


# ---------------------- /start ----------------------
@dp.message(Command("start"))
async def start(msg: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "🍰 Добро пожаловать в «Сладкий рай»!\n\n"
        "Мы готовим самые вкусные торты в Кызыле 🎂\n"
        "Индивидуальный подход к каждому заказу ✨"
    )
    if is_admin(msg.from_user.id):
        await msg.answer(
            f"{welcome_text}\n\nВы вошли как администратор.",
            reply_markup=get_admin_main_keyboard()
        )
    else:
        await msg.answer(
            welcome_text,
            reply_markup=get_user_main_keyboard()
        )


# ---------------------- Назад в меню ----------------------
@dp.message(F.text == "🔙 Назад в меню")
async def back_to_menu(msg: types.Message, state: FSMContext):
    await state.clear()
    keyboard = get_admin_main_keyboard() if is_admin(msg.from_user.id) else get_user_main_keyboard()
    await msg.answer("🍰 Вы в главном меню", reply_markup=keyboard)


# ---------------------- Админ-панель ----------------------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(msg: types.Message):
    if is_admin(msg.from_user.id):
        await msg.answer("⚙️ Панель администратора", reply_markup=get_admin_panel_keyboard())


# ---------------------- Контакты и О нас ----------------------
@dp.message(F.text == "📞 Контакты")
async def show_contacts(msg: types.Message):
    contacts_text = (
        "📞 **Наши контакты:**\n\n"
        "📍 **Адрес:** г. Кызыл, ул. Кочетова, 25\n"
        "📱 **Телефон:** +7 (923) 456-78-90\n"
        "📧 **Email:** cakes@kyzyl.ru\n"
        "🕒 **Режим работы:** 10:00 - 20:00 ежедневно\n\n"
        "🚚 **Доставка:** с 11:00 до 19:00\n\n"
        "🍰 Ждём ваши заказы!"
    )
    await msg.answer(contacts_text, parse_mode="Markdown")


@dp.message(F.text == "ℹ️ О нас")
async def show_about(msg: types.Message):
    about_text = (
        "🍰 **О нашей кондитерской**\n\n"
        "«Сладкий рай» — это домашняя кондитерская с душой ❤️\n\n"
        "✨ Почему выбирают нас:\n"
        "• Только натуральные ингредиенты\n"
        "• Ручная работа\n"
        "• Уникальные рецепты\n"
        "• Индивидуальный дизайн\n"
        "• Бесплатная доставка от 3000₽\n\n"
        "🎂 Каждый торт мы готовим с любовью!"
    )
    await msg.answer(about_text, parse_mode="Markdown")


@dp.message(F.text == "⭐ Акции")
async def show_promos(msg: types.Message):
    promos_text = (
        "⭐ **Наши акции:**\n\n"
        "🎁 **При заказе от 3000₽** - бесплатная доставка\n"
        "🎂 **Именинникам** - скидка 10% (при предъявлении паспорта)\n"
        "🔄 **При повторном заказе** - скидка 5%\n\n"
        "✨ Следите за новыми акциями в нашем Instagram!"
    )
    await msg.answer(promos_text, parse_mode="Markdown")


# ---------------------- Добавление торта ----------------------
@dp.message(F.text == "➕ Добавить торт")
async def add_cake_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        "📸 Отправьте фото торта",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AddCake.waiting_for_photo)


@dp.message(AddCake.waiting_for_photo, F.photo)
async def add_cake_photo(msg: types.Message, state: FSMContext):
    await state.update_data(photo_id=msg.photo[-1].file_id)
    await msg.answer(
        "🍰 Введите название и цену торта через запятую\n"
        "Пример: **Медовик, 2500**\n\n"
        "Цена должна быть числом!"
    )
    await state.set_state(AddCake.waiting_for_name_price)


@dp.message(AddCake.waiting_for_name_price)
async def add_cake_name_price(msg: types.Message, state: FSMContext):
    try:
        if "," not in msg.text:
            raise ValueError("Отсутствует запятая")

        name, price_str = map(str.strip, msg.text.split(",", 1))
        price = int(price_str)

        if price <= 0:
            raise ValueError("Цена должна быть положительной")

    except ValueError as e:
        await msg.answer(
            "❌ Неверный формат.\n"
            "Используйте: **название, цена**\n"
            "Пример: **Медовик, 2500**"
        )
        return

    await state.update_data(name=name, price=price)
    await msg.answer("⚖️ Укажите вес торта (в кг):\nПример: 1.5, 2, 2.5")
    await state.set_state(AddCake.waiting_for_weight)


@dp.message(AddCake.waiting_for_weight)
async def add_cake_weight(msg: types.Message, state: FSMContext):
    try:
        weight = float(msg.text.strip().replace(',', '.'))
        if weight <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректный вес (например: 1.5, 2, 2.5)")
        return

    await state.update_data(weight=weight)
    await msg.answer("📝 Введите описание торта:\n(Состав, особенности, начинка)")
    await state.set_state(AddCake.waiting_for_description)


@dp.message(AddCake.waiting_for_description)
async def add_cake_description(msg: types.Message, state: FSMContext):
    if len(msg.text) < 10:
        await msg.answer("❌ Описание слишком короткое. Напишите хотя бы 10 символов.")
        return

    data = await state.get_data()
    await add_cake(data["name"], data["price"], data["weight"], msg.text, data["photo_id"])

    await msg.answer(
        "✅ Торт успешно добавлен в меню!",
        reply_markup=get_admin_panel_keyboard()
    )
    await state.clear()


# ---------------------- Просмотр тортов ----------------------
@dp.message(F.text == "🎂 Наши торты")
async def show_cakes(msg: types.Message, state: FSMContext):
    cakes = await get_available_cakes()
    if not cakes:
        await msg.answer("🍰 Скоро здесь появятся наши вкуснейшие торты! Следите за обновлениями.")
        return

    await msg.answer("🍰 **Наши торты:**", parse_mode="Markdown")

    for cake in cakes:
        cake_id, name, price, weight, description, photo_id = cake
        buttons = [[
            InlineKeyboardButton(
                text="🛒 Добавить в корзину",
                callback_data=f"add_to_cart:{cake_id}"
            )
        ]]

        caption = (
            f"🍰 *{name}*\n"
            f"💰 *{price} ₽*  |  ⚖️ *{weight} кг*\n\n"
            f"_{description}_"
        )

        await msg.answer_photo(
            photo=photo_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


# ---------------------- Корзина ----------------------
@dp.message(F.text == "🛒 Корзина")
async def show_cart(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cart = data.get('cart', [])

    if not cart:
        await msg.answer(
            "🛒 Ваша корзина пуста\n"
            "Добавьте торты из нашего меню 🎂"
        )
        return

    cart_text = "🛒 **Ваша корзина:**\n\n"
    total_price = 0
    keyboard = []

    for item in cart:
        cake = await get_cake(item['cake_id'])
        if cake:
            name, price, weight = cake[1], cake[2], cake[3]
            cart_text += f"🍰 {name} - {price} ₽ ({weight} кг)\n"
            total_price += price
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ Удалить {name[:20]}",
                    callback_data=f"remove_from_cart:{item['cake_id']}"
                )
            ])

    cart_text += f"\n💰 **Итого: {total_price} ₽**"

    keyboard.append([InlineKeyboardButton(text="📦 Оформить заказ", callback_data="checkout")])
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_cart")])
    keyboard.append([InlineKeyboardButton(text="🧹 Очистить корзину", callback_data="clear_cart")])

    await msg.answer(
        cart_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@dp.callback_query(F.data.startswith("add_to_cart:"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    cake_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    cart = data.get('cart', [])

    cart.append({'cake_id': cake_id})
    await state.update_data(cart=cart)

    await callback.answer("✅ Торт добавлен в корзину!")

    # Обновляем кнопку
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ В корзине",
                callback_data=f"already_in_cart:{cake_id}"
            )]
        ])
    )


@dp.callback_query(F.data.startswith("remove_from_cart:"))
async def remove_from_cart(callback: CallbackQuery, state: FSMContext):
    cake_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    cart = data.get('cart', [])

    for i, item in enumerate(cart):
        if item['cake_id'] == cake_id:
            cart.pop(i)
            break

    await state.update_data(cart=cart)
    await callback.answer("❌ Торт удалён из корзины")
    await callback.message.delete()
    await show_cart(callback.message, state)


@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await callback.answer("🧹 Корзина очищена")
    await callback.message.delete()
    await show_cart(callback.message, state)


@dp.callback_query(F.data == "refresh_cart")
async def refresh_cart(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await show_cart(callback.message, state)


# ---------------------- Оформление заказа ----------------------
@dp.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get('cart', [])

    if not cart:
        await callback.answer("❌ Корзина пуста!")
        return

    await callback.message.delete()
    await callback.message.answer(
        "📝 **Оформление заказа**\n\n"
        "Шаг 1 из 5:\n"
        "Введите ваше **имя**:",
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.waiting_for_name)
    await callback.answer()


@dp.message(OrderStates.waiting_for_name)
async def process_name(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 2:
        await msg.answer("❌ Имя должно содержать хотя бы 2 символа. Попробуйте ещё раз:")
        return

    await state.update_data(customer_name=msg.text.strip())
    await msg.answer(
        "Шаг 2 из 5:\n"
        "Введите ваш **номер телефона**:\n\n"
        "Пример: +7 923 456-78-90 или 89234567890"
    )
    await state.set_state(OrderStates.waiting_for_phone)


@dp.message(OrderStates.waiting_for_phone)
async def process_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()

    if not validate_phone(phone):
        await msg.answer(
            "❌ Неверный формат телефона.\n"
            "Пример: +7 923 456-78-90 или 89234567890\n\n"
            "Попробуйте ещё раз:"
        )
        return

    await state.update_data(customer_phone=phone)
    await msg.answer(
        "Шаг 3 из 5:\n"
        "Введите **дату доставки**:\n\n"
        "Пример: 25.12.2024 или завтра/послезавтра"
    )
    await state.set_state(OrderStates.waiting_for_delivery_date)


@dp.message(OrderStates.waiting_for_delivery_date)
async def process_delivery_date(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 3:
        await msg.answer("❌ Укажите корректную дату. Попробуйте ещё раз:")
        return

    await state.update_data(delivery_date=msg.text.strip())
    await msg.answer(
        "Шаг 4 из 5:\n"
        "Введите **время доставки**:\n\n"
        "Пример: 14:00 или с 15:00 до 17:00"
    )
    await state.set_state(OrderStates.waiting_for_delivery_time)


@dp.message(OrderStates.waiting_for_delivery_time)
async def process_delivery_time(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 3:
        await msg.answer("❌ Укажите корректное время. Попробуйте ещё раз:")
        return

    await state.update_data(delivery_time=msg.text.strip())
    await msg.answer(
        "Шаг 5 из 5:\n"
        "Напишите **пожелания к торту**:\n\n"
        "(надпись, декор, особые пожелания)\n"
        "Если пожеланий нет, отправьте \"Нет\""
    )
    await state.set_state(OrderStates.waiting_for_wish)


@dp.message(OrderStates.waiting_for_wish)
async def process_wish(msg: types.Message, state: FSMContext):
    wish = msg.text.strip() if msg.text.strip().lower() != "нет" else "Без пожеланий"
    data = await state.get_data()

    cart = data.get('cart', [])
    name = data.get('customer_name')
    phone = data.get('customer_phone')
    delivery_date = data.get('delivery_date')
    delivery_time = data.get('delivery_time')

    if not cart:
        await msg.answer("❌ Корзина пуста. Заказ не может быть оформлен.")
        await state.clear()
        return

    # Создаём заказы для каждого торта в корзине
    order_ids = []
    cakes_info = []
    total_price = 0

    for item in cart:
        cake = await get_cake(item['cake_id'])
        if cake and cake[6] == 1:  # Проверяем, доступен ли торт
            cakes_info.append(cake)
            order_id = await create_order(
                item['cake_id'], name, phone,
                f"Дата: {delivery_date}, Время: {delivery_time}, Адрес: {delivery_date}",
                wish
            )
            order_ids.append(order_id)
            total_price += cake[2]

    if not cakes_info:
        await msg.answer("❌ Некоторые торты из корзины уже недоступны. Пожалуйста, обновите корзину.")
        await state.clear()
        return

    # Формируем сообщение для администратора
    cakes_list = "\n".join([f"🍰 {c[1]} - {c[2]} ₽ ({c[3]} кг)" for c in cakes_info])
    admin_message = (
        f"📩 **НОВЫЙ ЗАКАЗ**\n\n"
        f"🍰 **Торты:**\n{cakes_list}\n"
        f"💰 **Итого:** {total_price} ₽\n\n"
        f"👤 **Имя:** {name}\n"
        f"🆔 **Username:** @{msg.from_user.username if msg.from_user.username else 'нет'}\n"
        f"📱 **Телефон:** {phone}\n"
        f"📅 **Дата доставки:** {delivery_date}\n"
        f"⏰ **Время доставки:** {delivery_time}\n"
        f"📝 **Пожелания:** {wish}\n"
        f"🆔 **User ID:** {msg.from_user.id}\n"
        f"📅 **Дата заказа:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    # Отправляем уведомление администратору
    await bot.send_message(ADMIN_ID, admin_message, parse_mode="Markdown")

    # Отправляем подтверждение пользователю
    await msg.answer(
        f"✅ **Заказ успешно оформлен!**\n\n"
        f"Спасибо, {name}! 🍰\n"
        f"Мы скоро свяжемся с вами по телефону {phone}\n"
        f"для подтверждения заказа.\n\n"
        f"🍰 Ваш заказ:\n{cakes_list}\n\n"
        f"📅 Доставка: {delivery_date} в {delivery_time}\n"
        f"📝 Пожелания: {wish}\n\n"
        f"💰 Сумма заказа: {total_price} ₽\n\n"
        f"Ожидайте звонка в ближайшее время!",
        parse_mode="Markdown",
        reply_markup=get_user_main_keyboard() if not is_admin(msg.from_user.id) else get_admin_main_keyboard()
    )

    # Очищаем корзину
    await state.clear()


# ---------------------- Админ: Редактирование торта ----------------------
@dp.message(F.text == "✏️ Редактировать торт")
async def edit_cake_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    cakes = await get_all_cakes_for_admin()
    if not cakes:
        await msg.answer("Нет тортов для редактирования")
        return

    keyboard = []
    for cake in cakes:
        status = "✅" if cake[6] == 1 else "❌"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {cake[1]} - {cake[2]} ₽ ({cake[3]} кг)",
                callback_data=f"edit_cake:{cake[0]}"
            )
        ])

    await msg.answer(
        "✏️ Выберите торт для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(EditCake.choosing_cake)


@dp.callback_query(EditCake.choosing_cake, F.data.startswith("edit_cake:"))
async def edit_cake_choose(callback: CallbackQuery, state: FSMContext):
    cake_id = int(callback.data.split(":")[1])
    await state.update_data(edit_cake_id=cake_id)

    keyboard = [
        [InlineKeyboardButton(text="📝 Название", callback_data="edit_field:name")],
        [InlineKeyboardButton(text="💰 Цена", callback_data="edit_field:price")],
        [InlineKeyboardButton(text="⚖️ Вес", callback_data="edit_field:weight")],
        [InlineKeyboardButton(text="📄 Описание", callback_data="edit_field:description")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data="edit_field:photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_field:cancel")]
    ]

    await callback.message.edit_text(
        "✏️ Что хотите изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(EditCake.choosing_field)
    await callback.answer()


@dp.callback_query(EditCake.choosing_field, F.data.startswith("edit_field:"))
async def edit_cake_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]

    if field == "cancel":
        await callback.message.delete()
        await callback.message.answer("❌ Редактирование отменено")
        await state.clear()
        return

    await state.update_data(edit_field=field)

    messages = {
        "name": "🍰 Введите новое название торта:",
        "price": "💰 Введите новую цену (только цифры):",
        "weight": "⚖️ Введите новый вес (в кг, например: 1.5):",
        "description": "📝 Введите новое описание:",
        "photo": "📸 Отправьте новое фото торта:"
    }

    await callback.message.delete()
    await callback.message.answer(messages[field])

    states = {
        "name": EditCake.waiting_for_new_name,
        "price": EditCake.waiting_for_new_price,
        "weight": EditCake.waiting_for_new_weight,
        "description": EditCake.waiting_for_new_description,
        "photo": EditCake.waiting_for_new_photo
    }

    await state.set_state(states[field])
    await callback.answer()


@dp.message(EditCake.waiting_for_new_name)
async def edit_cake_new_name(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 2:
        await msg.answer("❌ Слишком короткое название. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    cake_id = data.get('edit_cake_id')

    await update_cake(cake_id, name=msg.text.strip())
    await msg.answer("✅ Название обновлено!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


@dp.message(EditCake.waiting_for_new_price)
async def edit_cake_new_price(msg: types.Message, state: FSMContext):
    try:
        price = int(msg.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректное число (только цифры, >0):")
        return

    data = await state.get_data()
    cake_id = data.get('edit_cake_id')

    await update_cake(cake_id, price=price)
    await msg.answer("✅ Цена обновлена!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


@dp.message(EditCake.waiting_for_new_weight)
async def edit_cake_new_weight(msg: types.Message, state: FSMContext):
    try:
        weight = float(msg.text.strip().replace(',', '.'))
        if weight <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректный вес (например: 1.5, 2, 2.5):")
        return

    data = await state.get_data()
    cake_id = data.get('edit_cake_id')

    await update_cake(cake_id, weight=weight)
    await msg.answer("✅ Вес обновлен!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


@dp.message(EditCake.waiting_for_new_description)
async def edit_cake_new_description(msg: types.Message, state: FSMContext):
    if len(msg.text.strip()) < 10:
        await msg.answer("❌ Описание слишком короткое. Напишите хотя бы 10 символов:")
        return

    data = await state.get_data()
    cake_id = data.get('edit_cake_id')

    await update_cake(cake_id, description=msg.text.strip())
    await msg.answer("✅ Описание обновлено!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


@dp.message(EditCake.waiting_for_new_photo, F.photo)
async def edit_cake_new_photo(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cake_id = data.get('edit_cake_id')

    await update_cake(cake_id, photo_id=msg.photo[-1].file_id)
    await msg.answer("✅ Фото обновлено!", reply_markup=get_admin_panel_keyboard())
    await state.clear()


# ---------------------- Админ: Удаление торта ----------------------
@dp.message(F.text == "🗑 Удалить торт")
async def delete_cake_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    cakes = await get_all_cakes_for_admin()
    if not cakes:
        await msg.answer("Нет тортов для удаления")
        return

    keyboard = []
    for cake in cakes:
        status = "✅" if cake[6] == 1 else "❌"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {cake[1]} - {cake[2]} ₽ ({cake[3]} кг)",
                callback_data=f"delete_cake:{cake[0]}"
            )
        ])

    await msg.answer(
        "🗑 Выберите торт для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@dp.callback_query(F.data.startswith("delete_cake:"))
async def delete_cake_confirm(callback: CallbackQuery, state: FSMContext):
    cake_id = int(callback.data.split(":")[1])
    await state.update_data(delete_cake_id=cake_id)

    cake = await get_cake(cake_id)
    if cake:
        name = cake[1]

        keyboard = [
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete:yes"),
                InlineKeyboardButton(text="❌ Нет, отмена", callback_data="confirm_delete:no")
            ]
        ]

        await callback.message.edit_text(
            f"⚠️ Вы уверены, что хотите удалить торт **{name}**?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    else:
        await callback.message.edit_text("❌ Торт не найден")

    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete:"))
async def delete_cake_execute(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "yes":
        data = await state.get_data()
        cake_id = data.get('delete_cake_id')

        await delete_cake(cake_id)
        await callback.message.edit_text("✅ Торт успешно удален из меню!")
    else:
        await callback.message.edit_text("❌ Удаление отменено")

    await state.clear()
    await callback.answer()


# ---------------------- Админ: Просмотр заказов ----------------------
@dp.message(F.text == "📋 Активные заказы")
async def show_active_orders(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    orders = await get_active_orders()
    if not orders:
        await msg.answer("📋 Нет активных заказов")
        return

    for order in orders:
        order_id, cake_id, customer_name, phone, address, delivery_date, wish, created_at, status = order
        cake = await get_cake(cake_id)
        cake_name = cake[1] if cake else "Неизвестный торт"
        cake_weight = cake[3] if cake else "?"

        # Добавляем кнопки для выполнения и отмены заказа
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнен", callback_data=f"complete_order:{order_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_order:{order_id}")
            ]
        ])

        await msg.answer(
            f"📋 **Заказ #{order_id}**\n"
            f"🍰 **Торт:** {cake_name} ({cake_weight} кг)\n"
            f"👤 **Клиент:** {customer_name}\n"
            f"📞 **Телефон:** {phone}\n"
            f"📍 **Адрес:** {address}\n"
            f"📅 **Доставка:** {delivery_date}\n"
            f"📝 **Пожелания:** {wish}\n"
            f"📅 **Заказ создан:** {created_at}\n"
            f"📊 **Статус:** Активный",
            parse_mode="Markdown",
            reply_markup=keyboard
        )


@dp.message(F.text == "✅ Выполненные заказы")
async def show_completed_orders(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    orders = await get_completed_orders()
    if not orders:
        await msg.answer("✅ Нет выполненных заказов")
        return

    for order in orders:
        order_id, cake_id, customer_name, phone, address, delivery_date, wish, created_at, completed_at, status = order
        cake = await get_cake(cake_id)
        cake_name = cake[1] if cake else "Неизвестный торт"
        cake_weight = cake[3] if cake else "?"

        await msg.answer(
            f"✅ **Заказ #{order_id}**\n"
            f"🍰 **Торт:** {cake_name} ({cake_weight} кг)\n"
                        f"👤 **Клиент:** {customer_name}\n"
            f"📞 **Телефон:** {phone}\n"
            f"📍 **Адрес:** {address}\n"
            f"📅 **Доставка:** {delivery_date}\n"
            f"📝 **Пожелания:** {wish}\n"
            f"📅 **Создан:** {created_at}\n"
            f"✅ **Выполнен:** {completed_at}\n"
            f"📊 **Статус:** Выполнен",
            parse_mode="Markdown"
        )


@dp.message(F.text == "❌ Отмененные заказы")
async def show_cancelled_orders(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    orders = await get_cancelled_orders()
    if not orders:
        await msg.answer("❌ Нет отмененных заказов")
        return

    for order in orders:
        order_id, cake_id, customer_name, phone, address, delivery_date, wish, created_at, cancelled_at, status, reason = order
        cake = await get_cake(cake_id)
        cake_name = cake[1] if cake else "Неизвестный торт"
        cake_weight = cake[3] if cake else "?"

        await msg.answer(
            f"❌ **Заказ #{order_id}**\n"
            f"🍰 **Торт:** {cake_name} ({cake_weight} кг)\n"
            f"👤 **Клиент:** {customer_name}\n"
            f"📞 **Телефон:** {phone}\n"
            f"📍 **Адрес:** {address}\n"
            f"📅 **Доставка:** {delivery_date}\n"
            f"📝 **Пожелания:** {wish}\n"
            f"📅 **Создан:** {created_at}\n"
            f"❌ **Отменен:** {cancelled_at}\n"
            f"📝 **Причина:** {reason}\n"
            f"📊 **Статус:** Отменен",
            parse_mode="Markdown"
        )


# ---------------------- Админ: Отмена заказа ----------------------
@dp.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(cancel_order_id=order_id)

    keyboard = [
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data="confirm_cancel:yes"),
            InlineKeyboardButton(text="❌ Нет, оставить", callback_data="confirm_cancel:no")
        ]
    ]

    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите отменить этот заказ?\n"
        "Торт будет возвращен в каталог.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_cancel:"))
async def cancel_order_execute(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "yes":
        data = await state.get_data()
        order_id = data.get('cancel_order_id')

        # Получаем информацию о заказе для уведомления
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT customer_name, phone, address, cake_id FROM orders WHERE id = ?",
            (order_id,)
        )
        order_info = cursor.fetchone()
        conn.close()

        if order_info:
            customer_name, phone, address, cake_id = order_info
            cake = await get_cake(cake_id)
            cake_name = cake[1] if cake else "Неизвестный торт"

            # Отменяем заказ
            await cancel_order(order_id, "Отменен администратором")

            # Уведомляем администратора
            await callback.message.edit_text(
                f"❌ **Заказ #{order_id} отменен!**\n\n"
                f"🍰 Торт: {cake_name}\n"
                f"👤 Клиент: {customer_name}\n"
                f"📞 Телефон: {phone}\n"
                f"📍 Адрес: {address}\n\n"
                f"✅ Торт возвращен в каталог."
            )
        else:
            await callback.message.edit_text("❌ Заказ не найден")
    else:
        await callback.message.edit_text("✅ Отмена отменена")

    await state.clear()
    await callback.answer()


@dp.callback_query(F.data.startswith("complete_order:"))
async def complete_order_callback(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    await complete_order(order_id)
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ Заказ отмечен как выполненный!"
    )
    await callback.answer("✅ Заказ выполнен")


# ---------------------- Админ: Статистика ----------------------
@dp.message(F.text == "📊 Статистика")
async def show_statistics(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM cakes")
    total_cakes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cakes WHERE is_available = 1")
    available_cakes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'active'")
    active_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
    completed_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'")
    cancelled_orders = cursor.fetchone()[0]

    # Выручка
    cursor.execute("""
        SELECT SUM(c.price) 
        FROM orders o 
        JOIN cakes c ON o.cake_id = c.id 
        WHERE o.status = 'completed'
    """)
    total_revenue = cursor.fetchone()[0] or 0

    # Самый популярный торт
    cursor.execute("""
        SELECT c.name, COUNT(*) as order_count
        FROM orders o
        JOIN cakes c ON o.cake_id = c.id
        WHERE o.status = 'completed'
        GROUP BY c.id
        ORDER BY order_count DESC
        LIMIT 1
    """)
    popular = cursor.fetchone()
    popular_cake = f"{popular[0]} ({popular[1]} заказов)" if popular else "Нет данных"

    conn.close()

    stats_text = (
        "📊 **СТАТИСТИКА МАГАЗИНА**\n\n"
        f"🍰 **Торты:**\n"
        f"• Всего: {total_cakes}\n"
        f"• Доступно: {available_cakes}\n\n"
        f"📦 **Заказы:**\n"
        f"• Всего: {total_orders}\n"
        f"• Активные: {active_orders}\n"
        f"• Выполненные: {completed_orders}\n"
        f"• Отмененные: {cancelled_orders}\n\n"
        f"💰 **Выручка:** {total_revenue} ₽\n\n"
        f"🏆 **Самый популярный торт:**\n{popular_cake}"
    )

    await msg.answer(stats_text, parse_mode="Markdown")


# ---------------------- Запуск ----------------------
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот для продажи тортиков успешно запущен! 🍰")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())