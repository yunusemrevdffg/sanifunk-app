from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sani_funk_ultra_2024_secure" 
app.permanent_session_lifetime = timedelta(days=30)

# Dateipfade für die Datenbank (JSON-Dateien)
USER_FILE = 'users.json'
GROUP_FILE = 'groups.json'
REPORT_FILE = 'reports.json'
BAN_CHAT_FILE = 'ban_chats.json'

# --- DATEN-MANAGEMENT ---
def load_data(file):
    if not os.path.exists(file): return {}
    with open(file, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Daten beim Start laden
USERS = load_data(USER_FILE)
GROUPS = load_data(GROUP_FILE)
REPORTS = load_data(REPORT_FILE)
BAN_CHATS = load_data(BAN_CHAT_FILE)

@app.context_processor
def inject_globals():
    return dict(USERS=USERS, GROUPS=GROUPS, REPORTS=REPORTS, BAN_CHATS=BAN_CHATS)

# --- HELFER ---
def is_user_banned():
    if 'email' in session:
        user = USERS.get(session['email'])
        return user.get('banned', False) if user else False
    return False

# --- NAVIGATION & AUTH ---
@app.route('/')
def index():
    if 'email' not in session: return redirect(url_for('login'))
    if is_user_banned(): return redirect(url_for('banned_page'))
    
    user = USERS.get(session['email'])
    if not user: return redirect(url_for('logout'))
    if user.get('role') == 'HAUPTADMIN': return redirect(url_for('management'))
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
            if USERS[email].get('banned'):
                return redirect(url_for('banned_page'))
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen!')
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email', '').lower().strip()
    pw = request.form.get('password', '').strip()
    if email in USERS:
        flash('E-Mail existiert bereits!')
    else:
        USERS[email] = {
            'name': name, 
            'password': pw, 
            'role': 'SANI', 
            'group': None, 
            'active_alarm': None, 
            'banned': False
        }
        save_data(USER_FILE, USERS)
        flash('Registrierung erfolgreich! Bitte einloggen.')
    return redirect(url_for('login'))

# --- HAUPTSEITEN ---
@app.route('/dashboard')
def dashboard():
    if 'email' not in session or is_user_banned(): return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if not user.get('group'): return redirect(url_for('group_menu'))
    
    group = GROUPS.get(user.get('group'), {'members': []})
    return render_template('dashboard.html', user=user, members_emails=group.get('members', []), all_users=USERS)

@app.route('/alarm_log')
def alarm_log():
    if 'email' not in session or is_user_banned(): return redirect(url_for('login'))
    user = USERS.get(session['email'])
    group = GROUPS.get(user.get('group'), {})
    return render_template('alarm_log.html', history=group.get('history', []), user=user)

@app.route('/chat')
def chat():
    if 'email' not in session or is_user_banned(): return redirect(url_for('login'))
    user = USERS[session['email']]
    group = GROUPS.get(user.get('group'), {})
    return render_template('chat.html', user=user, messages=group.get('messages', []))

@app.route('/group-menu', methods=['GET', 'POST'])
def group_menu():
    if 'email' not in session or is_user_banned(): return redirect(url_for('login'))
    email = session['email']
    if request.method == 'POST':
        action = request.form.get('action')
        g_name = request.form.get('group_name', '').strip()
        
        if action == 'create':
            GROUPS[g_name] = {
                'admin': email, 
                'members': [email], 
                'messages': [], 
                'history': [], 
                'type': request.form.get('group_type'), 
                'password': request.form.get('group_password')
            }
            # Beim Erstellen wird man immer ADMIN
            USERS[email].update({'group': g_name, 'role': 'ADMIN'})
            
        elif action == 'join':
            target = GROUPS.get(g_name)
            if target:
                if target['type'] == 'private' and target['password'] != request.form.get('join_password'):
                    flash('Falsches Passwort!')
                    return redirect(url_for('group_menu'))
                
                if email not in target['members']: target['members'].append(email)
                
                # UPDATE: Nur auf SANI setzen, wenn die aktuelle Rolle nicht schon ADMIN oder HAUPTADMIN ist
                current_role = USERS[email].get('role', 'SANI')
                if current_role not in ['ADMIN', 'HAUPTADMIN']:
                    USERS[email]['role'] = 'SANI'
                
                USERS[email]['group'] = g_name
                
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
        return redirect(url_for('dashboard'))
    return render_template('group_menu.html', groups=GROUPS)

@app.route('/api/leave_group', methods=['POST'])
def leave_group():
    email = session.get('email')
    if email and email in USERS:
        old_group = USERS[email].get('group')
        if old_group in GROUPS:
            if email in GROUPS[old_group]['members']:
                GROUPS[old_group]['members'].remove(email)
        
        USERS[email]['group'] = None
        # USERS[email]['role'] = 'SANI'  <-- DIESE ZEILE LÖSCHEN ODER AUSKOMMENTIEREN
        
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'ok'})

