#!/usr/bin/env python3
"""
Telegram Bot - Threaded Version
"""

import asyncio
import logging
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import psutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "7983514177:AAEk5pO0q1w209q5-Im1iRkxV6v3FS0UIP8"

# ==================== HANDLERS ====================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Coolify Manager Aktif!*\n\nTelegram üzerinden sunucunuzu yönetin.\n\n/help - Komutlar",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""📋 *Komutlar:*

/status - Durum
/metrics - Detaylı
/cpu - CPU
/ram - RAM
/disk - Disk
/top - Processler
/list - Uygulamalar
/help - Yardım""", parse_mode="Markdown")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    e = lambda v: "🟢" if v < 50 else "🟡" if v < 80 else "🔴"
    
    await update.message.reply_text(
        f"📊 *Durum*\n\n{e(cpu)} CPU: {cpu:.0f}%\n{e(ram)} RAM: {ram:.0f}%\n{e(disk)} Disk: {disk:.0f}%",
        parse_mode="Markdown"
    )

async def metrics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    
    await update.message.reply_text(
        f"""📈 *Metrikler*

CPU: {cpu:.1f}%
RAM: {ram.percent:.1f}% ({ram.used/1024**3:.1f}/{ram.total/1024**3:.1f}GB)
Disk: {disk.percent}% ({disk.used/1024**3:.1f}/{disk.total/1024**3:.1f}GB)
Net: ↓{net.bytes_recv/1024**2:.1f}MB ↑{net.bytes_sent/1024**2:.1f}MB""",
        parse_mode="Markdown"
    )

async def cpu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cpu = psutil.cpu_percent(interval=1)
    e = "🟢" if cpu < 50 else "🟡" if cpu < 80 else "🔴"
    await update.message.reply_text(f"{e} CPU: {cpu:.1f}%", parse_mode="Markdown")

async def ram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = psutil.virtual_memory()
    e = "🟢" if r.percent < 50 else "🟡" if r.percent < 80 else "🔴"
    await update.message.reply_text(f"{e} RAM: {r.percent:.1f}%", parse_mode="Markdown")

async def disk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = psutil.disk_usage('/')
    e = "🟢" if d.percent < 50 else "🟡" if d.percent < 80 else "🔴"
    await update.message.reply_text(f"{e} Disk: {d.percent:.1f}%", parse_mode="Markdown")

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    procs = []
    for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
        try:
            info = p.info
            if info['cpu_percent']:
                procs.append(info)
        except:
            pass
    procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
    
    msg = "🔥 *Top 5*\n\n"
    for i, p in enumerate(procs[:5], 1):
        msg += f"{i}. {p['name'][:15]} - CPU:{p['cpu_percent']:.0f}% RAM:{p['memory_percent']:.0f}%\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Uygulamalar\n\n🔴 API bağlantısı bekleniyor...", parse_mode="Markdown")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ /help yazın!")

# ==================== MAIN ====================

def run_bot():
    """Run bot in new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("metrics", metrics_cmd))
    app.add_handler(CommandHandler("cpu", cpu_cmd))
    app.add_handler(CommandHandler("ram", ram_cmd))
    app.add_handler(CommandHandler("disk", disk_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("🤖 Bot başladı!")
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    # Thread ile çalıştır
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    print("Bot çalışıyor... (Ctrl+C ile durdur)")
    
    # Ana thread'i canlı tut
    try:
        t.join()
    except KeyboardInterrupt:
        print("\nBot durduruldu.")
