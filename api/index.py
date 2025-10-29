from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from functools import lru_cache
from datetime import datetime, timedelta
import time

app = Flask(__name__)
CORS(app)

# Cache configuration
CACHE_DURATION = timedelta(hours=1)
cache_timestamp = {}

# Pre-processed data structures for faster search
search_index = {}
country_index = {}
category_index = {}

@lru_cache(maxsize=1)
def fetch_data(data_type):
    """Fetch data from IPTV API with caching"""
    base_url = "https://iptv-org.github.io/api"
    urls = {
        'channels': f"{base_url}/channels.json",
        'streams': f"{base_url}/streams.json",
        'logos': f"{base_url}/logos.json",
        'countries': f"{base_url}/countries.json"
    }
    
    try:
        response = requests.get(urls[data_type], timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return []

def get_cached_data(data_type):
    """Get data with time-based cache invalidation"""
    current_time = datetime.now()
    
    if data_type in cache_timestamp:
        if current_time - cache_timestamp[data_type] > CACHE_DURATION:
            fetch_data.cache_clear()
            # Clear search indexes when cache expires
            global search_index, country_index, category_index
            search_index.clear()
            country_index.clear()
            category_index.clear()
            cache_timestamp[data_type] = current_time
    else:
        cache_timestamp[data_type] = current_time
    
    return fetch_data(data_type)

def build_search_index():
    """Build search index for faster searching"""
    if search_index:
        return
        
    channels = get_cached_data('channels')
    streams = get_cached_data('streams')
    logos = get_cached_data('logos')
    
    # Create logo lookup dictionary
    logo_dict = {}
    for logo in logos:
        logo_dict[logo.get('channel')] = logo.get('url')
    
    # Create streams lookup dictionary
    streams_dict = {}
    for stream in streams:
        channel_id = stream.get('channel')
        if channel_id not in streams_dict:
            streams_dict[channel_id] = []
        streams_dict[channel_id].append({
            'url': stream['url'],
            'title': stream.get('title'),
            'quality': stream.get('quality'),
            'referrer': stream.get('referrer'),
            'user_agent': stream.get('user_agent')
        })
    
    # Build search index
    for channel in channels:
        channel_id = channel['id']
        
        # Combine all searchable text
        search_terms = [
            channel['name'].lower(),
            *[alt.lower() for alt in channel.get('alt_names', [])],
            channel.get('network', '').lower(),
            *[cat.lower() for cat in channel.get('categories', [])],
            channel.get('country', '').lower()
        ]
        
        # Pre-combine channel data
        combined_data = {
            'id': channel_id,
            'name': channel['name'],
            'alt_names': channel.get('alt_names', []),
            'country': channel['country'],
            'network': channel.get('network'),
            'categories': channel.get('categories', []),
            'logo': logo_dict.get(channel_id),
            'streams': streams_dict.get(channel_id, []),
            'website': channel.get('website'),
            'is_nsfw': channel.get('is_nsfw', False),
            'launched': channel.get('launched'),
            'created_by': 'https://t.me/zerodevbro'
        }
        
        # Index by search terms
        for term in search_terms:
            if term not in search_index:
                search_index[term] = []
            search_index[term].append(combined_data)
        
        # Index by country
        country = channel['country']
        if country not in country_index:
            country_index[country] = []
        country_index[country].append(combined_data)
        
        # Index by category
        for category in channel.get('categories', []):
            if category not in category_index:
                category_index[category] = []
            category_index[category].append(combined_data)

def combine_channel_data(channel):
    """Combine channel with its streams and logos (fallback method)"""
    streams = get_cached_data('streams')
    logos = get_cached_data('logos')
    
    channel_streams = [s for s in streams if s.get('channel') == channel['id']]
    channel_logos = [l for l in logos if l.get('channel') == channel['id']]
    
    logo_url = channel_logos[0]['url'] if channel_logos else None
    
    return {
        'id': channel['id'],
        'name': channel['name'],
        'alt_names': channel.get('alt_names', []),
        'country': channel['country'],
        'network': channel.get('network'),
        'categories': channel.get('categories', []),
        'logo': logo_url,
        'streams': [{
            'url': s['url'],
            'title': s.get('title'),
            'quality': s.get('quality'),
            'referrer': s.get('referrer'),
            'user_agent': s.get('user_agent')
        } for s in channel_streams],
        'website': channel.get('website'),
        'is_nsfw': channel.get('is_nsfw', False),
        'launched': channel.get('launched'),
        'created_by': 'https://t.me/zerodevbro'
    }

@app.route('/')
def home():
    return jsonify({
        'message': 'IPTV Channel Search API - Optimized',
        'created_by': 'https://t.me/zerodevbro',
        'endpoints': {
            '/api/search?q=<channel_name>': 'Search channels by name',
            '/api/country/<country_code>': 'Get all channels by country',
            '/api/countries': 'List all available countries',
            '/api/channel/<channel_id>': 'Get specific channel details',
            '/api/categories': 'List all channel categories'
        }
    })

@app.route('/api/search')
def search_channels():
    """Search channels by name - Optimized version"""
    start_time = time.time()
    query = request.args.get('q', '').lower().strip()
    
    if not query:
        return jsonify({
            'error': 'Please provide a search query using ?q=channel_name',
            'created_by': 'https://t.me/zerodevbro'
        }), 400
    
    # Build search index if not exists
    build_search_index()
    
    # Split query into terms for better matching
    query_terms = query.split()
    results_set = set()
    results = []
    
    # Search using pre-built index
    for term in query_terms:
        if term in search_index:
            for channel in search_index[term]:
                channel_id = channel['id']
                if channel_id not in results_set:
                    results_set.add(channel_id)
                    results.append(channel)
    
    # Fallback to linear search if no results from index
    if not results:
        channels = get_cached_data('channels')
        for channel in channels:
            if (query in channel['name'].lower() or 
                any(query in alt.lower() for alt in channel.get('alt_names', []))):
                results.append(combine_channel_data(channel))
    
    # Sort by relevance (exact matches first)
    results.sort(key=lambda x: (
        query not in x['name'].lower(),
        len(x['name'])
    ))
    
    processing_time = round((time.time() - start_time) * 1000, 2)
    
    return jsonify({
        'query': query,
        'total_results': len(results),
        'processing_time_ms': processing_time,
        'channels': results[:100],  # Limit results for performance
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/country/<country_code>')
def get_by_country(country_code):
    """Get all channels by country code - Optimized"""
    country_code = country_code.upper()
    
    # Build search index if not exists
    build_search_index()
    
    if country_code in country_index:
        country_channels = country_index[country_code]
    else:
        # Fallback to original method
        channels = get_cached_data('channels')
        country_channels = [
            combine_channel_data(ch) for ch in channels 
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
def list_countries():
    """List all available countries - Optimized"""
    build_search_index()
    
    countries = get_cached_data('countries')
    countries_list = []
    
    for country in countries:
        code = country['code']
        channel_count = len(country_index.get(code, []))
        if channel_count > 0:
            countries_list.append({
                'code': code,
                'name': country['name'],
                'flag': country['flag'],
                'channel_count': channel_count
            })
    
    return jsonify({
        'total_countries': len(countries_list),
        'countries': sorted(countries_list, key=lambda x: x['channel_count'], reverse=True),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/channel/<channel_id>')
def get_channel(channel_id):
    """Get specific channel by ID - Optimized"""
    build_search_index()
    
    # Search in all indexed channels
    for term_channels in search_index.values():
        for channel in term_channels:
            if channel['id'] == channel_id:
                return jsonify({
                    'channel': channel,
                    'created_by': 'https://t.me/zerodevbro'
                })
    
    # Fallback to original method
    channels = get_cached_data('channels')
    channel = next((ch for ch in channels if ch['id'] == channel_id), None)
    
    if not channel:
        return jsonify({
            'error': f'Channel not found: {channel_id}',
            'created_by': 'https://t.me/zerodevbro'
        }), 404
    
    return jsonify({
        'channel': combine_channel_data(channel),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/categories')
def list_categories():
    """List all channel categories - Optimized"""
    build_search_index()
    
    categories_list = [{'name': k, 'count': len(v)} for k, v in category_index.items()]
    
    return jsonify({
        'total_categories': len(categories_list),
        'categories': sorted(categories_list, key=lambda x: x['count'], reverse=True),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/stats')
def get_stats():
    """Get API performance statistics"""
    build_search_index()
    
    return jsonify({
        'search_index_size': len(search_index),
        'countries_indexed': len(country_index),
        'categories_indexed': len(category_index),
        'total_channels_indexed': sum(len(channels) for channels in country_index.values()),
        'cache_status': {k: v.isoformat() for k, v in cache_timestamp.items()},
        'created_by': 'https://t.me/zerodevbro'
    })

if __name__ == '__main__':
    # Pre-build indexes on startup
    print("Building search indexes...")
    build_search_index()
    print(f"Index built: {len(search_index)} search terms, {len(country_index)} countries, {len(category_index)} categories")
    app.run(debug=True)
