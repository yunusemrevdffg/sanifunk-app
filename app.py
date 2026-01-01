from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort, send_from_directory
import json
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sani_funk_2024_secure" 
app.permanent_session_lifetime = timedelta(days=30)

USER_FILE = 'users.json'
GROUP_FILE = 'groups.json'

def load_data(file):
    if not os.path.exists(file): return {}
    with open(file, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

USERS = load_data(USER_FILE)
GROUPS = load_data(GROUP_FILE)

ONESIGNAL_APP_ID = "d870e250-c800-4f83-bacb-c05f6e08c99f"
ONESIGNAL_API_KEY = "os_v2_app_3byoeugiabhyhowlybpw4cgjt73jjhkomigurg5ebzfpa4uvtea7dair63pdi5nkbwe4u5z3n77gb2tmfxko5bcg4nrtfw4s4mklsmi"

def send_push(title, message, is_alarm=True):
    header = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Basic {ONESIGNAL_API_KEY}"}
    payload = {"app_id": ONESIGNAL_APP_ID, "included_segments": ["All"], "headings": {"en": title}, "contents": {"en": message}, "priority": 10}
    if is_alarm: payload["ios_sound"] = "alarm.wav"
    try: requests.post("https://onesignal.com/api/v1/notifications", headers=header, json=payload, timeout=5)
    except: pass

@app.route('/OneSignalSDKWorker.js')
def onesignal_worker():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'OneSignalSDKWorker.js')

@app.route('/')
def index():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if not user: return redirect(url_for('logout'))
    if not user.get('group'): return redirect(url_for('group_menu'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        pw = request.form.get('password', '').strip()
        if email in USERS and USERS[email]['password'] == pw:
            session.permanent = True
            session['email'] = email
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen!')
    return render_template('login.html')

@app.route('/group-menu', methods=['GET', 'POST'])
def group_menu():
    if 'email' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        g_name = request.form.get('group_name', '').strip()
        if g_name:
            if g_name not in GROUPS:
                GROUPS[g_name] = {'members': [], 'messages': [], 'history': [], 'global_alarm': None}
            if session['email'] not in GROUPS[g_name]['members']:
                GROUPS[g_name]['members'].append(session['email'])
            USERS[session['email']]['group'] = g_name
            save_data(USER_FILE, USERS); save_data(GROUP_FILE, GROUPS)
            return redirect(url_for('dashboard'))
    return render_template('group_menu.html', groups=GROUPS)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    group = GROUPS.get(user.get('group'), {'members': []})
    return render_template('dashboard.html', user=user, members_emails=group.get('members', []), all_users=USERS)

@app.route('/chat')
def chat():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    group = GROUPS.get(user.get('group'), {})
    return render_template('chat.html', user=user, messages=group.get('messages', []))

@app.route('/api/check_alarm')
def check_alarm():
    user = USERS.get(session.get('email'))
    if not user: return jsonify({'active': False})
    p = user.get('active_alarm'); g = GROUPS.get(user['group'], {}).get('global_alarm')
    if p and p['active']: return jsonify(p)
    if g and g['active'] and g['sender_email'] != session['email']: return jsonify(g)
    return jsonify({'active': False})

@app.route('/api/stop_alarm', methods=['POST'])
def stop_alarm():
    email = session['email']
    if email in USERS: USERS[email]['active_alarm'] = None
    group = USERS[email].get('group')
    if group in GROUPS: GROUPS[group]['global_alarm'] = None
    save_data(USER_FILE, USERS); save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'stopped'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)