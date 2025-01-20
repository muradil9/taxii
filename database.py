from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import aiogram.utils.exceptions
import sqlite3
import logging

# === Настройки ===
BOT_TOKEN = "7845697254:AAGsWAMPZ_tXWzhRHw7exPtGpO2civ4oMb4"
TAXI_GROUP_ID = -4678887716
ADMIN_ID = [6620133292, 5418350256]  # Замените на реальный юзернейм администратора
ADMIN_USERNAME = "@trading_mma"  # Ник администратора
GROUP_LINK = "https://t.me/+Z-cM4_F__5Q2ODUy"  # Ссылка на группу
BANK_DETAILS = """
Реквизиты для пополнения баланса:
- Банк: Kaspi Bank
- Номер счета: +7772319268
- Получатель: Мурадил Марупов 
"""

# === Логирование ===
logging.basicConfig(level=logging.INFO)

# === Инициализация бота и диспетчера ===
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# === Подключение к базе данных SQLite ===
conn = sqlite3.connect("taxi_bot.db")
cursor = conn.cursor()

# Создаем таблицу для водителей, если её нет
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS drivers (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     user_id INTEGER UNIQUE,
#     name TEXT,
#     car_model TEXT,
#     phone TEXT,
#     balance INTEGER DEFAULT 0,
#     orders_completed INTEGER DEFAULT 0
# )
# """)
# conn.commit()
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pickup TEXT,
    destination TEXT,
    phone TEXT,
    price INTEGER,
    status TEXT DEFAULT 'pending'
)
""")
conn.commit()

# === Состояния ===
class OrderTaxi(StatesGroup):
    waiting_for_pickup = State()
    waiting_for_destination = State()
    waiting_for_price = State()
    waiting_for_phone = State()

class RegisterDriver(StatesGroup):
    waiting_for_name = State()
    waiting_for_car_model = State()
    waiting_for_phone = State()

class EditDriverProfile(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_car_model = State()
    waiting_for_new_phone = State()

class TopUpBalance(StatesGroup):
    waiting_for_phone = State()
    waiting_for_amount = State()
    
class AdminStates(StatesGroup):
    waiting_for_driver_phone = State()
    waiting_for_topup_amount = State()
    


# === Главное меню ===
@dp.message_handler(commands="start")
async def start_command(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🧑‍✈️ Стать таксистом", "🚖 Вызвать такси", "👤 Мой профиль")
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard)

# === Кнопка "Назад" ===
@dp.message_handler(text="⬅️ Назад")
async def go_back(message: types.Message):
    await start_command(message)

# === Вызов такси ===
@dp.message_handler(text="🚖 Вызвать такси")
async def start_taxi_order(message: types.Message):
    await message.answer("Введите адрес, откуда вас забрать:")
    await OrderTaxi.waiting_for_pickup.set()

@dp.message_handler(state=OrderTaxi.waiting_for_pickup)
async def pickup_handler(message: types.Message, state: FSMContext):
    await state.update_data(pickup=message.text)
    await message.answer("Введите адрес, куда вас отвезти:")
    await OrderTaxi.waiting_for_destination.set()

@dp.message_handler(state=OrderTaxi.waiting_for_destination)
async def destination_handler(message: types.Message, state: FSMContext):
    await state.update_data(destination=message.text)
    data = await state.get_data()
    pickup = data.get('pickup')
    destination = data.get('destination')
    phone = data.get('phone')
    price = data.get('price')
    if not pickup or not destination:
        await message.answer("Произошла ошибка. Пожалуйста, начните заказ заново.")
        await state.finish()
        return
    phone_button = KeyboardButton("📞 Поделиться номером", request_contact=True)
    phone_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(phone_button)
    await message.answer("Пожалуйста, поделитесь своим номером телефона:", reply_markup=phone_keyboard)
    await OrderTaxi.waiting_for_phone.set()

# @dp.message_handler(content_types=types.ContentType.CONTACT, state=OrderTaxi.waiting_for_phone)
# async def phone_handler(message: types.Message, state: FSMContext):
#     if message.contact is None:
#         await message.answer("Пожалуйста, используйте кнопку для отправки номера телефона.")
#         return
#     # Сохраняем номер телефона в состоянии
#     await state.update_data(phone=message.contact.phone_number)
#     await message.answer("Сколько вы готовы заплатить за поездку? (минимум 300):", reply_markup=types.ReplyKeyboardRemove())
#     await OrderTaxi.waiting_for_price.set()
    
@dp.message_handler(content_types=types.ContentType.CONTACT, state=OrderTaxi.waiting_for_phone)
async def phone_handler(message: types.Message, state: FSMContext):
    if message.contact is None:
        await message.answer("Пожалуйста, используйте кнопку для отправки номера телефона.")
        return
    # Сохраняем номер телефона в состоянии
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Сколько вы готовы заплатить за поездку? (минимум 300):", reply_markup=types.ReplyKeyboardRemove())
    await OrderTaxi.waiting_for_price.set()


@dp.message_handler(state=OrderTaxi.waiting_for_price)
async def price_handler(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        if price < 300:
            await message.answer("Минимальная сумма — 300. Введите другую сумму:")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
        return

    await state.update_data(price=price)
    data = await state.get_data()
    user_id = message.from_user.id
    pickup = data.get('pickup')
    destination = data.get('destination')
    phone = data.get('phone')

    # Сохранение данных о заказе в базу данных
    cursor.execute("INSERT INTO orders (user_id, pickup, destination, phone, price, status) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, pickup, destination, phone, price, 'pending'))
    conn.commit()

    await process_order(message, state)
    

async def process_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pickup = data.get('pickup')
    destination = data.get('destination')
    phone = data.get('phone')
    price = data.get('price')

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🚖 Забрать заказ", callback_data=f"take_order|{message.from_user.id}|{price}")
    )
    order_message = (
        f"Новый заказ:\n"
        f"🚩 Откуда: {pickup}\n"
        f"🏁 Куда: {destination}\n"
        f"💰 Цена: {price}\n"
        f"📞 Заказчик: @{message.from_user.username or 'Неизвестно'}"
    )
    try:
        await bot.send_message(TAXI_GROUP_ID, order_message, reply_markup=keyboard)
        await message.answer("Ваш заказ отправлен таксистам. Ожидайте подтверждения.")
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения в группу: {e}")
        await message.answer("Не удалось отправить заказ таксистам. Проверьте настройки.")

    await state.finish()

    start_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("/start"))
    await message.answer("Для нового заказа нажмите /start", reply_markup=start_keyboard)



# === Принятие заказа таксистом ===
@dp.callback_query_handler(lambda c: c.data.startswith("take_order"))
async def take_order_handler(callback_query: types.CallbackQuery):
    driver_id = callback_query.from_user.id
    client_id, price = callback_query.data.split("|")[1], int(callback_query.data.split("|")[2])

    # Извлечение данных о заказе из базы данных
    cursor.execute("SELECT pickup, destination, phone FROM orders WHERE user_id = ? AND price = ? AND status = 'pending'",
                   (client_id, price))
    order = cursor.fetchone()

    if not order:
        await callback_query.answer("Ошибка: Заказ не найден или уже принят!", show_alert=True)
        return

    pickup, destination, phone = order

    cursor.execute("SELECT name, car_model, phone, balance, orders_completed FROM drivers WHERE user_id = ?", (driver_id,))
    driver = cursor.fetchone()

    if driver:
        name, car_model, driver_phone, balance, orders_completed = driver
        # Проверка баланса
        required_balance = price * 0.1
        if balance < required_balance:
            await callback_query.answer("У вас недостаточно средств для выполнения этого заказа.", show_alert=True)
            return

        # Списание 10% с баланса и увеличение количества выполненных заказов
        cursor.execute("UPDATE drivers SET balance = balance - ?, orders_completed = orders_completed + 1 WHERE user_id = ?", (required_balance, driver_id))
        conn.commit()

        # Обновление статуса заказа
        cursor.execute("UPDATE orders SET status = 'accepted' WHERE user_id = ? AND price = ?", (client_id, price))
        conn.commit()

        # Уведомляем клиента
        driver_info = (
            f"🚖 Ваш заказ принят таксистом:\n"
            f"Имя: {name}\n"
            f"Модель авто: {car_model}\n"
            f"Телефон: {driver_phone}"
        )
        await bot.send_message(client_id, driver_info)

        # Уведомляем таксиста
        client_info = (
            f"🚩 Новый клиент:\n"
            f"Имя: @{callback_query.from_user.username or 'Неизвестно'}\n"
            f"Номер телефона: {phone}\n"
            f"Откуда: {pickup}\n"
            f"Куда: {destination}\n"
            f"Цена: {price}\n"
        )
        await bot.send_message(driver_id, client_info)

        # Убираем кнопку "Забрать заказ" и добавляем уведомление о принятии заказа
        original_message_id = callback_query.message.message_id
        group_message = (
            f"📢 Заказ забрал:\n"
            f"Таксист: {name} (@{callback_query.from_user.username or 'Неизвестно'})\n"
            f"Модель авто: {car_model}\n"
            f"Телефон: {driver_phone}"
        )
        await bot.edit_message_text(
            chat_id=TAXI_GROUP_ID,
            message_id=original_message_id,
            text=group_message
        )

        await callback_query.answer("Вы успешно приняли заказ!")
    else:
        await callback_query.answer("Вы не зарегистрированы как таксист.", show_alert=True)
# === Профиль таксиста ===
@dp.message_handler(text="👤 Мой профиль")
async def driver_profile(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT name, car_model, phone, balance, orders_completed FROM drivers WHERE user_id = ?", (user_id,))
    driver = cursor.fetchone()

    if driver:
        name, car_model, phone, balance, orders_completed = driver
        profile_info = (
            f"👤 Ваш профиль:\n"
            f"Имя: {name}\n"
            f"Модель авто: {car_model}\n"
            f"Телефон: {phone}\n"
            f"💰 Баланс: {balance} тг\n"
            f"🚖 Выполнено заказов: {orders_completed}"
        )
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("✏️ Изменить данные", "💳 Пополнить баланс", "⬅️ Назад")
        await message.answer(profile_info, reply_markup=keyboard)
    else:
        await message.answer("Вы не зарегистрированы как таксист. Нажмите '🧑‍✈️ Стать таксистом' для регистрации.")

# === Регистрация как таксист ===
@dp.message_handler(text="🧑‍✈️ Стать таксистом")
async def register_as_driver(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT user_id FROM drivers WHERE user_id = ?", (user_id,))
    existing_driver = cursor.fetchone()

    if existing_driver:
        await message.answer("Вы уже являетесь таксистом.")
        return

    await message.answer("Введите ваше имя:")
    await RegisterDriver.waiting_for_name.set()

@dp.message_handler(state=RegisterDriver.waiting_for_name)
async def register_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите модель вашего автомобиля:")
    await RegisterDriver.waiting_for_car_model.set()

@dp.message_handler(state=RegisterDriver.waiting_for_car_model)
async def register_car_model(message: types.Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer("Введите номер телефона:")
    await RegisterDriver.waiting_for_phone.set()

@dp.message_handler(state=RegisterDriver.waiting_for_phone)
async def register_phone(message: types.Message, state: FSMContext):
    phone = message.text
    await state.update_data(phone=phone)

    data = await state.get_data()
    cursor.execute("INSERT INTO drivers (user_id, name, car_model, phone) VALUES (?, ?, ?, ?)",
                   (message.from_user.id, data['name'], data['car_model'], data['phone']))
    conn.commit()

    # Отправка ссылки на группу
    await message.answer("Вы успешно зарегистрированы как таксист! Ваш профиль создан.")
    await message.answer(f"Присоединяйтесь к нашей группе: {GROUP_LINK}")
    await state.finish()

# === Изменить данные ===
@dp.message_handler(text="✏️ Изменить данные")
async def edit_driver_profile(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT name, car_model, phone FROM drivers WHERE user_id = ?", (user_id,))
    driver = cursor.fetchone()

    if driver:
        name, car_model, phone = driver
        await message.answer(f"Ваши текущие данные:\nИмя: {name}\nМодель авто: {car_model}\nТелефон: {phone}\n\n"
                             "Введите новое имя:")
        await EditDriverProfile.waiting_for_new_name.set()
    else:
        await message.answer("Вы не зарегистрированы как таксист.")

@dp.message_handler(state=EditDriverProfile.waiting_for_new_name)
async def edit_name(message: types.Message, state: FSMContext):
    await state.update_data(new_name=message.text)
    await message.answer("Введите новую модель автомобиля:")
    await EditDriverProfile.waiting_for_new_car_model.set()

@dp.message_handler(state=EditDriverProfile.waiting_for_new_car_model)
async def edit_car_model(message: types.Message, state: FSMContext):
    await state.update_data(new_car_model=message.text)
    await message.answer("Введите новый номер телефона:")
    await EditDriverProfile.waiting_for_new_phone.set()

@dp.message_handler(state=EditDriverProfile.waiting_for_new_phone)
async def edit_phone(message: types.Message, state: FSMContext):
    new_phone = message.text
    await state.update_data(new_phone=new_phone)

    data = await state.get_data()
    cursor.execute("UPDATE drivers SET name = ?, car_model = ?, phone = ? WHERE user_id = ?",
                   (data['new_name'], data['new_car_model'], data['new_phone'], message.from_user.id))
    conn.commit()

    await message.answer("Ваши данные успешно обновлены.")
    await state.finish()

# === Пополнение баланса ===
@dp.message_handler(text="💳 Пополнить баланс")
async def start_top_up_balance(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("⬅️ Назад")
    await message.answer(
        f"Для пополнения баланса, отправьте чек на имя {ADMIN_USERNAME}.\n\n{BANK_DETAILS}",
        reply_markup=keyboard
    )

# === Команда администратора для пополнения баланса ===
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас нет доступа к админ-панели.")
        return

    admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    admin_keyboard.add(KeyboardButton("📊 Статистика"), KeyboardButton("🚖 Управление заказами"))
    admin_keyboard.add(KeyboardButton("👥 Управление водителями"), KeyboardButton("$ Пополнить баланс"))
    admin_keyboard.add(KeyboardButton("⬅️ Выйти"))

    await message.answer("Добро пожаловать в админ-панель!", reply_markup=admin_keyboard)

# Обработчик для выхода из админ-панели
@dp.message_handler(text="⬅️ Выйти")
async def exit_admin_panel(message: types.Message):
    await message.answer("Вы вышли из админ-панели.", reply_markup=types.ReplyKeyboardRemove())

# Обработчик для пополнения баланса
@dp.message_handler(text="$ Пополнить баланс")
async def topup_balance(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас нет доступа к этой функции.")
        return

    await message.answer("Введите номер телефона таксиста, которому хотите пополнить баланс:")
    await AdminStates.waiting_for_driver_phone.set()

@dp.message_handler(state=AdminStates.waiting_for_driver_phone)
async def process_driver_phone(message: types.Message, state: FSMContext):
    phone = message.text
    cursor.execute("SELECT user_id, name FROM drivers WHERE phone = ?", (phone,))
    driver = cursor.fetchone()
    if driver is None:
        await message.answer("Таксист с таким номером телефона не найден. Попробуйте снова.")
        return
    driver_id, driver_name = driver
    await state.update_data(driver_id=driver_id)
    await message.answer(f"Вы выбрали таксиста {driver_name}. Введите сумму пополнения:")
    await AdminStates.waiting_for_topup_amount.set()

@dp.message_handler(state=AdminStates.waiting_for_topup_amount)
async def process_topup_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма пополнения должна быть положительной. Попробуйте снова.")
            return
        data = await state.get_data()
        driver_id = data['driver_id']
        cursor.execute("UPDATE drivers SET balance = balance + ? WHERE user_id = ?", (amount, driver_id))
        conn.commit()
        await message.answer(f"Баланс таксиста с номером телефона {message.text} успешно пополнен на {amount} тг.")
        
        # Уведомляем таксиста о пополнении баланса
        try:
            await bot.send_message(driver_id, f"Ваш баланс был пополнен на {amount} тг. Ваш текущий баланс: {amount} тг.")
        except aiogram.utils.exceptions.ChatNotFound:
            await message.answer("Не удалось отправить уведомление таксисту. Возможно, бот никогда не взаимодействовал с этим пользователем.")
        
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму.")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
