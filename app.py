from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import requests, threading, time, orjson, subprocess, uuid, os

app = Flask(__name__)
CORS(app)

BASE_URL = "https://iptv-org.github.io/api"
DATA = {"channels": [], "streams": [], "logos": [], "countries": []}
SEARCH_INDEX = {}
LAST_UPDATE = 0
CACHE_DURATION = 3600 * 3  # 3 hours
HLS_DIR = "hls_temp"

os.makedirs(HLS_DIR, exist_ok=True)


# ------------------------ DATA FETCHING ------------------------
def fetch_all_data():
    global DATA, SEARCH_INDEX, LAST_UPDATE
    print("[INFO] Refreshing IPTV data...")
    urls = {
        "channels": f"{BASE_URL}/channels.json",
        "streams": f"{BASE_URL}/streams.json",
        "logos": f"{BASE_URL}/logos.json",
        "countries": f"{BASE_URL}/countries.json",
    }

    try:
        for key, url in urls.items():
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            DATA[key] = r.json()
    except Exception as e:
        print(f"[ERROR] Data fetch failed: {e}")
        return

    SEARCH_INDEX.clear()
    for ch in DATA["channels"]:
        SEARCH_INDEX[ch["id"]] = {
            "id": ch["id"],
            "name": ch["name"].lower(),
            "alt": [a.lower() for a in ch.get("alt_names", [])],
            "country": ch.get("country"),
        }

    LAST_UPDATE = time.time()
    print("[INFO] IPTV data updated successfully.")


def auto_refresh():
    while True:
        time.sleep(CACHE_DURATION)
        fetch_all_data()


threading.Thread(target=fetch_all_data, daemon=True).start()
threading.Thread(target=auto_refresh, daemon=True).start()


# ------------------------ REAL HLS CONVERTER ------------------------
def generate_hls(src_url):
    """
    Converts a stream to HLS on-the-fly using FFmpeg.
    Returns the URL of the .m3u8 playlist.
    """
    stream_id = str(uuid.uuid4())
    playlist_path = os.path.join(HLS_DIR, f"{stream_id}.m3u8")

    # FFmpeg command
    cmd = [
        "ffmpeg",
        "-y",                # overwrite
        "-i", src_url,       # input stream
        "-c:v", "copy",      # copy video codec
        "-c:a", "aac",       # audio codec
        "-f", "hls",
        "-hls_time", "4",    # segment length
        "-hls_list_size", "5",
        "-hls_flags", "delete_segments",
        playlist_path
    ]

    # Run FFmpeg as background process
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Return the m3u8 URL
    return f"/hls/{stream_id}.m3u8"


@app.route("/hls/<stream_file>")
def hls_serve(stream_file):
    path = os.path.join(HLS_DIR, stream_file)
    if not os.path.exists(path):
        return jsonify({"error": "Stream not found"}), 404

    def generate():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024*8)
                if not chunk:
                    break
                yield chunk
    return Response(generate(), mimetype="application/vnd.apple.mpegurl")


@app.route("/api/hls")
def hls_api():
    src_url = request.args.get("url")
    if not src_url:
        return jsonify({"error": "Missing ?url parameter"}), 400

    playlist_url = generate_hls(src_url)
    base_url = request.host_url.rstrip("/")
    return jsonify({"hls_url": f"{base_url}{playlist_url}"})


# ------------------------ CHANNEL DATA ------------------------
def combine_channel_data(channel):
    base = request.host_url.rstrip("/")
    streams = [s for s in DATA["streams"] if s.get("channel") == channel["id"]]
    logos = [l for l in DATA["logos"] if l.get("channel") == channel["id"]]
    logo_url = logos[0]["url"] if logos else None

    return {
        "id": channel["id"],
        "name": channel["name"],
        "alt_names": channel.get("alt_names", []),
        "country": channel.get("country"),
        "network": channel.get("network"),
        "categories": channel.get("categories", []),
        "logo": logo_url,
        "streams": [
            {
                "url": f"{base}/api/hls?url={s['url']}",
                "title": s.get("title"),
                "quality": s.get("quality"),
                "referrer": s.get("referrer"),
                "user_agent": s.get("user_agent"),
            } for s in streams
        ],
        "website": channel.get("website"),
        "is_nsfw": channel.get("is_nsfw", False),
        "launched": channel.get("launched"),
        "created_by": "https://t.me/zerodevbro",
    }


# ------------------------ ROUTES ------------------------
@app.route("/")
def home():
    return jsonify({
        "message": "🚀 Real-time IPTV HLS API (FFmpeg)",
        "created_by": "https://t.me/zerodevbro",
        "uptime": f"{round((time.time() - LAST_UPDATE)/60, 1)} min since last refresh",
        "endpoints": {
            "/api/search?q=<name>": "Search channels by name",
            "/api/country/<code>": "Get all channels by country",
            "/api/countries": "List all countries",
            "/api/channel/<id>": "Get channel details",
            "/api/hls?url=<stream_url>": "Convert any stream to HLS in real-time"
        }
    })


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"error": "Missing ?q=", "created_by": "https://t.me/zerodevbro"}), 400

    results = []
    for ch_id, ch in SEARCH_INDEX.items():
        if q in ch["name"] or any(q in alt for alt in ch["alt"]):
            original = next(c for c in DATA["channels"] if c["id"] == ch_id)
            results.append(combine_channel_data(original))
            if len(results) >= 50:
                break

    return app.response_class(
        response=orjson.dumps({
            "query": q,
            "results": len(results),
            "channels": results,
            "created_by": "https://t.me/zerodevbro"
        }),
        status=200,
        mimetype="application/json"
    )


# ------------------------ RUN ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
