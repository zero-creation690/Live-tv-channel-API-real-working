from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
import requests, threading, time, orjson, urllib.parse, subprocess, os, uuid

app = Flask(__name__)
CORS(app)

BASE_URL = "https://iptv-org.github.io/api"
DATA = {"channels": [], "streams": [], "logos": [], "countries": []}
SEARCH_INDEX = {}
LAST_UPDATE = 0
CACHE_DURATION = 3600 * 3  # 3 hours

# HLS temporary folder
HLS_DIR = "/tmp/hls"
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


# ------------------------ HLS CONVERTER ------------------------
def generate_hls(stream_url):
    """Create HLS playlist in /tmp/hls/<uuid>/index.m3u8"""
    stream_id = str(uuid.uuid4())
    out_dir = os.path.join(HLS_DIR, stream_id)
    os.makedirs(out_dir, exist_ok=True)
    out_m3u8 = os.path.join(out_dir, "index.m3u8")

    # Skip if already exists
    if not os.path.exists(out_m3u8):
        cmd = [
            "ffmpeg", "-i", stream_url,
            "-c:v", "copy", "-c:a", "aac",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+omit_endlist",
            out_m3u8
        ]
        subprocess.Popen(cmd)
    return f"/tmp/hls/{stream_id}/index.m3u8"


@app.route("/api/hls")
def hls_proxy():
    src_url = request.args.get("url")
    if not src_url:
        return jsonify({"error": "Missing ?url parameter"}), 400

    # If already .m3u8
    if src_url.endswith(".m3u8"):
        return redirect(src_url, code=302)

    # Otherwise generate HLS
    hls_path = generate_hls(src_url)
    base = request.host_url.rstrip("/")
    return redirect(f"{base}/hls/{os.path.basename(os.path.dirname(hls_path))}/index.m3u8", code=302)


# ------------------------ CHANNEL COMBINE ------------------------
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
                "url": f"{base}/api/hls?url={urllib.parse.quote(s['url'], safe='')}",
                "title": s.get("title"),
                "quality": s.get("quality"),
                "referrer": s.get("referrer"),
                "user_agent": s.get("user_agent"),
            }
            for s in streams
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
        "message": "🚀 Ultra Fast IPTV API with Real HLS",
        "created_by": "https://t.me/zerodevbro",
        "uptime": f"{round((time.time() - LAST_UPDATE)/60, 1)} min since last refresh",
        "endpoints": {
            "/api/search?q=<name>": "Search channels by name",
            "/api/country/<code>": "Get all channels by country",
            "/api/countries": "List all countries",
            "/api/channel/<id>": "Get specific channel details",
            "/api/categories": "List all categories",
            "/api/hls?url=<stream_url>": "Convert stream to HLS (playable)"
        }
    })


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"error": "Missing ?q="}), 400

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


@app.route("/api/countries")
def list_countries():
    counts = {}
    for ch in DATA["channels"]:
        cc = ch.get("country")
        if cc:
            counts[cc] = counts.get(cc, 0) + 1

    countries = [
        {"code": c["code"], "name": c["name"], "flag": c.get("flag"), "channel_count": counts.get(c["code"], 0)}
        for c in DATA["countries"] if counts.get(c["code"], 0) > 0
    ]
    countries.sort(key=lambda x: x["channel_count"], reverse=True)
    return jsonify({"total": len(countries), "countries": countries})


@app.route("/api/country/<code>")
def by_country(code):
    code = code.upper()
    channels = [ch for ch in DATA["channels"] if ch.get("country") == code]
    results = [combine_channel_data(c) for c in channels[:50]]
    return jsonify({"country": code, "total": len(results), "channels": results})


@app.route("/api/channel/<ch_id>")
def channel(ch_id):
    channel = next((c for c in DATA["channels"] if c["id"] == ch_id), None)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    return jsonify({"channel": combine_channel_data(channel)})


@app.route("/api/categories")
def categories():
    cats = {}
    for ch in DATA["channels"]:
        for cat in ch.get("categories", []):
            cats[cat] = cats.get(cat, 0) + 1
    result = [{"name": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: x[1], reverse=True)]
    return jsonify({"total": len(result), "categories": result})


# ------------------------ RUN ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
