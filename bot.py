import os
import sqlite3
import pandas as pd
from datetime import datetime, date, time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8392703842:AAG-KsyGv6x4-aKfCZnBF08JxiiyO5JQCw0"           # вставьте сюда токен от @BotFather
ADMIN_CHAT_ID = 685885086                # вставьте свой числовой ID (узнать у @userinfobot)

# Состояния для диалога
SELECTING_DEPARTMENT, SELECTING_PRODUCT, TYPING_AMOUNT = range(3)

# Список подразделений (можно изменить на свои)
DEPARTMENTS = [
    "110 Галерея",
    "150 Магистральная",
    "170 Советская",
    "190 Авангард",
    "210 Пионерская",
    "230 Строитель",
    "250 Сосновка",
    "270 Моршанск",
    "290 Первомайский",
    "310 Пушкина",
    "330 Гранд",
    "350 Кирсанов",
    "370 Токаревка",
    "390 Аптека",
    "410 Бондари",
    "470 Сенько",
    "510 Гражданская",
    "530 Мичуринск",
    "590 Дубняк",
    "610 Расск.Шоссе",
    "630 Север",
]

DB_FILE = "shop.db"
# ===============================

def init_db():
    """Создаёт таблицы, если их нет"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Таблица товаров
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Добавим начальные товары, если таблица пуста
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        initial_products = ["Бананы"]
        for p in initial_products:
            try:
                c.execute("INSERT INTO products (name) VALUES (?)", (p,))
            except:
                pass
    
    # Таблица перемещений
    c.execute('''
        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            department TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            user_id INTEGER,
            username TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    conn.commit()
    conn.close()

def get_products():
    """Возвращает список названий товаров из БД"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name FROM products ORDER BY name")
    products = [row[0] for row in c.fetchall()]
    conn.close()
    return products

