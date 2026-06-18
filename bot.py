import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "8331925159:AAFW6XK7LE7GcJP6ABbiE7KaWXh2zvfdrtI")

CATEGORIES = {
    "🛒 Продукты": "продукты",
    "☕ Кафе": "кафе",
    "💊 Здоровье": "здоровье",
    "📢 Реклама": "реклама",
    "🏛 Налоги": "налоги",
    "🎁 Донат": "донат",
    "📦 Другие траты": "другие"
}

DATA_FILE = "expenses.json"

CHOOSING_CATEGORY, ENTERING_AMOUNT, ENTERING_NOTE = range(3)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data(user_id, data):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"expenses": []}
    return data[uid]

def main_keyboard():
    buttons = list(CATEGORIES.keys())
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    keyboard.append(["📊 Статистика", "📅 За месяц"])
    keyboard.append(["🗑 Сбросить всё"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для учёта расходов.\n\n"
        "Выбери категорию и введи сумму.\n"
        "💡 Валюта — любая (€, $, грн и т.д.)\n\n"
        "Выбери категорию:",
        reply_markup=main_keyboard()
    )
    return CHOOSING_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 Статистика":
        await show_stats(update, context, period="all")
        return CHOOSING_CATEGORY

    if text == "📅 За месяц":
        await show_stats(update, context, period="month")
        return CHOOSING_CATEGORY

    if text == "🗑 Сбросить всё":
        data = load_data()
        uid = str(update.effective_user.id)
        if uid in data:
            data[uid] = {"expenses": []}
            save_data(data)
        await update.message.reply_text("✅ Все данные сброшены.", reply_markup=main_keyboard())
        return CHOOSING_CATEGORY

    if text in CATEGORIES:
        context.user_data["category"] = CATEGORIES[text]
        context.user_data["category_emoji"] = text
        await update.message.reply_text(
            f"Выбрана категория: {text}\n\n💰 Введи сумму (например: 25.50 или 100):"
        )
        return ENTERING_AMOUNT

    await update.message.reply_text("Выбери категорию из меню:", reply_markup=main_keyboard())
    return CHOOSING_CATEGORY

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❗ Введи корректную сумму (например: 25.50):")
        return ENTERING_AMOUNT

    context.user_data["amount"] = amount
    await update.message.reply_text(
        "📝 Добавь заметку (необязательно).\nИли отправь /skip чтобы пропустить:"
    )
    return ENTERING_NOTE

async def enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip() if update.message.text != "/skip" else ""
    await save_expense(update, context, note)
    return CHOOSING_CATEGORY

async def skip_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_expense(update, context, "")
    return CHOOSING_CATEGORY

async def save_expense(update, context, note):
    data = load_data()
    user_data = get_user_data(update.effective_user.id, data)

    expense = {
        "category": context.user_data["category"],
        "amount": context.user_data["amount"],
        "note": note,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    user_data["expenses"].append(expense)
    save_data(data)

    emoji = context.user_data["category_emoji"]
    note_text = f"\n📝 {note}" if note else ""
    await update.message.reply_text(
        f"✅ Сохранено!\n\n{emoji} {context.user_data['amount']:.2f}{note_text}\n📅 {expense['date']}",
        reply_markup=main_keyboard()
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, period="all"):
    data = load_data()
    user_data = get_user_data(update.effective_user.id, data)
    expenses = user_data["expenses"]

    if period == "month":
        current_month = datetime.now().strftime("%Y-%m")
        expenses = [e for e in expenses if e["date"].startswith(current_month)]
        title = f"📅 Расходы за {datetime.now().strftime('%B %Y')}"
    else:
        title = "📊 Все расходы"

    if not expenses:
        await update.message.reply_text("📭 Расходов пока нет.", reply_markup=main_keyboard())
        return

    totals = {}
    for e in expenses:
        cat = e["category"]
        totals[cat] = totals.get(cat, 0) + e["amount"]

    total_all = sum(totals.values())

    emoji_map = {v: k for k, v in CATEGORIES.items()}

    lines = [f"{title}\n{'─'*25}"]
    for cat, amount in sorted(totals.items(), key=lambda x: -x[1]):
        emoji = emoji_map.get(cat, "📦")
        percent = (amount / total_all * 100) if total_all > 0 else 0
        lines.append(f"{emoji} — {amount:.2f} ({percent:.0f}%)")

    lines.append(f"{'─'*25}")
    lines.append(f"💰 Итого: {total_all:.2f}")
    lines.append(f"🔢 Записей: {len(expenses)}")

    await update.message.reply_text("\n".join(lines), reply_markup=main_keyboard())

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
        states={
            CHOOSING_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            ENTERING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
            ENTERING_NOTE: [
                CommandHandler("skip", skip_note),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_note)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
