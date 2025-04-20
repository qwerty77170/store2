import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Токен бота (получите у @BotFather)
API_TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"
ADMIN_ID = 123456789  # Ваш ID в Telegram (узнать можно у @userinfobot)

# Инициализация бота
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Состояния для FSM
class AdminStates(StatesGroup):
    wait_product_data = State()
    wait_product_delete = State()

# Подключение к SQLite
def get_db():
    conn = sqlite3.connect('shop.db')
    return conn

# Создание таблиц при первом запуске
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT,
            login TEXT,
            password TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ===== КЛАВИАТУРЫ ===== #
def get_main_keyboard(is_admin=False):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")],
        *([[InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")]] if is_admin else [])
    ])
    return keyboard

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="🗑 Удалить товар", callback_data="delete_product")],
        [InlineKeyboardButton(text="📊 Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    return keyboard

def get_products_keyboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products")
    products = cursor.fetchall()
    conn.close()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(text=f"{product[1]} - {product[2]}₽", callback_data=f"buy_{product[0]}")] for product in products],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    return keyboard

# ===== ОСНОВНЫЕ КОМАНДЫ ===== #
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer(
        "🛒 Добро пожаловать в магазин!",
        reply_markup=get_main_keyboard(is_admin)
    )

# ===== ОБРАБОТКА КНОПОК ===== #
@dp.callback_query(Text("main_menu"))
async def main_menu(call: types.CallbackQuery):
    is_admin = (call.from_user.id == ADMIN_ID)
    await call.message.edit_text(
        "🛒 Главное меню",
        reply_markup=get_main_keyboard(is_admin)
    )

@dp.callback_query(Text("catalog"))
async def show_catalog(call: types.CallbackQuery):
    await call.message.edit_text(
        "📦 Выберите товар:",
        reply_markup=get_products_keyboard()
    )

@dp.callback_query(Text("admin_panel"))
async def admin_panel(call: types.CallbackQuery):
    if call.from_user.id == ADMIN_ID:
        await call.message.edit_text(
            "⚙️ Админ-панель",
            reply_markup=get_admin_keyboard()
        )
    else:
        await call.answer("⛔ Доступ запрещен!")

# ===== АДМИН-ПАНЕЛЬ ===== #
@dp.callback_query(Text("add_product"))
async def add_product_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id == ADMIN_ID:
        await call.message.edit_text(
            "📝 Введите данные товара в формате:\n\n"
            "<b>Название | Цена | Описание | Логин | Пароль</b>\n\n"
            "Пример: <code>YouTube Premium | 500 | Аккаунт на 1 месяц | test@mail.com | 12345</code>"
        )
        await state.set_state(AdminStates.wait_product_data)
    else:
        await call.answer("⛔ Доступ запрещен!")

@dp.message(AdminStates.wait_product_data)
async def add_product_finish(message: types.Message, state: FSMContext):
    try:
        name, price, desc, login, password = map(str.strip, message.text.split("|"))
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (name, price, description, login, password) VALUES (?, ?, ?, ?, ?)",
            (name, int(price), desc, login, password)
        )
        conn.commit()
        conn.close()
        await message.answer("✅ Товар добавлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()

@dp.callback_query(Text("list_products"))
async def list_products(call: types.CallbackQuery):
    if call.from_user.id == ADMIN_ID:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price FROM products")
        products = cursor.fetchall()
        conn.close()

        if not products:
            await call.answer("🗃 Товаров нет!")
            return

        text = "📦 Список товаров:\n\n"
        for product in products:
            text += f"{product[0]}. {product[1]} - {product[2]}₽\n"

        await call.message.edit_text(text, reply_markup=get_admin_keyboard())
    else:
        await call.answer("⛔ Доступ запрещен!")

@dp.callback_query(Text("delete_product"))
async def delete_product_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id == ADMIN_ID:
        await call.message.edit_text("✏️ Введите ID товара для удаления:")
        await state.set_state(AdminStates.wait_product_delete)
    else:
        await call.answer("⛔ Доступ запрещен!")

@dp.message(AdminStates.wait_product_delete)
async def delete_product_finish(message: types.Message, state: FSMContext):
    try:
        product_id = int(message.text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        await message.answer("✅ Товар удален!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()

# ===== ПОКУПКА ТОВАРА ===== #
@dp.callback_query(Text(startswith="buy_"))
async def process_buy(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        await call.answer("❌ Товар не найден!")
        return

    pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить (тест)", callback_data=f"pay_{product_id}")]
    ])

    await call.message.edit_text(
        f"💳 Оформление заказа:\n\n"
        f"Товар: {product[0]}\n"
        f"Цена: {product[1]}₽\n\n"
        "Нажмите кнопку ниже для симуляции оплаты:",
        reply_markup=pay_keyboard
    )

@dp.callback_query(Text(startswith="pay_"))
async def process_pay(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, login, password FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        await call.answer("❌ Товар не найден!")
        return

    await call.message.edit_text(
        f"✅ Оплата прошла успешно!\n\n"
        f"Товар: {product[0]}\n"
        f"Цена: {product[1]}₽\n\n"
        "Данные для входа:\n"
        f"Логин: <code>{product[2]}</code>\n"
        f"Пароль: <code>{product[3]}</code>"
    )

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())