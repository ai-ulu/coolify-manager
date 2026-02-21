"""
Coolify API Client
Coolify sunucusu ile iletişim kuran temel sınıf
"""

import requests
from typing import Optional, Dict, List
from datetime import datetime
import logging

from config import COOLIFY_CONFIG, get_coolify_headers

logger = logging.getLogger(__name__)


class CoolifyAPI:
    """Coolify API ile iletişim kuran sınıf"""
    
    def __init__(self, url: str = None, api_key: str = None):
        self.base_url = url or COOLIFY_CONFIG["url"]
        self.api_key = api_key or COOLIFY_CONFIG["api_key"]
        self.timeout = COOLIFY_CONFIG["timeout"]
        self.session = requests.Session()
        self.session.headers.update(get_coolify_headers(self.api_key))
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """API isteği yapar"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout: {url}")
            return {"error": "Timeout"}
        except requests.exceptions.ConnectionError:
            logger.error(f"Bağlantı hatası: {url}")
            return {"error": "Bağlantı hatası"}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP hatası: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Beklenmeyen hata: {e}")
            return {"error": str(e)}
    
    # ==================== UYGULAMALAR ====================
    
    def get_applications(self) -> List[Dict]:
        """Tüm uygulamaları getirir"""
        result = self._request("GET", "/api/v1/applications")
        return result if isinstance(result, list) else []
    
    def get_application(self, application_id: str) -> Dict:
        """Belirli bir uygulamayı getirir"""
        return self._request("GET", f"/api/v1/applications/{application_id}")
    
    def get_application_status(self, application_id: str) -> Dict:
        """Uygulama durumunu getirir"""
        return self._request("GET", f"/api/v1/applications/{application_id}/status")
    
    def deploy_application(self, application_id: str, force: bool = False) -> Dict:
        """Uygulama deploy eder"""
        data = {"force": force} if force else {}
        return self._request("POST", f"/api/v1/applications/{application_id}/deploy", json=data)
    
    def start_application(self, application_id: str) -> Dict:
        """Uygulamayı başlatır"""
        return self._request("POST", f"/api/v1/applications/{application_id}/start")
    
    def stop_application(self, application_id: str) -> Dict:
        """Uygulamayı durdurur"""
        return self._request("POST", f"/api/v1/applications/{application_id}/stop")
    
    def restart_application(self, application_id: str) -> Dict:
        """Uygulamayı yeniden başlatır"""
        return self._request("POST", f"/api/v1/applications/{application_id}/restart")
    
    def delete_application(self, application_id: str) -> Dict:
        """Uygulamayı siler"""
        return self._request("DELETE", f"/api/v1/applications/{application_id}")
    
    def get_application_logs(self, application_id: str, limit: int = 100) -> str:
        """Uygulama loglarını getirir"""
        result = self._request("GET", f"/api/v1/applications/{application_id}/logs?limit={limit}")
        return result.get("logs", "") if isinstance(result, dict) else str(result)
    
    # ==================== YEDEKLEME ====================
    
    def get_backups(self, application_id: str) -> List[Dict]:
        """Uygulama yedeklerini getirir"""
        return self._request("GET", f"/api/v1/applications/{application_id}/backups")
    
    def create_backup(self, application_id: str) -> Dict:
        """Yedek oluşturur"""
        return self._request("POST", f"/api/v1/applications/{application_id}/backups")
    
    def restore_backup(self, application_id: str, backup_id: str) -> Dict:
        """Yedekten geri yükler"""
        return self._request("POST", f"/api/v1/applications/{application_id}/backups/{backup_id}/restore")
    
    def delete_backup(self, application_id: str, backup_id: str) -> Dict:
        """Yedek siler"""
        return self._request("DELETE", f"/api/v1/applications/{application_id}/backups/{backup_id}")
    
    # ==================== KAYNAKLAR ====================
    
    def get_resources(self) -> Dict:
        """Tüm kaynakları getirir (uygulama, veritabanı, vs)"""
        return self._request("GET", "/api/v1/resources")
    
    def get_resource_status(self, resource_id: str) -> Dict:
        """Kaynak durumunu getirir"""
        return self._request("GET", f"/api/v1/resources/{resource_id}/status")
    
    # ==================== SUNUCU ====================
    
    def get_server_status(self) -> Dict:
        """Sunucu durumunu getirir"""
        return self._request("GET", "/api/v1/status")
    
    def get_server_stats(self) -> Dict:
        """Sunucu istatistiklerini getirir (CPU, RAM, Disk)"""
        return self._request("GET", "/api/v1/stats")
    
    def get_server_logs(self, limit: int = 100) -> str:
        """Sunucu loglarını getirir"""
        result = self._request("GET", f"/api/v1/logs?limit={limit}")
        return result.get("logs", "") if isinstance(result, dict) else str(result)
    
    # ==================== PROJELER ====================
    
    def get_projects(self) -> List[Dict]:
        """Projeleri getirir"""
        result = self._request("GET", "/api/v1/projects")
        return result if isinstance(result, list) else []
    
    def get_project(self, project_id: str) -> Dict:
        """Projeyi getirir"""
        return self._request("GET", f"/api/v1/projects/{project_id}")
    
    # ==================== ORTAMLAR ====================
    
    def get_environments(self, project_id: str) -> List[Dict]:
        """Proje ortamlarını getirir"""
        return self._request("GET", f"/api/v1/projects/{project_id}/environments")
    
    # ==================== HELPER METOTLAR ====================
    
    def get_all_status(self) -> Dict:
        """Tüm sistem durumunu özetler"""
        return {
            "server": self.get_server_status(),
            "resources": self.get_resources(),
            "stats": self.get_server_stats(),
            "timestamp": datetime.now().isoformat(),
        }
    
    def format_status(self, application: Dict) -> str:
        """Uygulama durumunu formatlı şekilde döndürür"""
        name = application.get("name", "Bilinmiyor")
        status = application.get("status", "unknown")
        url = application.get("url", "")
        
        emoji = {
            "running": "🟢",
            "stopped": "🔴",
            "deploying": "🔵",
            "error": "❌",
        }.get(status.lower(), "⚪")
        
        return f"{emoji} {name}\n   Durum: {status}\n   URL: {url}"
    
    def test_connection(self) -> bool:
        """API bağlantısını test eder"""
        result = self.get_server_status()
        return "error" not in result and result != {"error": "Timeout"}


# Global API instance
api = CoolifyAPI()


def get_api(server_name: str = None) -> CoolifyAPI:
    """API instance'ı döndürür"""
    return api
