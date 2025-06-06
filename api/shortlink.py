from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
@app.route('/status')
def status():
    try:
        return jsonify({
            'status': 'ok',
            'service': 'Studio Comanda Shortlinks - Debug Mode',
            'version': '1.0-debug',
            'supabase_url': os.getenv('SUPABASE_URL')[:20] + '...' if os.getenv('SUPABASE_URL') else None,
            'supabase_key_length': len(os.getenv('SUPABASE_ANON_KEY', '')),
            'all_env_vars': [k for k in os.environ.keys() if k.startswith(('SUPABASE', 'ADMIN', 'SECRET', 'IP_SALT'))]
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'type': type(e).__name__
        }), 500

@app.route('/test')
def test():
    return jsonify({'test': 'working'})

if __name__ == '__main__':
    app.run()
