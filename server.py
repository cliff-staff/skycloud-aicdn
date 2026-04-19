#!/usr/bin/env python3
import http.server
import json
import os
import datetime
import secrets
from urllib.parse import urlparse

BASE = os.path.dirname(__file__)
DATA_FILE   = os.path.join(BASE, 'leads.json')
CONFIG_FILE = os.path.join(BASE, 'config.json')

# ── 帳號設定：優先讀 config.json，沒有就用預設值建立檔案 ────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    cfg = {'username': os.environ.get('ADMIN_USER', 'admin'),
           'password': os.environ.get('ADMIN_PASS', 'skycloud2026')}
    save_config(cfg)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# 執行期 session tokens（重啟後失效，需重新登入）
_sessions = set()

def load_leads():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_leads(leads):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

class Handler(http.server.SimpleHTTPRequestHandler):

    def _auth(self):
        return self.headers.get('X-Token', '') in _sessions

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/leads':
            if not self._auth():
                return self._json(401, {'success': False, 'error': 'Unauthorized'})
            leads = load_leads()
            for i, lead in enumerate(leads):
                lead['rowIndex'] = i + 2
            self._json(200, {'success': True, 'data': leads})
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length)) if length else {}

        if path == '/api/login':
            cfg = load_config()
            if data.get('username') == cfg['username'] and data.get('password') == cfg['password']:
                token = secrets.token_hex(32)
                _sessions.add(token)
                self._json(200, {'success': True, 'token': token})
            else:
                self._json(401, {'success': False, 'error': '帳號或密碼錯誤'})

        elif path == '/api/logout':
            _sessions.discard(self.headers.get('X-Token', ''))
            self._json(200, {'success': True})

        elif path == '/api/change-password':
            if not self._auth():
                return self._json(401, {'success': False, 'error': 'Unauthorized'})
            cfg = load_config()
            if data.get('current') != cfg['password']:
                return self._json(400, {'success': False, 'error': '目前密碼錯誤'})
            new_pw = data.get('new', '').strip()
            if len(new_pw) < 6:
                return self._json(400, {'success': False, 'error': '新密碼至少需要 6 個字元'})
            cfg['password'] = new_pw
            save_config(cfg)
            self._json(200, {'success': True})

        elif path == '/api/leads':
            action = data.get('action', 'addRow')
            if action != 'addRow' and not self._auth():
                return self._json(401, {'success': False, 'error': 'Unauthorized'})
            leads = load_leads()
            if action == 'addRow':
                leads.append({
                    'name':      data.get('name', ''),
                    'title':     data.get('title', ''),
                    'company':   data.get('company', ''),
                    'email':     data.get('email', ''),
                    'domain':    data.get('domain', ''),
                    'status':    data.get('status', '待處理'),
                    'start':     data.get('start', ''),
                    'end':       data.get('end', ''),
                    'ip':        data.get('ip', ''),
                    'note':      data.get('note', ''),
                    'createdAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
                save_leads(leads)
                self._json(200, {'success': True})
            elif action == 'updateRow':
                idx = (data.get('rowIndex') or 2) - 2
                if 0 <= idx < len(leads):
                    for f in ['status','name','title','company','email','domain','start','end','ip','note']:
                        if f in data:
                            leads[idx][f] = data[f]
                    save_leads(leads)
                self._json(200, {'success': True})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Token')
        self.end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}]", fmt % args)

if __name__ == '__main__':
    cfg = load_config()
    print(f'Admin: {cfg["username"]} / {cfg["password"]}')
    print('Server running on http://localhost:8765')
    http.server.HTTPServer(('', 8765), Handler).serve_forever()