@app.route('/api/trigger_alarm', methods=['POST'])
def trigger_alarm():
    if 'email' not in session or is_user_banned(): return jsonify({'status': 'error'}), 403
    user = USERS.get(session['email'])
    group_name = user.get('group')
    if not group_name: return jsonify({'status': 'error'}), 400
    
    data = request.json
    target_type = data.get('target', 'all')
    
    # Bestimmen, an wen der Alarm geht (für den Log)
    target_name = "ALLE" if target_type == "all" else USERS.get(target_type, {}).get('name', 'Unbekannt')

    alarm_entry = {
        'from_name': user['name'],
        'from_email': session['email'],
        'to_name': target_name,
        'message': data.get('message', 'EINSATZ'), 
        'lat': data.get('lat'), 
        'lng': data.get('lng'),
        'time': datetime.now().strftime('%H:%M:%S'), # Jetzt mit Sekunden
        'date': datetime.now().strftime('%d.%m.%Y')
    }
    
    if 'history' not in GROUPS[group_name]: GROUPS[group_name]['history'] = []
    GROUPS[group_name]['history'].insert(0, alarm_entry)
    
    # Alarm an User verteilen
    if target_type == 'all':
        for m in GROUPS[group_name]['members']:
            if m in USERS: USERS[m]['active_alarm'] = alarm_entry
    elif target_type in USERS:
        USERS[target_type]['active_alarm'] = alarm_entry
        
    save_data(USER_FILE, USERS)
    save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'ok'})

@app.route('/api/check_alarm')
def check_alarm():
    user = USERS.get(session.get('email'))
    if user and user.get('active_alarm'):
        a = user['active_alarm']
        return jsonify({
            'active': True, 
            'from': a['sender'], 
            'msg': a['message'], 
            'lat': a.get('lat'), 
            'lng': a.get('lng')
        })
    return jsonify({'active': False})

@app.route('/api/stop_alarm', methods=['POST'])
def stop_alarm():
    if 'email' in session:
        USERS[session['email']]['active_alarm'] = None
        save_data(USER_FILE, USERS)
    return jsonify({'status': 'ok'})

# --- CHAT SYSTEM (API) ---
@app.route('/api/send_message', methods=['POST'])
def send_message():
    user = USERS.get(session.get('email'))
    if not user or not user.get('group') or is_user_banned(): return jsonify({'status': 'error'}), 403
    data = request.json
    group_name = user['group']
    new_msg = {
        'sender': user['name'], 
        'content': data.get('message'), 
        'time': datetime.now().strftime('%H:%M')
    }
    if 'messages' not in GROUPS[group_name]: GROUPS[group_name]['messages'] = []
    GROUPS[group_name]['messages'].append(new_msg)
    save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'ok'})

@app.route('/api/get_messages')
def get_messages():
    user = USERS.get(session.get('email'))
    if not user or not user.get('group') or is_user_banned(): return jsonify([])
    return jsonify(GROUPS.get(user['group'], {}).get('messages', []))

# --- ADMIN & BANNED ---
@app.route('/management')
def management():
    if 'email' not in session or is_user_banned(): return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if user['role'] not in ['ADMIN', 'HAUPTADMIN']: abort(403)
    
    is_haupt = (user['role'] == 'HAUPTADMIN')
    m_list = list(USERS.keys()) if is_haupt else GROUPS.get(user['group'], {}).get('members', [])
    return render_template('management.html', user=user, members=m_list, USERS=USERS, GROUPS=GROUPS, REPORTS=REPORTS, is_hauptadmin=is_haupt)

@app.route('/banned')
def banned_page():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if not user or not user.get('banned'): return redirect(url_for('index'))
    return render_template('banned.html', user=user)

