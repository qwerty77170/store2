import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Конфигурация
API_TOKEN = "ВАШ_TELEGRAM_BOT_TOKEN"
ADMIN_ID = 123456789  # Ваш ID в Telegram

# Инициализация бота
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Состояния для FSM
class AdminStates(StatesGroup):
    wait_product_data = State()
    wait_product_delete = State()

# Подключение к SQLite
def get_db():
    return sqlite3.connect('shop.db')

# Инициализация БД
def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                login TEXT,
                password TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

init_db()

# ===== КЛАВИАТУРЫ ===== #
def get_main_keyboard(is_admin=False):
    buttons = [
        [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="🗑 Удалить товар", callback_data="delete_product")],
        [InlineKeyboardButton(text="📊 Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

def get_products_keyboard():
    with get_db() as conn:
        products = conn.execute("SELECT id, name, price FROM products").fetchall()
    
    buttons = [
        [InlineKeyboardButton(text=f"{p[1]} - {p[2]}₽", callback_data=f"buy_{p[0]}")] 
        for p in products
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ===== ОСНОВНЫЕ КОМАНДЫ ===== #
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🛒 Добро пожаловать в магазин!",
        reply_markup=get_main_keyboard(message.from_user.id == ADMIN_ID)
    )

# ===== ОБРАБОТКА КНОПОК ===== #
@dp.callback_query(F.data == "main_menu")
async def main_menu(call: types.CallbackQuery):
    await call.message.edit_text(
        "🛒 Главное меню",
        reply_markup=get_main_keyboard(call.from_user.id == ADMIN_ID)
    )

@dp.callback_query(F.data == "catalog")
async def show_catalog(call: types.CallbackQuery):
    await call.message.edit_text(
        "📦 Выберите товар:",
        reply_markup=get_products_keyboard()
    )

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: types.CallbackQuery):
    if call.from_user.id == ADMIN_ID:
        await call.message.edit_text(
            "⚙️ Админ-панель",
            reply_markup=get_admin_keyboard()
        )
    else:
        await call.answer("⛔ Доступ запрещен!")

# ===== АДМИН-ПАНЕЛЬ ===== #
@dp.callback_query(F.data == "add_product")
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
        with get_db() as conn:
            conn.execute(
                "INSERT INTO products VALUES (NULL, ?, ?, ?, ?, ?)",
                (name, int(price), desc, login, password)
        await message.answer("✅ Товар добавлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()

@dp.callback_query(F.data == "list_products")
async def list_products(call: types.CallbackQuery):
    if call.from_user.id == ADMIN_ID:
        with get_db() as conn:
            products = conn.execute("SELECT id, name, price FROM products").fetchall()
        
        if not products:
            await call.answer("🗃 Товаров нет!")
            return

        text = "📦 Список товаров:\n\n" + "\n".join(
            f"{p[0]}. {p[1]} - {p[2]}₽" for p in products
        )
        await call.message.edit_text(text, reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "delete_product")
async def delete_product_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id == ADMIN_ID:
        await call.message.edit_text("✏️ Введите ID товара для удаления:")
        await state.set_state(AdminStates.wait_product_delete)

@dp.message(AdminStates.wait_product_delete)
async def delete_product_finish(message: types.Message, state: FSMContext):
    try:
        product_id = int(message.text)
        with get_db() as conn:
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await message.answer("✅ Товар удален!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()

# ===== ПОКУПКА ТОВАРА ===== #
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    with get_db() as conn:
        product = conn.execute(
            "SELECT name, price FROM products WHERE id = ?", 
            (product_id,)
        ).fetchone()

    if not product:
        await call.answer("❌ Товар не найден!")
        return

    await call.message.edit_text(
        f"💳 Оформление заказа:\n\n"
        f"Товар: {product[0]}\n"
        f"Цена: {product[1]}₽\n\n"
        "Нажмите кнопку ниже для симуляции оплаты:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Оплатить (тест)", callback_data=f"pay_{product_id}")
        ]])
    )

@dp.callback_query(F.data.startswith("pay_"))
async def process_pay(call: types.CallbackQuery):
    product_id = int(call.data.split("_")[1])
    with get_db() as conn:
        product = conn.execute(
            "SELECT name, price, login, password FROM products WHERE id = ?", 
            (product_id,)
        ).fetchone()

    await call.message.edit_text(
        f"✅ Оплата прошла успешно!\n\n"
        f"Товар: {product[0]}\n"
        f"Цена: {product[1]}₽\n\n"
        f"Логин: <code>{product[2]}</code>\n"
        f"Пароль: <code>{product[3]}</code>"
    )

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
