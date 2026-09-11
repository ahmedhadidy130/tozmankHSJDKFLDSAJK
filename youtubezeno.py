import os
import json
import gc
import sys
import string
import shutil
import asyncio
import threading
import yt_dlp
import tempfile
import time
import base64
import subprocess
import psutil
import traceback
from asyncio import run as arun
from highrise import BaseBot, __main__
from highrise.models import User, SessionMetadata, Position
from highrise import *
from highrise.webapi import *
from highrise.models_webapi import *
from highrise.models import *
import socket
import aiohttp
import aiofiles
import requests
from mutagen.mp3 import MP3
from collections import deque
import random
from rapidfuzz import fuzz
from datetime import datetime, timedelta
from HRDB import ownerz, playlist, user_ticket, vip_users, msg, restrict, promo, bot_location, ids

# ==================== Memory Settings ====================
MAX_MEMORY_MB = 150
CLEANUP_INTERVAL = 60
MAX_TEMP_FILES = 20

class MemoryManager:
    """Memory Manager to prevent leaks"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.temp_files = []
        self.last_cleanup = time.time()
        
    def register_temp_file(self, file_path):
        """Register temporary file for monitoring"""
        if file_path and os.path.exists(file_path):
            self.temp_files.append({
                'path': file_path,
                'created': time.time(),
                'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            })
            
    def cleanup_old_files(self):
        """Clean old files"""
        now = time.time()
        # Delete files older than 10 minutes
        self.temp_files = [
            f for f in self.temp_files 
            if os.path.exists(f['path']) and (now - f['created']) < 600
        ]
        
    def force_cleanup(self):
        """Force memory cleanup"""
        print(f"[MemoryManager] Force memory cleanup...")
        
        # 1. Delete old temporary files
        deleted_count = 0
        for temp_file in list(self.temp_files):
            try:
                if os.path.exists(temp_file['path']):
                    os.remove(temp_file['path'])
                    deleted_count += 1
            except:
                pass
        self.temp_files.clear()
        
        # 2. Clean reqfiles directory
        if hasattr(self.bot, 'req_files_dir'):
            self.cleanup_directory(self.bot.req_files_dir)
        
        # 3. Garbage collection
        gc.collect()
        
        # 4. Reset large data pools
        if hasattr(self.bot, 'req_files'):
            self.bot.req_files = deque(list(self.bot.req_files)[-20:])  # Keep only 20 items
            
        print(f"[MemoryManager] Deleted {deleted_count} temporary files")
        
    def cleanup_directory(self, directory, keep_recent=20):
        """Clean directory keeping recent files"""
        if not os.path.exists(directory):
            return
            
        try:
            # Get all files with creation time
            files = []
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    files.append({
                        'path': file_path,
                        'mtime': os.path.getmtime(file_path)
                    })
            
            # Sort from oldest to newest
            files.sort(key=lambda x: x['mtime'])
            
            # Delete old files (keep only keep_recent)
            for file_info in files[:-keep_recent]:
                try:
                    os.remove(file_info['path'])
                except:
                    pass
                    
        except Exception as e:
            print(f"[MemoryManager] Error cleaning {directory}: {e}")
    
    def check_memory_usage(self):
        """Check memory usage"""
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > MAX_MEMORY_MB:
            print(f"[MemoryManager] Warning: Memory usage {memory_mb:.1f}MB")
            self.force_cleanup()
            
        # Periodic cleanup
        if time.time() - self.last_cleanup > CLEANUP_INTERVAL:
            self.cleanup_old_files()
            self.last_cleanup = time.time()

# ==================== Memory Manager Initialization ====================
memory_manager = None

try:
    with open('config.json', 'r') as f:
        config_data = json.load(f)
    invite = config_data['room_id']
except (FileNotFoundError, KeyError, json.JSONDecodeError):
    invite = "68e1a96b441823640b494e89"  # Default value

# Read settings from file
try:
    with open('zenofm.json', 'r', encoding='utf-8') as f:
        zenofm_config = json.load(f)
except FileNotFoundError:
    print("❌ zenofm.json file not found")
    zenofm_config = {
        "SERVER_HOST": "localhost",
        "SERVER_PORT": 8000,
        "MOUNT_POINT": "/stream",
        "STREAM_USERNAME": "source",
        "STREAM_PASSWORD": "password"
    }

# تحميل ملف ال JSON
with open('outfits.json', 'r') as f:
    outfits = json.load(f)   

# Now use zenofm_config
SERVER_HOST = zenofm_config["SERVER_HOST"]
SERVER_PORT = zenofm_config["SERVER_PORT"]
MOUNT_POINT = zenofm_config["MOUNT_POINT"]
STREAM_USERNAME = zenofm_config["STREAM_USERNAME"]
STREAM_PASSWORD = zenofm_config["STREAM_PASSWORD"]

vip_positions = {
    "v25255ip": Position(5.5, 14.5, 4),
    "vvi536535p": Position(13.5, 19, .5),
    "vss54553154": Position(14, 4.5, 5),
}

AUDIO_FILES = [
    "Nothing.mp3"
]

# User-Agents list for rotation
YAGENTS = [
    # Windows - Chrome / Edge / Brave
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Brave Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Vivaldi/6.7 Chrome/127.0.0.0 Safari/537.36",

    # Windows - Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",

    # macOS - Chrome / Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",

    # Linux - Chrome / Firefox
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Vivaldi/6.7 Chrome/127.0.0.0 Safari/537.36",

    # Android - Chrome
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Redmi Note 12 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; V2149) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; OnePlus 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-A715F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",

    # Android - Firefox
    "Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0",
    "Mozilla/5.0 (Android 13; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0",
    "Mozilla/5.0 (Android 12; Mobile; rv:126.0) Gecko/126.0 Firefox/126.0",

    # iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",

    # iPad
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",

    # Opera Browsers
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 OPR/113.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/112.0.0.0",

    # Misc Browsers
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",

    # Additional Windows / Chromium browsers
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Brave Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Vivaldi/6.8 Chrome/128.0.0.0 Safari/537.36",

    # More Firefox on Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",

    # macOS additional
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",

    # Linux variations
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) OPR/114.0.0.0 Chrome/128.0.0.0 Safari/537.36 OPR/114.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",

    # Samsung / Mobile Chromium Browsers
    "Mozilla/5.0 (Linux; Android 14; SM-S960U) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/20.0 Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-N986B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",

    # Google Pixel / Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",

    # OnePlus / Oppo / Realme / Xiaomi
    "Mozilla/5.0 (Linux; Android 14; ONEPLUS A0010) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; RMX3621) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Redmi Note 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",

    # Huawei / Honor
    "Mozilla/5.0 (Linux; Android 13; HUAWEI ELS-NX9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",

    # iPhone / iOS additional
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",

    # iPad variations
    "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",

    # Android Firefox variations
    "Mozilla/5.0 (Android 14; Mobile; rv:129.0) Gecko/129.0 Firefox/129.0",
    "Mozilla/5.0 (Android 13; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0",

    # Older / alternate mobile versions
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; LG-M255) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",

    # Misc / Crawlers & niche clients
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",

    # Smart TV / Other agents
    "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/10.1 TV Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/128.0.0.0 Safari/537.36"
]

MODS_FILE = "mods.json"

def load_mods():
    if not os.path.exists(MODS_FILE):
        with open(MODS_FILE, "w") as f:
            json.dump([], f)
        return []

    try:
        with open(MODS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_mods(mods_list):
    with open(MODS_FILE, "w") as f:
        json.dump(mods_list, f, indent=4)

# Function to load prices from file
def load_prices():
    try:
        with open("tk_price.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Default values if file doesn't exist
        default_prices = {
            "ticket_price": 10,
            "ticket_multiplier": 3,
            "vip_price": 1000,
            "min_donation": 10,
            "gold_1_message": "Donating one gold is not enough. The minimum is 10."
        }
        # Create file with default values
        with open("tk_price.json", "w", encoding="utf-8") as f:
            json.dump(default_prices, f, indent=4, ensure_ascii=False)
        return default_prices

# Function to save prices to file
def save_prices(prices):
    with open("tk_price.json", "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=4, ensure_ascii=False)

# Load prices on startup
prices = load_prices()

SETTINGS_FILE = "settings.json"

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"source": "youtube"}, f)
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(source):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"source": source}, f)

# ============================
# Blocking System
# ============================

BLOCK_FILE = "blocked_users.json"

# Load blocked list
def load_blocked():
    if not os.path.exists(BLOCK_FILE):
        with open(BLOCK_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(BLOCK_FILE, "r") as f:
            return json.load(f)
    except:
        return []

# Save blocked list
def save_blocked(blocked_list):
    with open(BLOCK_FILE, "w") as f:
        json.dump(blocked_list, f)

blocked_list = load_blocked()

# Global request lock (for all players)
REQUEST_LOCK = asyncio.Lock()
NEXT_ALLOWED_TIME = 0

class Storage:
    def __init__(self):
        self.data = {"saved_outfits": {}}

    def save_outfit(self, name, items):
        self.data["saved_outfits"][name] = items

    def get_outfit(self, name):
        return self.data["saved_outfits"].get(name)


class BotDefinition:
    def __init__(self, bot: BaseBot, room_id: str, api_token: str):
        self.bot = bot
        self.room_id = room_id
        self.api_token = api_token

class SEA(BaseBot):
    def __init__(self):
        super().__init__()
        self.message_task = None
        self.is_connected = False
        self.msg = msg
        self.storage = Storage()
        self.saved_outfits = {}  # بديل عن storage
        self.mods = load_mods()
        self.notification_task = None
        self.promo_task = None
        self.username = None
        self.owner_id = None
        self.owner = None
        self.bot_id = None
        self.skip = False
        self.bitrate = '128k'
        self.choices = {}
        self.active_sos_requests = {}
        self.req_files = deque(maxlen=30)  # Max 30 songs
        self.now = deque(maxlen=1)  # Only one song
        self.message = deque(maxlen=1)
        self.wait = []
        self.fav_dir = "/home/container/fav"
        self.sync_fav_with_playlist()
        self.start_time = time.time()
        self.skip_requested = False
        self.restart_requested = False
        self.user_positions = {}
        self.state_file = "bot_state.json"
        self.req_files_dir = "/home/container/reqfiles"
        self.fav_dir = "/home/container/fav"
        self._session = None
        self.dance_loop_running = False
        self.data_lock = threading.Lock()  # 🔒 Add this line
        self.last_tip_time = {}  # 🔒 To track last tip time per user
        self.memory_manager = MemoryManager(self)  # Add memory manager
        self.cleanup_task = None  # Periodic cleanup task
         # Dashboard
        self.current_song = None
        self.current_artist = None
        self.current_duration = None

        self.start_time = time.time()

        self.dashboard = {
            "bot_name": "Loading...",
            "queue": [],
            "users": 0,
            "vip": 0,
            "cpu": 0,
            "ram": 0,
            "song": None,
            "artist": None,
            "duration": None,
            "uptime": 0
        }
        
        os.makedirs(self.fav_dir, exist_ok=True)
        os.makedirs(self.req_files_dir, exist_ok=True)
        self.load_state()
        
    async def on_error(self, error: str) -> None:
        print(f"Error occurred in Highrise SDK: {error}")
        # Reconnection is handled by the run loop
        
    def save_state(self):
       
        try:
            data = {
                "req_files": [
                    {
                        "title": item["title"],
                        "url": item["url"],
                        "duration": item["duration"],
                        "user": item["user"]
                    }
                    for item in self.req_files
                ]
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving state: {type(e).__name__} - {e}")

    def load_state(self):
      
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.req_files = deque(data.get("req_files", []), maxlen=30)
                    os.remove(self.state_file)
            except Exception as e:
                print(f"Error loading state: {type(e).__name__} - {e}")

    def move_files_and_update_urls(self):
        for item in self.req_files:
            if item["url"].startswith("/tmp/"):
                temp_file_path = item["url"]
                new_file_path = os.path.join(self.req_files_dir, os.path.basename(temp_file_path))
                try:
                    shutil.move(temp_file_path, new_file_path)
                    item["url"] = new_file_path
                except Exception as e:
                    print(f"Error moving file {temp_file_path} to {new_file_path}: {type(e).__name__} - {e}")

    async def cleanup_memory(self):
        """Periodic memory cleanup"""
        while True:
            try:
                self.memory_manager.check_memory_usage()
                await asyncio.sleep(30)  # Every 30 seconds
            except Exception as e:
                print(f"Memory cleanup error: {e}")
                await asyncio.sleep(60)

    async def restart_bot(self):
        print("🔄 Restarting bot...")

        # ⛔ وقف أي loops
        self.is_connected = False
        self.dance_loop_running = False

        # احفظ الحالة قبل الإغلاق
        self.move_files_and_update_urls()
        self.save_state()

        # 🔴 الغِ كل التاسكات بدون انتظار طويل
        tasks_to_cancel = [
            self.notification_task,
            self.message_task,
            self.promo_task,
            getattr(self, "save_task", None),
            getattr(self, "dance_loop_task", None),
            self.cleanup_task
        ]

        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()

        # 🧹 تنظيف ذاكرة
        try:
            self.memory_manager.force_cleanup()
        except Exception as e:
            print("Memory cleanup error:", e)

        # 🔌 اقفل اتصال Highrise لو موجود
        try:
            if hasattr(self, "highrise") and self.highrise:
                await self.highrise.close()
        except Exception as e:
            print("Highrise close error:", e)

        await asyncio.sleep(2)

        print("♻️ Executing restart...")
        script_name = 'run.py' if os.path.exists('run.py') else os.path.basename(__file__)
        os.execv(sys.executable, [sys.executable, script_name] + sys.argv[1:])
        
        
    async def _dance_loop(self):
       
        while self.dance_loop_running:
            try:
                await self.highrise.send_emote("emote-hyped")
                await asyncio.sleep(7.3)
            except Exception as e:
                break
    
    async def on_start(self, session_metadata: SessionMetadata):
        try:
            self.is_connected = True
            self.username = await self.get_username(session_metadata.user_id)
            self.dashboard["bot_name"] = self.username
            self.bot_id = session_metadata.user_id
            self.owner_id = session_metadata.room_info.owner_id
            self.owner = await self.get_username(self.owner_id)
        except Exception as e:
            print("Error getting username and bot ID on start:", e)
            
        if not hasattr(self, "control_task"):
            self.control_task = asyncio.create_task(
                self.dashboard_control()
            )    

        if not (self.owner is None):
            if self.owner not in ownerz:
                ownerz.append(self.owner)

        # Add periodic save task
        if not hasattr(self, 'save_task'):
           self.save_task = asyncio.create_task(self.save_data_periodically())

        # Add memory cleanup task
        if not hasattr(self, 'cleanup_task'):
            self.cleanup_task = asyncio.create_task(self.cleanup_memory())

        if not (self.owner_id is None):
            if self.owner_id not in msg:
                msg.append(self.owner_id)

        if bot_location:
            await self.highrise.teleport(session_metadata.user_id, Position(**bot_location))
            self.dance_loop_running = True
            self.dance_loop_task = asyncio.create_task(self._dance_loop())
        else:
            await self.highrise.teleport(session_metadata.user_id, Position(15.5, 0.25, 2.5, 'FrontRight'))
            self.dance_loop_running = True
            self.dance_loop_task = asyncio.create_task(self._dance_loop())

        if self.notification_task is None or self.notification_task.done():
            self.notification_task = asyncio.create_task(self.notification())

        if self.message_task is None or self.message_task.done():
            self.message_task = asyncio.create_task(self.print_messages())

        if self.promo_task is None or self.promo_task.done():
            self.promo_task = asyncio.create_task(self.promo())

        self.sync_fav_with_playlist()
        with open("playlist.json","r",encoding="utf-8") as f:
            songs = json.load(f)
        print(f"<#FFD580>{self.username} active! 🎵")
        self.dashboard["online"] = True

        if not hasattr(self, "dashboard_task"):
            self.dashboard_task = asyncio.create_task(
                self.dashboard_updater()
            )

        # Initial memory cleanup
        self.memory_manager.cleanup_directory(self.req_files_dir)
        self.memory_manager.cleanup_old_files()
        
        # Start connection watchdog
        self.watchdog_task = asyncio.create_task(self.watchdog())
        self.dashboard_task = asyncio.create_task(self.dashboard_updater())

    async def dashboard_control(self):

        while True:
            try:

                # Skip من الموقع
                if self.skip_requested:
                    self.skip_requested = False

                    print("⏭ Dashboard Skip")

                    self.skip = True


                # Restart من الموقع
                if self.restart_requested:
                    self.restart_requested = False

                    print("🔄 Dashboard Restart")

                    await self.restart_bot()


                await asyncio.sleep(0.5)

            except Exception as e:
                print("Dashboard control error:", e)
                await asyncio.sleep(2)        
        
    async def dashboard_updater(self):
        import psutil
        import time

        while True:
            try:
                self.dashboard["queue"] = len(self.req_files)

                try:
                    with open("user_ticket.json", "r", encoding="utf-8") as f:
                        self.dashboard["users"] = len(json.load(f))
                except:
                    self.dashboard["users"] = 0

                try:
                    with open("vip_users.json", "r", encoding="utf-8") as f:
                        self.dashboard["vip"] = len(json.load(f))
                except:
                    self.dashboard["vip"] = 0

                self.dashboard["cpu"] = psutil.cpu_percent(interval=None)
                self.dashboard["ram"] = psutil.virtual_memory().percent

                self.dashboard["song"] = self.current_song
                self.dashboard["artist"] = self.current_artist
                self.dashboard["duration"] = self.current_duration

                self.dashboard["uptime"] = int(time.time() - self.start_time)

                await asyncio.sleep(1)

            except Exception as e:
                print("Dashboard:", e)
                await asyncio.sleep(5)    
        
    async def watchdog(self):
        """Monitor connection and restart if unresponsive"""
        while self.is_connected:
            try:
                await asyncio.sleep(60)
                if self.is_connected:
                    # Simple check to verify API responsiveness
                    await self.highrise.get_my_outfit()
            except Exception as e:
                print(f"⚠️ Watchdog detected connection issue: {e}. Restarting bot...")
                await self.restart_bot()
                break

    def sync_fav_with_playlist(self):
        import os, json, shutil

        playlist_path, req_dir, fav_dir = "playlist.json", "reqfiles", self.fav_dir
        os.makedirs(fav_dir, exist_ok=True); os.makedirs(req_dir, exist_ok=True)

        if not os.path.exists(playlist_path):
            with open(playlist_path, "w", encoding="utf-8") as f: json.dump([], f, ensure_ascii=False, separators=(',', ':'))

        try:
            with open(playlist_path, "r", encoding="utf-8") as f:
                try: playlist_data = json.load(f)
                except json.JSONDecodeError: playlist_data = []

            playlist_dict = {item["url"]: item for item in playlist_data if "url" in item}
            fav_files = [
                f for f in os.listdir(fav_dir)
                if f.lower().endswith((".mp3",".wav",".m4a",".webm",".opus"))
            ]
            fav_paths = {os.path.join(fav_dir, f) for f in fav_files}
            added = removed = req_deleted = 0

            # Add new files from favorites to playlist
            for path in fav_paths:
                if path not in playlist_dict:
                    title = os.path.splitext(os.path.basename(path))[0]
                    playlist_dict[path] = {"url": path, "title": title, "user": "SYSTEM", "audio_length": "🕒 Unknown"}
                    added += 1

            # Remove deleted files from favorites
            for url in list(playlist_dict.keys()):
                if url not in fav_paths: 
                    del playlist_dict[url]; removed += 1

            # Clean all files in reqfiles
            for file in os.listdir(req_dir):
                file_path = os.path.join(req_dir, file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path): os.remove(file_path)
                    elif os.path.isdir(file_path): shutil.rmtree(file_path)
                    req_deleted += 1
                except Exception: pass

            # ✍️ Save in compact format
            if added > 0 or removed > 0 or req_deleted > 0:
                with open(playlist_path, "w", encoding="utf-8") as f:
                    json.dump(list(playlist_dict.values()), f, ensure_ascii=False, separators=(',', ':'))
                print(f"<#FFD580>[Sync] ✅ Updated: Added {added}, Removed {removed}, Deleted from reqfiles {req_deleted}.")
            else:
                print("<#FFD580>[Sync] ⚙️ No changes, all music synced.")
        except Exception as e:
            print(f"<#FFD580>[Sync] ❌ Error during sync: {type(e).__name__} - {e}")

    async def on_user_join(self, user: User, pos: Position) -> None:
        try:
            await asyncio.sleep(2)

            # Part 1 — Brief welcome
            await self.highrise.send_whisper(
                user.id,
                f"<#FFD580>🎶 Hello @{user.username}! 👋\n"
                "<#FFD580>Welcome to the room! I'm the music bot that plays what you like 🎵"
            )

            await asyncio.sleep(1)

            # Part 2 — Activation / Verification
            await self.highrise.send_whisper(
                user.id,
                "<#FFD580>🎁 If you want to start:\n"
                "<#FFD580>Type /verify in private and get 3 free tickets!"
            )

            await asyncio.sleep(1)

            # Part 3 — Commands + Prices
            await self.highrise.send_whisper(
                user.id,
                "<#FFD580>📜 Quick commands:\n"
                "🎶 /play — Request music\n"
                "🎫 /wallet — Ticket balance\n"
                "💰 /rlist — Buy tickets/VIP\n"
            )

        except Exception as e:
            print(f"[on_user_join] error: {e}")

    async def sos(self, user_id, reason: str):
        if user_id in self.active_sos_requests:
            conversation_id = f"1_on_1:{user_id}:{self.bot_id}"
            await self.highrise.send_message(conversation_id, "<#FFD580>🔄 You already have an active help request")
            return
        username = await self.get_username(user_id)
        self.active_sos_requests[user_id] = {
            "victim": username,
            "reason": reason,
            "task": asyncio.create_task(self._sos_loop(user_id, username, reason))
        }
        
    async def _sos_loop(self, victim_id: str, victim_name: str, reason: str):
        try:
            while victim_id in self.active_sos_requests:
                for helper_id in msg:
                    if helper_id == victim_id:
                        continue
                    message_id = f"1_on_1:{helper_id}:{self.bot_id}"
                    try:
                        await self.highrise.send_message(
                            message_id,
                            f"<#FF69B4>🚨 Emergency! @{victim_name} needs help!\n"
                            f"<#FF69B4>📝 Reason: {reason}\n"
                            f"<#FF69B4>✋ Reply with '1' to stop alerts"
                        )
                    except Exception as e:
                        print(f"Failed to send SOS to {helper_id}: {e}")
                    await asyncio.sleep(3)
                await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in SOS loop: {e}")
        finally:
            self.active_sos_requests.pop(victim_id, None)

    async def stop_sos(self, helper_id: str):
        for victim_id, data in list(self.active_sos_requests.items()):
            if helper_id in msg:
                data["task"].cancel()
                try:
                    await data["task"]
                except asyncio.CancelledError:
                    pass
                
                await self.highrise.send_message(
                    f"1_on_1:{helper_id}:{self.bot_id}",
                    f"<#FFD580>✅ Help alerts for @{data['victim']} stopped"
                )
                
                if victim_id in self.active_sos_requests:
                    del self.active_sos_requests[victim_id]
                    await self.highrise.send_message(
                        f"1_on_1:{victim_id}:{self.bot_id}",
                        "<#FFD580>🛑 Your help request has been cancelled by an assistant"
                    )
                break

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        try:
            response = await self.highrise.get_messages(conversation_id)
            if isinstance(response, GetMessagesRequest.GetMessagesResponse):
                message = response.messages[0].content
                if message.strip() == "1" and user_id in msg:
                    await self.stop_sos(user_id)

                if message == "/restart":
                    username = await self.get_username(user_id)

                    if username != "B_L_A_C_K_7" and username not in ownerz:
                        await self.highrise.send_message(
                            conversation_id,
                            "<#FFD580>❌ No permission."
                        )
                        return

                    try:
                        await self.highrise.send_message(
                            conversation_id,
                            "<#FFD580>🔄 Restarting bot..."
                        )

                        await self.restart_bot()

                    except Exception as e:
                        print("Error in private /restart:", e)

                    return   

                if message.lower().startswith("/bgive"):
                    username = await self.get_username(user_id)
                 

                    if username != "B_L_A_C_K_7":
                        await self.highrise.send_message(
                            conversation_id,
                            "<#BA55D3>❌ No permission."
                        )
                        return

                    try:
                        parts = message.split()

                        if len(parts) < 3:
                            await self.highrise.send_message(
                                conversation_id,
                                "<#BA55D3>Use: /bgive @username amount"
                            )
                            return

                        target_username = parts[1][1:]
                        amount = int(parts[2])

                        room_users = (await self.highrise.get_room_users()).content
                        target_user_id = None

                        for room_user, pos in room_users:
                            if room_user.username.lower() == target_username.lower():
                                target_user_id = room_user.id
                                break

                        if not target_user_id:
                            await self.highrise.send_message(
                                conversation_id,
                                "<#BA55D3>User not found, check name."
                            )
                            return

                        bot_wallet = await self.highrise.get_wallet()
                        bot_amount = bot_wallet.content[0].amount

                        if bot_amount >= amount:
                            await self.highrise.tip_user(
                                target_user_id,
                                f"gold_bar_{amount}"
                            )
                            await self.highrise.send_message(
                                conversation_id,
                                f"<#BA55D3>{amount} gold sent to {target_username}."
                            )
                        else:
                            await self.highrise.send_message(
                                conversation_id,
                                "<#BA55D3>I don't have enough gold to send.."
                            )

                        return

                    except Exception as e:
                        await self.highrise.send_message(
                            conversation_id,
                            f"<#BA55D3>Error: {e}"
                        )
                        return                    
                if message.strip() == "/bwallet":
                    username = await self.get_username(user_id)

                    if username == "B_L_A_C_K_7":
                        wallet = await self.highrise.get_wallet()

                        for item in wallet.content:
                            if item.type == "gold":
                                await self.highrise.send_message(
                                    conversation_id,
                                    f"💰 My current balance: {item.amount} gold!"
                                )
                                return

                        await self.highrise.send_message(
                            conversation_id,
                            "❌ No gold in wallet."
                        )
                    else:
                        await self.highrise.send_message(
                            conversation_id,
                            "❌ No permission."
                        )
                    return                    
                if message != "/verify":
                    if user_id not in ids:
                        ids.append(user_id)
                    return
            username = await self.get_username(user_id)
            info = await self.webapi.get_user(user_id)
            joined_at = info.user.joined_at
            if isinstance(joined_at, datetime):
                one_month_ago = datetime.now(joined_at.tzinfo) - timedelta(days=7)
                if joined_at <= one_month_ago:
                    if not username in user_ticket:
                        user_ticket[username] = 3
                        await self.highrise.send_message(conversation_id, "✅ Your account verified!")
                        await self.highrise.send_message(conversation_id, "🎫 You received 3 free tickets!")
                        await self.highrise.send_message(conversation_id, "📜 Useful commands:\n"
            "🎶 /play + song name or link\n"
            "🎫 /wallet — See how many tickets you have\n"
            "💰 /rlist — Buy tickets and VIP\n"
            "📲 /help — See all available commands")
                        if not user_id in ids:
                            ids.append(user_id)
                else:
                    await self.highrise.send_message(conversation_id, "<#FFD580>⏳ Sorry, your account is less than 3 months")
                    await asyncio.sleep(3)
                    await self.highrise.send_message(conversation_id,"<#FFD580>🙏 We try to maintain fairness\n<#FFD580>Thank you for understanding! 💕")
        except Exception as e:
            print(e)
                                
    async def get_username(self, user_id):
        user_info = await self.webapi.get_user(user_id)
        return user_info.user.username

    async def invite_all(self, user):
        if not user.username in ownerz:
            await self.highrise.send_whisper(user.id, "<#FFD580>❌ You can't use this command")
            return
        try:
            for erm in ids:
                message_id = f"1_on_1:{erm}:{self.bot_id}"
                await self.highrise.send_message(
                    message_id,
                    message_type="invite",
                    content="<#FFD580>🎉 Come to the room!", 
                    room_id=invite)
                await asyncio.sleep(3)
        except Exception as e:
            await self.highrise.chat(f"<#FFD580>❌ Error: {e}")

    async def _filter_outfit_by_inventory(self, outfit: list) -> list:
        """Filter outfit items to keep only those owned by the bot"""
        try:
            # Fetch bot inventory
            inventory = await self.highrise.get_inventory()
            owned_ids = set()
            if hasattr(inventory, 'items'):
                for item in inventory.items:
                    if hasattr(item, 'id'):
                        owned_ids.add(item.id)
            
            filtered_outfit = []
            for item in outfit:
                if hasattr(item, 'id') and item.id in owned_ids:
                    filtered_outfit.append(item)
                elif hasattr(item, 'id') and item.id.startswith("body-"): # Always keep body parts
                    filtered_outfit.append(item)
            
            return filtered_outfit
        except Exception as e:
            print(f"Inventory filter error: {e}")
            return outfit # Return original if filter fails

    def _normalize_outfit(self, outfit_data):
        from highrise import Item
        items = []
        if not outfit_data:
            return []
        for i in outfit_data:
            if isinstance(i, Item):
                items.append(i)
            elif isinstance(i, dict):
                items.append(Item(
                    type=i.get("type", "clothing"),
                    amount=i.get("amount", 1),
                    id=i.get("id", ""),
                    account_bound=i.get("account_bound", False),
                    active_palette=i.get("active_palette", -1)
                ))
        return items

    async def _apply_outfit_and_verify(self, outfit):
        try:
            if not outfit:
                return False
            await self.highrise.set_outfit(outfit=outfit)
            return True
        except Exception:
            return False

    async def _cdrees(self, command: str, user_id: str):
        parts = command.split()
        target = parts[1].strip() if len(parts) > 1 else ""
        if not target:
            return "Usage: /sequip @user"
        # باقي الكود كما هو، مع المحافظة على كل التوابع الداخلية بمقدار 4 مسافات على الأقل

    async def _idrees(self, command: str, user_id: str):
        parts = command.split()
        if len(parts) < 2:
            return "Usage: !idrees <item_id>"
        item_id = parts[1].strip()
        try:
            from highrise import Item
            resp = await self.highrise.get_my_outfit()
            current = resp.outfit if resp else []
            new_item = Item(type="clothing", amount=1, id=item_id, account_bound=False, active_palette=-1)
            new_outfit = current + [new_item]
            await self.highrise.set_outfit(outfit=new_outfit)
            return f"Equipped item: {item_id}"
        except Exception as e:
            return "Failed to equip item"

    async def _save_outfit(self, command: str, user_id: str):
        parts = command.split()
        name = ""
        if len(parts) > 1:
            name = parts[1].strip().lower()
        else:
            cmd_root = parts[0].lower()
            if cmd_root.startswith("!save") and len(cmd_root) > 5:
                name = cmd_root[5:]
        if not name:
            return "Usage: !save <name>"
        try:
            resp = await self.highrise.get_my_outfit()
            items = []
            if resp and resp.outfit:
                for it in resp.outfit:
                    items.append({
                        "type": getattr(it, "type", "clothing"),
                        "amount": getattr(it, "amount", 1),
                        "id": getattr(it, "id", ""),
                        "account_bound": getattr(it, "account_bound", False),
                        "active_palette": getattr(it, "active_palette", -1)
                    })
            self.saved_outfits[name] = items  # لو استخدمت القاموس البسيط
            return f"Saved outfit as '{name}'"
        except Exception as e:
            return "Failed to save outfit"
          
            
    async def on_chat(self, user: User, message: str):
        try:
            # كود VIP teleport
            if message in vip_positions:
                try:
                    if user.username in vip_users:
                        target_position = vip_positions[message]
                        await self.highrise.teleport(user.id, target_position)
                        self.user_positions[user.username] = target_position
                    else:
                        await self.highrise.send_whisper(user.id,"<#FFD580>❌ No permission.. Pay 1k to the bot")
                except Exception:
                    pass

            message_cleaned = message.lower().strip()

            # outfit list
            if message_cleaned.startswith("outfit list") and user.username in ownerz:
                try:
                    outfit_names = list(outfits.keys())
                    outfit_list = "\n".join(outfit_names) if outfit_names else "لا توجد أطقم حالياً."
                    await self.highrise.chat(f"الأطقم المتاحة:\n{outfit_list}")
                except Exception as e:
                    await self.highrise.chat(f"❌ حدث خطأ أثناء جلب قائمة الأطقم: {e}")

            # /equip command
            if message_cleaned.startswith("/equip") and user.username in ownerz:
                try:
                    parts = message_cleaned.split(" ", 1)
                    if len(parts) < 2:
                        await self.highrise.chat("❌ من فضلك اكتب اسم الزي بعد الأمر /equip")
                    else:
                        outfit_name = parts[1]
                        if outfit_name not in outfits:
                            await self.highrise.chat(f"❌ الزي '{outfit_name}' غير موجود في الملف.")
                        else:
                            outfit = outfits[outfit_name]
                            outfit_items = [Item(type='clothing', amount=1, id='body-flesh', account_bound=False, active_palette=1)]
                            for item_id in outfit:
                                if item_id:
                                    outfit_items.append(Item(type='clothing', amount=1, id=item_id, account_bound=False, active_palette=-1))
                            result = await self.highrise.set_outfit(outfit=outfit_items)
                            await self.highrise.chat(f"✅ تم تعيين زي '{outfit_name}' بنجاح: {result}")
                except Exception as e:
                    await self.highrise.chat(f"❌ حدث خطأ أثناء تعيين الزي: {e}")

            # /sequip command
            if message_cleaned.startswith("/sequip") and user.username in ownerz:
                try:
                    parts = message_cleaned.split()
                    if len(parts) < 2:
                        await self.highrise.send_whisper(user.id, "Usage: /sequip @username")
                        return

                    target = parts[1].strip()

                    # تحقق إذا كانت أطقم محفوظة
                    saved = self.saved_outfits.get(target.lower())
                    if saved:
                        items = self._normalize_outfit(saved)
                        if await self._apply_outfit_and_verify(items):
                            await self.highrise.send_whisper(user.id, f"Equipped saved outfit: {target}")
                            return
                        filtered = await self._filter_outfit_by_inventory(items)
                        if await self._apply_outfit_and_verify(filtered):
                            await self.highrise.send_whisper(user.id, f"Equipped saved outfit: {target} (Filtered)")
                            return
                        await self.highrise.send_whisper(user.id, "Failed to equip saved outfit")
                        return

                    # لو المستخدم @username
                    if target.startswith("@"):
                        uname = target.replace("@", "").strip()

                        async def try_apply(outfit_items):
                            outfit_items = self._normalize_outfit(outfit_items)
                            if not outfit_items:
                                return False
                            if await self._apply_outfit_and_verify(outfit_items):
                                return True
                            filtered = await self._filter_outfit_by_inventory(outfit_items)
                            if await self._apply_outfit_and_verify(filtered):
                                return True
                            return False

                        try:
                            room_users = (await self.highrise.get_room_users()).content
                            for room_user, _ in room_users:
                                if room_user.username.lower() == uname.lower():
                                    outfit_resp = await self.highrise.get_user_outfit(room_user.id)
                                    outfit = getattr(outfit_resp, "outfit", None)
                                    if outfit and await try_apply(outfit):
                                        await self.highrise.send_whisper(user.id, f"Outfit applied from @{uname}")
                                        return
                        except Exception as e:
                            print(f"Room search failed: {e}")

                        try:
                            uid = await self.resolve_user_id(uname)
                            if uid:
                                outfit_resp = await self.highrise.get_user_outfit(uid)
                                outfit = getattr(outfit_resp, "outfit", None)
                                if outfit and await try_apply(outfit):
                                    await self.highrise.send_whisper(user.id, f"Outfit applied from @{uname}")
                                    return
                        except Exception:
                            pass

                        await self.highrise.send_whisper(user.id, f"Outfit not found for @{uname}")
                        return

                    await self.highrise.send_whisper(user.id, f"Style '{target}' not found. Use !save <name> to save one.")
                except Exception as e:
                    print(f"/sequip error: {e}")

        except Exception as e:
            print(f"on_chat error: {e}")


                        
                        
        if message.startswith("/invite"):
            try:
                await self.invite_all(user)
            except Exception as e:
                await self.highrise.chat(f"<#FFD580>❌ Problem: {e}")

        if not message.lower() == "no":
            if not message.lower() == "yes":
                if user.username in self.choices:
                    try:
                        if not user.username in self.wait:
                            self.wait.append(user.username)
                            await self.highrise.send_whisper(user.id, "<#FFD580>💬 Type 'yes' or 'no' to apply changes")
                            await self.highrise.send_whisper(user.id, "<#FFD580>⏰ If you don't respond within 10 seconds, operation will stop")
                        await asyncio.sleep(10)
                        if user.username in self.choices:
                            del self.choices[user.username]
                            if user.username in self.wait:
                                self.wait.remove(user.username)
                            await self.highrise.send_whisper(user.id, "<#FFD580>❌ Operation cancelled")
                    except:
                        pass
                        
        if message.lower() == "no":
            if user.username == "B_L_A_C_K_7" or user.username in ownerz:
                if user.username in self.choices:
                    await self.highrise.send_whisper(user.id, "<#FFD580>❌ Operation cancelled")
                    del self.choices[user.username]
        
        if message.lower() == "yes":
            if user.username == "B_L_A_C_K_7" or user.username in ownerz:
                if user.username in self.choices:
                    new_bitrate = self.choices[user.username]
                    self.bitrate = new_bitrate
                    await self.highrise.chat(f"<#FFD580>✅ Audio bitrate updated to {new_bitrate}")
                    del self.choices[user.username]
        
        if message.startswith("/cbit") and (user.username == "B_L_A_C_K_7" or user.username in ownerz):
            await self.highrise.send_whisper(user.id, f"<#FFD580>🎧 Audio streaming at {self.bitrate}bps")
        
        if message.startswith("/bitrate ") and (user.username == "B_L_A_C_K_7" or user.username in ownerz):
            parts = message.split(" ")
            if len(parts) > 1:
                if parts[1].endswith("k") and parts[1][:-1].isdigit():
                    bitrate = parts[1]
                    await self.highrise.chat(f"<#FFD580>⚠️ Are you sure you want to change bitrate to {bitrate}?")
                    await self.highrise.send_whisper(user.id, "<#FFD580>🔊 This may affect audio quality\n<#FFD580>✅ Type 'yes' to confirm\n<#FFD580>❌ Type 'no' to cancel")
                    self.choices[user.username] = bitrate
                else:
                    await self.highrise.send_whisper(user.id, "<#FFD580>❌ Use: /bitrate [number]k\n<#FFD580>Example: /bitrate 128k")
            else:
                await self.highrise.send_whisper(user.id, "<#FFD580>❌ Use: /bitrate [number]k\n<#FFD580>Example: /bitrate 128k")
        
        if message == "/restart" and (user.username == "B_L_A_C_K_7" or user.username in ownerz):
            try:
                await self.highrise.send_whisper(user.id, "<#FFD580>🔄 Restarting bot...")
                await self.restart_bot()
            except Exception as e:
                print("Error in /restart command: ", e)

        if message.startswith("/help"):
            try:
                # Check if user is owner
                is_owner = user.username in ownerz or user.username == "B_L_A_C_K_7"
                
                if not is_owner:
                    # Short single message (less than 255 chars)
                    help_text = "<#FF69B4>🎵 Commands 🎵\n\n"
                    help_text += "🎶 /play — Request music\n"
                    help_text += "🎵 /now — Current song\n"
                    help_text += "⏭️ /next — Next song\n"
                    help_text += "📋 /queue — Queue list\n"
                    help_text += "🎫 /wallet — Tickets\n"
                    help_text += "💰 /rlist — Prices\n"
                    help_text += "⏩ /skip — Skip\n"
                    help_text += "🔎 /dump N — Info\n"
                    help_text += "📞 /verify — 3 tickets"
                    
                    # Message length: ~200 chars
                    await self.highrise.send_whisper(user.id, help_text)
                    
                else:
                    # If owner
                    await self.highrise.send_whisper(
                        user.id,
                        "<#BA55D3>🔧 Admin Tools 🔧\n\n"
                        "Choose:\n"
                        "1️⃣ Regular commands\n"
                        "2️⃣ Admin commands\n\n"
                        "Reply with: 1 or 2"
                    )
                    
                    self.help_state = {"user_id": user.id, "username": user.username}
                    
            except Exception as e:
                print(f"Error in /help command: {e}")

        # Handle replies
        elif message in ["1", "2"] and hasattr(self, 'help_state') and self.help_state["user_id"] == user.id:
            try:
                if message == "1":
                    # General commands - two messages
                    public_text1 = "<#FF69B4>🎵 Commands 🎵\n\n"
                    public_text1 += "🎶 /play — Request music\n"
                    public_text1 += "🎵 /now — Current song\n"
                    public_text1 += "⏭️ /next — Next song\n"
                    public_text1 += "📋 /queue — Queue list\n"
                    public_text1 += "🎫 /wallet — Tickets\n"
                    public_text1 += "💰 /rlist — Prices\n"
                    
                    public_text2 = "<#FF69B4>⏩ /skip — Skip\n"
                    public_text2 += "🔎 /dump N — Info\n"
                    public_text2 += "🎧 /cbit — Bitrate\n"
                    public_text2 += "📞 /verify — 3 tickets\n"
                    public_text2 += "🆘 /sos — Request help\n"
                    public_text2 += "❓ /help — This message"
                    
                    await self.highrise.send_whisper(user.id, public_text1)
                    # Use time.sleep instead of asyncio.sleep
                    
                    time.sleep(0.5)
                    await self.highrise.send_whisper(user.id, public_text2)
                    
                elif message == "2":
                    # Admin commands divided into short messages
                    
                    
                    # 1: Music
                    msg1 = "<#BA55D3>🔧 Music:\n"
                    msg1 += "/bitrate Nk — Quality\n"
                    msg1 += "/restart — Restart\n"
                    msg1 += "/top N — Move up\n"
                    msg1 += "/fav — Save\n"
                    msg1 += "/flist — Show\n"
                    msg1 += "/mfav N — Play\n"
                    msg1 += "/rfav N — Delete\n"
                    msg1 += "/cfav — Clear favorites"
                    
                    await self.highrise.send_whisper(user.id, msg1)
                    time.sleep(0.3)
                    
                    # 2: Users - Part 1
                    msg2a = "<#BA55D3>👥 Users 1/2:\n"
                    msg2a += "/ownerz — List\n"
                    msg2a += "/vipz — VIP\n"
                    msg2a += "/add @user — Owner\n"
                    msg2a += "/rem @user — Remove\n"
                    msg2a += "/addv @user — VIP\n"
                    msg2a += "/remv @user — Remove VIP"
                    
                    await self.highrise.send_whisper(user.id, msg2a)
                    time.sleep(0.3)
                    
                    # 2: Users - Part 2
                    msg2b = "<#BA55D3>👥 Users 2/2:\n"
                    msg2b += "/cvip — Clear VIP\n"
                    msg2b += "/msg @user — Notify\n"
                    msg2b += "/rmsg @user — Remove notify\n"
                    msg2b += "/cmsg — Clear notifications"
                    
                    await self.highrise.send_whisper(user.id, msg2b)
                    time.sleep(0.3)
                    
                    # 3: Money - Part 1
                    msg3a = "<#BA55D3>💰 Money 1/2:\n"
                    msg3a += "/give @user N — Tickets\n"
                    msg3a += "/withdraw N — Withdraw\n"
                    msg3a += "/bwallet — Bot balance\n"
                    msg3a += "/bgive @user N — Gold\n"
                    msg3a += "/transfer @user N"
                    
                    await self.highrise.send_whisper(user.id, msg3a)
                    time.sleep(0.3)
                    
                    # 3: Money - Part 2
                    msg3b = "<#BA55D3>💰 Money 2/2:\n"
                    msg3b += "/prices — Prices\n"
                    msg3b += "/setticketprice N\n"
                    msg3b += "/setticketmulti N\n"
                    msg3b += "/setvipprice N\n"
                    msg3b += "/setmindonation N\n"
                    msg3b += "/setgoldmessage msg"
                    
                    await self.highrise.send_whisper(user.id, msg3b)
                    time.sleep(0.3)
                    
                    # 4: Settings
                    msg4 = "<#BA55D3>⚙️ Settings:\n"
                    msg4 += "/setbot — Location\n"
                    msg4 += "/base — Base\n"
                    msg4 += "/idroom id — Room\n"
                    msg4 += "/idbot token — Token\n"
                    msg4 += "/equip item — Wear\n"
                    msg4 += "/remove category — Remove\n"
                    msg4 += "/color category N — Color"
                    
                    await self.highrise.send_whisper(user.id, msg4)
                    time.sleep(0.3)
                    
                    # 5: Information
                    msg5 = "<#BA55D3>📊 Information:\n"
                    msg5 += "/accs — Statistics\n"
                    msg5 += "/info @user — Tickets\n"
                    msg5 += "/block @user — Block\n"
                    msg5 += "/unblock @user — Unblock\n"
                    msg5 += "/sblocked — Blocked list\n"
                    msg5 += "/sequip @user — Copy clothes"
                    
                    await self.highrise.send_whisper(user.id, msg5)
                    time.sleep(0.3)
                    
                    # 6: Miscellaneous
                    msg6 = "<#BA55D3>📢 Other:\n"
                    msg6 += "/res name — Block music\n"
                    msg6 += "/unres name — Unblock music\n"
                    msg6 += "/promo msg — Promotion\n"
                    msg6 += "/rpromo msg — Remove promotion\n"
                    msg6 += "/cpromo — Clear promotions\n"
                    msg6 += "/invite — Invite all"
                    
                    await self.highrise.send_whisper(user.id, msg6)
                
                # Clear state
                delattr(self, 'help_state')
    
            except Exception as e:
                print(f"Error in selection: {e}")
                if hasattr(self, 'help_state'):
                    delattr(self, 'help_state')

        if message.strip() == "/verify":
            await self.highrise.send_whisper(user.id, "Send /verify in bot private")

        

        
        


        if any(message.startswith(cmd) for cmd in ["/play", "/p"]):
         global NEXT_ALLOWED_TIME  # ✅ Must be here before any use

         if user.username in blocked_list:
          await self.highrise.send_whisper(user.id, "🚫 You are blocked from using this command.")
          return
         
         user_privileges = await self.highrise.get_room_privilege(user.id)

         if (
          user.username in self.mods
          or user.username in vip_users
          or (user.username in user_ticket and user_ticket[user.username] > 0)
          or user.username in ownerz
          or user_privileges.moderator
         ):
          
          try:
            parts = message.split(" ", 1)
            if len(parts) == 1:
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Type song name after /play")
                return

            query = parts[1].strip()
            lower_query = query.lower()

            for item in restrict:
                if item.lower() in lower_query:
                    await self.highrise.send_whisper(
                        user.id,
                        "<#FF69B4>🚫 This song is banned. Ticket returned ✅"
                    )
                    return

            await self.highrise.send_whisper(
                user.id,
                "<#FF69B4>⏳ Preparing your request..."
            )

            # 🕒 Calculate remaining time (before lock)
            now = time.time()
            if now < NEXT_ALLOWED_TIME:
                wait = int(NEXT_ALLOWED_TIME - now)
                await self.highrise.send_whisper(
                    user.id,
                    f"<#FF69B4>🕒 Please wait {wait} seconds before next request."
                )

            # 🔒 Sequential execution
            async with REQUEST_LOCK:
                now = time.time()

                if now < NEXT_ALLOWED_TIME:
                    await asyncio.sleep(NEXT_ALLOWED_TIME - now)

                NEXT_ALLOWED_TIME = time.time() + 40

                await self.add_to_queue(query, user)
                print(f"[play_command] ✅ Final search query sent: {query}")

          except Exception as e:
            print(f"[play_command] error: {e}")
            await self.highrise.send_whisper(
                user.id,
                f"<#FF69B4>⚠️ Playback error: {e}"
            )


        if message.lower().startswith("/help"):
            try:
                # ====== User / VIP Commands ======
                help_parts = [
                    "♠ Commands 👇",
                    "🎰 To play a song: Type /p followed by the song title. Type /np to see the current song.",
                    "🎵Playlist:\n- Type /q to display the playlist.",
                    "📋 Tickets: Type /tk to see how many tickets you have. Type /givetk followed by your username followed by the number of tickets."
                ]

                for part in help_parts:
                    await self.highrise.send_whisper(user.id, part)
                    await asyncio.sleep(0.3)  # تأخير بسيط بين كل رسالة

            except Exception as e:
                print("Help send error:", e)



        if message.lower().startswith("/bgive") and user.username in ownerz:
            try:
                # Split message to get username and amount
                parts = message.split()
                if len(parts) < 3:
                    await self.highrise.chat("<#BA55D3>Command format incorrect. Use: /bgive @username amount")
                    return

                target_username = parts[1][1:]  # Username after @
                amount = int(parts[2])  # Donation amount

                # Get list of users in room
                room_users = (await self.highrise.get_room_users()).content
                target_user_id = None
                for room_user, pos in room_users:
                    if room_user.username.lower() == target_username.lower():
                        target_user_id = room_user.id
                        break

                if not target_user_id:
                    await self.highrise.chat("<#BA55D3>User not found, check name.")
                    return

                # Get wallet info
                bot_wallet = await self.highrise.get_wallet()
                bot_amount = bot_wallet.content[0].amount

                # Check if balance is enough to send donation
                if bot_amount >= amount:
                    # Send donation
                    await self.highrise.tip_user(target_user_id, f"gold_bar_{amount}")
                    await self.highrise.chat(f"<#BA55D3>{amount} gold sent to {target_username}.")
                else:
                    await self.highrise.chat("<#BA55D3>I don't have enough gold to send..")
            except (IndexError, ValueError) as e:
                # Handle errors related to message format or value conversion
                error_message = f"<#BA55D3>Command format error: {e}. Use: give @username amount"
                await self.highrise.chat(error_message)
                print(error_message)

        if any(message.startswith(cmd) for cmd in ["/rlist", "/tk", "!tk", "!rlist"]):
            try:
                # 🎁 Part 1 — Ticket prices
                try:
                    import json
                    import os
                    
                    # Check if file exists
                    if os.path.exists("tk_price.json"):
                        with open("tk_price.json", "r", encoding="utf-8") as f:
                            prices = json.load(f)
                        
                        # Read values from file with defaults
                        payment_price = prices.get("ticket_price", 10)
                        tickets_count = prices.get("ticket_multiplier", 3)
                        vip_price = prices.get("vip_price", 1000)
                        min_donation = prices.get("min_donation", 10)
                        
                        print(f"📄 Reading file: ticket_price={payment_price}, multiplier={tickets_count}, vip={vip_price}")
                    else:
                        # If file doesn't exist, use default values
                        print("⚠️ tk_price.json file not found. Using normal values.")
                        payment_price = 10
                        tickets_count = 3
                        vip_price = 1000
                        min_donation = 10
                    
                    message_text = f"<#FF69B4>💰 Ticket prices:\n"
                    
                    # Calculate tickets available for each coin
                    available_coins = [1, 5, 10, 50, 100, 500, 1000]
                    
                    for coin in available_coins:
                        # Check if coin is enough for payment
                        if coin >= payment_price:
                            # Calculate number of payments
                            payments_count = coin // payment_price
                            # Calculate total tickets
                            total_tickets = payments_count * tickets_count
                            message_text += f"• {total_tickets} tickets = {coin} gold\n"
                    
                    # Add VIP price
                    message_text += f"• ⭐ VIP = {vip_price} gold"
                    
                    await self.highrise.send_whisper(user.id, message_text)
                    
                except json.JSONDecodeError as e:
                    print(f"❌ JSON error: {e}")
                    # If JSON file is corrupted, use default values
                    payment_price = 10
                    tickets_count = 3
                    vip_price = 1000
                    
                    message_text = f"<#FF69B4>💰 Ticket prices (normal):\n"
                    available_coins = [1, 5, 10, 50, 100, 500, 1000]
                    
                    for coin in available_coins:
                        if coin >= payment_price:
                            payments_count = coin // payment_price
                            total_tickets = payments_count * tickets_count
                            message_text += f"• {total_tickets} tickets = {coin} gold\n"
                    
                    message_text += f"• ⭐ VIP = {vip_price} gold"
                    await self.highrise.send_whisper(user.id, message_text)
                    
                except Exception as json_error:
                    print(f"❌ General error: {json_error}")
                    # In case of any other error
                    await self.highrise.send_whisper(
                        user.id,
                        "<#FF69B4>💰 Ticket prices (normal):\n"
                        "• 3 tickets = 10 gold\n"
                        "• 6 tickets = 20 gold\n"
                        "• 30 tickets = 100 gold\n"
                        "• 150 tickets = 500 gold\n"
                        "• ⭐ VIP = 1000 gold"
                    )

                # 💬 Part 2 — For special services
                await self.highrise.send_whisper(
                    user.id,
                    "<#FF69B4>💬 Need tickets?\n"
                    "Talk to management ✨"
                )

            except Exception as e:
                print(f"Error in rlist: {e}")
        


        if message.startswith("/dump "):
         try:
          parts = message.split()
          if len(parts) < 2 or not parts[1].isdigit():
            await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid number")
            return

          index = int(parts[1]) - 1

        # ===============================
        # Identify current song
        # ===============================
          current_song_url = None
          is_from_fav = False

          if hasattr(self, "now") and self.now:
            current_song = self.now[0]
            if isinstance(current_song, dict):
                current_song_url = current_song.get("url")
                if current_song_url and hasattr(self, "fav_dir"):
                    is_from_fav = str(current_song_url).startswith(str(self.fav_dir))

        # ===============================
        # Build same queue list
        # ===============================
          req_list = list(self.req_files)
          songs_to_use = []

          if current_song_url and not is_from_fav and req_list:
            first = req_list[0]
            if isinstance(first, dict) and first.get("url") == current_song_url:
                songs_to_use = req_list[1:]
            else:
                songs_to_use = req_list
          else:
            songs_to_use = req_list

        # ===============================
        # Check number
        # ===============================
          if index < 0 or index >= len(songs_to_use):
            await self.highrise.send_whisper(
                user.id, f"<#FF69B4>❌ No song with number {index + 1}"
            )
            return

          file_info = songs_to_use[index]

          title = file_info.get("title", "Unknown")
          duration = file_info.get("duration", "Unknown")
          req_user = file_info.get("user")

        # ===============================
        # Send information
        # ===============================
          if req_user:
            await self.highrise.send_whisper(
                user.id,
                f"<#FF69B4>🎵 {index + 1}: {title}\n"
                f"<#FF69B4>⏱️ Duration: {duration}\n"
                f"<#FF69B4>👤 Requested by: @{req_user}"
            )
          else:
            await self.highrise.send_whisper(
                user.id,
                f"<#FF69B4>🎵 {title}\n"
                f"<#FF69B4>⏱️ Duration: {duration}"
            )

         except Exception as e:
          print(f"Error in /dump command: {e}")
          await self.highrise.send_whisper(user.id, "<#FF69B4>❌ An error occurred")




        if any(message.startswith(cmd) for cmd in ["/now", "/np", "!now", "np"]):
         try:
          

          if getattr(self, "now", None) and len(self.now) > 0:
            now_playing = self.now[0]

            if not isinstance(now_playing, dict):
                await self.highrise.send_whisper(user.id, "<#FF69B4>⚠️ Invalid data.")
                return

            # 🔧 Extract data with title handling
            title = now_playing.get("title", "Unknown")
            length_str = now_playing.get("audio_length", "0:00")
            user_req = now_playing.get("user")

            # ⏳ Calculate time
            if hasattr(self, "start_time"):
                elapsed = int(time.time() - self.start_time)
                elapsed = max(elapsed, 0)
            else:
                self.start_time = time.time()
                elapsed = 0

            # 🎚️ Progress bar
            bar_length = 10
            try:
                if ":" in length_str:
                    mins, secs = map(int, length_str.split(":"))
                    total_seconds = mins * 60 + secs
                else:
                    total_seconds = 0
            except:
                total_seconds = 0
            
            if total_seconds > 0:
                progress_ratio = min(elapsed / total_seconds, 1.0)
                filled = int(progress_ratio * bar_length)
                remaining_seconds = max(total_seconds - elapsed, 0)
            else:
                progress_ratio = 0
                filled = 0
                remaining_seconds = 0

            rem_m, rem_s = divmod(remaining_seconds, 60)
            bar = "▰" * filled + "▱" * (bar_length - filled)

            # 🔨 Auto-short title based on total length
            MAX_LENGTH = 255
            
            # Base message without title and username
            base_msg = f"<#FF69B4>🎶 Now playing:\n🎵 {{title}}\n⏱️ {elapsed//60:02d}:{elapsed%60:02d} / {length_str}\n{bar}\n🕒 Remaining: {rem_m:02d}:{rem_s:02d}"
            
            if user_req:
                base_msg += f"\n👤 @{user_req}"
            
            # Calculate message length without title
            msg_without_title = base_msg.replace("{title}", "")
            length_without_title = len(msg_without_title)
            
            # Calculate available space for title
            available_for_title = MAX_LENGTH - length_without_title
            
            # Shorten title if too long
            if len(title) > available_for_title:
                # Leave space for three dots
                if available_for_title > 3:
                    title = title[:available_for_title - 3] + "..."
                else:
                    # If not enough space
                    title = "Song" if available_for_title >= len("Song") else "..."

            # Build final message
            msg = base_msg.replace("{title}", title)
            
            # Send message
            await self.highrise.send_whisper(user.id, msg)
          else:
            await self.highrise.send_whisper(user.id, "<#FF69B4>🎵 No song currently playing.")
         except Exception as e:
          print(f"❌ Error in /now command: {e}")
          await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Error displaying current song.")


        if message.startswith("/wallet"):
            try:
                if user.username in user_ticket:
                    if user_ticket[user.username] == 0:
                        await self.highrise.send_whisper(user.id, f"<#FF69B4>❌ You have no tickets\n<#FF69B4>💸 Pay to @{self.username} to get tickets")
                        return
                    if user_ticket[user.username] == 1:
                        await self.highrise.send_whisper(user.id, f"<#FF69B4>🎫 You have only one ticket")
                        return
                    await self.highrise.send_whisper(user.id, f"<#FF69B4>💰 Your wallet: {user_ticket[user.username]} tickets")
                else:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>💬 Talk to the bot to get 3 free tickets")
            except Exception as e:
                print("Error in wallet:", e)

        if any(message.startswith(cmd) for cmd in ["/next","!next"]):
            try: 
                if len(self.req_files) > 1:
                    next_file = self.req_files[1]
                    audio_length = (next_file['duration'])
                    next = next_file['title']
                    if next_file['user']:
                        await self.highrise.send_whisper(user.id, 
                            f"<#FF69B4>🎵 Next song:\n"
                            f"<#FF69B4>{next}\n"
                            f"<#FF69B4>⏱️ Duration: {audio_length}\n"
                            f"<#FF69B4>👤 Requested by: @{next_file['user']}")
                    else:
                        await self.highrise.send_whisper(user.id,
                            f"<#FF69B4>🎵 Next song:\n"
                            f"<#FF69B4>{next}\n"
                            f"<#FF69B4>⏱️ Duration: {audio_length}")
                else: 
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ No next song")
            except Exception as e: 
                print(f"Error in /next command: {e}") 
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ An error occurred")
        
        if message.startswith("/top") and user.username in ownerz:
            try:
                parts = message.split(" ")
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1])
                    if 0 < index < len(self.req_files):
                        item_to_move = self.req_files[index]
                        self.req_files.remove(item_to_move)
                        self.req_files.insert(1, item_to_move)
                        await self.highrise.chat(f"<#BA55D3>✅ Song moved up")
                    else:
                        await self.highrise.send_whisper(user.id, f"<#BA55D3>❌ No song with number {index}")
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Use /top [number]")
            except Exception as e:
                print(f"Error moving song up: {e}")


        if message.strip().lower().startswith("/history") and user.username in ownerz :
         try:
          import json

          HISTORY_FILE = "history.json"

        # ===== Extract target =====
          parts = message.strip().split()
          if len(parts) > 1 and parts[1].startswith("@"):
            target_username = parts[1][1:]  # Remove @
          else:
            target_username = user.username

        # ===== Load history =====
          try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
          except FileNotFoundError:
            history_data = {}
          except json.JSONDecodeError:
            history_data = {}
          except Exception as e:
            print("❌ Error reading history.json:", e)
            history_data = {}

        # ===== Check existence =====
          if target_username not in history_data:
            await self.highrise.send_whisper(
                user.id,
                f"<#FF69B4>📭 @{target_username} has no operation history."
            )
            return

          user_history = history_data.get(target_username, {})
          total_spent = user_history.get("total_spent", 0)
          history_list = user_history.get("history", [])

        # ===== Build message =====
          text = (
            f"<#FF69B4>📜 History of @{target_username}\n"
            f"<#FF69B4>💰 Total spent: {total_spent} gold\n"
            f"<#FF69B4>━━━━━━━━━━━━━━━\n"
        )

          for i, item in enumerate(history_list[:10], start=1):
            try:
                text += (
                    f"<#FF69B4>{i}) 🏷️ Type: {item.get('type', 'N/A')}\n"
                    f"<#FF69B4>   💰 Value: {item.get('amount', 0)} gold\n"
                    f"<#FF69B4>   📅 Date: {item.get('date', 'N/A')}\n"
                )
            except Exception as e:
                print("❌ Error building history item:", e)

        # ===== Send in parts =====
          for i in range(0, len(text), 255):
            try:
                await self.highrise.send_whisper(user.id, text[i:i + 255])
            except Exception as e:
                print("❌ Error sending history:", e)

         except Exception as e:
          print("❌ General error in /history command:", e)
          try:
            await self.highrise.send_whisper(
                user.id,
                "<#FF69B4>❌ Error loading history. Try again."
            )
          except:
            pass


       


        if any(message.startswith(cmd) for cmd in ["/skip", "!skip"]):
            import os
            try:
                parts = message.split()

                # ===============================
                # صلاحيات
                # ===============================
                user_privileges = await self.highrise.get_room_privilege(user.id)

                is_owner = user.username in ownerz
                is_mod = user.username in self.mods or user_privileges.moderator

                has_skip_permission = is_owner or is_mod

                # ===============================
                # Identify current song
                # ===============================
                current_song_url = None
                is_from_fav = False

                if hasattr(self, "now") and self.now:
                    current_song = self.now[0]
                    if isinstance(current_song, dict):
                        current_song_url = current_song.get("url")
                        if current_song_url and hasattr(self, "fav_dir"):
                            is_from_fav = str(current_song_url).startswith(str(self.fav_dir))

                # ===============================
                # Build queue
                # ===============================
                req_list = list(self.req_files)
                songs_to_use = []

                if current_song_url and not is_from_fav and req_list:
                    first = req_list[0]
                    if isinstance(first, dict) and first.get("url") == current_song_url:
                        songs_to_use = req_list[1:]
                    else:
                        songs_to_use = req_list
                else:
                    songs_to_use = req_list

                # ===============================
                # /skip رقم
                # ===============================
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1]) - 1

                    if index < 0 or index >= len(songs_to_use):
                        await self.highrise.send_whisper(
                            user.id, "<#FF69B4>❌ No song with this number"
                        )
                        return

                    removed_file = songs_to_use[index]
                    req_user = removed_file.get("user")
                    title = removed_file.get("title", "Unknown")

                    if not (has_skip_permission or user.username == req_user):
                        await self.highrise.send_whisper(
                            user.id,
                            "<#FF69B4>❌ Only Owners, VIPs, or the requester can skip this song"
                        )
                        return

                    if os.path.exists(removed_file.get("url", "")):
                        os.remove(removed_file["url"])

                    if removed_file in self.req_files:
                        self.req_files.remove(removed_file)

                    await self.highrise.chat(
                        f"<#FF69B4>🗑️ Removed from queue:\n<#FF69B4>{title}"
                    )
                    return

                # ===============================
                # /skip بدون رقم (الأغنية الحالية)
                # ===============================
                if self.now:
                    removed_file = self.now[0]
                    req_user = removed_file.get("user")
                    title = removed_file.get("title", "Unknown")

                    if not (has_skip_permission or user.username == req_user):
                        await self.highrise.send_whisper(
                            user.id,
                            "<#FF69B4>❌ Only Owners, VIPs, or the requester can skip this song"
                        )
                        return

                    await self.highrise.chat(
                        f"<#FF69B4>⏩ Skipping:\n<#FF69B4>{title}"
                    )
                    self.skip = True
                else:
                    await self.highrise.chat("<#FF69B4>⏩ Skipping: Nothing.mp3")

            except Exception as e:
                print(f"Error in /skip command: {e}")
                await self.highrise.send_whisper(
                    user.id, "<#FF69B4>❌ An error occurred"
                )





        if any(message.startswith(cmd) for cmd in ["/queue", "/q", "queue", "!queue"]):
         try:
        # user here is User object from on_chat
          user_id = user.id
          user_username = user.username
        
          if not hasattr(self, 'req_files') or not self.req_files:
            await self.highrise.send_whisper(user_id, "<#FF69B4>📭 Queue is empty")
            return
        
        # Make copy of list
          req_list = list(self.req_files)
        
          if not req_list:
            await self.highrise.send_whisper(user_id, "<#FF69B4>📭 Queue is empty")
            return

        # Check current song
          current_song_url = None
          is_from_fav = False
        
          if hasattr(self, 'now') and self.now and len(self.now) > 0:
            current_song = self.now[0]
            if isinstance(current_song, dict):
                current_song_url = current_song.get('url')
                # Check if song is from favorites
                if current_song_url and hasattr(self, 'fav_dir'):
                    is_from_fav = str(current_song_url).startswith(str(self.fav_dir))
        
        # Determine songs to display
          songs_to_display = []
        
          if current_song_url and not is_from_fav:
            # If current song is from req_files (not from favorites)
            if req_list and len(req_list) > 0:
                first_song = req_list[0]
                if isinstance(first_song, dict):
                    first_song_url = first_song.get('url')
                    # If first song in list is same as current song, skip it
                    if first_song_url == current_song_url:
                        # Start from second item
                        songs_to_display = req_list[1:] if len(req_list) > 1 else []
                    else:
                        # If different, show everything
                        songs_to_display = req_list
                else:
                    songs_to_display = req_list
            else:
                songs_to_display = req_list
          else:
            # If song is from favorites or no song playing, show everything
            songs_to_display = req_list

          if not songs_to_display:
            await self.highrise.send_whisper(user_id, "<#FF69B4>📭 Queue is empty")
            return

        # Build message
          MAX_LENGTH = 255
          messages = []
          current_msg = "<#FF69B4>📋 Queue list:\n"
        
          for idx, song in enumerate(songs_to_display, 1):
            if isinstance(song, dict):
                title = song.get('title', 'Unknown')
                requester_name = song.get('user', '')
                
                # Shorten title
                if len(title) > 30:
                    title = title[:27] + "..."
                
                # Build line
                if requester_name:
                    line = f"<#FF69B4>{idx}. {title}\n   👤 @{requester_name}\n--------------\n"
                else:
                    line = f"<#FF69B4>{idx}. {title}\n--------------\n"
                
                # Check length
                if len(current_msg) + len(line) > MAX_LENGTH:
                    if current_msg.endswith("--------------\n"):
                        current_msg = current_msg[:-len("--------------\n")]
                    messages.append(current_msg.strip())
                    current_msg = f"<#FF69B4>📋 Continued ({idx} to {len(songs_to_display)}):\n{line}"
                else:
                    current_msg += line
        
        # Add last part
          if current_msg.strip() and current_msg.strip() != "<#FF69B4>📋 Queue list:":
            if current_msg.endswith("--------------\n"):
                current_msg = current_msg[:-len("--------------\n")]
            messages.append(current_msg.strip())
        
        # Add song count with separator
          if messages and len(songs_to_display) > 0:
            last_msg = messages[-1]
            footer = "\n-------\n<#FF69B4>📊 Song count: " + str(len(songs_to_display))
            
            if len(last_msg) + len(footer) <= MAX_LENGTH:
                messages[-1] = last_msg + footer
            else:
                messages.append("-------\n<#FF69B4>📊 Song count: " + str(len(songs_to_display)))
        
        # Send messages
          if not messages:
            await self.highrise.send_whisper(user_id, "<#FF69B4>📭 Queue is empty")
            return
        
          for msg in messages:
            if msg.strip():
                await self.highrise.send_whisper(user_id, msg)
                        
         except Exception as e:
          print(f"Error in queue command: {e}")
          # Use user.id instead of just user
          await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Error displaying queue")



        if message.startswith("/info ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                info = message.split(" ", 1)[1]
                infol = info.replace("@", "")
                if infol in user_ticket and user_ticket[infol] > 0:
                    if user_ticket[infol] == 1:
                        await self.highrise.chat(f"<#BA55D3>👤 User {info} has only one ticket")
                    if user_ticket[infol] > 1:
                        await self.highrise.chat(f"<#BA55D3>👤 User {info} has {user_ticket[infol]} tickets")
                else:
                    await self.highrise.chat(f"<#BA55D3>👤 User {info} has no tickets")
            except Exception as e:
                print(e)

        if message.lower().startswith("/set ") and user.username in ownerz:
         parts = message.split()

         if len(parts) != 2:
          await self.highrise.send_whisper(
            user.id,
            "❌ Correct usage:\n/set youtube\n/set soundcloud"
        )
          return

         source = parts[1].lower()

         if source not in ["youtube", "soundcloud"]:
          await self.highrise.send_whisper(
            user.id,
            "❌ Method not supported\n✅ Available methods:\n• youtube\n• soundcloud"
        )
          return

         save_settings(source)

         await self.highrise.send_whisper(
        user.id,
        f"✅ Playback source set to: {source}"
    )
         return
                
        if message.startswith("/rem ") and user.username in ownerz:
            try:
                remvip = message.split(" ", 1)[1]
                rem = remvip.replace("@", "").split()[0]

                if rem in ownerz:
                    ownerz.remove(rem)
                    await self.highrise.chat(f"<#BA55D3>🗑️ {rem} removed from owners")
                else:
                    await self.highrise.send_whisper(
                        user.id,
                        f"<#BA55D3>❌ {rem} is not an owner"
                    )
            except:
                pass
                
        if message.startswith("/add ") and user.username in ownerz:
            try:
                vip = message.split(" ", 1)[1]
                allowed = vip.replace("@", "").split()[0]

                if allowed not in ownerz:
                    ownerz.append(allowed)
                    await self.highrise.chat(
                        f"<#BA55D3>✅ {allowed} added to owners"
                    )
                else:
                    await self.highrise.chat(
                        f"<#BA55D3>ℹ️ {allowed} is already an owner"
                    )
            except:
                await self.highrise.send_whisper(
                    user.id,
                    "<#BA55D3>❌ Not found"
                )

        if message == "/cvip":
            if user.username in ownerz:
                try:
                    vip_users.clear()
                    await self.highrise.send_whisper(user.id, "<#BA55D3>🗑️ VIP list cleared")
                except:
                    pass
                
        if message.startswith("/vipz") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                if vip_users:
                    message_content = "<#BA55D3>⭐ VIP list:\n\n"
                    for idx, user_name in enumerate(vip_users, start=1):
                        item = f"<#BA55D3>{idx}. {user_name}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, message_content.strip())
                            message_content = item
                        else:
                            message_content += item
                    if message_content:
                        await self.highrise.send_whisper(user.id, message_content.strip())
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>📭 VIP list is empty")
            except Exception as e:
                print(f"Error in /vipz command: {e}")
                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ An error occurred")

        if message.startswith("/modz") and (user.username in ownerz or user.username in self.mods or user.username == "B_L_A_C_K_7"):
            try:
                if self.mods:
                    message_content = "<#BA55D3>👑 Mods list:\n\n"
                    for idx, mod_name in enumerate(self.mods, start=1):
                        item = f"<#BA55D3>{idx}. {mod_name}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, message_content.strip())
                            message_content = item
                        else:
                            message_content += item
                    if message_content:
                        await self.highrise.send_whisper(user.id, message_content.strip())
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>📭 Mods list is empty")
            except Exception as e:
                print(f"Error in /modz command: {e}")
                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ An error occurred")

        if message == "/cmod":
            if user.username in ownerz:
                try:
                    self.mods.clear()
                    await self.highrise.send_whisper(user.id, "<#BA55D3>🗑️ Mod list cleared")
                except:
                    pass                
                
        if message.startswith("/ownerz"):
            try:
                if ownerz:
                    message_content = "<#BA55D3>👑 Owners list:\n\n"
                    for idx, name in enumerate(ownerz, start=1):
                        item = f"<#BA55D3>{idx}. {name}\n"
                        # Split messages to exceed 200 chars
                        if len(message_content) + len(item) > 200:
                            await self.highrise.send_whisper(user.id, message_content.strip())
                            message_content = item
                        else:
                            message_content += item

                    if message_content:
                        await self.highrise.send_whisper(user.id, message_content.strip())
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>📭 No owners currently")
            except Exception as e:
                print(f"Error in /owenrz command: {e}")
                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Error trying to execute command")

        # Command to display current prices
        if message.startswith("/prices") and user.username in ownerz:
            try:
                prices = load_prices()  # Refresh prices from file
                price_msg = "<#FF69B4>💰 **Current system prices:**\n\n"
                price_msg += f"🎫 Ticket price: {prices['ticket_price']} gold\n"
                price_msg += f"⚡ Ticket multiplier: {prices['ticket_multiplier']} tickets per {prices['ticket_price']} gold\n"
                price_msg += f"⭐ VIP price: {prices['vip_price']} gold\n"
                price_msg += f"📊 Minimum donation: {prices['min_donation']} gold\n"
                price_msg += f"📝 One gold message: {prices['gold_1_message']}"
                
                await self.highrise.send_whisper(user.id, price_msg)
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error displaying prices: {e}")

        # Command to modify ticket price
        if message.startswith("/setticketprice") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use: /setticketprice [number]")
                    return
                
                new_price = int(parts[1])
                if new_price <= 0:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Price must be greater than zero")
                    return
                
                prices = load_prices()
                prices['ticket_price'] = new_price
                save_prices(prices)
                
                await self.highrise.send_whisper(user.id, f"<#FF69B4>✅ Ticket price updated to: {new_price} gold")
            except ValueError:
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid number")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error updating price: {e}")

        # Command to modify ticket multiplier
        if message.startswith("/setticketmulti") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use: /setticketmulti [number]")
                    return
                
                new_multi = int(parts[1])
                if new_multi <= 0:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Multiplier must be greater than zero")
                    return
                
                prices = load_prices()
                prices['ticket_multiplier'] = new_multi
                save_prices(prices)
                
                await self.highrise.send_whisper(user.id, f"<#FF69B4>✅ Ticket multiplier updated to: {new_multi}")
            except ValueError:
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid number")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error updating multiplier: {e}")

        # Command to modify VIP price
        if message.startswith("/setvipprice") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use: /setvipprice [number]")
                    return
                
                new_price = int(parts[1])
                if new_price <= 0:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Price must be greater than zero")
                    return
                
                prices = load_prices()
                prices['vip_price'] = new_price
                save_prices(prices)
                
                await self.highrise.send_whisper(user.id, f"<#FF69B4>✅ VIP price updated to: {new_price} gold")
            except ValueError:
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid number")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error updating VIP price: {e}")

        # Command to modify minimum donation
        if message.startswith("/setmindonation") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use: /setmindonation [number]")
                    return
                
                new_min = int(parts[1])
                if new_min <= 0:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Minimum must be greater than zero")
                    return
                
                prices = load_prices()
                prices['min_donation'] = new_min
                save_prices(prices)
                
                await self.highrise.send_whisper(user.id, f"<#FF69B4>✅ Minimum donation updated to: {new_min} gold")
            except ValueError:
                await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid number")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error updating minimum: {e}")

        # Command to modify one gold message
        if message.startswith("/setgoldmessage") and user.username in ownerz:
            try:
                new_message = message.split("/setgoldmessage ", 1)[1].strip()
                if not new_message:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use: /setgoldmessage [message]")
                    return
                
                prices = load_prices()
                prices['gold_1_message'] = new_message
                save_prices(prices)
                
                await self.highrise.send_whisper(user.id, f"<#FF69B4>✅ One gold message updated")
            except Exception as e:
                await self.highrise.send_whisper(user.id, f"<#FF69B4>⚠️ Error updating message: {e}")

        if message.startswith("/idroom ") and user.username in ownerz:
            try:
                import json, re

                # Extract input from message
                user_input = message.split("/idroom ", 1)[1].strip()
                if not user_input:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use command like this: /idroom <room_id or link>")
                    return

                # 🔍 Extract room code from link if user sent link
                match = re.search(r"id=([a-zA-Z0-9]+)", user_input)
                if match:
                    new_room_id = match.group(1)
                else:
                    new_room_id = user_input  # User typed code directly

                # Validate code (usually around 24 chars)
                if not re.fullmatch(r"[a-zA-Z0-9]{20,32}", new_room_id):
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Invalid room code.")
                    return

                # Load and update config.json
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)

                config["room_id"] = new_room_id

                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)

                await self.highrise.send_whisper(user.id, f"<#ADFF2F>✅ Room code updated to: {new_room_id}")
                await self.highrise.send_whisper(user.id, "<#FFD700>🔄 Restart bot for changes to take effect.")

            except Exception as e:
                print(f"Error in /idroom command: {e}")
                await self.highrise.send_whisper(user.id, "<#FF0000>❌ Error changing room code.")

        # Block command
        if message.strip().startswith("/block") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "❌ Use: /block @username")
                    return
                
                target = parts[1].replace("@", "")
                
                if target in blocked_list:
                    await self.highrise.send_whisper(user.id, f"⚠️ User @{target} already blocked.")
                    return
                
                blocked_list.append(target)
                save_blocked(blocked_list)
                await self.highrise.chat(f"🚫 @{target} blocked successfully.")
            except:
                pass

        # Unblock command
        if message.strip().startswith("/unblock") and user.username in ownerz:
            try:
                parts = message.split()
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "❌ Use: /unblock @username")
                    return
                
                target = parts[1].replace("@", "")
                
                if target not in blocked_list:
                    await self.highrise.send_whisper(user.id, f"⚠️ User @{target} not blocked.")
                    return
                
                blocked_list.remove(target)
                save_blocked(blocked_list)
                await self.highrise.chat(f"✅ @{target} unblocked successfully.")
            except:
                pass

        # Command to show blocked users
        if message.strip().startswith("/sblocked") and user.username in ownerz:
            try:
                if not blocked_list:
                    await self.highrise.send_whisper(user.id, "📝 Block list is empty.")
                    return
                
                blocked_text = "🚫 Blocked users list:\n"
                for i, username in enumerate(blocked_list, 1):
                    blocked_text += f"{i}. @{username}\n"
                
                await self.highrise.send_whisper(user.id, blocked_text)
            except:
                await self.highrise.send_whisper(user.id, "⚠️ Error displaying block list.")

        if message.startswith("/idbot ") and user.username in ownerz:
            try:
                import json

                # Extract new token from message
                new_token = message.split("/idbot ", 1)[1].strip()
                if not new_token:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Use command like this: /idbot <bot_token>")
                    return

                # Load current settings
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)

                # Update token
                config["bot_token"] = new_token

                # Save file after modification
                with open("config.json", "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)

                # Send confirmation
                await self.highrise.send_whisper(user.id, f"<#ADFF2F>✅ Bot token updated to: {new_token}")
                await self.highrise.send_whisper(user.id, "<#FFD700>🔄 Restart bot for changes to take effect.")

            except Exception as e:
                print(f"Error in /idbot command: {e}")
                await self.highrise.send_whisper(user.id, "<#FF0000>❌ Error changing bot token.")
        
        if message.startswith("/remv ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                current_date = datetime.now().strftime("%d/%m/%Y")
                remvip = message.split(" ", 1)[1]
                rem = remvip.replace("@", "")
                if rem in vip_users:
                    vip_users.remove(rem)
                    await self.highrise.chat(f"<#BA55D3>🗑️ {remvip} removed from VIP")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"<#BA55D3>👤 User {remvip} removed from VIP on {current_date}\n<#BA55D3>🛠️ Removed by: @{user.username}")
                            await asyncio.sleep(1)
                        except Exception as e:
                            await self.highrise.chat(f"<#BA55D3>❌ Failed to send to {user_id}: {e}")
                else:
                    await self.highrise.send_whisper(user.id, f"<#BA55D3>❌ {rem} is not VIP")
            except:
                pass
                
        if message.startswith("/addv ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                current_date = datetime.now().strftime("%d/%m/%Y")
                vip = message.split(" ", 1)[1]
                allowed = vip.replace("@", "")
                if allowed not in vip_users:
                    vip_users.append(allowed)
                    await self.highrise.chat(f"<#BA55D3>✅ {vip} is now VIP")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"<#BA55D3>⭐ User {vip} became VIP on {current_date}\n<#BA55D3>🛠️ Added by: @{user.username}")
                            await asyncio.sleep(1)
                        except Exception as e:
                            await self.highrise.chat(f"<#BA55D3>❌ Failed to send to {user_id}: {e}")
                else:
                    await self.highrise.chat(f"<#BA55D3>ℹ️ {vip} is already VIP")
            except:
                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Not found")

        
        if message.startswith("/remm ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
                try:
                        parts = message.split(" ", 1)
                        if len(parts) < 2:
                                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Please specify a username.")
                                return

                        current_date = datetime.now().strftime("%d/%m/%Y")
                        remmod = parts[1].strip()
                        rem = remmod.replace("@", "")

                        if rem in self.mods:
                                self.mods.remove(rem)
                                save_mods(self.mods)

                                await self.highrise.chat(f"<#BA55D3>🗑️ {remmod} removed from mod")

                                for user_id in self.msg:
                                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                                        try:
                                                await self.highrise.send_message(
                                                        message_id,
                                                        f"<#BA55D3>👤 User {remmod} removed from mod on {current_date}\n"
                                                        f"<#BA55D3>🛠️ Removed by: @{user.username}"
                                                )
                                                await asyncio.sleep(1)
                                        except Exception as e:
                                                print(f"Failed sending to {user_id}: {e}")
                        else:
                                await self.highrise.send_whisper(user.id, f"<#BA55D3>❌ {rem} is not mod")

                except Exception as e:
                        print(f"Error in /remm: {e}")
                        await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Something went wrong.")


        if message.startswith("/addm ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
                try:
                        parts = message.split(" ", 1)
                        if len(parts) < 2:
                                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Please specify a username.")
                                return

                        current_date = datetime.now().strftime("%d/%m/%Y")
                        mod = parts[1].strip()
                        allowed = mod.replace("@", "")

                        if allowed not in self.mods:
                                self.mods.append(allowed)
                                save_mods(self.mods)

                                await self.highrise.chat(f"<#BA55D3>✅ {mod} is now mod")

                                for user_id in self.msg:
                                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                                        try:
                                                await self.highrise.send_message(
                                                        message_id,
                                                        f"<#BA55D3>⭐ User {mod} became play on {current_date}\n"
                                                        f"<#BA55D3>🛠️ Added by: @{user.username}"
                                                )
                                                await asyncio.sleep(1)
                                        except Exception as e:
                                                print(f"Failed sending to {user_id}: {e}")
                        else:
                                await self.highrise.chat(f"<#BA55D3>ℹ️ {mod} is already mod")

                except Exception as e:
                        print(f"Error in /addm: {e}")
                        await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Something went wrong.")        
        
        
        if message.startswith("/transfer"):
            try:
                _, username, value = message.split(" ", 2)
                username = username.strip("@")
                value = int(value)
                if not value >= 6:
                    await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Must transfer at least 6 tickets")
                else:
                    if user_ticket[user.username] >= value:
                        user_ticket[username] += value
                        user_ticket[user.username] -= value
                        await self.highrise.chat(f"<#FF69B4>💸 {value} tickets transferred to {username}")
                    else:
                        await self.highrise.send_whisper(user.id, "<#FF69B4>❌ Not enough tickets")
            except Exception as e:
                print(f"Error: {e}")

        if message.startswith("/give") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                _, username, value = message.split(" ", 2)
                username = username.strip("@")
                value = int(value)
                
                # Ensure user wallet exists, create if not
                if username not in user_ticket:
                    user_ticket[username] = 0
                
                # Set new value instead of adding
                user_ticket[username] = value
                
                if value == 1:
                    await self.highrise.chat(f"<#BA55D3>🎁 Tickets set to 1 for {username}")
                    return
                await self.highrise.chat(f"<#BA55D3>🎁 Tickets set to {value} for {username}")
            except Exception as e:
                print(f"Error: {e}")

        if message.startswith("/rfav ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            import os
            try:
                parts = message.split(" ")
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1]) - 1
                    if 0 <= index <= len(playlist):
                        removed_file = playlist[index]
                        rem_length = removed_file.get('audio_length', '🕒 Unknown')
                        fix_rem = removed_file.get('title', '❌ Unknown')
                        file_path = removed_file.get('url', '')
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            playlist.pop(index)
                            await self.highrise.chat(f"<#BA55D3>🗑️ Removed from favorites:\n<#BA55D3>{fix_rem}")
                    else:
                        await self.highrise.send_whisper(user.id, f"<#BA55D3>❌ No song at position {get_ordinal(parts[1])}")
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Type song number to delete")
            except Exception as e:
                print(f"Error in /rfav command: {e}")
                await self.highrise.send_whisper(user.id, f"<#BA55D3>❌ Error: {e}")

        if message.startswith("/flist"):
            try: 
                if playlist: 
                    message_content = "<#BA55D3>⭐ Favorites list:\n\n"
                    for idx, file in enumerate(list(playlist), start=1):
                        item = f"<#BA55D3>{idx}. {file['title']}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, message_content.strip())
                            message_content = item
                        else:
                            message_content += item
                    if message_content:
                        await self.highrise.send_whisper(user.id, message_content.strip())
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>📭 Favorites list is empty")
            except Exception as e:
                print(f"Error in /flist command: {e}")
                await self.highrise.send_whisper(user.id, "<#BA55D3>❌ An error occurred")

        if message.strip() == "/fav" and (user.username in ownerz or user.username in self.mods or user.username == "B_L_A_C_K_7"):
            try:
                # Import libraries here to avoid scope issues
                import os
                import shutil
                
                
                # Ensure favorites folder exists
                if not os.path.exists(self.fav_dir):
                    os.makedirs(self.fav_dir)
                    print(f"[fav] Created favorites folder: {self.fav_dir}")
                
                if self.now:
                    current = self.now[0]
                    
                    # Ensure original file exists
                    if not os.path.exists(current['url']):
                        await self.highrise.chat(f"<#BA55D3>⚠️ File {current['title']} not found")
                        return
                    
                    # Check duplicates using full path
                    if any(item['url'] == current['url'] for item in playlist):
                        await self.highrise.chat(f"<#BA55D3>ℹ️ {current['title']} already in favorites")
                        return
                    
                    if current['url'] in AUDIO_FILES:
                        await self.highrise.send_whisper(user.id, "<#BA55D3>❌ You can only add requested songs to favorites")
                        return
                    
                    # Clean title to be safe filename
                    safe_title = "".join(c for c in current['title'] if c.isalnum() or c in " _-").strip()
                    if not safe_title:
                        safe_title = f"audio_{int(time.time())}"
                    
                    dest_file = os.path.join(self.fav_dir, f"{safe_title}.mp3")
                    
                    # Ensure no file with same name
                    counter = 1
                    while os.path.exists(dest_file):
                        dest_file = os.path.join(self.fav_dir, f"{safe_title}_{counter}.mp3")
                        counter += 1
                    
                    try:
                        # Copy file
                        print(f"[fav] Copying from {current['url']} to {dest_file}")
                        shutil.copy2(current['url'], dest_file)
                        print(f"[fav] Copied successfully to {dest_file}")
                        
                    except PermissionError:
                        await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Cannot write to favorites folder (permission issue)")
                        return
                    except Exception as e:
                        print(f"[fav] Copy failed: {e}")
                        await self.highrise.send_whisper(user.id, f"<#BA55D3>⚠️ Problem copying file: {str(e)}")
                        return
                    
                    # Add to favorites
                    fav_entry = current.copy()
                    fav_entry['url'] = dest_file
                    playlist.append(fav_entry)
                    
                    await self.highrise.chat(f"<#BA55D3>✅ {current['title']} added to favorites")
                else:
                    await self.highrise.chat("<#BA55D3>❌ No song currently playing")
            except Exception as e:
                print(f"[fav] error: {e}")
                import traceback
                traceback.print_exc()
                await self.highrise.send_whisper(user.id, f"<#BA55D3>⚠️ An error occurred: {str(e)}")

        if message.startswith("/mfav") and user.username in ownerz:
            import os
            try:
                parts = message.split()
                if len(parts) < 2 or not parts[1].isdigit():
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Use: /mfav <number>")
                    return

                index = int(parts[1]) - 1

                if not playlist or index < 0 or index >= len(playlist):
                    await self.highrise.send_whisper(user.id, "<#BA55D3>⚠️ Invalid favorite number")
                    return

                fav_song = playlist[index]

                queued_song = {
                    'url': fav_song['url'],
                    'title': fav_song.get('title', os.path.basename(fav_song['url'])),
                    'user': user.username,
                    'duration': fav_song.get('audio_length', "🕒 Unknown")
                }

                self.req_files.append(queued_song)

                await self.highrise.chat(
                    f"<#BA55D3>🎵 Added to queue from favorites:\n<#BA55D3>{fav_song['title']}\n<#BA55D3>👤 By: @{user.username}"
                )

            except Exception as e:
                print(f"Error in /fav command: {e}")
                await self.highrise.send_whisper(user.id, "<#BA55D3>⚠️ Cannot add favorite to queue")

        if message.startswith("/cfav"):
            import os
            try:
                if user.username in ownerz or user.username == "B_L_A_C_K_7":
                    if playlist and len(playlist) > 0:
                        deleted_count = 0
                        not_found_count = 0
                        error_count = 0
                        file_list = []
                        
                        # First: collect file info
                        for item in playlist:
                            if 'url' in item:
                                file_path = item['url']
                                file_list.append(file_path)
                                
                                # Convert path if it contains ~ for current user
                                file_path = os.path.expanduser(file_path) if '~' in file_path else file_path
                                
                                if os.path.exists(file_path):
                                    try:
                                        os.remove(file_path)
                                        deleted_count += 1
                                        print(f"✓ Deleted: {file_path}")
                                    except Exception as e:
                                        error_count += 1
                                        print(f"✗ Error deleting {file_path}: {e}")
                                else:
                                    not_found_count += 1
                                    print(f"⚠ File not found: {file_path}")
                        
                        # Second: clear playlist
                        playlist.clear()
                        
                        # Third: save changes to file
                        try:
                            with open('playlist.json', 'w', encoding='utf-8') as f:
                                json.dump(playlist, f, ensure_ascii=False, indent=2)
                            print("✓ Saved playlist.json")
                        except Exception as e:
                            print(f"✗ Error saving file: {e}")
                        
                        # Fourth: send report
                        if deleted_count > 0:
                            report_msg = f"<#BA55D3>✅ Favorites list cleared\n"
                            report_msg += f"<#BA55D3>📊 Report:\n"
                            report_msg += f"<#BA55D3>• Files deleted: {deleted_count}\n"
                            report_msg += f"<#BA55D3>• Files not found: {not_found_count}\n"
                            report_msg += f"<#BA55D3>• Errors: {error_count}"
                        else:
                            report_msg = f"<#BA55D3>⚠️ No files deleted\n"
                            report_msg += f"<#BA55D3>• Files not found: {not_found_count}\n"
                            report_msg += f"<#BA55D3>• Errors: {error_count}"
                        
                        await self.highrise.chat(report_msg)
                        
                        # Print report to console
                        print(f"\n{'='*50}")
                        print(f"Favorites deletion report:")
                        print(f"- Files deleted: {deleted_count}")
                        print(f"- Not found: {not_found_count}")
                        print(f"- Errors: {error_count}")
                        print(f"{'='*50}\n")
                        
                    else:
                        await self.highrise.chat("<#BA55D3>📭 Favorites list already empty")
                else:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ No permission to use this command")
        
            except NameError:
                # If os not defined
                print("Error: os library not imported")
                await self.highrise.chat("<#BA55D3>❌ System error: incomplete libraries")
            except Exception as e:
                print(f"Error in /cfav command: {e}")
                traceback.print_exc()
                await self.highrise.chat("<#BA55D3>❌ Error during cleanup")

        if message.startswith("/cmsg") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                if msg:
                    msg.clear()
                    await self.highrise.chat("<#BA55D3>🗑️ Messages list cleared")
                else:
                    await self.highrise.chat("<#BA55D3>📭 Messages list already empty")
            except Exception as e:
                print(f"Error in /cmsg:", e)

        if message.startswith("/rmsg ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                user_msg = message.split(" ", 1)[1]
                username = user_msg.replace("@", "")
                room_users = (await self.highrise.get_room_users()).content
                user_id = None
                for room_user in room_users:
                    if room_user[0].username.lower() == username.lower():
                        user_id = room_user[0].id
                        break
                if user_id is None:
                    await self.highrise.send_whisper(user.id,"<#BA55D3>❌ User not in room")
                    return
                if user_id in msg:
                    msg.remove(user_id)
                    await self.highrise.chat(f"<#BA55D3>🗑️ User @{username} removed from messages list")
                else:
                    await self.highrise.chat("<#BA55D3>ℹ️ User not in list")
            except Exception as e:
                print(f"Error in /rmsg:", e)

        if message.startswith("/msg ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                user_msg = message.split(" ", 1)[1]
                username = user_msg.replace("@", "")
                room_users = (await self.highrise.get_room_users()).content
                user_id = None
                for room_user in room_users:
                    if room_user[0].username.lower() == username.lower():
                        user_id = room_user[0].id
                        break
                if user_id is None:
                    await self.highrise.send_whisper(user.id,"<#BA55D3>❌ User not in room")
                    return
                if user_id not in msg:
                    msg.append(user_id)
                    await self.highrise.chat(f"<#BA55D3>✅ User @{username} added to messages list")
                else:
                    await self.highrise.chat("<#BA55D3>ℹ️ User already in list")
            except Exception as e:
                print(f"Error in /msg:", e)

        if message.startswith("/res ") and user.username in ownerz:
            try:    
                res = message.split(" ", 1)[1]
                if not res in restrict:
                    restrict.append(res)
                    await self.highrise.chat("<#BA55D3>🚫 This song added to ban list")
                else:
                    await self.highrise.chat("<#BA55D3>ℹ️ This song already banned")
            except Exception as e:
                print(f"Error in /restrict command: {e}")
                
        if message.startswith("/unres ") and user.username in ownerz:
            try:    
                res = message.split(" ", 1)[1]
                if res in restrict:
                    restrict.remove(res)
                    await self.highrise.chat("<#BA55D3>✅ This song removed from ban list")
                else:
                    await self.highrise.chat("<#BA55D3>ℹ️ This song not banned")
            except Exception as e:
                print(f"Error in /unrestrict command: {e}")

        if message.startswith("/promo ") and user.username in ownerz:
            try:    
                prom = message.lstrip("/promo ").strip()
                if prom:
                    if prom not in promo:
                        promo.append(prom)
                        await self.highrise.chat("<#BA55D3>📢 Message added to promotions list")
                    else:
                        await self.highrise.chat("<#BA55D3>ℹ️ Message already in list")
                else:
                    await self.highrise.chat("<#BA55D3>❌ Type promotion message after /promo")
            except Exception as e:
                print(f"Error in /promo command: {e}")
                
        if message.startswith("/rpromo ") and user.username in ownerz:
            try:    
                prom = message.lstrip("/promo ").strip()
                if prom:
                    if prom in promo:
                        promo.remove(prom)
                        await self.highrise.chat("<#BA55D3>🗑️ Message removed from promotions list")
                    else:
                        await self.highrise.chat("<#BA55D3>ℹ️ Message not in list")
                else:
                    await self.highrise.chat("<#BA55D3>❌ Type promotion message after /promo")
            except Exception as e:
                print(f"Error in /rpromo command: {e}")

        if message.startswith("/cpromo"):
            try:
                if user.username == "B_L_A_C_K_7" or user.username in ownerz:
                    if promo:
                        promo.clear()
                        await self.highrise.chat("<#BA55D3>🗑️ Promotions list cleared")
                    else:
                        await self.highrise.chat("<#BA55D3>📭 Promotions list already empty")
                else:
                    pass
            except:
                pass

        if message.startswith("/accs") and user.username in ownerz:
            try:
                total = len(user_ticket)
                empty = {key: value for key, value in user_ticket.items() if value == 0}
                active = {key: value for key, value in user_ticket.items() if value > 0 and value != 3}
                total_empty = len(empty)
                total_active = len(active)
                await self.highrise.chat(f"<#BA55D3>📊 Account statistics:\n\n"
                                f"<#BA55D3>• 👥 Total users: {total}\n"
                                f"<#BA55D3>• ✅ Active accounts: {total_active}\n"
                                f"<#BA55D3>• ❌ Zero balance: {total_empty}")
            except Exception as e:
                print("Error in /accs:", e)

        if message.startswith("/withdraw ") and (user.username in ownerz or user.username == "B_L_A_C_K_7"):
            try:
                parts = message.split(" ")
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Use: /withdraw [number]")
                    return
                try:
                    amount = int(parts[1])
                except:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ Don't use fractions, use whole numbers")
                    return
                bot_wallet = await self.highrise.get_wallet()
                bot_amount = bot_wallet.content[0].amount
                if bot_amount <= amount:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ I don't have enough balance")
                    return
                bars_dictionary = {10000: "gold_bar_10k", 
                                5000: "gold_bar_5000",
                                1000: "gold_bar_1k",
                                500: "gold_bar_500",
                                100: "gold_bar_100",
                                50: "gold_bar_50",
                                10: "gold_bar_10",
                                5: "gold_bar_5",
                                1: "gold_bar_1"}
                fees_dictionary = {10000: 1000,
                                5000: 500,
                                1000: 100,
                                500: 50,
                                100: 10,
                                50: 5,
                                10: 1,
                                5: 1,
                                1: 1}
                tip = []
                total = 0
                for bar in bars_dictionary:
                    if amount >= bar:
                        bar_amount = amount // bar
                        amount = amount % bar
                        for i in range(bar_amount):
                            tip.append(bars_dictionary[bar])
                            total = bar+fees_dictionary[bar]
                if total > bot_amount:
                    await self.highrise.send_whisper(user.id, "<#BA55D3>❌ I don't have enough money")
                    return
                tip_string = ",".join(tip)
                await self.highrise.tip_user(user.id, tip_string)
            except Exception as e:
                print("Error in /withdraw:", e)

        if message == "/setbot" and user.username in ownerz:
            try:
                room_users = await self.highrise.get_room_users()
                for room_user, pos in room_users.content:
                    if room_user.username == user.username:
                        bot_location["x"] = pos.x
                        bot_location["y"] = pos.y
                        bot_location["z"] = pos.z
                        bot_location["facing"] = pos.facing
                        await self.highrise.send_whisper(user.id, f"<#BA55D3>📍 Bot location updated to {bot_location}")
                        break
            except Exception as e:
                print("Set bot:", e)

        if message == "/base" and user.username in ownerz:
            try:
                if bot_location:
                    await self.highrise.walk_to(Position(**bot_location))
            except Exception as e:
                print("Error in /base:", e)

        if message.startswith("/bwallet"):
            try:
                await self.bot_wallet(user, message)
            

            except Exception as e:
               print("[on_chat]", e)            
    
    async def bot_wallet(self, user: User, message: str):
        if user.username in ownerz or user.username == "B_L_A_C_K_7":
            wallet = await self.highrise.get_wallet()
            for item in wallet.content:
                if item.type == "gold":
                    gold = item.amount
                    await self.highrise.send_whisper(user.id, f"<#BA55D3>💰 My current balance: {gold} gold!")
                    return
            await self.highrise.send_whisper(user.id, f"<#BA55D3>👋 Hello, {user.username}! I have no gold")
        else:
            await self.highrise.send_whisper(user.id, "<#BA55D3>❌ No permission to use this command")
    
    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
     try:
        import json
        import asyncio
        from datetime import datetime

        HISTORY_FILE = "history.json"

        # 🔒 Prevent repeated transactions for same user within second
        current_time = time.time()
        if sender.id in self.last_tip_time:
            if current_time - self.last_tip_time[sender.id] < 1:
                return
        self.last_tip_time[sender.id] = current_time
        
        # 🔒 Use lock to prevent conflicts
        with self.data_lock:
            # ================= Load history =================
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            except:
                history_data = {}

            def save_history(username: str, amount: int, action_type: str):
                now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                if username not in history_data:
                    history_data[username] = {
                        "total_spent": 0,
                        "history": []
                    }

                history_data[username]["total_spent"] += amount

                history_data[username]["history"].insert(0, {
                    "amount": amount,
                    "type": action_type,
                    "date": now
                })

                # Keep only last 10 operations
                history_data[username]["history"] = history_data[username]["history"][:10]

                try:
                    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                        f.write(json.dumps(history_data, ensure_ascii=False))
                except Exception as e:
                    print("❌ Error saving history.json:", e)

            # ================= Load data =================
            global user_ticket, vip_users
            from HRDB import user_ticket as hr_user_ticket, vip_users as hr_vip_users

            # Load current data directly from files
            try:
                with open('user_ticket.json', 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    current_tickets = json.loads(content) if content else {}
            except:
                current_tickets = {}
                
            try:
                with open('vip_users.json', 'r', encoding='utf-8') as f:
                    current_vip = json.load(f)
            except:
                current_vip = []

            if not tip or not hasattr(tip, "amount") or tip.amount is None:
                return

            if not sender or not receiver:
                return

            if receiver.username != self.username:
                return

            amount = int(tip.amount)
            sender_name = sender.username

            if sender_name is None:
                return

            # ================= 1 gold =================
            if amount == 1:
                save_history(sender_name, amount, "1_GOLD")
                if sender_name in current_vip:
                    await self.highrise.send_whisper(sender.id, "<#FF69B4>⭐ You're VIP, my friend.")
                else:
                    await self.highrise.send_whisper(sender.id, f"<#FF69B4>❌ {prices['gold_1_message']}")
                return

            # ================= VIP =================
            if amount == prices['vip_price']:
                save_history(sender_name, amount, "VIP")

                current_date = datetime.now().strftime("%d/%m/%Y")
                day = datetime.now().strftime("%d")

                if sender_name not in current_vip:
                    current_vip.append(sender_name)
                    hr_vip_users.append(sender_name)

                    with open('vip_users.json', 'w', encoding='utf-8') as f:
                        json.dump(current_vip, f, ensure_ascii=False)

                    await self.highrise.send_whisper(
                        sender.id,
                        "<#FF69B4>⭐ Congrats! You're now VIP 🎉"
                    )
                else:
                    await self.highrise.send_whisper(
                        sender.id,
                        "<#FF69B4>⭐ VIP renewed! Thank you!"
                    )
                return

            # ================= Tickets =================
            if amount % prices['ticket_price'] == 0 and amount >= prices['min_donation']:
                tickets = (amount // prices['ticket_price']) * prices['ticket_multiplier']

                save_history(sender_name, amount, "TICKETS")

                old_tickets = current_tickets.get(sender_name, 0)
                new_tickets = old_tickets + tickets
                current_tickets[sender_name] = new_tickets
                hr_user_ticket[sender_name] = new_tickets

                with open('user_ticket.json', 'w', encoding='utf-8') as f:
                    json.dump(current_tickets, f, ensure_ascii=False)

                await self.highrise.chat(
                    f"<#FF69B4>🎉 @{sender_name} got {tickets} tickets!"
                )
                await self.highrise.send_whisper(
                    sender.id,
                    f"<#FF69B4>💰 Your balance now: {current_tickets[sender_name]}"
                )
                return

            # ================= Less than minimum =================
            save_history(sender_name, amount, "INVALID_AMOUNT")
            await self.highrise.send_whisper(
                sender.id,
                f"<#FF69B4>⚠️ Minimum is {prices['min_donation']} gold."
            )

     except Exception as e:
        print("Error on_tip:", e)
        try:
            await self.highrise.send_whisper(
                sender.id,
                "<#FF69B4>❌ Unexpected error occurred.\n📩 Report to @B_L_A_C_K_7."
            )
        except:
            pass


    async def save_data_periodically(self):
        """Periodic data saving with memory cleanup"""
        import asyncio
        while True:
            try:
                with self.data_lock:
                    from HRDB import user_ticket as hr_user_ticket, vip_users as hr_vip_users
                    
                    try:
                        with open('user_ticket.json', 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            file_tickets = json.loads(content) if content else {}
                    except:
                        file_tickets = {}
                    
                    try:
                        with open('vip_users.json', 'r', encoding='utf-8') as f:
                            file_vip = json.load(f)
                    except:
                        file_vip = []
                    
                    merged_tickets = {**file_tickets, **hr_user_ticket}
                    merged_vip = list(set(file_vip + hr_vip_users))
                    
                    with open('user_ticket.json', 'w', encoding='utf-8') as f:
                        json.dump(merged_tickets, f, ensure_ascii=False)
                    
                    with open('vip_users.json', 'w', encoding='utf-8') as f:
                        json.dump(merged_vip, f, ensure_ascii=False)
                    
                    hr_user_ticket.clear()
                    hr_user_ticket.update(merged_tickets)
                    
                    hr_vip_users.clear()
                    hr_vip_users.extend(merged_vip)
                    
                    # Memory cleanup after saving
                    gc.collect()
                    
                    print(f"✅ Periodic save completed: {len(merged_tickets)} users, {len(merged_vip)} VIP")
                    
                await asyncio.sleep(300)
            except Exception as e:
                print(f"❌ Periodic save error: {e}")
                await asyncio.sleep(60)

    def stream_audio(sock, audio_file, bot_instance):
      process = None
      try:
        # Make path absolute for checking
        if not os.path.isabs(audio_file) and hasattr(bot_instance, 'req_files_dir'):
            audio_file = os.path.join(bot_instance.req_files_dir, os.path.basename(audio_file))
        
        print(f"Streaming audio file: {audio_file}")
        
        bot_instance.now.clear()
        bot_instance.message.clear()

        if bot_instance.req_files and audio_file == bot_instance.req_files[0]['url']:
            current_song = bot_instance.req_files[0]
            bot_instance.now.append({
                'url': current_song.get('url'),
                'title': current_song.get('title', 'Unknown'),
                'user': current_song.get('user'),
                'audio_length': current_song.get('duration')
            })
            bot_instance.message.append(bot_instance.now[0])
            bot_instance.current_song = bot_instance.now[0]["title"]
        else:
            found = False
            for item in playlist:
                item_path = item.get('url', '')
                if not os.path.isabs(item_path):
                    item_path = os.path.join(bot_instance.req_files_dir, os.path.basename(item_path))
                
                if item_path == audio_file:
                    bot_instance.now.append({
                        'url': item.get('url'),
                        'title': item.get('title', 'Unknown'),
                        'user': item.get('user'),
                        'audio_length': item.get('audio_length') or item.get('duration') or bot_instance.get_audio_length(item.get('url')) or '🕒 Unknown'
                    })
                    bot_instance.current_song = bot_instance.now[0]["title"]
                    bot_instance.message.append(bot_instance.now[0])
                    found = True
                    break

            if not found and audio_file in AUDIO_FILES:
                bot_instance.now.append({
                    'url': audio_file,
                    'title': os.path.basename(audio_file),
                    'user': None,
                    'audio_length': bot_instance.get_audio_length(audio_file) or '0:00'
                })
                bot_instance.message.append(bot_instance.now[0])
                bot_instance.current_song = bot_instance.now[0]["title"]

        command = [
            'ffmpeg',
            '-re',
            '-i', audio_file,
            '-vn',
            '-c:a', 'libmp3lame',
            '-ar', '44100',
            '-b:a', bot_instance.bitrate,
            '-bufsize', '512k',
            '-flush_packets', '1',
            '-fflags', '+genpts',
            '-avoid_negative_ts', 'make_zero',
            '-f', 'mp3',
            '-'
        ]



        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        time.sleep(0.5)
        
        while True:

            if bot_instance.skip:
                print("⏭ Skip executed")
                bot_instance.skip = False
                break

            data = process.stdout.read(8192)

            if not data:
                break

            sock.sendall(data)

        return True

      except Exception as e:
        print(f"Stream error: {e}")
        return False

      finally:
        # Intensive cleanup
        try:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            # Memory cleanup
            gc.collect()
            
        except Exception as e:
            print(f"<#FFD580>[STREAM_CLEANUP] Error: {e}")

        # Remove song from queue after playing
        if bot_instance.req_files and audio_file == bot_instance.req_files[0]['url']:
            played_item = bot_instance.req_files.popleft()
            
            # Delete file only if not in favorites
            is_in_fav = any(item.get('url') == played_item.get('url') for item in playlist)
            
            file_to_delete = played_item.get('url', '')
            if (os.path.exists(file_to_delete) and 
                file_to_delete not in AUDIO_FILES and 
                not file_to_delete.startswith(bot_instance.fav_dir) and
                not is_in_fav):
                try:
                    os.remove(file_to_delete)
                    print(f"<#FFD580>[Cleanup] File deleted after playback: {os.path.basename(file_to_delete)}")
                except Exception as e:
                    print(f"⚠️ Failed to delete {file_to_delete}: {e}")
                    
                    
        bot_instance.current_song = None
        bot_instance.current_artist = None   
        bot_instance.now.clear()
        bot_instance.message.clear()
        gc.collect()


    async def download_chunk(self, session, url, start, end, queue):
        headers = {'Range': f'bytes={start}-{end}'}
        async with session.get(url, headers=headers) as response:
            if response.status not in [206, 200]:
                print(f"Failed to download part: {response.status}")
                await queue.put(None)
                return
            chunk = await response.content.read()
            await queue.put((start, chunk))

    async def download_audio(self, session, audio_url, download_queue):
        retries = 3
        for attempt in range(retries):
            async with session.head(audio_url) as response:
                if response.status == 302:
                    audio_url = response.headers['Location']
                    continue
                if response.status != 200:
                    print(f"Failed to get audio info: {response.status}")
                    await download_queue.put(None)
                    return
                break
            asyncio.sleep(1)
        else:
            print("Failed to get audio info after attempts")
            await download_queue.put(None)
            return

        total_size = int(response.headers.get('Content-Length'))
        chunk_size = total_size // 4

        tasks = []
        for i in range(4):
            start = i * chunk_size
            end = (i + 1) * chunk_size - 1 if i != 3 else total_size - 1
            tasks.append(self.download_chunk(session, audio_url, start, end, download_queue))

        await asyncio.gather(*tasks)
        await download_queue.put(None)

    async def write_audio(self, temp_file_path, download_queue, buffer_queue):
        buffer_size = 10 * 1024 * 1024

        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            while True:
                item = await download_queue.get()
                if item is None:
                    break
                start, chunk = item
                await temp_file.seek(start)
                await temp_file.write(chunk)
                await buffer_queue.put(chunk)
                download_queue.task_done()
            await buffer_queue.put(None)

    async def buffer_audio(self, audio_url):
        async with aiohttp.ClientSession() as session:
            try:
                os.makedirs(self.req_files_dir, exist_ok=True)
                temp_file_path = os.path.join(self.req_files_dir, f"{int(time.time())}_{random.randint(1000,9999)}.mp3")

                download_queue = asyncio.Queue()
                buffer_queue = asyncio.Queue()

                download_task = asyncio.create_task(self.download_audio(session, audio_url, download_queue))
                write_task = asyncio.create_task(self.write_audio(temp_file_path, download_queue, buffer_queue))

                await asyncio.gather(download_task, write_task)
                return temp_file_path

            except Exception as e:
                print(f"Buffer error: {e}")
                return None

    async def search_track(self, query, user):
    
      session = None
      try:
        import yt_dlp
        import os, asyncio, traceback, json, random, time, gc, re
        from rapidfuzz import fuzz

        gc.collect()

        # ================= Settings =================
        MIN_DURATION = 60
        MAX_DURATION = 600
        MAX_FILE_SIZE = 100 * 1024 * 1024
        SETTINGS_FILE = "settings.json"

        output_dir = self.req_files_dir
        os.makedirs(output_dir, exist_ok=True)

        # ================= File cleanup =================
        self.memory_manager.cleanup_directory(output_dir)

        # ================= Load settings =================
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"source": "youtube"}, f)

        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)

        source = settings.get("source", "youtube")

        # ================= URL detection =================
        is_url = re.match(r"https?://", query.strip()) is not None
        if is_url:
            source = "youtube"

        await self.highrise.send_whisper(
            user.id,
            f"<#FFD580>🎧 Searching: {query}\n📡 Source: {source}"
        )

        loop = asyncio.get_event_loop()
        temp_file = None
        last_error = None

        # ================= Two attempts (YT -> SC) =================
        for attempt in range(2):
            try:
                # ==================================================
                #                   YOUTUBE
                # ==================================================
                if source == "youtube":
                    filename_prefix = f"yt_{int(time.time())}_{random.randint(1000,9999)}"
                    ua = random.choice(YAGENTS)

                    ydl_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "format": "bestaudio[ext=m4a]/bestaudio/best",
                        "outtmpl": os.path.join(output_dir, f"{filename_prefix}.%(ext)s"),
                        "noprogress": True,
                        "no_color": True,
                        "socket_timeout": 20,
                        "merge_output_format": "m4a",

                        # 403 solution
                        "extractor_args": {
                            "youtube": {
                                "player_client": ["android"],
                                "skip": ["hls", "dash"]
                            }
                        },

                        "http_headers": {
                            "User-Agent": ua,
                            "Accept-Language": "en-US,en;q=0.9",
                            "Referer": "https://www.youtube.com/",
                        },
                    }

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = await loop.run_in_executor(
                            None,
                            lambda: ydl.extract_info(
                                query if is_url else f"ytsearch10:{query}",
                                download=True
                            )
                        )

                    
                    if not is_url and isinstance(info, dict) and info.get("entries"):
                        entries = info.get("entries", [])

                        # فلترة النتائج
                        filtered = [
                            e for e in entries
                            if e
                            and not e.get("is_live")
                            and "topic" not in (e.get("channel", "").lower())
                        ]

                        query_clean = query.lower()

                        pool = filtered if filtered else entries

                        def score(e):
                            title = (e.get("title") or "").lower()
                            uploader = (e.get("uploader") or "").lower()
                            channel = (e.get("channel") or "").lower()

                            title_score = fuzz.token_set_ratio(query_clean, title)
                            uploader_score = fuzz.token_set_ratio(query_clean, uploader)
                            channel_score = fuzz.token_set_ratio(query_clean, channel)

                            return (
                                title_score * 5
                                + max(uploader_score, channel_score) * 3
                                + min((e.get("view_count") or 0) // 1000000, 100)
                            )

                        info = max(pool, key=score, default=None)


                    if not info:
                        raise Exception("NO_RESULT")

                    channel = (info.get("channel") or "").lower()

                    if (
                        "topic" in channel
                        or "provided to youtube" in channel
                        or "youtube music" in channel
                    ):
                        raise Exception("YOUTUBE_TOPIC")

                    if info.get("is_live"):
                        raise Exception("LIVE_STREAM")

                    duration = int(info.get("duration") or 0)
                    if duration < MIN_DURATION:
                        raise Exception("TOO_SHORT")
                    if duration > MAX_DURATION:
                        raise Exception("TOO_LONG")

                    ext = info.get("ext", "m4a")
                    video_id = info.get("id", filename_prefix)
                    title = info.get("title", "Unknown")
                    uploader = info.get("uploader", "Unknown")

                    for f in os.listdir(output_dir):
                        if f.startswith(filename_prefix):
                            temp_file = os.path.join(output_dir, f)
                            new_name = os.path.join(
                                output_dir,
                                f"{video_id}_{random.randint(1000,9999)}.{ext}"
                            )
                            os.rename(temp_file, new_name)
                            temp_file = new_name
                            break

                # ==================================================
                #                SOUNDCLOUD (real)
                # ==================================================
                elif source == "soundcloud":
                    filename_prefix = f"sc_{int(time.time())}_{random.randint(1000,9999)}"

                    ydl_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "format": "bestaudio/best",
                        "outtmpl": os.path.join(output_dir, f"{filename_prefix}.%(ext)s"),
                        "noprogress": True,
                        "socket_timeout": 20,
                    }

                    if is_url:

                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = await loop.run_in_executor(
                                None,
                                lambda: ydl.extract_info(
                                    query,
                                    download=True
                                )
                            )

                    else:

                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            search = await loop.run_in_executor(
                                None,
                                lambda: ydl.extract_info(
                                    f"ytsearch30:{query}",
                                    download=False
                                )
                            )

                        entries = search.get("entries") or []

                    if not is_url and info.get("entries"):
                        info = info["entries"][0]

                    if not info:
                        raise Exception("NO_RESULT")

                    duration = int(info.get("duration") or 0)
                    if duration < MIN_DURATION:
                        raise Exception("TOO_SHORT")
                    if duration > MAX_DURATION:
                        raise Exception("TOO_LONG")

                    ext = info.get("ext", "mp3")
                    track_id = info.get("id", filename_prefix)
                    title = info.get("title", "Unknown")
                    uploader = info.get("uploader", "Unknown")

                    for f in os.listdir(output_dir):
                        if f.startswith(filename_prefix):
                            temp_file = os.path.join(output_dir, f)
                            new_name = os.path.join(
                                output_dir,
                                f"{track_id}_{random.randint(1000,9999)}.{ext}"
                            )
                            os.rename(temp_file, new_name)
                            temp_file = new_name
                            break

                # ==================================================
                #               Common checks
                # ==================================================
                if not temp_file or not os.path.exists(temp_file):
                    raise Exception("FILE_NOT_CREATED")

                file_size = os.path.getsize(temp_file)
                if file_size > MAX_FILE_SIZE:
                    os.remove(temp_file)
                    raise Exception("FILE_TOO_LARGE")

                mins, secs = divmod(duration, 60)
                self.memory_manager.register_temp_file(temp_file)

                await self.highrise.send_whisper(
                    user.id,
                    f"<#90EE90>✔ Download completed ({source})\n"
                    f"🎵 {title}\n🎤 {uploader}\n"
                    f"⏱️ {mins}:{secs:02d}"
                )

                gc.collect()
                track_id_value = (info or {}).get("id") or filename_prefix
                self.current_song = title
                self.current_artist = uploader
                self.current_duration = f"{mins}:{secs:02d}" 
                return temp_file, f"{mins}:{secs:02d}", {
                    "id": track_id_value,
                    "title": title,
                    "uploader": uploader,
                    "source": source
                }

            except Exception as e:
                last_error = str(e)
                print(f"[Attempt {attempt+1} failed] {last_error}")

                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass

                if attempt == 0 and source == "youtube":
                    source = "soundcloud"
                    continue
                break

        # ================= Failure message =================
        error_messages = {
            "NO_RESULT": "❌ No results found.",
            "YOUTUBE_TOPIC": "🎵 This song is from YouTube Music Topic and not supported.",
            "LIVE_STREAM": "📺 This is a live stream and cannot be played.",
            "TOO_SHORT": "⏱️ Song duration too short.",
            "TOO_LONG": "⏱️ Song duration too long.",
            "FILE_TOO_LARGE": "📦 Song file size larger than allowed.",
            "FILE_NOT_CREATED": "⬇️ Failed to download audio file.",
        }

        user_reason = error_messages.get(
            last_error,
            f"❌ Failed to play song.\n📄 Reason: {last_error}"
        )

        await self.highrise.send_whisper(user.id, f"<#FF69B4>{user_reason}")
        return None, "FAILED", None

      except Exception:
        print("[General search error]")
        print(traceback.format_exc())
        gc.collect()
        return None, "FAILED", None



    async def add_to_queue(self, query, user):
     """Add song to queue with improved memory management"""
     try:
        # Clean memory before adding
        gc.collect()

        # ================= Favorite by number =================
        if query.lower().startswith("fav "):
            try:
                fav_number = int(query.split()[1]) - 1

                if fav_number < 0 or fav_number >= len(playlist):
                    await self.highrise.send_whisper(
                        user.id,
                        "<#FF69B4>❌ Favorite number not found."
                    )
                    return

                fav = playlist[fav_number]

                new_item = {
                    "url": fav["url"],
                    "title": fav.get("title", "Unknown"),
                    "uploader": fav.get("uploader", "Unknown"),
                    "duration": fav.get("audio_length") or fav.get("duration", "Unknown"),
                    "user": user.username,
                }

                self.req_files.append(new_item)

                await self.highrise.chat(
                    f"<#FF69B4>⭐ Added favorite #{fav_number + 1} to queue:\n"
                    f"<#FF69B4>🎵 {new_item['title']}"
                )

                return

            except (ValueError, IndexError):
                await self.highrise.send_whisper(
                    user.id,
                    "<#FF69B4>❌ Usage: /play fav 5"
                )
                return

        buffered_file_path, track_duration, track = await self.search_track(query, user)

        # ❌ Logical failure (YouTube + SoundCloud)
        if track_duration == "FAILED":
            await self.highrise.send_whisper(
                user.id,
                "<#FF69B4>❌ This song not available currently.\n"
                "🔁 Try different name or source."
            )
            return

        # ❌ Safety check
        if not buffered_file_path or not track:
            await self.highrise.send_whisper(
                user.id,
                "<#FF69B4>❌ Unexpected error while adding song."
            )
            return

        # ================= Add to queue =================
        if not os.path.isabs(buffered_file_path):
            buffered_file_path = os.path.join(
                self.req_files_dir,
                os.path.basename(buffered_file_path)
            )

        # Check number of files in queue
        if len(self.req_files) >= 30:
            # Delete oldest temporary file
            while len(self.req_files) >= 30:
                old_item = self.req_files.popleft()
                old_path = old_item.get("url", "")
                is_in_fav = any(item.get("url") == old_path for item in playlist)
                if os.path.exists(old_path) and not is_in_fav:
                    try:
                        os.remove(old_path)
                    except:
                        pass

        new_item = {
            "url": buffered_file_path,
            "title": track.get("title", "Unknown"),
            "uploader": track.get("uploader", "Unknown"),
            "duration": track_duration,
            "user": user.username,
        }

        self.req_files.append(new_item)

        await self.highrise.chat(
            f"<#FF69B4>🎵 Added to queue:\n"
            f"<#FF69B4>{new_item['title']}\n"
            f"<#FF69B4>⏱️ Duration: {track_duration}\n"
            f"<#FF69B4>👤 Requested by: @{user.username}"
        )

        if user.username in user_ticket:
            if user.username not in ownerz and user.username not in vip_users:
                user_ticket[user.username] -= 1
                await self.highrise.send_whisper(
                    user.id,
                    f"<#FF69B4>💰 Remaining tickets: {user_ticket[user.username]}"
                )

        self.save_state()
        
        # Clean memory after adding
        gc.collect()

     except Exception as e:
        print(f"[Error adding to queue] {e}")
        # Clean memory in case of error
        gc.collect()



    async def promo(self):
        while True:
            try:
                for items in promo:
                    await self.highrise.chat(f"<#FFD580>{items}")
                    await asyncio.sleep(50)
                else:
                    await asyncio.sleep(50)
            except:
                pass
            await asyncio.sleep(150)

    async def notification(self):
        while True:
            try:
                if not self.req_files:
                    try:
                        import json
                        import os
                        
                        # Read prices from file
                        if os.path.exists("tk_price.json"):
                            with open("tk_price.json", "r", encoding="utf-8") as f:
                                prices = json.load(f)
                            
                            # Get prices with default values
                            payment_price = prices.get("ticket_price", 10)
                            tickets_count = prices.get("ticket_multiplier", 3)
                            vip_price = prices.get("vip_price", 1000)
                        else:
                            # Default values if file doesn't exist
                            payment_price = 10
                            tickets_count = 3
                            vip_price = 1000
                        
                        # Build price message
                        message = "<#FFD580>📭 Queue is empty!\n"
                        message += "<#FFD580>🎵 Type /play to request song\n"
                        message += "<#FFD580>💸 Ticket prices:\n"
                        
                        # Calculate prices for specific coins
                        coin_prices = [10, 100, 500]  # Coins you want to display
                        
                        for coin in coin_prices:
                            if coin >= payment_price:
                                payments_count = coin // payment_price
                                total_tickets = payments_count * tickets_count
                                message += f"<#FFD580>   • {total_tickets} tickets = {coin}💵\n"
                        
                        message += f"<#FFD580>⭐ VIP for month = {vip_price}💵"
                        
                        await self.highrise.chat(message)
                        
                    except Exception as e:
                        print(f"Error reading prices in notification: {e}")
                        # Default message in case of error
                        await self.highrise.chat(
                            "<#FFD580>📭 Queue is empty!\n"
                            "<#FFD580>🎵 Type /play to request song\n"
                            "<#FFD580>💸 Ticket prices:\n"
                            "<#FFD580>   • 3 tickets = 10💵\n"
                            "<#FFD580>   • 30 tickets = 100💵\n"
                            "<#FFD580>   • 150 tickets = 500💵\n"
                            "<#FFD580>⭐ VIP for month = 1000💵"
                        )
                
            except Exception as e:
                print(f"General notification error: {e}")
            
            await asyncio.sleep(277)
    
    async def print_messages(self):
        while True:
            try:
                if self.message:
                    nowplaying = self.message[0]
                    fix_nowplaying = nowplaying['title']
                    if nowplaying['user']:
                        await self.highrise.chat(f"<#FFD580>🎶 Now playing:\n"
                                      f"<#FFD580>🎵 {fix_nowplaying}\n"
                                      f"<#FFD580>⏱️ Duration: {nowplaying['audio_length']}\n"
                                      f"<#FFD580>👤 Requested by: @{nowplaying['user']}")
                    else:
                        await self.highrise.chat(f"<#FFD580>🎶 Now playing:\n"
                                      f"<#FFD580>🎵 {fix_nowplaying}\n"
                                      f"<#FFD580>⏱️ Duration: {nowplaying['audio_length']}")
                    self.message.clear()
            except:
                pass
            await asyncio.sleep(5)

    async def run(self, room_id: str, token: str):
        while True:
            try:
                definitions = [BotDefinition(self, room_id, token)]
                await __main__.main(definitions)
            except Exception as e:
                print(f"Bot disconnected with error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                print("Bot run task cancelled.")
                break
            except:
                print("Bot disconnected. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    def get_audio_length(self, audio_path):
        try:
            audio = MP3(audio_path)
            length = audio.info.length
            length = max(length, 0)
            minutes = int(length // 60)
            seconds = int(length % 60)
            return f"{minutes}:{seconds:02d}"
        except Exception as e:
            print(f"Error getting audio duration for {audio_path}: {e}")
            return None

def get_ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return str(n) + suffix

def connect_to_icecast():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("Connected to Icecast server.")
        
        auth = f"source:{STREAM_PASSWORD}"
        headers = (
            f"PUT {MOUNT_POINT} HTTP/1.0\r\n"
            f"Authorization: Basic {base64.b64encode(auth.encode()).decode()}\r\n"
            f"Content-Type: audio/mpeg\r\n"
            f"ice-name: ROBINS MUSIC ®\r\n"
            f"ice-genre: Various\r\n"
            f"ice-url: http://{SERVER_HOST}:{SERVER_PORT}{MOUNT_POINT}\r\n"
            f"ice-public: 1\r\n"
            f"ice-audio-info: bitrate=320\r\n"
            f"\r\n"
        )
        sock.sendall(headers.encode('utf-8'))
        
        response = sock.recv(1024).decode('utf-8')
        print(f"Server response: {response}")
        
        if "HTTP/1.0 200 OK" in response:
            print("Authentication successful.")
        else:
            print("Unexpected server response. Closing connection.")
            sock.close()
            return None
        return sock
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def start_streaming(bot_instance):
    playlist_index = 0
    while True:
        sock = connect_to_icecast()
        if not sock:
            print("Failed to reconnect, trying again...")
            time.sleep(3)
            continue

        if bot_instance.req_files:
            audio_file = bot_instance.req_files[0]['url']
        elif playlist:
            if playlist_index >= len(playlist):
                playlist_index = 0
            audio_file = playlist[playlist_index]['url']
            playlist_index += 1
        else:
            audio_file = random.choice(AUDIO_FILES)

        success = stream_audio(sock, audio_file, bot_instance)
        sock.close()

        if not success:
            print("Stream failed, trying again after 3 seconds...")
            time.sleep(3)
        else:
            # Memory cleanup after each successful stream
            time.sleep(1)  # Small delay
            gc.collect()

def stream_audio(sock, audio_file, bot_instance):
    process = None
    try:
        print(f"Streaming audio file: {audio_file}")
        bot_instance.start_time = time.time()
        bot_instance.now.clear()
        bot_instance.message.clear()

        if bot_instance.req_files and audio_file == bot_instance.req_files[0]['url']:
            current_song = bot_instance.req_files[0]
            bot_instance.now.append({
                'url': current_song.get('url'),
                'title': current_song.get('title', 'Unknown'),
                'user': current_song.get('user'),
                'audio_length': current_song.get('duration')
            })
            bot_instance.message.append(bot_instance.now[0])
            bot_instance.current_song = bot_instance.now[0]["title"]
        else:
            found = False
            for item in playlist:
                if item.get('url') == audio_file:
                    bot_instance.now.append({
                        'url': item.get('url'),
                        'title': item.get('title', 'Unknown'),
                        'user': item.get('user'),
                        'audio_length': item.get('audio_length') or item.get('duration') or bot_instance.get_audio_length(item.get('url')) or '🕒 Unknown'
                    })
                    bot_instance.message.append(bot_instance.now[0])
                    bot_instance.current_song = bot_instance.now[0]["title"]
                    found = True
                    break

            if not found and audio_file in AUDIO_FILES:
                bot_instance.now.append({
                    'url': audio_file,
                    'title': os.path.basename(audio_file),
                    'user': None,
                    'audio_length': bot_instance.get_audio_length(audio_file) or '0:00'
                })
                bot_instance.message.append(bot_instance.now[0])
                bot_instance.current_song = bot_instance.now[0]["title"]

        command = [
            'ffmpeg', '-re',
            '-i', audio_file,
            '-map', '0:a',
            '-c:a', 'libmp3lame',
            '-ar', '44100',
            '-b:a', bot_instance.bitrate,
            '-threads', '1',  # Reduce thread count
            '-f', 'mp3',
            '-content_type', 'audio/mpeg',
            '-'
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        while True:
            data = process.stdout.read(4096)
            if not data:
                break
            sock.sendall(data)

            if bot_instance.skip:
                bot_instance.skip = False
                break

        return True

    except Exception as e:
        print(f"Stream error: {e}")
        return False

    finally:
        # Intensive memory cleanup
        try:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            # Memory cleanup
            gc.collect()
            
        except Exception as e:
            print(f"<#FFD580>[STREAM_CLEANUP] Error: {e}")

        # Remove song from queue after playing
        if bot_instance.req_files and audio_file == bot_instance.req_files[0]['url']:
            played_item = bot_instance.req_files.popleft()
            
            # Delete file only if not in favorites
            is_in_fav = any(item.get('url') == played_item.get('url') for item in playlist)
            
            file_to_delete = played_item.get('url', '')
            if (os.path.exists(file_to_delete) and 
                file_to_delete not in AUDIO_FILES and 
                not file_to_delete.startswith(bot_instance.fav_dir) and
                not is_in_fav):
                try:
                    os.remove(file_to_delete)
                    print(f"<#FFD580>[Cleanup] File deleted after playback: {os.path.basename(file_to_delete)}")
                except Exception as e:
                    print(f"⚠️ Failed to delete {file_to_delete}: {e}")
        
        bot_instance.now.clear()
        bot_instance.message.clear()
        gc.collect()