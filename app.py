from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, threading, time, orjson

app = Flask(__name__)
CORS(app)

BASE_URL = "https://iptv-org.github.io/api"
DATA = {"channels": [], "streams": [], "logos": [], "countries": []}
SEARCH_INDEX = {}
LAST_UPDATE = 0
CACHE_DURATION = 3600 * 3  # 3 hours


def fetch_all_data():
    """Fetch all IPTV JSON data and preprocess"""
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

    # Build lowercase search index
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
    """Background thread to refresh cache periodically"""
    while True:
        time.sleep(CACHE_DURATION)
        fetch_all_data()


@app.before_first_request
def startup():
    """Load data on first API hit"""
    fetch_all_data()
    threading.Thread(target=auto_refresh, daemon=True).start()


def combine_channel_data(channel):
    """Combine channel with stream & logo"""
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
                "url": s["url"],
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


@app.route("/")
def home():
    return jsonify({
        "message": "🚀 IPTV Search API (Optimized for Koyeb)",
        "created_by": "https://t.me/zerodevbro",
        "uptime": f"{round((time.time() - LAST_UPDATE)/60, 1)} min since last data refresh",
        "endpoints": {
            "/api/search?q=<name>": "Search channels by name",
            "/api/country/<code>": "Get all channels by country",
            "/api/countries": "List all countries",
            "/api/channel/<id>": "Get channel details"
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


@app.route("/api/countries")
def list_countries():
    counts = {}
    for ch in DATA["channels"]:
        cc = ch.get("country")
        if cc:
            counts[cc] = counts.get(cc, 0) + 1

    countries = [
        {
            "code": c["code"],
            "name": c["name"],
            "flag": c.get("flag"),
            "channel_count": counts.get(c["code"], 0)
        }
        for c in DATA["countries"]
        if counts.get(c["code"], 0) > 0
    ]

    countries.sort(key=lambda x: x["channel_count"], reverse=True)
    return jsonify({
        "total": len(countries),
        "countries": countries,
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/country/<code>")
def by_country(code):
    code = code.upper()
    channels = [ch for ch in DATA["channels"] if ch.get("country") == code]

    if not channels:
        return jsonify({"error": f"No channels found for {code}"}), 404

    results = [combine_channel_data(c) for c in channels[:50]]
    return jsonify({
        "country": code,
        "total": len(results),
        "channels": results,
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/channel/<ch_id>")
def channel(ch_id):
    channel = next((c for c in DATA["channels"] if c["id"] == ch_id), None)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    return jsonify({
        "channel": combine_channel_data(channel),
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/categories")
def categories():
    cats = {}
    for ch in DATA["channels"]:
        for cat in ch.get("categories", []):
            cats[cat] = cats.get(cat, 0) + 1
    result = [{"name": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: x[1], reverse=True)]
    return jsonify({
        "total": len(result),
        "categories": result,
        "created_by": "https://t.me/zerodevbro"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
