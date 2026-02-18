"""
Telegram Bot - Ana Arayüz
Tüm agent'larla iletişim kuran Telegram bot'u
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
import uuid

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, filters
)

from .config import TELEGRAM_CONFIG
from .coolify_api import CoolifyAPI
from .agents.monitoring_agent import MonitoringAgent, get_monitoring_agent
from .agents.scheduler_agent import SchedulerAgent, get_scheduler_agent
from .agents.coordinator_agent import MultiServerCoordinator, get_coordinator

logger = logging.getLogger(__name__)


class CoolifyBot:
    """
    Coolify Telegram Bot'u.
    Tüm komutları işler ve agent'ları koordine eder.
    """
    
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.api = CoolifyAPI()
        self.monitoring = get_monitoring_agent()
        self.scheduler = get_scheduler_agent()
        self.coordinator = get_coordinator()
        self.user_sessions: Dict[str, Dict] = {}
        
        # Komutları kaydet
        self._register_commands()
    
    def _register_commands(self):
        """Komut handler'larını kaydeder"""
        # Ana komutlar
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        
        # Monitoring komutları
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("metrics", self.cmd_metrics))
        self.app.add_handler(CommandHandler("cpu", self.cmd_cpu))
        self.app.add_handler(CommandHandler("ram", self.cmd_ram))
        self.app.add_handler(CommandHandler("disk", self.cmd_disk))
        self.app.add_handler(CommandHandler("top", self.cmd_top))
        self.app.add_handler(CommandHandler("alerts", self.cmd_alerts))
        
        # Uygulama komutları
        self.app.add_handler(CommandHandler("list", self.cmd_list))
        self.app.add_handler(CommandHandler("deploy", self.cmd_deploy))
        self.app.add_handler(CommandHandler("start", self.cmd_start_app))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("restart", self.cmd_restart))
        self.app.add_handler(CommandHandler("logs", self.cmd_logs))
        
        # Backup komutları
        self.app.add_handler(CommandHandler("backup", self.cmd_backup))
        self.app.add_handler(CommandHandler("backups", self.cmd_backups))
        self.app.add_handler(CommandHandler("restore", self.cmd_restore))
        
        # Scheduler komutları
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        
        # Server komutları
        self.app.add_handler(CommandHandler("servers", self.cmd_servers))
        
        # Mesaj handler (AI sohbet için)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start komutu"""
        await update.message.reply_text(
            "🐫 *Coolify Multi-Agent Yönetim Sistemi*\n\n"
            "Hoş geldiniz! Sistemi yönetmek için komutları kullanabilirsiniz.\n\n"
            "📋 *Mevcut Komutlar:*\n"
            "/help - Tüm komutları göster\n"
            "/status - Genel durum\n"
            "/metrics - Detaylı metrikler\n"
            "/list - Uygulama listesi\n"
            "/servers - Sunucu durumları\n\n"
            "💬 Ayrıca sorularınızı yazabilirsiniz - AI asistanınız yardımcı olur!",
            parse_mode="Markdown"
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help komutu"""
        help_text = """
🐫 *Coolify Multi-Agent Sistemi*

📊 *Monitoring*
/status - Genel sistem durumu
/metrics - Detaylı metrikler
/cpu - CPU kullanımı
/ram - RAM kullanımı
/disk - Disk kullanımı
/top - En çok kaynak kullanan processler
/alerts - Aktif alarmlar

🚀 *Uygulama Yönetimi*
/list - Tüm uygulamaları listele
/deploy <isim> - Uygulama deploy et
/start <isim> - Uygulamayı başlat
/stop <isim> - Uygulamayı durdur
/restart <isim> - Uygulamayı yeniden başlat
/logs <isim> - Uygulama logları

💾 *Yedekleme*
/backup - Yedek oluştur
/backups - Yedekleri listele
/restore <id> - Yedekten geri yükle

📅 *Zamanlı Görevler*
/schedule - Scheduled görevleri göster

🖥️ *Sunucular*
/servers - Tüm sunucuları göster

💬 AI ile sohbet için direkt mesaj yazın!
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sistem durumu"""
        try:
            # Monitoring verilerini al
            metrics = self.monitoring.format_metrics()
            alerts = self.monitoring.format_alerts()
            server_status = self.coordinator.get_unified_status()
            
            msg = f"{server_status}\n\n{metrics}\n{alerts}"
            await update.message.reply_text(msg, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detaylı metrikler"""
        try:
            msg = self.monitoring.format_metrics()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_cpu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """CPU durumu"""
        try:
            metrics = self.monitoring.history[-1] if self.monitoring.history else None
            if metrics:
                emoji = "🟢" if metrics.cpu_percent < 50 else "🟡" if metrics.cpu_percent < 80 else "🔴"
                msg = f"{emoji} *CPU Kullanımı:* {metrics.cpu_percent:.1f}%\n\n"
                msg += f"Load Average: {metrics.load_average[0]:.2f} | {metrics.load_average[1]:.2f} | {metrics.load_average[2]:.2f}"
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text("📊 Metrik verisi yok")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_ram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """RAM durumu"""
        try:
            metrics = self.monitoring.history[-1] if self.monitoring.history else None
            if metrics:
                emoji = "🟢" if metrics.ram_percent < 50 else "🟡" if metrics.ram_percent < 80 else "🔴"
                msg = f"{emoji} *RAM Kullanımı:* {metrics.ram_percent:.1f}%\n\n"
                msg += f"Kullanılan: {metrics.ram_used_gb:.1f}GB / {metrics.ram_total_gb:.1f}GB"
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text("📊 Metrik verisi yok")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_disk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disk durumu"""
        try:
            metrics = self.monitoring.history[-1] if self.monitoring.history else None
            if metrics:
                emoji = "🟢" if metrics.disk_percent < 50 else "🟡" if metrics.disk_percent < 80 else "🔴"
                msg = f"{emoji} *Disk Kullanımı:* {metrics.disk_percent:.1f}%\n\n"
                msg += f"Kullanılan: {metrics.disk_used_gb:.1f}GB / {metrics.disk_total_gb:.1f}GB"
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text("📊 Metrik verisi yok")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """En çok kaynak kullanan processler"""
        try:
            msg = self.monitoring.get_top_processes()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Aktif alarmlar"""
        try:
            msg = self.monitoring.format_alerts()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uygulama listesi"""
        try:
            apps = self.api.get_applications()
            
            if not apps:
                await update.message.reply_text("📋 Uygulama bulunamadı")
                return
            
            msg = "📋 *Uygulamalar:*\n\n"
            for app in apps[:20]:  # Max 20
                status = app.get("status", "unknown")
                emoji = {"running": "🟢", "stopped": "🔴", "deploying": "🔵"}.get(status, "⚪")
                name = app.get("name", "Bilinmiyor")
                msg += f"{emoji} {name}\n"
            
            await update.message.reply_text(msg, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_deploy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Deploy komutu"""
        try:
            app_name = context.args[0] if context.args else None
            
            if not app_name:
                await update.message.reply_text("📝 Kullanım: /deploy <uygulama_adi>")
                return
            
            await update.message.reply_text(f"🚀 Deploy başlatılıyor: {app_name}...")
            
            # Uygulamayı bul
            apps = self.api.get_applications()
            app = None
            for a in apps:
                if a.get("name", "").lower() == app_name.lower():
                    app = a
                    break
            
            if not app:
                await update.message.reply_text(f"❌ Uygulama bulunamadı: {app_name}")
                return
            
            # Deploy et
            result = self.api.deploy_application(app.get("id"))
            
            if "error" in result:
                await update.message.reply_text(f"❌ Deploy hatası: {result.get('error')}")
            else:
                await update.message.reply_text(f"✅ Deploy başlatıldı!\n{result}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_start_app(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uygulama başlatma"""
        try:
            app_name = context.args[0] if context.args else None
            
            if not app_name:
                await update.message.reply_text("📝 Kullanım: /start <uygulama_adi>")
                return
            
            apps = self.api.get_applications()
            app = next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)
            
            if not app:
                await update.message.reply_text(f"❌ Uygulama bulunamadı")
                return
            
            result = self.api.start_application(app.get("id"))
            await update.message.reply_text(f"✅ {app_name} başlatıldı!")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uygulama durdurma"""
        try:
            app_name = context.args[0] if context.args else None
            
            if not app_name:
                await update.message.reply_text("📝 Kullanım: /stop <uygulama_adi>")
                return
            
            apps = self.api.get_applications()
            app = next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)
            
            if not app:
                await update.message.reply_text(f"❌ Uygulama bulunamadı")
                return
            
            result = self.api.stop_application(app.get("id"))
            await update.message.reply_text(f"⏹️ {app_name} durduruldu!")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Uygulama yeniden başlatma"""
        try:
            app_name = context.args[0] if context.args else None
            
            if not app_name:
                await update.message.reply_text("📝 Kullanım: /restart <uygulama_adi>")
                return
            
            apps = self.api.get_applications()
            app = next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)
            
            if not app:
                await update.message.reply_text(f"❌ Uygulama bulunamadı")
                return
            
            result = self.api.restart_application(app.get("id"))
            await update.message.reply_text(f"🔄 {app_name} yeniden başlatılıyor!")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log görüntüleme"""
        try:
            app_name = context.args[0] if context.args else None
            
            if not app_name:
                await update.message.reply_text("📝 Kullanım: /logs <uygulama_adi>")
                return
            
            apps = self.api.get_applications()
            app = next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)
            
            if not app:
                await update.message.reply_text(f"❌ Uygulama bulunamadı")
                return
            
            logs = self.api.get_application_logs(app.get("id"), limit=20)
            logs = logs[-2000:] if len(logs) > 2000 else logs  # Max 2000 char
            
            await update.message.reply_text(f"📜 *{app_name} Logları:*\n\n"
                                           f"```\n{logs}\n```", parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yedek oluşturma"""
        try:
            app_name = context.args[0] if context.args else None
            
            if app_name:
                apps = self.api.get_applications()
                app = next((a for a in apps if a.get("name", "").lower() == app_name.lower()), None)
                
                if app:
                    backup = await self.scheduler.create_backup(app.get("id"), app.get("name"))
                    await update.message.reply_text(f"💾 Yedek oluşturuldu: {backup.id}")
                else:
                    await update.message.reply_text(f"❌ Uygulama bulunamadı")
            else:
                # Tüm uygulamaları yedekle
                await update.message.reply_text("💾 Tüm uygulamalar yedekleniyor...")
                apps = self.api.get_applications()
                for app in apps[:10]:
                    await self.scheduler.create_backup(app.get("id"), app.get("name"))
                await update.message.reply_text(f"💾 {len(apps)} uygulama yedeklendi!")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_backups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yedekleri listeleme"""
        try:
            msg = self.scheduler.list_backups()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_restore(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yedekten geri yükleme"""
        try:
            backup_id = context.args[0] if context.args else None
            app_id = context.args[1] if len(context.args) > 1 else None
            
            if not backup_id or not app_id:
                await update.message.reply_text("📝 Kullanım: /restore <yedek_id> <uygulama_id>")
                return
            
            result = await self.scheduler.restore_backup(backup_id, app_id)
            
            if result:
                await update.message.reply_text(f"✅ Geri yükleme tamamlandı!")
            else:
                await update.message.reply_text(f"❌ Geri yükleme başarısız")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled görevleri listele"""
        try:
            msg = self.scheduler.list_tasks()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def cmd_servers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sunucuları listele"""
        try:
            # Sunucuları kontrol et
            await self.coordinator.check_all_servers()
            msg = self.coordinator.list_servers()
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Hata: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mesaj işleme (AI sohbet)"""
        # TODO: OpenAI/CAMEL-AI entegrasyonu
        await update.message.reply_text(
            "💬 AI asistan entegrasyonu yakında aktif olacak!\n"
            "Şimdilik komutları kullanabilirsiniz: /help"
        )
    
    async def send_alert(self, chat_id: str, message: str):
        """Alert gönderme"""
        try:
            await self.app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Alert gönderme hatası: {e}")
    
    def run(self):
        """Bot'u başlatır"""
        logger.info("Telegram Bot başlatılıyor...")
        self.app.run_polling(drop_pending_updates=True)


# Global bot instance
bot: Optional[CoolifyBot] = None


def create_bot(token: str) -> CoolifyBot:
    """Bot oluşturur"""
    global bot
    bot = CoolifyBot(token)
    return bot


def get_bot() -> Optional[CoolifyBot]:
    """Bot instance'ını döndürür"""
    return bot
