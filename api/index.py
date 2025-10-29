import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from threading import Lock

# --- Configuration ---
IPTV_API_BASE_URL = "https://iptv-org.github.io/api"
# Cache duration for data refresh if the serverless container stays warm
CACHE_DURATION = timedelta(hours=6)

# --- Global Data Cache and Lock ---
# This data will persist in memory across "warm" serverless function invocations.
GLOBAL_CACHE = {
    'is_loaded': False,
    'last_loaded': None,
    # Indexed data for fast lookup
    'channels_list': [],  # Primary list for search/country filtering
    'channels_map': {},   # {channel_id: channel_object} for instant lookup
    'streams_map': {},    # {channel_id: [stream_objects]}
    'logos_map': {},      # {channel_id: logo_url}
    'countries_map': {},  # {code: country_object}
    'channel_counts': {}, # {code: count}
}

DATA_LOCK = Lock()

app = Flask(__name__)
CORS(app)

def fetch_external_data():
    """Fetches and parses all external JSON data."""
    data_urls = {
        'channels': f"{IPTV_API_BASE_URL}/channels.json",
        'streams': f"{IPTV_API_BASE_URL}/streams.json",
        'logos': f"{IPTV_API_BASE_URL}/logos.json",
        'countries': f"{IPTV_API_BASE_URL}/countries.json"
    }
    
    data = {}
    print(f"[{datetime.now().isoformat()}] Fetching large external data...")
    try:
        # Give a long timeout for the initial massive data fetch (critical for Vercel)
        for data_type, url in data_urls.items():
            response = requests.get(url, timeout=45) 
            response.raise_for_status()
            data[data_type] = response.json()
        return data
    except requests.RequestException as e:
        print(f"CRITICAL ERROR during initial data fetch: {e}")
        return None

def initialize_and_index_data():
    """Initializes the global cache by fetching, indexing, and merging data."""
    raw_data = fetch_external_data()
    if raw_data is None:
        return False
        
    print(f"[{datetime.now().isoformat()}] Indexing data for fast access...")

    # 1. Index Logos and Streams for O(1) lookups
    logos_map = {logo['channel']: logo['url'] for logo in raw_data.get('logos', [])}
    streams_map = {}
    for stream in raw_data.get('streams', []):
        channel_id = stream.get('channel')
        if channel_id:
            streams_map.setdefault(channel_id, []).append({
                'url': stream.get('url'),
                'title': stream.get('title'),
                'quality': stream.get('quality'),
                'referrer': stream.get('referrer'),
                'user_agent': stream.get('user_agent')
            })

    # 2. Combine Channel data and create fast lookup structures
    channels_list = raw_data.get('channels', [])
    channels_map = {}
    channel_counts = {}
    
    # Merge stream and logo data directly into the channel objects once
    for channel in channels_list:
        ch_id = channel['id']
        
        # Add pre-indexed streams/logos
        channel['logo'] = logos_map.get(ch_id)
        channel['streams'] = streams_map.get(ch_id, [])
        
        channels_map[ch_id] = channel
        
        # Count channels per country
        cc = channel.get('country')
        if cc:
            channel_counts[cc] = channel_counts.get(cc, 0) + 1

    # 3. Index Countries
    countries_map = {c['code']: c for c in raw_data.get('countries', [])}
    
    # --- Update Global Cache (Atomic Update) ---
    GLOBAL_CACHE.update({
        'channels_list': channels_list,
        'channels_map': channels_map,
        'streams_map': streams_map,
        'logos_map': logos_map,
        'countries_map': countries_map,
        'channel_counts': channel_counts,
        'last_loaded': datetime.now(),
        'is_loaded': True
    })
    
    print(f"[{datetime.now().isoformat()}] Data indexing successful. Channels: {len(channels_list)}")
    return True

def ensure_data_ready(func):
    """Decorator to ensure data is loaded and potentially refreshed."""
    def wrapper(*args, **kwargs):
        with DATA_LOCK:
            now = datetime.now()
            should_refresh = (
                GLOBAL_CACHE['is_loaded'] == False or
                (GLOBAL_CACHE['last_loaded'] and (now - GLOBAL_CACHE['last_loaded'] > CACHE_DURATION))
            )
            
            if should_refresh:
                if not initialize_and_index_data():
                    # Return 503 if the initial fetch failed
                    return jsonify({
                        'error': 'Service Unavailable: Failed to load required external data.',
                        'created_by': 'https://t.me/zerodevbro'
                    }), 503 
        
        # Data is loaded (or refreshed), proceed with the request
        return func(*args, **kwargs)
    return wrapper

