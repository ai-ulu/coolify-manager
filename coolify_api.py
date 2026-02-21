"""
Coolify API client.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

from config import COOLIFY_CONFIG, get_coolify_headers

logger = logging.getLogger(__name__)


class CoolifyAPI:
    def __init__(self, url: str = None, api_key: str = None):
        self.base_url = (url or COOLIFY_CONFIG["url"]).rstrip("/")
        self.api_key = api_key or COOLIFY_CONFIG["api_key"]
        self.timeout = COOLIFY_CONFIG["timeout"]
        self.session = requests.Session()
        self.session.headers.update(get_coolify_headers(self.api_key))

    def _request(self, method: str, endpoint: str, log_404: bool = False, **kwargs) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.Timeout:
            logger.error("Timeout: %s", url)
            return {"error": "Timeout"}
        except requests.exceptions.ConnectionError:
            logger.error("Connection error: %s", url)
            return {"error": "Connection error"}
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else None
            if status_code == 404 and not log_404:
                logger.debug("Endpoint not found (404): %s", url)
            else:
                logger.error("HTTP error (%s): %s", status_code, url)
            return {"error": str(exc), "status_code": status_code}
        except Exception as exc:
            logger.error("Unexpected error: %s", exc)
            return {"error": str(exc)}

    def get_applications(self) -> List[Dict]:
        result = self._request("GET", "/api/v1/applications")
        return result if isinstance(result, list) else []

    def get_application(self, application_id: str) -> Dict:
        return self._request("GET", f"/api/v1/applications/{application_id}")

    def get_application_status(self, application_id: str) -> Dict:
        return self._request("GET", f"/api/v1/applications/{application_id}/status")

    def deploy_application(self, application_id: str, force: bool = False) -> Dict:
        data = {"force": force} if force else {}
        return self._request("POST", f"/api/v1/applications/{application_id}/deploy", json=data)

    def start_application(self, application_id: str) -> Dict:
        return self._request("POST", f"/api/v1/applications/{application_id}/start")

    def stop_application(self, application_id: str) -> Dict:
        return self._request("POST", f"/api/v1/applications/{application_id}/stop")

    def restart_application(self, application_id: str) -> Dict:
        return self._request("POST", f"/api/v1/applications/{application_id}/restart")

    def delete_application(self, application_id: str) -> Dict:
        return self._request("DELETE", f"/api/v1/applications/{application_id}")

    def get_application_logs(self, application_id: str, limit: int = 100) -> str:
        result = self._request("GET", f"/api/v1/applications/{application_id}/logs?limit={limit}")
        return result.get("logs", "") if isinstance(result, dict) else str(result)

    def get_backups(self, application_id: str) -> List[Dict]:
        result = self._request("GET", f"/api/v1/applications/{application_id}/backups")
        return result if isinstance(result, list) else []

    def create_backup(self, application_id: str) -> Dict:
        return self._request("POST", f"/api/v1/applications/{application_id}/backups")

    def restore_backup(self, application_id: str, backup_id: str) -> Dict:
        return self._request("POST", f"/api/v1/applications/{application_id}/backups/{backup_id}/restore")

    def delete_backup(self, application_id: str, backup_id: str) -> Dict:
        return self._request("DELETE", f"/api/v1/applications/{application_id}/backups/{backup_id}")

    def get_resources(self) -> Dict:
        return self._request("GET", "/api/v1/resources")

    def get_resource_status(self, resource_id: str) -> Dict:
        return self._request("GET", f"/api/v1/resources/{resource_id}/status")

    def get_server_status(self) -> Dict:
        candidates = ["/api/v1/status", "/api/v1/health"]
        for endpoint in candidates:
            result = self._request("GET", endpoint)
            if isinstance(result, dict) and "error" not in result:
                return result

        # Fallback: if applications can be listed, API is effectively reachable.
        apps = self.get_applications()
        if isinstance(apps, list):
            return {"status": "reachable", "applications": len(apps)}
        return {"error": "server status unavailable"}

    def get_server_stats(self) -> Dict:
        result = self._request("GET", "/api/v1/stats")
        if isinstance(result, dict) and "status_code" in result and result.get("status_code") == 404:
            return {}
        return result if isinstance(result, dict) else {}

    def get_server_logs(self, limit: int = 100) -> str:
        result = self._request("GET", f"/api/v1/logs?limit={limit}")
        return result.get("logs", "") if isinstance(result, dict) else str(result)

    def get_projects(self) -> List[Dict]:
        result = self._request("GET", "/api/v1/projects")
        return result if isinstance(result, list) else []

    def get_project(self, project_id: str) -> Dict:
        return self._request("GET", f"/api/v1/projects/{project_id}")

    def get_environments(self, project_id: str) -> List[Dict]:
        result = self._request("GET", f"/api/v1/projects/{project_id}/environments")
        return result if isinstance(result, list) else []

    def get_all_status(self) -> Dict:
        return {
            "server": self.get_server_status(),
            "resources": self.get_resources(),
            "stats": self.get_server_stats(),
            "timestamp": datetime.now().isoformat(),
        }

    def format_status(self, application: Dict) -> str:
        name = application.get("name", "Unknown")
        status = application.get("status", "unknown")
        url = application.get("url", "")
        return f"{name}\nstatus={status}\nurl={url}"

    def test_connection(self) -> bool:
        result = self.get_server_status()
        if isinstance(result, dict) and "error" not in result:
            return True
        apps = self.get_applications()
        return isinstance(apps, list)


api = CoolifyAPI()


def get_api(server_name: str = None) -> CoolifyAPI:
    return api
