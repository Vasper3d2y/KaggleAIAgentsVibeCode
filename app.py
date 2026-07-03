import os
import time
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
CACHE_DURATION = 600  # Cache for 10 minutes
_cache = {
    'data': None,
    'last_updated': 0
}

def clean_html_content(html_str):
    """
    Cleans up description HTML: makes links open in a new tab
    and ensures standard formatting.
    """
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, 'html.parser')
    for a in soup.find_all('a'):
        a['target'] = '_blank'
        a['rel'] = 'noopener noreferrer'
    return str(soup)

def fetch_release_notes():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    response = requests.get(FEED_URL, headers=headers, timeout=15)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch feed: HTTP {response.status_code}")
    
    # Parse XML
    # Atom namespace
    namespaces = {'atom': 'http://www.w3.org/2005/Atom'}
    root = ET.fromstring(response.content)
    
    entries = []
    
    for entry in root.findall('atom:entry', namespaces):
        title_el = entry.find('atom:title', namespaces)
        updated_el = entry.find('atom:updated', namespaces)
        id_el = entry.find('atom:id', namespaces)
        link_el = entry.find('atom:link', namespaces)
        content_el = entry.find('atom:content', namespaces)
        
        date_str = title_el.text if title_el is not None else ""
        updated_str = updated_el.text if updated_el is not None else ""
        entry_id = id_el.text if id_el is not None else ""
        
        link_href = ""
        if link_el is not None:
            link_href = link_el.attrib.get('href', '')
            
        content_html = content_el.text if content_el is not None else ""
        
        # Split content_html by h3 tags to isolate specific updates
        soup = BeautifulSoup(content_html, 'html.parser')
        h3s = soup.find_all('h3')
        
        if not h3s:
            # If no h3 tag exists, add as a single general update
            text_content = soup.get_text().strip()
            entries.append({
                'id': entry_id,
                'date': date_str,
                'updated': updated_str,
                'link': link_href,
                'category': 'General',
                'description': clean_html_content(content_html),
                'text_content': text_content
            })
        else:
            for idx, h3 in enumerate(h3s):
                category = h3.get_text().strip()
                
                # Gather all siblings after this h3 until the next h3
                description_parts = []
                sibling = h3.next_sibling
                while sibling and sibling.name != 'h3':
                    description_parts.append(str(sibling))
                    sibling = sibling.next_sibling
                
                desc_html = "".join(description_parts).strip()
                desc_soup = BeautifulSoup(desc_html, 'html.parser')
                text_content = desc_soup.get_text().strip()
                
                # Create a unique ID for this specific update within the entry
                sub_id = f"{entry_id}_{idx}_{category.lower().replace(' ', '_')}"
                
                entries.append({
                    'id': sub_id,
                    'date': date_str,
                    'updated': updated_str,
                    'link': link_href,
                    'category': category,
                    'description': clean_html_content(desc_html),
                    'text_content': text_content
                })
                
    return entries

def get_releases(force_refresh=False):
    now = time.time()
    if force_refresh or not _cache['data'] or (now - _cache['last_updated'] > CACHE_DURATION):
        _cache['data'] = fetch_release_notes()
        _cache['last_updated'] = now
    return _cache['data'], _cache['last_updated']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/releases')
def api_releases():
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    try:
        releases, last_updated = get_releases(force_refresh=force_refresh)
        return jsonify({
            'success': True,
            'releases': releases,
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_updated)),
            'cache_age_seconds': int(time.time() - last_updated)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Run the server locally on port 5001 to avoid common permission issues or port conflicts
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