def prepare_channel_response(channel):
    """Formats the channel object for final response."""
    return {
        'id': channel['id'],
        'name': channel['name'],
        'alt_names': channel.get('alt_names', []),
        'country': channel['country'],
        'network': channel.get('network'),
        'categories': channel.get('categories', []),
        'logo': channel.get('logo'),
        # Streams were merged during indexing, ensuring speed
        'streams': channel.get('streams', []), 
        'website': channel.get('website'),
        'is_nsfw': channel.get('is_nsfw', False),
        'launched': channel.get('launched'),
        'created_by': 'https://t.me/zerodevbro'
    }

# --- API Endpoints ---

@app.route('/')
@ensure_data_ready
def home():
    return jsonify({
        'message': 'IPTV Channel Search API (Serverless Optimized)',
        'created_by': 'https://t.me/zerodevbro',
        'endpoints': {
            '/api/search?q=<channel_name>': 'Search channels by name',
            '/api/country/<country_code>': 'Get all channels by country',
            '/api/countries': 'List all available countries',
            '/api/channel/<channel_id>': 'Get specific channel details'
        }
    })

@app.route('/api/search')
@ensure_data_ready
def search_channels():
    """Search channels by name - Now uses the pre-indexed channels list."""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({
            'error': 'Please provide a search query using ?q=channel_name',
            'created_by': 'https://t.me/zerodevbro'
        }), 400
    
    channels = GLOBAL_CACHE['channels_list']
    
    results = []
    # This iteration is fast because the channel object already contains streams/logos.
    for channel in channels:
        if (query in channel['name'].lower() or 
            any(query in alt.lower() for alt in channel.get('alt_names', []))):
            results.append(prepare_channel_response(channel))
    
    return jsonify({
        'query': query,
        'total_results': len(results),
        'channels': results,
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/country/<country_code>')
@ensure_data_ready
def get_by_country(country_code):
    """Get all channels by country code - Fast iteration over pre-indexed data."""
    country_code = country_code.upper()
    channels = GLOBAL_CACHE['channels_list']
    
    country_channels = [
        prepare_channel_response(ch) for ch in channels 
        if ch['country'] == country_code
    ]
    
    if not country_channels:
        return jsonify({
            'error': f'No channels found for country code: {country_code}',
            'created_by': 'https://t.me/zerodevbro'
        }), 404
    
    return jsonify({
        'country_code': country_code,
        'total_channels': len(country_channels),
        'channels': country_channels,
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/countries')
@ensure_data_ready
def list_countries():
    """List all available countries - Using pre-counted data for speed."""
    countries_map = GLOBAL_CACHE['countries_map']
    channel_counts = GLOBAL_CACHE['channel_counts']
    
    countries_list = [{
        'code': code,
        'name': countries_map[code]['name'],
        'flag': countries_map[code]['flag'],
        'channel_count': count
    } for code, count in channel_counts.items()]
    
    return jsonify({
        'total_countries': len(countries_list),
        'countries': sorted(countries_list, key=lambda x: x['channel_count'], reverse=True),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/channel/<channel_id>')
@ensure_data_ready
def get_channel(channel_id):
    """Get specific channel by ID - Instant lookup via map."""
    channel = GLOBAL_CACHE['channels_map'].get(channel_id)
    
    if not channel:
        return jsonify({
            'error': f'Channel not found: {channel_id}',
            'created_by': 'https://t.me/zerodevbro'
        }), 404
    
    return jsonify({
        'channel': prepare_channel_response(channel),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/categories')
@ensure_data_ready
def list_categories():
    """List all channel categories."""
    channels = GLOBAL_CACHE['channels_list']
    
    categories = {}
    for channel in channels:
        for cat in channel.get('categories', []):
            categories[cat] = categories.get(cat, 0) + 1
    
    return jsonify({
        'total_categories': len(categories),
        'categories': [{'name': k, 'count': v} for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)],
        'created_by': 'https://t.me/zerodevbro'
    })

if __name__ == '__main__':
    # Initial load attempt for local testing
    with DATA_LOCK:
        initialize_and_index_data()
    # In Vercel, this block is ignored, and the data load occurs on the first request via the decorator.
    app.run(debug=True)
