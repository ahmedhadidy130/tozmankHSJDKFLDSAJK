import threading
import asyncio
import importlib
import json
import os
import yt_dlp
import time
from flask import Flask, jsonify, render_template, request

# ================== FLASK ==================
app = Flask(__name__)
BOT_STATUS = {
    "running": False,
    "last_error": None,
    "last_restart": None
}
BOT_INSTANCE = None


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify(BOT_STATUS), 200

@app.route("/api/status")
def api_status():

    if BOT_INSTANCE is None:
        return jsonify({
            "online": False
        })

    return jsonify({
        "online": BOT_STATUS["running"],
        "bot_name": BOT_INSTANCE.dashboard.get("bot_name", "Music Bot"),
        "song": BOT_INSTANCE.current_song or BOT_INSTANCE.dashboard.get("song"),
        "artist": BOT_INSTANCE.current_artist,
        "duration": BOT_INSTANCE.current_duration,
        "queue": BOT_INSTANCE.dashboard["queue"],
        "users": BOT_INSTANCE.dashboard["users"],
        "vip": BOT_INSTANCE.dashboard["vip"],
        "cpu": BOT_INSTANCE.dashboard["cpu"],
        "ram": BOT_INSTANCE.dashboard["ram"],
        "uptime": BOT_INSTANCE.dashboard["uptime"],
        "last_error": BOT_STATUS["last_error"],
        "last_restart": BOT_STATUS["last_restart"]
         })
        
@app.route("/api/skip", methods=["POST"])
def api_skip():

    print("⏭ Dashboard Skip Button Pressed")

    if BOT_INSTANCE:

        BOT_INSTANCE.skip = True

        print("✅ Skip sent to bot")

        return jsonify({
            "success": True,
            "message": "Skip requested"
        })

    return jsonify({
        "success": False,
        "message": "Bot offline"
    })

@app.route("/api/favorites")
def api_favorites():

    fav_dir = "/home/container/fav"

    songs = []

    print("Checking fav:", fav_dir)

    if os.path.exists(fav_dir):

        for root, dirs, files in os.walk(fav_dir):

            for file in files:

                print("Found file:", file)

                if file.lower().endswith((
                    ".mp3",
                    ".wav",
                    ".m4a",
                    ".webm",
                    ".opus"
                )):

                    songs.append({
                        "name": file,
                        "path": os.path.join(root, file)
                    })


    print("Favorites count:", len(songs))

    return jsonify(songs)

@app.route("/api/send_message", methods=["POST"])
def api_send_message():
    if BOT_INSTANCE:

        data = request.json
        msg = data.get("message")

        asyncio.run_coroutine_threadsafe(
            BOT_INSTANCE.highrise.chat(msg),
            BOT_INSTANCE.loop
        )

        return jsonify({"success": True})

    return jsonify({"success": False})

@app.route("/api/favorites/delete", methods=["POST"])
def delete_favorite():

    data = request.json
    filename = data.get("name")

    if not filename:
        return jsonify({
            "success":False
        })


    path = os.path.join(
        "/home/container/fav",
        os.path.basename(filename)
    )

    if os.path.exists(path):
        os.remove(path)

    # تحديث قائمة الفيفوريت داخل البوت
    if BOT_INSTANCE:
        try:
            BOT_INSTANCE.sync_fav_with_playlist()
            print("⭐ Favorites synced after delete")
        except Exception as e:
            print("Sync error:", e)

    return jsonify({
        "success":True
    })


 

@app.route("/api/youtube/search", methods=["POST"])
def youtube_search():

    data = request.json
    query = data.get("query")


    if not query:
        return jsonify([])


    try:

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }


        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            result = ydl.extract_info(
                f"ytsearch5:{query}",
                download=False
            )


        songs = []


        for item in result.get("entries", []):

            video_id = item.get("id")
            songs.append({

                "title": item.get("title"),
                "url": f"https://www.youtube.com/watch?v={video_id}"

            })


        return jsonify(songs)


    except Exception as e:

        print("YouTube Search Error:", e)

        return jsonify([])
    
@app.route("/api/favorites/add", methods=["POST"])
def add_favorite():

    data = request.json

    url = data.get("url")
    title = data.get("title","song")


    if not url:
        return jsonify({
            "success":False
        })


    fav_dir = "/home/container/fav"

    os.makedirs(fav_dir, exist_ok=True)


    filename = os.path.join(
        fav_dir,
        title.replace("/","_") + ".mp3"
    )

    try:

        opts = {
            "format": "bestaudio",
            "outtmpl": filename,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3"
                }
            ]
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            print("Downloading:", url)
            ydl.download([url])

        # تحديث قائمة الفيفوريت داخل البوت
        if BOT_INSTANCE:
            try:
                BOT_INSTANCE.sync_fav_with_playlist()
                print("⭐ Favorites synced after add")
            except Exception as e:
                print("Sync error:", e)

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("Download Error:", e)

        return jsonify({
            "success": False
        })

@app.route("/api/restart", methods=["POST"])
def api_restart():

    BOT_STATUS["last_restart"] = time.strftime("%Y-%m-%d %H:%M:%S")

    if BOT_INSTANCE:
        BOT_INSTANCE.restart_requested = True

    return jsonify({
        "success": True
    })       

# ================== CONFIG ==================
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError("❌ config.json not found!")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)



# ================== BOT RUNNER ==================
async def bot_loop():
    global BOT_STATUS, BOT_INSTANCE

    config = load_config()
    room_id = config.get("room_id")
    token = config.get("bot_token")
    bot_file = config.get("bot_file", "youtubezeno")
    bot_class = config.get("bot_class", "SEA")

    bot_module = importlib.import_module(bot_file)
    bot_class_obj = getattr(bot_module, bot_class)

    bot_instance = bot_class_obj()
    BOT_INSTANCE = bot_instance

    # تشغيل streaming لو موجود
    if hasattr(bot_module, "start_streaming"):
        t = threading.Thread(
            target=bot_module.start_streaming,
            args=(bot_instance,),
            daemon=True
        )
        t.start()

    while True:
        try:
            BOT_STATUS["running"] = True
            BOT_STATUS["last_error"] = None

            await bot_instance.run(room_id, token)

        except Exception as e:
            BOT_STATUS["running"] = False
            BOT_STATUS["last_error"] = str(e)
            BOT_STATUS["last_restart"] = time.strftime("%Y-%m-%d %H:%M:%S")

            print(f"❌ Bot crashed: {e}")
            print("🔁 Restarting in 5 seconds...")
            await asyncio.sleep(5)


def start_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_loop())


# ================== MAIN ==================
if __name__ == "__main__":
    # تشغيل البوت في Thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # تشغيل Flask (مهم عشان المنصات السحابية)
    app.run(host="0.0.0.0", port=30041)
