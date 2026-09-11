import json
import threading
import shutil
import os

# القفل لمنع التعارض في الكتابة
data_lock = threading.Lock()

data_mappings = {
    "user_ticket": {},
    "bot_location": {},
    "msg": [],
    "restrict": [],
    "promo": [],
    "vip_users": [],
    "playlist": [],
    "ownerz": [],
    "ids": []
}

# تحديث البيانات العالمية
globals().update(data_mappings)

def save_data():
    """Save all data to corresponding JSON files."""
    try:
        with data_lock:
            total, used, free = shutil.disk_usage("/")
            if free < 1024 * 1024:
                print("⚠️ Not enough disk space to save data.")
                return
            
            # استخدام نسخة من البيانات للكتابة
            data_to_save = {}
            for var_name in data_mappings.keys():
                data_to_save[var_name] = globals()[var_name].copy() if hasattr(globals()[var_name], 'copy') else list(globals()[var_name])
            
            for var_name, data in data_to_save.items():
                filename = f"{var_name}.json"
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                except Exception as e:
                    print(f"❌ Error saving {filename}: {e}")
    
    except Exception as e:
        print(f"❌ Error in save_data: {e}")
    
    # إعادة جدولة الحفظ بعد 100 ثانية
    threading.Timer(100, save_data).start()

def load_data():
    """Load all data from corresponding JSON files."""
    for var_name, default_value in data_mappings.items():
        filename = f"{var_name}.json"
        try:
            with open(filename, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                # تحويل القاموس/القائمة إلى النوع المناسب
                if isinstance(default_value, dict):
                    globals()[var_name].update(loaded_data)
                elif isinstance(default_value, list):
                    globals()[var_name].clear()
                    globals()[var_name].extend(loaded_data)
                else:
                    globals()[var_name] = loaded_data
        except (FileNotFoundError, json.JSONDecodeError):
            # إذا كان الملف غير موجود أو به خطأ، استخدم القيمة الافتراضية
            if isinstance(default_value, dict):
                globals()[var_name].clear()
            elif isinstance(default_value, list):
                globals()[var_name].clear()
            else:
                globals()[var_name] = default_value
        except Exception as e:
            print(f"⚠️ Error loading {filename}: {e}")

def sync_favorites():

    fav_dir = "/home/container/fav"

    if not os.path.exists(fav_dir):
        return

    playlist.clear()

    for file in os.listdir(fav_dir):

        if file.lower().endswith(".mp3"):

            path = os.path.join(fav_dir, file)

            playlist.append({
                "url": path,
                "title": os.path.splitext(file)[0],
                "user": "SYSTEM",
                "audio_length": "🕒 Unknown"
            })

    with open("playlist.json", "w", encoding="utf-8") as f:
        json.dump(
            playlist,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"⭐ Favorites synced: {len(playlist)} songs")            
            
# تحميل البيانات عند بدء التشغيل

load_data()
sync_favorites()

# بدء عملية الحفظ الدورية
save_data()

print("✅ HRDB initialized successfully!")