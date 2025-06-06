"""
Studio Comanda - Sistema Shortlink Professionale
Deployato su Vercel - Versione Production
"""

from flask import Flask, request, redirect, jsonify
import string
import random
import hashlib
import datetime
import requests
import os
from urllib.parse import urlparse

app = Flask(__name__)

# Configurazione dalle environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
SECRET_KEY = os.getenv('SECRET_KEY')
SHORTLINK_LENGTH = 7

app.secret_key = SECRET_KEY or 'fallback-key'

def generate_short_code():
    """Genera codice random: a3Zm8Kx"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(SHORTLINK_LENGTH))

def validate_short_code(code):
    """Valida shortcode"""
    return code and len(code) == SHORTLINK_LENGTH and code.isalnum()

def hash_ip(ip):
    """Hash IP per privacy"""
    salt = os.getenv('IP_SALT', 'default-salt')
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()[:16]

def query_supabase(endpoint, method='GET', data=None):
    """Query Supabase"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise Exception("Configurazione Supabase mancante")
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f"Bearer {SUPABASE_ANON_KEY}",
        'Content-Type': 'application/json'
    }
    
    if method == 'GET':
        response = requests.get(url, headers=headers, timeout=10)
    elif method == 'POST':
        headers['Prefer'] = 'return=representation'
        response = requests.post(url, headers=headers, json=data, timeout=10)
    elif method == 'PATCH':
        headers['Prefer'] = 'return=minimal'
        response = requests.patch(url, headers=headers, json=data, timeout=10)
    
    response.raise_for_status()
    return response.json() if response.content else None

def create_shortlink(destination_url, description=None):
    """Crea shortlink unico"""
    for attempt in range(5):
        short_code = generate_short_code()
        
        # Verifica unicità
        existing = query_supabase(f"shortlinks?short_id=eq.{short_code}")
        if not existing or len(existing) == 0:
            # Crea nuovo shortlink
            data = {
                'short_id': short_code,
                'destination_url': destination_url,
                'access_count': 0,
                'original_filename': description or 'API Generated',
                'content_type': 'application/pdf',
                'created_at': datetime.datetime.utcnow().isoformat()
            }
            
            result = query_supabase('shortlinks', 'POST', data)
            if result:
                return short_code
    
    raise Exception("Impossibile generare shortlink unico")

@app.route('/')
@app.route('/status')
def status():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'service': 'Studio Comanda Shortlinks',
        'version': '1.0',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/api/create', methods=['POST'])
def api_create():
    """Crea shortlink via API"""
    try:
        data = request.get_json()
        if not data or 'destination_url' not in data:
            return jsonify({'error': 'destination_url richiesto'}), 400
        
        destination_url = data['destination_url']
        description = data.get('description', 'API Generated')
        
        # Valida URL
        parsed = urlparse(destination_url)
        if not parsed.scheme or not parsed.netloc:
            return jsonify({'error': 'URL non valido'}), 400
        
        # Crea shortlink
        short_code = create_shortlink(destination_url, description)
        short_url = f"https://{request.host}/{short_code}"
        
        return jsonify({
            'success': True,
            'short_code': short_code,
            'short_url': short_url,
            'destination_url': destination_url,
            'description': description
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/<short_code>')
def redirect_shortlink(short_code):
    """Redirect shortlink"""
    try:
        if not validate_short_code(short_code):
            return "Shortlink non valido", 400
        
        # Query database
        shortlinks = query_supabase(f"shortlinks?short_id=eq.{short_code}&select=destination_url,access_count")
        
        if not shortlinks or len(shortlinks) == 0:
            return "Link non trovato", 404
        
        shortlink = shortlinks[0]
        destination_url = shortlink['destination_url']
        current_count = shortlink.get('access_count', 0)
        
        # Update analytics
        try:
            client_ip = request.headers.get('X-Forwarded-For', '127.0.0.1').split(',')[0].strip()
            analytics_data = {
                'access_count': current_count + 1,
                'last_accessed': datetime.datetime.utcnow().isoformat(),
                'last_user_agent': request.headers.get('User-Agent', '')[:500],
                'last_ip_hash': hash_ip(client_ip)
            }
            query_supabase(f"shortlinks?short_id=eq.{short_code}", 'PATCH', analytics_data)
        except:
            pass  # Analytics non-critical
        
        return redirect(destination_url, code=302)
        
    except Exception as e:
        return f"Errore: {str(e)}", 500

@app.route('/analytics')
def analytics():
    """Analytics dashboard"""
    auth = request.args.get('auth')
    if auth != ADMIN_PASSWORD:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        shortlinks = query_supabase('shortlinks?select=*&order=access_count.desc')
        
        if not shortlinks:
            return jsonify({'error': 'Nessun dato'}), 500
        
        total_links = len(shortlinks)
        total_clicks = sum(link.get('access_count', 0) for link in shortlinks)
        
        return jsonify({
            'summary': {
                'total_links': total_links,
                'total_clicks': total_clicks,
                'avg_clicks': round(total_clicks / total_links, 1) if total_links > 0 else 0,
                'last_update': datetime.datetime.utcnow().isoformat()
            },
            'top_performers': [
                {
                    'short_id': link['short_id'],
                    'clicks': link.get('access_count', 0),
                    'description': link.get('original_filename', 'N/A'),
                    'created': link.get('created_at', ''),
                    'last_accessed': link.get('last_accessed', '')
                }
                for link in shortlinks[:10]
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
