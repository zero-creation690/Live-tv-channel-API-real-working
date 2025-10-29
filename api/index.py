from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from functools import lru_cache
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Cache configuration
CACHE_DURATION = timedelta(hours=1)
cache_timestamp = {}

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
            cache_timestamp[data_type] = current_time
    else:
        cache_timestamp[data_type] = current_time
    
    return fetch_data(data_type)

def combine_channel_data(channel):
    """Combine channel with its streams and logos"""
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
        'message': 'IPTV Channel Search API',
        'created_by': 'https://t.me/zerodevbro',
        'endpoints': {
            '/api/search?q=<channel_name>': 'Search channels by name',
            '/api/country/<country_code>': 'Get all channels by country',
            '/api/countries': 'List all available countries',
            '/api/channel/<channel_id>': 'Get specific channel details'
        }
    })

@app.route('/api/search')
def search_channels():
    """Search channels by name"""
    query = request.args.get('q', '').lower()
    
    if not query:
        return jsonify({
            'error': 'Please provide a search query using ?q=channel_name',
            'created_by': 'https://t.me/zerodevbro'
        }), 400
    
    channels = get_cached_data('channels')
    
    results = []
    for channel in channels:
        if (query in channel['name'].lower() or 
            any(query in alt.lower() for alt in channel.get('alt_names', []))):
            results.append(combine_channel_data(channel))
    
    return jsonify({
        'query': query,
        'total_results': len(results),
        'channels': results,
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/country/<country_code>')
def get_by_country(country_code):
    """Get all channels by country code"""
    country_code = country_code.upper()
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
    """List all available countries"""
    countries = get_cached_data('countries')
    channels = get_cached_data('channels')
    
    # Count channels per country
    country_counts = {}
    for channel in channels:
        cc = channel['country']
        country_counts[cc] = country_counts.get(cc, 0) + 1
    
    countries_list = [{
        'code': c['code'],
        'name': c['name'],
        'flag': c['flag'],
        'channel_count': country_counts.get(c['code'], 0)
    } for c in countries if country_counts.get(c['code'], 0) > 0]
    
    return jsonify({
        'total_countries': len(countries_list),
        'countries': sorted(countries_list, key=lambda x: x['channel_count'], reverse=True),
        'created_by': 'https://t.me/zerodevbro'
    })

@app.route('/api/channel/<channel_id>')
def get_channel(channel_id):
    """Get specific channel by ID"""
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
    """List all channel categories"""
    channels = get_cached_data('channels')
    
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
    app.run(debug=True)
