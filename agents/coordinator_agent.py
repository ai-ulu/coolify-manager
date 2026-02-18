"""
Multi-Server Coordinator Agent
Birden fazla Coolify sunucusunun koordinasyonu
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging
import uuid

from ..config import SERVERS
from ..coolify_api import CoolifyAPI

logger = logging.getLogger(__name__)


@dataclass
class Server:
    """Sunucu bilgisi"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    url: str = ""
    api_key: str = ""
    enabled: bool = True
    status: str = "unknown"  # online, offline, degraded
    last_check: Optional[datetime] = None
    applications_count: int = 0
    total_resources: Dict = field(default_factory=dict)


class MultiServerCoordinator:
    """
    Çoklu sunucu koordinatörü.
    Birden fazla Coolify sunucusunu tek bir arayüzden yönetir.
    """
    
    def __init__(self):
        self.servers: Dict[str, Server] = {}
        self.api_clients: Dict[str, CoolifyAPI] = {}
        self._load_servers()
    
    def _load_servers(self):
        """Kayıtlı sunucuları yükler"""
        for key, config in SERVERS.items():
            self.add_server(
                name=config.get("name", key),
                url=config.get("url", ""),
                api_key=config.get("api_key", ""),
                enabled=config.get("enabled", True),
            )
    
    def add_server(self, name: str, url: str, api_key: str, 
                   enabled: bool = True) -> Server:
        """Yeni sunucu ekler"""
        server = Server(
            name=name,
            url=url,
            api_key=api_key,
            enabled=enabled,
        )
        self.servers[name] = server
        
        # API client oluştur
        self.api_clients[name] = CoolifyAPI(url=url, api_key=api_key)
        
        logger.info(f"Sunucu eklendi: {name}")
        return server
    
    def remove_server(self, name: str) -> bool:
        """Sunucuyu kaldırır"""
        if name in self.servers:
            del self.servers[name]
            del self.api_clients[name]
            logger.info(f"Sunucu kaldırıldı: {name}")
            return True
        return False
    
    def get_server(self, name: str) -> Optional[Server]:
        """Sunucu bilgisini döndürür"""
        return self.servers.get(name)
    
    def get_api(self, server_name: str) -> Optional[CoolifyAPI]:
        """Sunucu API'sini döndürür"""
        return self.api_clients.get(server_name)
    
    async def check_server_status(self, server_name: str) -> Server:
        """Sunucu durumunu kontrol eder"""
        server = self.servers.get(server_name)
        if not server:
            return None
        
        api = self.api_clients.get(server_name)
        if not api:
            server.status = "offline"
            return server
        
        try:
            status = api.get_server_status()
            if "error" not in status:
                server.status = "online"
                # Kaynak sayısını al
                apps = api.get_applications()
                server.applications_count = len(apps) if isinstance(apps, list) else 0
            else:
                server.status = "offline"
        except Exception as e:
            logger.error(f"Sunucu kontrol hatası ({server_name}): {e}")
            server.status = "offline"
        
        server.last_check = datetime.now()
        return server
    
    async def check_all_servers(self) -> Dict[str, Server]:
        """Tüm sunucuların durumunu kontrol eder"""
        for name in self.servers:
            await self.check_server_status(name)
        return self.servers
    
    def list_servers(self) -> str:
        """Sunucuları listeler"""
        if not self.servers:
            return "🖥️ Kayıtlı sunucu yok"
        
        msg = "🖥️ **Sunucular:**\n\n"
        
        for name, server in self.servers.items():
            status_emoji = {
                "online": "🟢",
                "offline": "🔴",
                "degraded": "🟡",
                "unknown": "⚪",
            }.get(server.status, "⚪")
            
            enabled = "✅" if server.enabled else "⏸️"
            
            msg += f"{enabled} **{server.name}** {status_emoji}\n"
            msg += f"   URL: {server.url}\n"
            msg += f"   Durum: {server.status}\n"
            msg += f"   Uygulamalar: {server.applications_count}\n"
            if server.last_check:
                msg += f"   Son kontrol: {server.last_check.strftime('%H:%M:%S')}\n"
            msg += "\n"
        
        return msg
    
    def get_unified_status(self) -> str:
        """Birleşik durum bilgisi"""
        if not self.servers:
            return "🖥️ Sunucu yok"
        
        online = sum(1 for s in self.servers.values() if s.status == "online")
        offline = sum(1 for s in self.servers.values() if s.status == "offline")
        total = len(self.servers)
        
        if offline == total:
            emoji = "🔴"
            status = "Tüm sunucular çevrimdışı"
        elif online == total:
            emoji = "🟢"
            status = "Tüm sunucular çevrimiçi"
        else:
            emoji = "🟡"
            status = f"{online}/{total} çevrimiçi"
        
        return f"{emoji} **{status}**"
    
    async def deploy_to_all(self, application_name: str = None) -> Dict[str, Dict]:
        """Tüm sunuculara deploy eder"""
        results = {}
        
        for name, server in self.servers.items():
            if not server.enabled or server.status != "online":
                results[name] = {"status": "skipped", "reason": "sunucu kapalı"}
                continue
            
            api = self.api_clients.get(name)
            if not api:
                results[name] = {"status": "error", "reason": "API bulunamadı"}
                continue
            
            try:
                if application_name:
                    # Belirli uygulamayı bul ve deploy et
                    apps = api.get_applications()
                    for app in apps:
                        if app.get("name") == application_name:
                            result = api.deploy_application(app.get("id"))
                            results[name] = result
                            break
                else:
                    # Tüm uygulamaları deploy et
                    apps = api.get_applications()
                    results[name] = {"deployed": len(apps) if isinstance(apps, list) else 0}
                    
            except Exception as e:
                logger.error(f"Deploy hatası ({name}): {e}")
                results[name] = {"status": "error", "reason": str(e)}
        
        return results
    
    async def get_all_applications(self) -> Dict[str, List[Dict]]:
        """Tüm sunuculardaki uygulamaları getirir"""
        all_apps = {}
        
        for name, server in self.servers.items():
            if not server.enabled:
                continue
            
            api = self.api_clients.get(name)
            if not api:
                continue
            
            try:
                apps = api.get_applications()
                all_apps[name] = apps if isinstance(apps, list) else []
            except Exception as e:
                logger.error(f"Uygulama listeleme hatası ({name}): {e}")
                all_apps[name] = []
        
        return all_apps
    
    def format_server_status(self, server_name: str) -> str:
        """Belirli sunucunun durumunu formatlar"""
        server = self.servers.get(server_name)
        if not server:
            return f"Sunucu bulunamadı: {server_name}"
        
        api = self.api_clients.get(server_name)
        if not api:
            return f"API bulunamadı: {server_name}"
        
        msg = f"🖥️ **{server.name}**\n\n"
        
        # Sunucu durumu
        status_emoji = {"online": "🟢", "offline": "🔴", "degraded": "🟡"}.get(server.status, "⚪")
        msg += f"Durum: {status_emoji} {server.status}\n"
        msg += f"URL: {server.url}\n\n"
        
        # Uygulamalar
        try:
            apps = api.get_applications()
            if isinstance(apps, list):
                msg += f"**Uygulamalar ({len(apps)}):**\n"
                for app in apps:
                    status = app.get("status", "unknown")
                    emoji = {"running": "🟢", "stopped": "🔴", "deploying": "🔵"}.get(status, "⚪")
                    msg += f"{emoji} {app.get('name', 'Bilinmiyor')}\n"
        except Exception as e:
            msg += f"Uygulama listeleme hatası: {e}\n"
        
        return msg


# Global coordinator
coordinator = MultiServerCoordinator()


def get_coordinator() -> MultiServerCoordinator:
    """Coordinator instance'ını döndürür"""
    return coordinator
