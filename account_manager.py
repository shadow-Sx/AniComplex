import os
import time
import threading
import requests
import logging
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== DATABASE CONNECTION ====================
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://ShadowUzDev:ShadowUzDevAnimeshnik@cluster0.vudnhub.mongodb.net/?appName=AniComplex")
client = MongoClient(MONGO_URI)
db = client["AniComplex"]
active_account_collection = db["active_accounts"]
account_status_collection = db["account_status"]

# ==================== ACCOUNT CONFIGURATION ====================
ACCOUNTS = [
    {
        "id": "account_1",
        "url": "https://anicomplex.onrender.com",
        "render_api_key": os.getenv("RENDER_API_KEY_1", ""),
        "service_id": os.getenv("RENDER_SERVICE_ID_1", ""),
        "webhook_url": f"https://anicomplex.onrender.com/webhook"
    },
    {
        "id": "account_2", 
        "url": "https://anicomplex-k7kt.onrender.com",
        "render_api_key": os.getenv("RENDER_API_KEY_2", ""),
        "service_id": os.getenv("RENDER_SERVICE_ID_2", ""),
        "webhook_url": f"https://anicomplex-k7kt.onrender.com/webhook"
    }
]

class AccountManager:
    def __init__(self):
        self.current_account = None
        self.is_switching = False
        self.health_check_interval = 60  # 1 daqiqa
        self.usage_threshold = 0.9  # 90% limit ishlatilganda switch
        self._load_current_account()
        
    def _load_current_account(self):
        """MongoDB dan faol accountni yuklash"""
        try:
            active = active_account_collection.find_one({"status": "active"})
            if active:
                for account in ACCOUNTS:
                    if account["id"] == active["account_id"]:
                        self.current_account = account
                        logger.info(f"✅ Active account loaded: {account['id']} - {account['url']}")
                        break
            if not self.current_account and ACCOUNTS:
                self.current_account = ACCOUNTS[0]
                self._save_active_account(ACCOUNTS[0]["id"])
                logger.info(f"🔄 Default account set: {ACCOUNTS[0]['id']}")
        except Exception as e:
            logger.error(f"❌ Error loading active account: {e}")
            if ACCOUNTS:
                self.current_account = ACCOUNTS[0]
    
    def _save_active_account(self, account_id):
        """MongoDB ga faol accountni saqlash"""
        try:
            active_account_collection.delete_many({})
            active_account_collection.insert_one({
                "account_id": account_id,
                "status": "active",
                "last_updated": datetime.utcnow()
            })
            logger.info(f"💾 Active account saved: {account_id}")
        except Exception as e:
            logger.error(f"❌ Error saving active account: {e}")
    
    def get_webhook_url(self):
        """Joriy webhook URL ni qaytarish"""
        if self.current_account:
            return self.current_account["webhook_url"]
        return None
    
    def check_render_usage(self):
        """Render usage statistikasini tekshirish"""
        if not self.current_account:
            return None
            
        api_key = self.current_account.get("render_api_key")
        service_id = self.current_account.get("service_id")
        
        if not api_key or not service_id:
            logger.warning(f"⚠️ Missing API key or service ID for {self.current_account['id']}")
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }
            
            # Render API orqali bandwidth usage ni olish
            response = requests.get(
                f"https://api.render.com/v1/services/{service_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Bandwidth usage ni tekshirish (Render specific)
                usage_percent = self._calculate_usage(data)
                
                # Statusni saqlash
                account_status_collection.update_one(
                    {"account_id": self.current_account["id"]},
                    {"$set": {
                        "usage_percent": usage_percent,
                        "last_checked": datetime.utcnow(),
                        "status": "warning" if usage_percent > self.usage_threshold else "normal"
                    }},
                    upsert=True
                )
                
                logger.info(f"📊 {self.current_account['id']} usage: {usage_percent:.1%}")
                return usage_percent
                
        except Exception as e:
            logger.error(f"❌ Error checking Render usage: {e}")
            return None
    
    def _calculate_usage(self, service_data):
        """Render servis ma'lumotlaridan usage foizini hisoblash"""
        # Render bepul tier limiti: 100 GB bandwidth, 750 soat compute
        try:
            # Bu yerda Render API response dan kerakli ma'lumotlarni olish
            # Hozircha dummy qiymat qaytaramiz
            suspended = service_data.get("suspended", "")
            if suspended == "suspended":
                return 1.0  # 100% - limit tugagan
            
            # Real usage ni hisoblash uchun Render API docs ga qarang
            return 0.5  # 50% dummy value
            
        except Exception as e:
            logger.error(f"❌ Usage calculation error: {e}")
            return 0.0
    
    def switch_to_next_account(self):
        """Keyingi accountga o'tish"""
        if self.is_switching:
            logger.warning("⚠️ Account switching already in progress")
            return False
            
        self.is_switching = True
        
        try:
            current_index = -1
            for i, account in enumerate(ACCOUNTS):
                if account["id"] == self.current_account["id"]:
                    current_index = i
                    break
            
            next_index = (current_index + 1) % len(ACCOUNTS)
            next_account = ACCOUNTS[next_index]
            
            # Eski accountni to'xtatish
            self._stop_render_service(self.current_account)
            
            # Yangi accountni ishga tushirish
            self._start_render_service(next_account)
            
            # Webhook ni yangilash
            self._update_telegram_webhook(next_account["webhook_url"])
            
            # Current accountni yangilash
            self.current_account = next_account
            self._save_active_account(next_account["id"])
            
            # Statusni yangilash
            account_status_collection.update_one(
                {"account_id": next_account["id"]},
                {"$set": {
                    "status": "active",
                    "switched_at": datetime.utcnow(),
                    "switch_count": account_status_collection.find_one(
                        {"account_id": next_account["id"]}
                    ).get("switch_count", 0) + 1 if account_status_collection.find_one(
                        {"account_id": next_account["id"]}
                    ) else 1
                }},
                upsert=True
            )
            
            logger.info(f"✅ Switched to {next_account['id']} - {next_account['url']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error switching accounts: {e}")
            return False
        finally:
            self.is_switching = False
    
    def _stop_render_service(self, account):
        """Render servisini to'xtatish"""
        try:
            api_key = account.get("render_api_key")
            service_id = account.get("service_id")
            
            if api_key and service_id:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                # Render API - suspend service
                response = requests.post(
                    f"https://api.render.com/v1/services/{service_id}/suspend",
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"⏸️ Stopped service: {account['id']}")
                else:
                    logger.warning(f"⚠️ Failed to stop service {account['id']}: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error stopping Render service: {e}")
    
    def _start_render_service(self, account):
        """Render servisini ishga tushirish"""
        try:
            api_key = account.get("render_api_key")
            service_id = account.get("service_id")
            
            if api_key and service_id:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                # Render API - resume service
                response = requests.post(
                    f"https://api.render.com/v1/services/{service_id}/resume",
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"▶️ Started service: {account['id']}")
                else:
                    logger.warning(f"⚠️ Failed to start service {account['id']}: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error starting Render service: {e}")
    
    def _update_telegram_webhook(self, webhook_url):
        """Telegram bot webhook ni yangilash"""
        try:
            bot_token = os.getenv("BOT_TOKEN")
            if bot_token:
                response = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/setWebhook",
                    json={"url": webhook_url},
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"🔄 Webhook updated to: {webhook_url}")
                else:
                    logger.warning(f"⚠️ Failed to update webhook: {response.text}")
        except Exception as e:
            logger.error(f"❌ Error updating webhook: {e}")
    
    def monitor_loop(self):
        """Asosiy monitoring loop"""
        logger.info("🔍 Starting account monitoring...")
        
        while True:
            try:
                # Health check
                if self.current_account:
                    try:
                        response = requests.get(
                            f"{self.current_account['url']}/health",
                            timeout=5
                        )
                        if response.status_code != 200:
                            logger.warning(f"⚠️ Health check failed for {self.current_account['id']}")
                            self.switch_to_next_account()
                    except requests.exceptions.RequestException:
                        logger.warning(f"⚠️ Cannot reach {self.current_account['url']}")
                        self.switch_to_next_account()
                
                # Usage check
                usage = self.check_render_usage()
                if usage and usage > self.usage_threshold:
                    logger.warning(f"⚠️ Usage threshold exceeded ({usage:.1%})")
                    self.switch_to_next_account()
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"❌ Monitor loop error: {e}")
                time.sleep(30)

# ==================== GLOBAL INSTANCE ====================
account_manager = AccountManager()
