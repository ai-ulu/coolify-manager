"""
AI/NLP Assistant - Yapay Zeka Asistanı
Normal dilde komut işleme ve akıllı yanıtlar
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AIAssistant:
    """
    Yapay Zeka Asistanı.
    Normal dilde komutları anlar ve işler.
    """
    
    def __init__(self, openai_api_key: str = None, ollama_url: str = None):
        self.openai_api_key = openai_api_key
        self.ollama_url = ollama_url or "http://ollama:11434"
        self.use_ollama = ollama_url is not None
        
        # Komut kalıpları
        self.command_patterns = {
            # Durum sorguları
            r"durum|ne var|nasıl|gidiyor|sistem": "status",
            r"cpu|işlemci": "cpu",
            r"ram|hafıza|bellek": "ram",
            r"disk|alan|depo": "disk",
            r"ağ|network|internet": "network",
            
            # Uygulama yönetimi
            r"uygulama|uygulamalar|app|apps": "list",
            r"başlat|çalıştır|start": "start",
            r"durdur|stop": "stop",
            r"yeniden|restart": "restart",
            r"deploy|yükle": "deploy",
            r"log|logs|çıktı": "logs",
            
            # Yedekleme
            r"yedek|backup": "backup",
            r"geri|yükle|restore": "restore",
            
            # Yardım
            r"yardım|help|ne yaparsın": "help",
        }
        
        # System prompt
        self.system_prompt = """Sen Coolify Sunucu Yöneticisisin. 
Kullanıcıya Türkçe yanıt ver.
Kısaca ve net yanıtlar ver.
Emojiler kullan.

Komutlar:
- /status: Sunucu durumu
- /cpu, /ram, /disk: Kaynak kullanımı
- /list: Uygulamalar
- /deploy <isim>: Deploy et
- /start, /stop, /restart <isim>: Uygulama kontrol
- /backup: Yedekle
- /help: Yardım

Önce kullanıcının ne istediğini anla, sonra uygun komutu çalıştır."""
    
    async def process_message(self, message: str) -> Dict:
        """Mesajı işler ve yanıt döndürür"""
        message = message.lower().strip()
        
        # Komut kalıbı eşleştirme
        for pattern, command in self.command_patterns.items():
            if any(word in message for word in pattern.replace("|", " ").split()):
                return {
                    "type": "command",
                    "command": command,
                    "original": message,
                }
        
        # AI'ya yönlendir (LLM varsa)
        if self.openai_api_key or self.use_ollama:
            return {
                "type": "ai",
                "prompt": message,
            }
        
        # Default yardım
        return {
            "type": "help",
            "message": "Anlayamadım. /help yazarak komutları görebilirsin.",
        }
    
    async def get_ai_response(self, prompt: str, context: str = "") -> str:
        """AI'dan yanıt alır"""
        
        if self.use_ollama:
            return await self._ollama_chat(prompt, context)
        
        if self.openai_api_key:
            return await self._openai_chat(prompt, context)
        
        return "AI yapılandırılmamış. /help yazabilirsin."
    
    async def _ollama_chat(self, prompt: str, context: str) -> str:
        """Ollama ile sohbet"""
        try:
            import requests
            
            full_prompt = f"{self.system_prompt}\n\nBağlam: {context}\n\nKullanıcı: {prompt}"
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": full_prompt,
                    "stream": False,
                },
                timeout=30,
            )
            
            if response.status_code == 200:
                return response.json().get("response", "Yanıt alınamadı")
            else:
                return f"AI hatası: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Ollama hatası: {e}")
            return f"AI bağlantı hatası: {str(e)[:50]}"
    
    async def _openai_chat(self, prompt: str, context: str) -> str:
        """OpenAI ile sohbet"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.openai_api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Bağlam: {context}\n\nKullanıcı: {prompt}"},
                ],
                max_tokens=500,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI hatası: {e}")
            return f"AI hatası: {str(e)[:50]}"
    
    async def analyze_problem(self, error_log: str) -> Dict:
        """Sorunları analiz eder"""
        
        if self.use_ollama or self.openai_api_key:
            prompt = f"""Aşağıdaki hata logunu analiz et ve Türkçe olarak:
1. Sorunun ne olduğunu
2. Nasıl çözüleceğini
3. Öncelik seviyesini (düşük/orta/yüksek/kritik)

Hata logu:
{error_log[:1000]}"""
            
            analysis = await self.get_ai_response(prompt)
            
            return {
                "analysis": analysis,
                "possible_issues": self._extract_issues(analysis),
                "suggested_actions": self._extract_actions(analysis),
            }
        
        # Fallback: basit analiz
        error_log_lower = error_log.lower()
        
        issues = []
        if "memory" in error_log_lower or "ram" in error_log_lower:
            issues.append({"type": "memory", "severity": "high"})
        if "cpu" in error_log_lower:
            issues.append({"type": "cpu", "severity": "high"})
        if "disk" in error_log_lower or "space" in error_log_lower:
            issues.append({"type": "disk", "severity": "critical"})
        if "connection" in error_log_lower:
            issues.append({"type": "network", "severity": "medium"})
        if "timeout" in error_log_lower:
            issues.append({"type": "timeout", "severity": "low"})
        
        return {
            "analysis": "Otomatik analiz tamamlandı",
            "possible_issues": issues,
            "suggested_actions": self._suggest_actions(issues),
        }
    
    def _extract_issues(self, analysis: str) -> list:
        """Analizden sorunları çıkarır"""
        # Basit keyword eşleştirme
        issues = []
        analysis_lower = analysis.lower()
        
        keywords = {
            "memory": "RAM yetersiz",
            "cpu": "CPU aşırı yüklü",
            "disk": "Disk dolu",
            "network": "Ağ sorunu",
            "timeout": "Zaman aşımı",
            "permission": "İzin hatası",
            "configuration": "Yapılandırma hatası",
        }
        
        for key, issue in keywords.items():
            if key in analysis_lower:
                issues.append(issue)
        
        return issues
    
    def _extract_actions(self, analysis: str) -> list:
        """Önerilen eylemleri çıkarır"""
        actions = []
        
        if "restart" in analysis.lower():
            actions.append("Uygulamayı yeniden başlat")
        if "scale" in analysis.lower():
            actions.append("Ölçeklendirmeyi artır")
        if "backup" in analysis.lower():
            actions.append("Yedekleme yap")
        if "clear" in analysis.lower() or "temizle" in analysis.lower():
            actions.append("Önbellek ve logları temizle")
        
        return actions
    
    def _suggest_actions(self, issues: list) -> list:
        """Sorunlara göre öneriler"""
        actions = []
        
        for issue in issues:
            issue_type = issue.get("type")
            if issue_type == "memory":
                actions.append("RAM'i artır veya uygulamayı yeniden başlat")
            elif issue_type == "cpu":
                actions.append("CPU kaynaklarını artır veya ölçekle")
            elif issue_type == "disk":
                actions.append("Eski dosyaları temizle")
            elif issue_type == "network":
                actions.append("Ağ bağlantısını kontrol et")
        
        if not actions:
            actions.append("Detaylı inceleme gerekli")
        
        return actions


# Global instance
ai_assistant = AIAssistant()


def get_ai_assistant() -> AIAssistant:
    return ai_assistant
