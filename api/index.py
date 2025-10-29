import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from threading import Lock
import json # Used for potential pre-built data loading

# --- Global Data Cache and Lock ---
# Using a dictionary to hold all pre-processed and indexed data
GLOBAL_DATA_CACHE = {
    'is_loaded': False,
    'channels': [],
    'streams_map': {}, # {channel_id: [stream_objects]}
    'logos_map': {},   # {channel_id: logo_url}
    'countries': [],
    'countries_map': {}, # {country_code: country_object}
    'channel_counts': {}, # {country_code: count}
}

DATA_LOCK = Lock()
# Note: In a true production environment, especially serverless,
# this data should ideally be built once and loaded from a
# persistent external store (like S3 or a DB) on startup.
# For this example, we'll keep the direct API fetching logic.

# --- Vercel Environment Configuration (Important) ---
# Vercel's serverless functions are essentially one-time execution scripts.
# The global variables persist across "warm" invocations.
# The base URL should be set as an environment variable or a constant.
IPTV_API_BASE_URL = os.environ.get("IPTV_API_BASE_URL", "https://iptv-org.github.io/api")

app = Flask(__name__)
CORS(app)

def fetch_and_process_data():
    """
    Fetches all data and processes it into optimized, indexed structures.
    This function should run only once.
    """
    print("--- Starting data fetch and processing ---")
    data_urls = {
        'channels': f"{IPTV_API_BASE_URL}/channels.json",
        'streams': f"{IPTV_API_BASE_URL}/streams.json",
        'logos': f"{IPTV_API_BASE_URL}/logos.json",
        'countries': f"{IPTV_API_BASE_URL}/countries.json"
    }
    
    data = {}
    for data_type, url in data_urls.items():
        try:
            # Increased timeout to 30 seconds for initial large payload fetch
            response = requests.get(url, timeout=30) 
            response.raise_for_status()
            data[data_type] = response.json()
        except requests.RequestException as e:
            print(f"Error fetching {data_type}: {e}")
            # In a serverless environment, if initial fetch fails, subsequent
            # requests will fail until the next cold start.
            return False

    # --- Step 1: Process Logos into a fast lookup map ---
    logos_map = {logo['channel']: logo['url'] for logo in data.get('logos', [])}
    
    # --- Step 2: Process Streams into a fast lookup map ---
    streams_map = {}
    for stream in data.get('streams', []):
        channel_id = stream.get('channel')
        if channel_id:
            streams_map.setdefault(channel_id, []).append({
                'url': stream.get('url'),
                'title': stream.get('title'),
                'quality': stream.get('quality'),
                'referrer': stream.get('referrer'),
                'user_agent': stream.get('user_agent')
            })

    # --- Step 3: Combine and Store Processed Data ---
    channels = data.get('channels', [])
    channel_counts = {}
    
    # This pre-processing is key: we only iterate over streams/logos ONCE here.
    # The 'channels' list remains as the primary source for search.
    
    for ch in channels:
        ch['logo'] = logos_map.get(ch['id'])
        ch['streams'] = streams_map.get(ch['id'], [])
        
        # Pre-count channels by country
        cc = ch.get('country')
        if cc:
            channel_counts[cc] = channel_counts.get(cc, 0) + 1

    # --- Step 4: Process Countries ---
    countries = data.get('countries', [])
    countries_map = {c['code']: c for c in countries}
    
    # --- Update Global Cache ---
    GLOBAL_DATA_CACHE.update({
        'channels': channels,
        'streams_map': streams_map,
        'logos_map': logos_map,
        'countries': countries,
        'countries_map': countries_map,
        'channel_counts': channel_counts,
        'is_loaded': True
    })
    
    print("--- Data processing complete. Cache is ready. ---")
    return True

def ensure_data_loaded(func):
    """Decorator to ensure data is loaded before processing a request."""
    def wrapper(*args, **kwargs):
        with DATA_LOCK:
            if not GLOBAL_DATA_CACHE['is_loaded']:
                if not fetch_and_process_data():
                    return jsonify({
                        'error': 'Failed to load initial data from IPTV API',
                        'created_by': 'https://t.me/zerodevbro'
                    }), 503 # Service Unavailable
        return func(*args, **kwargs)
    return wrapper

