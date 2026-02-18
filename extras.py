"""
SSL Monitor & Cloud Backup
SSL sertifika takibi ve bulut yedekleme
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import ssl
import socket

logger = logging.getLogger(__name__)


class SSLMonitor:
    """
    SSL Sertifika İzleyicisi.
    Sertifika sürelerini takip eder ve uyarı verir.
    """
    
    def __init__(self, notification_callback=None):
        self.notification_callback = notification_callback
        self.domains: Dict[str, Dict] = {}
        self.warning_days = 30  # 30 gün önce uyar
        self.critical_days = 7  # 7 gün önce kritik
    
    def add_domain(self, domain: str, port: int = 443):
        """Domain ekle"""
        self.domains[domain] = {"port": port, "last_check": None}
    
    async def check_all(self) -> Dict[str, Dict]:
        """Tüm domainleri kontrol et"""
        results = {}
        
        for domain, info in self.domains.items():
            try:
                result = await self.check_domain(domain, info["port"])
                results[domain] = result
                info["last_check"] = datetime.now()
            except Exception as e:
                results[domain] = {"error": str(e)}
        
        return results
    
    async def check_domain(self, domain: str, port: int = 443) -> Dict:
        """Tek domain kontrolü"""
        try:
            # SSL bağlantısı kur
            context = ssl.create_default_context()
            
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
            
            # Sertifika bilgileri
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y')
            days_left = (not_after - datetime.now()).days
            
            return {
                "valid": True,
                "days_left": days_left,
                "not_after": not_after.isoformat(),
                "issuer": cert.get("issuer", []),
                "subject": cert.get("subject", []),
            }
            
        except ssl.SSLCertVerificationError as e:
            return {"valid": False, "error": "Sertifika hatası", "details": str(e)}
        except socket.gaierror as e:
            return {"valid": False, "error": "Domain bulunamadı"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def format_status(self, results: Dict) -> str:
        """Sonuçları formatla"""
        msg = "🔐 *SSL Durumu*\n\n"
        
        for domain, result in results.items():
            if "error" in result:
                msg += f"❌ {domain}: {result.get('error')}\n\n"
            else:
                days = result.get("days_left", 0)
                if days <= 0:
                    emoji = "🔴"
                    status = "Süresi dolmuş!"
                elif days <= self.critical_days:
                    emoji = "🔴"
                    status = f"Kritik! {days} gün kaldı"
                elif days <= self.warning_days:
                    emoji = "🟡"
                    status = f"Uyarı! {days} gün kaldı"
                else:
                    emoji = "🟢"
                    status = f"✓ {days} gün kaldı"
                
                msg += f"{emoji} {domain}\n   {status}\n\n"
        
        return msg


class CloudBackup:
    """
    Bulut Yedekleme.
    Yedekleri S3, Google Drive'a yükler.
    """
    
    def __init__(self):
        self.s3_config: Dict = {}
        self.gdrive_config: Dict = {}
    
    def configure_s3(self, access_key: str, secret_key: str, bucket: str, region: str = "us-east-1"):
        """S3 yapılandır"""
        self.s3_config = {
            "access_key": access_key,
            "secret_key": secret_key,
            "bucket": bucket,
            "region": region,
        }
    
    def configure_gdrive(self, credentials_path: str):
        """Google Drive yapılandır"""
        self.gdrive_config = {"credentials": credentials_path}
    
    async def upload_to_s3(self, local_path: str, s3_key: str) -> bool:
        """S3'e yükle"""
        try:
            import boto3
            
            s3 = boto3.client(
                's3',
                aws_access_key_id=self.s3_config["access_key"],
                aws_secret_access_key=self.s3_config["secret_key"],
                region_name=self.s3_config["region"]
            )
            
            s3.upload_file(
                local_path,
                self.s3_config["bucket"],
                s3_key,
                ExtraArgs={'StorageClass': 'GLACIER'}  #Ucuz depolama
            )
            
            logger.info(f"S3 yükleme başarılı: {s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"S3 yükleme hatası: {e}")
            return False
    
    async def upload_to_gdrive(self, local_path: str, folder_id: str = None) -> bool:
        """Google Drive'a yükle"""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            
            creds = Credentials.from_loaded_credentials_info(self.gdrive_config.get("credentials"))
            service = build('drive', 'v3', credentials=creds)
            
            file_metadata = {
                'name': local_path.split('/')[-1],
                'parents': [folder_id] if folder_id else []
            }
            
            media = MediaFileUpload(local_path)
            
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f"Google Drive yükleme başarılı: {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Google Drive yükleme hatası: {e}")
            return False
    
    async def backup_to_cloud(self, source_path: str, backup_name: str = None) -> Dict:
        """Buluta yedekle"""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        results = {"s3": None, "gdrive": None}
        
        # S3
        if self.s3_config:
            success = await self.upload_to_s3(source_path, f"backups/{backup_name}")
            results["s3"] = "success" if success else "failed"
        
        # Google Drive
        if self.gdrive_config:
            success = await self.upload_to_gdrive(source_path)
            results["gdrive"] = "success" if success else "failed"
        
        return results


class ContainerTerminal:
    """
    Container Terminal.
    Bash komutu çalıştırma.
    """
    
    def __init__(self):
        self.docker_available = self._check_docker()
    
    def _check_docker(self) -> bool:
        """Docker var mı kontrol et"""
        try:
            import subprocess
            result = subprocess.run(["docker", "ps"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    async def run_command(self, command: str, container: str = None) -> Dict:
        """Komut çalıştır"""
        try:
            import subprocess
            
            if container:
                cmd = ["docker", "exec", container, "sh", "-c", command]
            else:
                cmd = command.split()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Komut zaman aşımı"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_containers(self) -> List[Dict]:
        """Containerları listele"""
        try:
            import subprocess
            import json
            
            result = subprocess.run(
                ["docker", "ps", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    containers.append(json.loads(line))
            
            return containers
            
        except Exception as e:
            logger.error(f"Container listesi hatası: {e}")
            return []
    
    def format_containers(self) -> str:
        """Containerları formatla"""
        containers = self.list_containers()
        
        if not containers:
            return "📦 Container bulunamadı"
        
        msg = "📦 *Container Listesi*\n\n"
        
        for c in containers:
            status = c.get("State", "unknown")
            emoji = "🟢" if status == "running" else "🔴"
            
            msg += f"{emoji} {c.get('Names', 'unknown')}\n"
            msg += f"   Image: {c.get('Image', '-')[:30]}\n"
            msg += f"   Status: {c.get('Status', '-')}\n\n"
        
        return msg


# Global instances
ssl_monitor = SSLMonitor()
cloud_backup = CloudBackup()
container_terminal = ContainerTerminal()


def get_ssl_monitor() -> SSLMonitor:
    return ssl_monitor


def get_cloud_backup() -> CloudBackup:
    return cloud_backup


def get_container_terminal() -> ContainerTerminal:
    return container_terminal