# --- NEU: BAN SUPPORT LOGIK ---
@app.route('/api/send_ban_appeal', methods=['POST'])
def send_ban_appeal():
    if 'email' not in session: return jsonify({'status': 'error'}), 403
    email = session['email']
    data = request.json
    if email not in BAN_CHATS: BAN_CHATS[email] = []
    BAN_CHATS[email].append({
    'sender': USERS[email]['name'],
    'message': data.get('message'),
    'time': datetime.now().strftime('%H:%M'),
    'date': datetime.now().strftime('%d.%m.%Y'),
    'is_admin': False  # <--- Wichtig für die Unterscheidung im Chat-Fenster
    })
    save_data(BAN_CHAT_FILE, BAN_CHATS)
    return jsonify({'status': 'ok'})

@app.route('/api/admin/reply_ban', methods=['POST'])
def reply_ban():
    admin = USERS.get(session.get('email'))
    if not admin or admin['role'] != 'HAUPTADMIN': abort(403)
    data = request.json
    target_email = data.get('email')
    if target_email in BAN_CHATS:
        BAN_CHATS[target_email].append({
            'sender': "HAUPTADMIN",
            'message': data.get('message'),
            'time': datetime.now().strftime('%H:%M'),
            'date': datetime.now().strftime('%d.%m.%Y'),
            'is_admin': True
        })
        save_data(BAN_CHAT_FILE, BAN_CHATS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/api/report_user', methods=['POST'])
def report_user():
    if 'email' not in session or is_user_banned(): return jsonify({'status': 'error'}), 403
    data = request.json
    target = data.get('target_email')
    if target in USERS:
        if target not in REPORTS: REPORTS[target] = []
        REPORTS[target].append({
            'from': USERS[session['email']]['name'], 
            'reason': data.get('reason'), 
            'time': datetime.now().strftime('%H:%M'), 
            'date': datetime.now().strftime('%d.%m.%Y')
        })
        save_data(REPORT_FILE, REPORTS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

# --- ADMIN ACTIONS (API) ---
@app.route('/api/admin/update_user', methods=['POST'])
def update_user():
    admin = USERS.get(session.get('email'))
    if not admin or admin['role'] not in ['ADMIN', 'HAUPTADMIN']: abort(403)
    data = request.json
    target = data.get('email')
    if target in USERS:
        if 'role' in data: USERS[target]['role'] = data['role']
        if 'password' in data: USERS[target]['password'] = data['password']
        save_data(USER_FILE, USERS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/api/admin/toggle_ban', methods=['POST'])
def toggle_ban():
    admin = USERS.get(session.get('email'))
    if not admin or admin['role'] not in ['ADMIN', 'HAUPTADMIN']: abort(403)
    target = request.json.get('email')
    
    if target in USERS:
        current_status = USERS[target].get('banned', False)
        new_status = not current_status
        
        USERS[target]['banned'] = new_status
        
        # Wenn er gerade entbannt wurde, markieren wir ihn permanent
        if current_status == True and new_status == False:
            USERS[target]['was_banned'] = True
            # Optional: Chat-Verlauf löschen, wenn er entbannt wurde
            if target in BAN_CHATS:
                del BAN_CHATS[target]
        
        save_data(USER_FILE, USERS)
        save_data(BAN_CHAT_FILE, BAN_CHATS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/api/admin/delete_user', methods=['POST'])
def delete_user():
    if USERS.get(session['email'], {}).get('role') != 'HAUPTADMIN': abort(403)
    target = request.json.get('email')
    if target in USERS:
        del USERS[target]
        save_data(USER_FILE, USERS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

# --- NEU: GRUPPEN LÖSCHEN ---
@app.route('/api/admin/delete_group', methods=['POST'])
def delete_group():
    if USERS.get(session['email'], {}).get('role') != 'HAUPTADMIN': abort(403)
    g_name = request.json.get('group_name')
    if g_name in GROUPS:
        for m_email in GROUPS[g_name]['members']:
            if m_email in USERS:
                USERS[m_email]['group'] = None
                USERS[m_email]['role'] = 'SANI'
        del GROUPS[g_name]
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/api/admin/clear_reports', methods=['POST'])
def clear_reports():
    if USERS.get(session['email'], {}).get('role') != 'HAUPTADMIN': abort(403)
    target = request.json.get('email')
    if target in REPORTS: 
        del REPORTS[target]
        save_data(REPORT_FILE, REPORTS)
    return jsonify({'status': 'ok'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)