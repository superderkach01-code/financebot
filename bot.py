import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN", "")

CATEGORIES = {
    "🛒 Продукты": "продукты",
    "☕ Кафе": "кафе",
    "💊 Здоровье": "здоровье",
    "📢 Реклама": "реклама",
    "🏛 Налоги": "налоги",
    "🎁 Донат": "донат",
    "📦 Другие траты": "другие"
}

DATA_FILE = "/tmp/expenses.json"
CHOOSING, AMOUNT, NOTE = range(3)

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_keyboard():
    buttons = list(CATEGORIES.keys())
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    keyboard.append(["📊 Статистика", "📅 За месяц"])
    keyboard.append(["🗑 Сбросить всё"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для учёта расходов.\nВыбери категорию:",
        reply_markup=main_keyboard()
    )
    return CHOOSING

async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = str(update.effective_user.id)

    if text == "📊 Статистика":
        await stats(update, context, "all")
        return CHOOSING
    if text == "📅 За месяц":
        await stats(update, context, "month")
        return CHOOSING
    if text == "🗑 Сбросить всё":
        data = load_data()
        data[uid] = {"expenses": []}
        save_data(data)
        await update.message.reply_text("✅ Данные сброшены.", reply_markup=main_keyboard())
        return CHOOSING
    if text in CATEGORIES:
        context.user_data["cat"] = CATEGORIES[text]
        context.user_data["cat_emoji"] = text
        await update.message.reply_text(f"Категория: {text}\n\n💰 Введи сумму:")
        return AMOUNT

    await update.message.reply_text("Выбери категорию:", reply_markup=main_keyboard())
    return CHOOSING

async def amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        context.user_data["amount"] = val
        await update.message.reply_text("📝 Заметка? (или /skip)")
        return NOTE
    except:
        await update.message.reply_text("❗ Введи число, например: 25.50")
        return AMOUNT

async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_expense(update, context, update.message.text)
    return CHOOSING

async def skip_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_expense(update, context, "")
    return CHOOSING

async def save_expense(update, context, note_text):
    data = load_data()
    uid = str(update.effective_user.id)
    if uid not in data:
        data[uid] = {"expenses": []}
    data[uid]["expenses"].append({
        "category": context.user_data["cat"],
        "amount": context.user_data["amount"],
        "note": note_text,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    save_data(data)
    emoji = context.user_data["cat_emoji"]
    note_line = f"\n📝 {note_text}" if note_text else ""
    await update.message.reply_text(
        f"✅ Сохранено!\n{emoji} {context.user_data['amount']:.2f}{note_line}",
        reply_markup=main_keyboard()
    )

async def stats(update, context, period):
    data = load_data()
    uid = str(update.effective_user.id)
    expenses = data.get(uid, {}).get("expenses", [])

    if period == "month":
        m = datetime.now().strftime("%Y-%m")
        expenses = [e for e in expenses if e["date"].startswith(m)]
        title = f"📅 За {datetime.now().strftime('%B %Y')}"
    else:
        title = "📊 Все расходы"

    if not expenses:
        await update.message.reply_text("📭 Расходов нет.", reply_markup=main_keyboard())
        return

    totals = {}
    for e in expenses:
        totals[e["category"]] = totals.get(e["category"], 0) + e["amount"]

    total = sum(totals.values())
    emoji_map = {v: k for k, v in CATEGORIES.items()}
    lines = [f"{title}\n{'─'*20}"]
    for cat, amt in sorted(totals.items(), key=lambda x: -x[1]):
        pct = amt / total * 100
        lines.append(f"{emoji_map.get(cat, '📦')} {amt:.2f} ({pct:.0f}%)")
    lines.append(f"{'─'*20}\n💰 Итого: {total:.2f}\n🔢 Записей: {len(expenses)}")
    await update.message.reply_text("\n".join(lines), reply_markup=main_keyboard())

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount)],
            NOTE: [CommandHandler("skip", skip_note), MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

