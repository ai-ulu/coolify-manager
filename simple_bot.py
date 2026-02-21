#!/usr/bin/env python3
"""
Simple Telegram Bot for Coolify Manager
"""

import asyncio
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🎉 *Coolify Manager Botu Aktif!*\n\n"
        "Sunucunuzu Telegram üzerinden yönetebilirsiniz.\n\n"
        "/help - Tüm komutları gör",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        """📋 *Mevcut Komutlar:*

/start - Botu başlat
/status - Sistem durumu
/metrics - Detaylı metrikler  
/cpu - CPU kullanımı
/ram - RAM kullanımı
/disk - Disk kullanımı
/top - En çok kaynak kullanan processler
/alerts - Aktif alarmlar

🚀 *Uygulama Yönetimi:*
/list - Uygulama listesi
/deploy <isim> - Deploy et
/start <isim> - Başlat
/stop <isim> - Durdur
/restart <isim> - Yeniden başlat
/logs <isim> - Logları göster

💾 *Yedekleme:*
/backup - Yedek oluştur
/backups - Yedekleri listele

📅 *Diğer:*
/schedule - Scheduled görevler
/servers - Sunucu durumları""",
        parse_mode="Markdown"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command"""
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    cpu_emoji = "🟢" if cpu < 50 else "🟡" if cpu < 80 else "🔴"
    ram_emoji = "🟢" if ram < 50 else "🟡" if ram < 80 else "🔴"
    disk_emoji = "🟢" if disk < 50 else "🟡" if disk < 80 else "🔴"
    
    await update.message.reply_text(
        f"""📊 *Sistem Durumu*

{cpu_emoji} CPU: {cpu:.1f}%
{ram_emoji} RAM: {ram:.1f}%
{disk_emoji} Disk: {disk:.1f}%

🤖 Coolify Manager v1.0""",
        parse_mode="Markdown"
    )

async def metrics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metrics command"""
    import psutil
    import datetime
    
    cpu = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    load = psutil.getloadavg()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    
    await update.message.reply_text(
        f"""📈 *Detaylı Metrikler*

*CPU:*
Kullanım: {cpu:.1f}%
Çekirdek: {cpu_count}
Load: {load[0]:.2f} | {load[1]:.2f} | {load[2]:.2f}

*RAM:*
Kullanılan: {ram.used / (1024**3):.1f}GB / {ram.total / (1024**3):.1f}GB
%{ram.percent}

*Disk:*
Kullanılan: {disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB
%{disk.percent}

*Network:*
Gönderilen: {net.bytes_sent / (1024**2):.1f}MB
Alınan: {net.bytes_recv / (1024**2):.1f}MB""",
        parse_mode="Markdown"
    )

async def cpu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CPU command"""
    import psutil
    cpu = psutil.cpu_percent(interval=1)
    emoji = "🟢" if cpu < 50 else "🟡" if cpu < 80 else "🔴"
    await update.message.reply_text(f"{emoji} *CPU:* {cpu:.1f}%", parse_mode="Markdown")

async def ram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """RAM command"""
    import psutil
    ram = psutil.virtual_memory()
    emoji = "🟢" if ram.percent < 50 else "🟡" if ram.percent < 80 else "🔴"
    await update.message.reply_text(
        f"{emoji} *RAM:* {ram.percent:.1f}%\nKullanılan: {ram.used / (1024**3):.1f}GB / {ram.total / (1024**3):.1f}GB",
        parse_mode="Markdown"
    )

async def disk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disk command"""
    import psutil
    disk = psutil.disk_usage('/')
    emoji = "🟢" if disk.percent < 50 else "🟡" if disk.percent < 80 else "🔴"
    await update.message.reply_text(
        f"{emoji} *Disk:* {disk.percent:.1f}%\nKullanılan: {disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB",
        parse_mode="Markdown"
    )

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Top processes"""
    import psutil
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            if pinfo['cpu_percent'] or pinfo['memory_percent']:
                processes.append(pinfo)
        except:
            pass
    
    processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    
    msg = "🔥 *Top 5 Process:*\n\n"
    for i, p in enumerate(processes[:5], 1):
        msg += f"{i}. {p['name'][:20]}\n   CPU: {p['cpu_percent']:.1f}% | RAM: {p['memory_percent']:.1f}%\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List applications"""
    # TODO: Coolify API bağlanınca gerçek uygulama listesini göster
    await update.message.reply_text(
        "📋 *Uygulamalar*\n\n"
        "🔴 *Coolify API bağlantısı bekleniyor...*\n\n"
        "API key ayarlandıktan sonra burada uygulamalarınız görünecek.",
        parse_mode="Markdown"
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo message"""
    await update.message.reply_text(
        "✅ Mesajını aldım!\n\n"
        "Komutlar için /help yazabilirsin!"
    )

async def main():
    """Main function"""
    logger.info("Bot başlatılıyor...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Komutlar
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("metrics", metrics_cmd))
    app.add_handler(CommandHandler("cpu", cpu_cmd))
    app.add_handler(CommandHandler("ram", ram_cmd))
    app.add_handler(CommandHandler("disk", disk_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    
    # Diğer mesajlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    logger.info("Bot hazır! Polling başladı...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_forever()