# ========== ДИАЛОГ С ПОЛЬЗОВАТЕЛЕМ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 1: выбор подразделения"""
    reply_keyboard = [[dept] for dept in DEPARTMENTS]
    await update.message.reply_text(
        "👋 Привет! Выберите ваше подразделение:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECTING_DEPARTMENT

async def department_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 2: выбор товара (после подразделения)"""
    department = update.message.text
    if department not in DEPARTMENTS:
        await update.message.reply_text(
            "Пожалуйста, выберите подразделение из кнопок ниже.",
            reply_markup=ReplyKeyboardMarkup([[dept] for dept in DEPARTMENTS], one_time_keyboard=True)
        )
        return SELECTING_DEPARTMENT

    context.user_data['department'] = department

    products = get_products()
    if not products:
        await update.message.reply_text(
            "Список товаров пуст. Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Создаём клавиатуру с товарами (по две кнопки в ряд)
    reply_keyboard = []
    row = []
    for i, prod in enumerate(products):
        row.append(prod)
        if len(row) == 2:
            reply_keyboard.append(row)
            row = []
    if row:
        reply_keyboard.append(row)

    await update.message.reply_text(
        f"Подразделение: {department}\nТеперь выберите товар:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECTING_PRODUCT

async def product_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Шаг 3: ввод количества (после выбора товара)"""
    product_name = update.message.text
    products = get_products()
    if product_name not in products:
        await update.message.reply_text(
            "Пожалуйста, выберите товар из кнопок.",
            reply_markup=ReplyKeyboardMarkup([[p] for p in products], one_time_keyboard=True)
        )
        return SELECTING_PRODUCT

    context.user_data['product'] = product_name
    await update.message.reply_text(
        f"Товар: {product_name}\nВведите количество в килограммах (можно дробное, например 23,754):",
        reply_markup=ReplyKeyboardRemove()
    )
    return TYPING_AMOUNT

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Финал: сохраняем данные в БД"""
    text = update.message.text.strip().replace(',', '.')
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите положительное число.")
        return TYPING_AMOUNT

    department = context.user_data.get('department')
    product_name = context.user_data.get('product')
    if not department or not product_name:
        await update.message.reply_text("Ошибка данных. Начните заново /start")
        return ConversationHandler.END

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM products WHERE name = ?", (product_name,))
    product_id = c.fetchone()[0]

    user = update.effective_user
    today = date.today().isoformat()

    c.execute('''
        INSERT INTO movements (date, department, product_id, amount, user_id, username)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (today, department, product_id, amount, user.id, user.username or user.first_name))
    conn.commit()
    conn.close()

    amount_str = f"{amount:g}".replace('.', ',')
    await update.message.reply_text(
        f"✅ Спасибо! Записано: {department}, {product_name} — {amount_str} кг.\n"
        "Если нужно добавить ещё, нажмите /start"
    )

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога"""
    await update.message.reply_text(
        "Действие отменено. Чтобы начать заново, нажмите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ========== КОМАНДЫ АДМИНИСТРАТОРА ==========
async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить новый товар (только админ)"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("У вас нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /add_product Название товара")
        return
    product_name = ' '.join(context.args)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (name) VALUES (?)", (product_name,))
        conn.commit()
        await update.message.reply_text(f"Товар '{product_name}' добавлен.")
    except sqlite3.IntegrityError:
        await update.message.reply_text("Такой товар уже существует.")
    finally:
        conn.close()

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить товар (только админ)"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("У вас нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /remove_product Название товара")
        return
    product_name = ' '.join(context.args)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE name = ?", (product_name,))
    if c.rowcount > 0:
        conn.commit()
        await update.message.reply_text(f"Товар '{product_name}' удалён.")
    else:
        await update.message.reply_text("Товар не найден.")
    conn.close()

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех товаров (доступно всем)"""
    products = get_products()
    if products:
        text = "📦 Список товаров:\n" + "\n".join(f"• {p}" for p in products)
    else:
        text = "Список товаров пуст."
    await update.message.reply_text(text)

# ========== ОТЧЁТЫ ==========
async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /report (только админ)"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("У вас нет прав.")
        return
    await update.message.reply_text("Формирую отчёт...")
    await send_daily_report(context.bot)
    await update.message.reply_text("Отчёт отправлен!")

async def send_daily_report(bot):
    """Формирует Excel-отчёт за сегодня и отправляет админу"""
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    
    df = pd.read_sql_query('''
        SELECT m.timestamp, m.department, p.name AS product, m.amount, m.username
        FROM movements m
        JOIN products p ON m.product_id = p.id
        WHERE m.date = ?
        ORDER BY m.timestamp
    ''', conn, params=(today,))
    conn.close()

    if df.empty:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"За {today} нет записей.")
        return

    # Сводка по подразделениям и товарам
    summary = df.groupby(['department', 'product'])['amount'].sum().reset_index()
    pivot = summary.pivot(index='department', columns='product', values='amount').fillna(0)

    detail = df[['timestamp', 'department', 'product', 'amount', 'username']].copy()
    detail.columns = ['Время', 'Подразделение', 'Товар', 'Количество (кг)', 'Пользователь']

    filename = f"report_{today}.xlsx"
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        pivot.to_excel(writer, sheet_name='Сводка')
        detail.to_excel(writer, sheet_name='Детально', index=False)

    with open(filename, 'rb') as f:
        await bot.send_document(
            chat_id=ADMIN_CHAT_ID,
            document=f,
            caption=f"Отчёт за {today}\nВсего записей: {len(df)}"
        )
    os.remove(filename)

# ========== НОВАЯ ФУНКЦИЯ ДЛЯ ЕЖЕДНЕВНОГО ОТЧЁТА ЧЕРЕЗ JOB QUEUE ==========
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    """Функция, которая вызывается планировщиком каждый день в 18:00"""
    await send_daily_report(context.bot)

# ========== ЗАПУСК ==========
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, department_chosen)],
            SELECTING_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_chosen)],
            TYPING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(conv_handler)

    application.add_handler(CommandHandler('add_product', add_product))
    application.add_handler(CommandHandler('remove_product', remove_product))
    application.add_handler(CommandHandler('list_products', list_products))
    application.add_handler(CommandHandler('report', generate_report))

    # Настройка ежедневного отчёта с помощью встроенного JobQueue
    job_queue = application.job_queue
    if job_queue:
        # Отправляем отчёт каждый день в 18:00
        job_queue.run_daily(daily_report_job, time(hour=18, minute=00))
        print("Ежедневный отчёт запланирован на 18:00")
    else:
        print("JobQueue не доступен (возможно, не установлен python-telegram-bot[job-queue])")

    print("Бот запущен с поддержкой множества товаров!")
    application.run_polling()

if __name__ == "__main__":
    main()




    # python bot.py