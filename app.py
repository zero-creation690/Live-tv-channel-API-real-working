from flask import Flask, request
from flask_cors import CORS
import requests, threading, time, orjson
from functools import lru_cache
import hashlib

app = Flask(__name__)
CORS(app)

BASE_URL = "https://iptv-org.github.io/api"
DATA = {"channels": [], "streams": [], "logos": [], "countries": []}
SEARCH_INDEX = {}
STREAM_MAP = {}  # Pre-mapped streams by channel ID
LOGO_MAP = {}    # Pre-mapped logos by channel ID
COUNTRY_MAP = {} # Pre-mapped channels by country
CATEGORY_MAP = {} # Pre-cached categories
LAST_UPDATE = 0
CACHE_DURATION = 3600 * 3

def fetch_all_data():
    """Fetch all IPTV JSON data and preprocess with aggressive caching"""
    global DATA, SEARCH_INDEX, STREAM_MAP, LOGO_MAP, COUNTRY_MAP, CATEGORY_MAP, LAST_UPDATE
    print("[INFO] Refreshing IPTV data...")
    
    urls = {
        "channels": f"{BASE_URL}/channels.json",
        "streams": f"{BASE_URL}/streams.json",
        "logos": f"{BASE_URL}/logos.json",
        "countries": f"{BASE_URL}/countries.json",
    }

    try:
        # Parallel fetch with session reuse
        session = requests.Session()
        session.headers.update({'Accept-Encoding': 'gzip, deflate'})
        
        for key, url in urls.items():
            r = session.get(url, timeout=20)
            r.raise_for_status()
            DATA[key] = r.json()
        session.close()
    except Exception as e:
        print(f"[ERROR] Data fetch failed: {e}")
        return

    # Build optimized lookup maps
    SEARCH_INDEX.clear()
    STREAM_MAP.clear()
    LOGO_MAP.clear()
    COUNTRY_MAP.clear()
    CATEGORY_MAP.clear()
    
    # Pre-map streams by channel ID for O(1) lookup
    for s in DATA["streams"]:
        ch_id = s.get("channel")
        if ch_id:
            if ch_id not in STREAM_MAP:
                STREAM_MAP[ch_id] = []
            STREAM_MAP[ch_id].append({
                "url": s["url"],
                "title": s.get("title"),
                "quality": s.get("quality"),
                "referrer": s.get("referrer"),
                "user_agent": s.get("user_agent"),
            })
    
    # Pre-map logos by channel ID
    for l in DATA["logos"]:
        ch_id = l.get("channel")
        if ch_id and ch_id not in LOGO_MAP:
            LOGO_MAP[ch_id] = l["url"]
    
    # Build search index with lowercase names
    for ch in DATA["channels"]:
        ch_id = ch["id"]
        SEARCH_INDEX[ch_id] = {
            "id": ch_id,
            "name": ch["name"].lower(),
            "alt": [a.lower() for a in ch.get("alt_names", [])],
            "country": ch.get("country"),
        }
        
        # Pre-map channels by country
        country = ch.get("country")
        if country:
            if country not in COUNTRY_MAP:
                COUNTRY_MAP[country] = []
            COUNTRY_MAP[country].append(ch)
        
        # Pre-count categories
        for cat in ch.get("categories", []):
            CATEGORY_MAP[cat] = CATEGORY_MAP.get(cat, 0) + 1
    
    LAST_UPDATE = time.time()
    print(f"[INFO] Data updated: {len(DATA['channels'])} channels, {len(DATA['streams'])} streams")


def auto_refresh():
    """Background thread to refresh cache periodically"""
    while True:
        time.sleep(CACHE_DURATION)
        fetch_all_data()


# Start data fetching immediately
threading.Thread(target=fetch_all_data, daemon=True).start()
threading.Thread(target=auto_refresh, daemon=True).start()


def combine_channel_data(channel):
    """Ultra-fast channel data combination using pre-built maps"""
    ch_id = channel["id"]
    return {
        "id": ch_id,
        "name": channel["name"],
        "alt_names": channel.get("alt_names", []),
        "country": channel.get("country"),
        "network": channel.get("network"),
        "categories": channel.get("categories", []),
        "logo": LOGO_MAP.get(ch_id),
        "streams": STREAM_MAP.get(ch_id, []),
        "website": channel.get("website"),
        "is_nsfw": channel.get("is_nsfw", False),
        "launched": channel.get("launched"),
        "created_by": "https://t.me/zerodevbro",
    }


def json_response(data, status=200):
    """Fast JSON response using orjson"""
    return app.response_class(
        response=orjson.dumps(data),
        status=status,
        mimetype="application/json"
    )


@app.route("/")
def home():
    uptime = round((time.time() - LAST_UPDATE) / 60, 1) if LAST_UPDATE else 0
    return json_response({
        "message": "🚀 IPTV Search API (Ultra-Fast Edition)",
        "created_by": "https://t.me/zerodevbro",
        "stats": {
            "channels": len(DATA["channels"]),
            "streams": len(DATA["streams"]),
            "countries": len(COUNTRY_MAP),
            "uptime_min": uptime
        },
        "endpoints": {
            "/api/search?q=<name>": "Search channels by name",
            "/api/country/<code>": "Get all channels by country",
            "/api/countries": "List all countries",
            "/api/channel/<id>": "Get channel details",
            "/api/categories": "List all categories"
        }
    })


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return json_response({"error": "Missing ?q=", "created_by": "https://t.me/zerodevbro"}, 400)

    limit = min(int(request.args.get("limit", 50)), 100)
    results = []
    
    # Optimized search with early termination
    for ch_id, ch in SEARCH_INDEX.items():
        if q in ch["name"] or any(q in alt for alt in ch["alt"]):
            original = next((c for c in DATA["channels"] if c["id"] == ch_id), None)
            if original:
                results.append(combine_channel_data(original))
                if len(results) >= limit:
                    break

    return json_response({
        "query": q,
        "results": len(results),
        "channels": results,
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/countries")
def list_countries():
    # Use pre-built country map for instant response
    countries = [
        {
            "code": c["code"],
            "name": c["name"],
            "flag": c.get("flag"),
            "channel_count": len(COUNTRY_MAP.get(c["code"], []))
        }
        for c in DATA["countries"]
        if c["code"] in COUNTRY_MAP
    ]
    
    countries.sort(key=lambda x: x["channel_count"], reverse=True)
    return json_response({
        "total": len(countries),
        "countries": countries,
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/country/<code>")
def by_country(code):
    code = code.upper()
    channels = COUNTRY_MAP.get(code, [])
    
    if not channels:
        return json_response({"error": f"No channels found for {code}"}, 404)
    
    limit = min(int(request.args.get("limit", 50)), 100)
    results = [combine_channel_data(c) for c in channels[:limit]]
    
    return json_response({
        "country": code,
        "total": len(channels),
        "returned": len(results),
        "channels": results,
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/channel/<ch_id>")
def channel(ch_id):
    channel = next((c for c in DATA["channels"] if c["id"] == ch_id), None)
    if not channel:
        return json_response({"error": "Channel not found"}, 404)
    
    return json_response({
        "channel": combine_channel_data(channel),
        "created_by": "https://t.me/zerodevbro"
    })


@app.route("/api/categories")
def categories():
    # Use pre-cached category counts
    result = [
        {"name": k, "count": v} 
        for k, v in sorted(CATEGORY_MAP.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return json_response({
        "total": len(result),
        "categories": result,
        "created_by": "https://t.me/zerodevbro"
    })


if __name__ == "__main__":
    # Production-ready settings
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
