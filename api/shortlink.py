"""
Studio Comanda - Vercel Serverless Shortlink Handler
Ottimizzato per performance e sicurezza su Vercel
"""

from flask import Flask, request, redirect, jsonify
import string
import random
import hashlib
import datetime
import requests
import os
import json
from urllib.parse import urlparse

app = Flask(__name__)

# Configurazione sicura tramite environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'StudioComanda2025!')
SECRET_KEY = os.getenv('SECRET_KEY', 'vercel-secure-key-2025')
SHORTLINK_LENGTH = 7

app.secret_key = SECRET_KEY

def generate_short_code(length=7):
    """Genera codice random professionale: a3Zm8Kx, mN4xP9z"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def validate_short_code(code):
    """Valida formato shortcode per sicurezza"""
    if not code or len(code) != SHORTLINK_LENGTH:
        return False
    return all(c in string.ascii_letters + string.digits for c in code)

def get_client_ip():
    """Ottieni IP client con headers Vercel"""
    return (
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        request.headers.get('X-Real-IP') or
        request.environ.get('REMOTE_ADDR', '0.0.0.0')
    )

def hash_ip(ip):
    """Hash IP per privacy GDPR-compliant"""
    salt = os.getenv('IP_SALT', 'studiocomanda_salt_2025')
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()[:16]

def query_supabase(endpoint, method='GET', data=None):
    """Query helper Supabase ottimizzato"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise Exception("Configurazione Supabase mancante")
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f"Bearer {SUPABASE_ANON_KEY}",
        'Content-Type': 'application/json',
        'User-Agent': 'StudioComanda-Vercel/1.0'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=8)
        elif method == 'POST':
            headers['Prefer'] = 'return=representation'
            response = requests.post(url, headers=headers, json=data, timeout=8)
        elif method == 'PATCH':
            headers['Prefer'] = 'return=minimal'
            response = requests.patch(url, headers=headers, json=data, timeout=8)
        
        response.raise_for_status()
        return response.json() if response.content else None
    except requests.exceptions.Timeout:
        raise Exception("Timeout database")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Errore database: {str(e)}")

def create_shortlink(destination_url, description=None):
    """Crea shortlink con retry logic per unicità"""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        short_code = generate_short_code(SHORTLINK_LENGTH)
        
        # Verifica unicità
        existing = query_supabase(f"shortlinks?short_id=eq.{short_code}")
        if existing and len(existing) > 0:
            continue
        
        # Crea shortlink
        data = {
            'short_id': short_code,
            'destination_url': destination_url,
            'access_count': 0,
            'original_filename': description or 'Generato via API',
            'content_type': 'application/pdf',
            'created_at': datetime.datetime.utcnow().isoformat()
        }
        
        result = query_supabase('shortlinks', 'POST', data)
        if result:
            return short_code
    
    raise Exception("Impossibile generare shortlink unico")

def render_error_page(code, message):
    """Pagina errore brandizzata Studio Comanda"""
    html = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Studio Comanda - {message}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 40px 20px;
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: #333; min-height: 100vh;
                display: flex; align-items: center; justify-content: center;
            }}
            .container {{
                background: white; border-radius: 12px; padding: 40px;
                max-width: 500px; text-align: center;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }}
            .logo {{
                font-size: 28px; font-weight: bold;
                background: linear-gradient(45deg, #3498db, #2980b9);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 20px;
            }}
            h1 {{
                margin: 0 0 20px 0; color: #2c3e50; font-size: 24px;
            }}
            p {{
                margin: 0 0 30px 0; color: #7f8c8d;
                line-height: 1.6; font-size: 16px;
            }}
            .btn {{
                display: inline-block;
                background: linear-gradient(45deg, #3498db, #2980b9);
                color: white; padding: 14px 28px;
                text-decoration: none; border-radius: 8px;
                font-weight: 600; font-size: 16px;
                transition: transform 0.2s ease;
            }}
            .btn:hover {{
                transform: translateY(-2px);
            }}
            .powered {{
                margin-top: 30px; font-size: 12px; color: #bdc3c7;
                display: flex; align-items: center; justify-content: center; gap: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">📊 Studio Comanda</div>
            <h1>{message}</h1>
            <p>Il link richiesto non è disponibile. Controlla l'URL o contatta il supporto.</p>
            <a href="https://studiocomanda.it" class="btn">🏠 Torna al sito</a>
            <div class="powered">
                ⚡ Powered by Vercel + Supabase
            </div>
        </div>
    </body>
    </html>
    """
    return html, code

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def handler(path=''):
    """Handler principale per tutte le routes Vercel"""
    
    # CORS headers per sicurezza
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'  # Modificare per produzione
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    try:
        # Route: /api/create - Crea shortlink
        if path == 'api/create' and request.method == 'POST':
            try:
                data = request.get_json()
                if not data or 'destination_url' not in data:
                    return jsonify({'error': 'destination_url richiesto'}), 400
                
                destination_url = data['destination_url']
                description = data.get('description', 'Generato via API')
                
                # Valida URL
                parsed = urlparse(destination_url)
                if not parsed.scheme or not parsed.netloc:
                    return jsonify({'error': 'URL destinazione non valido'}), 400
                
                # Crea shortlink
                short_code = create_shortlink(destination_url, description)
                domain = request.host or 'studiocomanda.it'
                short_url = f"https://{domain}/{short_code}"
                
                response = jsonify({
                    'success': True,
                    'short_code': short_code,
                    'short_url': short_url,
                    'destination_url': destination_url,
                    'description': description
                })
                
                return add_cors_headers(response)
                
            except Exception as e:
                return jsonify({'error': f'Errore creazione: {str(e)}'}), 500
        
        # Route: /{shortcode} - Redirect shortlink
        elif path and len(path) <= SHORTLINK_LENGTH and validate_short_code(path):
            short_code = path
            
            try:
                # Query database
                shortlinks = query_supabase(f"shortlinks?short_id=eq.{short_code}&select=destination_url,access_count")
                
                if not shortlinks or len(shortlinks) == 0:
                    return render_error_page(404, "Link non trovato")
                
                shortlink = shortlinks[0]
                destination_url = shortlink['destination_url']
                current_count = shortlink.get('access_count', 0)
                
                # Update analytics asincrono
                try:
                    analytics_data = {
                        'access_count': current_count + 1,
                        'last_accessed': datetime.datetime.utcnow().isoformat(),
                        'last_user_agent': request.headers.get('User-Agent', 'Unknown')[:500],
                        'last_ip_hash': hash_ip(get_client_ip())
                    }
                    query_supabase(f"shortlinks?short_id=eq.{short_code}", 'PATCH', analytics_data)
                except:
                    pass  # Non-critical
                
                # Redirect
                return redirect(destination_url, code=302)
                
            except Exception as e:
                return render_error_page(500, f"Errore server: {str(e)}")
        
        # Route: /status - Health check
        elif path == 'status':
            return jsonify({
                'status': 'ok',
                'service': 'Studio Comanda Shortlinks',
                'version': '1.0',
                'timestamp': datetime.datetime.utcnow().isoformat()
            })
        
        else:
            return render_error_page(404, "Pagina non trovata")
            
    except Exception as e:
        return render_error_page(500, f"Errore interno: {str(e)}")

# Vercel serverless function entry point
if __name__ == '__main__':
    app.run(debug=True)