# --- The function to combine data is now a simple lookup (eliminated streams/logos iteration) ---
def prepare_channel_response(channel):
    """Prepares a single channel object for the API response."""
    return {
        'id': channel['id'],
        'name': channel['name'],
        'alt_names': channel.get('alt_names', []),
        'country': channel['country'],
        'network': channel.get('network'),
        'categories': channel.get('categories', []),
        'logo': channel.get('logo'), # Pre-added during processing
        'streams': channel.get('streams', []), # Pre-added during processing
        'website': channel.get('website'),
        'is_nsfw': channel.get('is_nsfw', False),
        'launched': channel.get('launched'),
        'created_by': 'https://t.me/zerodevbro'
    }

# --- API Endpoints (Now much faster) ---

@app.route('/')
@ensure_data_loaded
def home():
    return jsonify({
        'message': 'IPTV Channel Search API (Optimized for Vercel)',
        'created_by': 'https://t.me/zerodevbro',
        'endpoints': {
            '/api/search?q=<channel_name>': 'Search channels by name',
            '/api/country/<country_code>': 'Get all channels by country',
            '/api/countries': 'List all available countries',
            '/api/channel/<channel_id>': 'Get specific channel details',
            '/api/categories': 'List all categories'
        }
    })

@app.route('/api/search')
@ensure_data_loaded
def search_channels():
    """Search channels by name - Faster, only iterates over channels"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({
            'error': 'Please provide a search query using ?q=channel_name',
            'created_by': 'https://t.me/zerodevbro'
        }), 400
    
    channels = GLOBAL_DATA_CACHE['channels']
    
    results = []
    # This loop is still necessary but the prepare_channel_response inside is now instant.
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
@ensure_data_loaded
def get_by_country(country_code):
    """Get all channels by country code - Much faster iteration"""
    country_code = country_code.upper()
    channels = GLOBAL_DATA_CACHE['channels']
    
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
@ensure_data_loaded
def list_countries():
    """List all available countries - Using pre-counted data"""
    countries = GLOBAL_DATA_CACHE['countries']
    channel_counts = GLOBAL_DATA_CACHE['channel_counts']
    
    countries_list = [{
        'code': c['code'],
        'name': c['name'],
        'flag': c['flag'],
        'channel_count': channel_counts.get(c['code'], 0)
    } for c in countries if channel_counts.get(c['code'], 0) > 0]
    
    return jsonify({
        'total_countries': len(countries_list),
        'countries': sorted(countries_list, key=lambda x: x['channel_count'], reverse=True),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/channel/<channel_id>')
@ensure_data_loaded
def get_channel(channel_id):
    """Get specific channel by ID - Now uses a fast dictionary lookup (indirectly)"""
    channels = GLOBAL_DATA_CACHE['channels']
    
    # We must still iterate here, but for a single item. 
    # For maximum speed, you'd create a map: channel_map = {ch['id']: ch for ch in channels}
    # But keeping one list simplifies the overall structure.
    channel = next((ch for ch in channels if ch['id'] == channel_id), None)
    
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
@ensure_data_loaded
def list_categories():
    """List all channel categories - Still requires iteration but is fast for a full list"""
    channels = GLOBAL_DATA_CACHE['channels']
    
    categories = {}
    for channel in channels:
        for cat in channel.get('categories', []):
            categories[cat] = categories.get(cat, 0) + 1
    
    return jsonify({
        'total_categories': len(categories),
        'categories': [{'name': k, 'count': v} for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)],
        'created_by': 'https://t.me/zerodevbro'
    })

# --- Vercel/Production Run Configuration ---

# Vercel needs the application object for deployment
# The command for Vercel should reference this file and the 'app' object, e.g., 'vercel' or 'gunicorn app:app'

# For local development, keep the main block
if __name__ == '__main__':
    # Initial load will happen here for local development. 
    # On Vercel, it happens on the first request (cold start).
    with DATA_LOCK:
        fetch_and_process_data()
    app.run(debug=True, port=5000)

