from flask import Flask, render_template, request, session, jsonify
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
import json
import os
from datetime import datetime, timedelta
import webuntis

app = Flask(__name__)
app.secret_key = "sani_funk_ultra_2024_secure" 
app.permanent_session_lifetime = timedelta(days=30)

# --- DATEIPFADE ---
USER_FILE = 'users.json'
GROUP_FILE = 'groups.json'
REPORT_FILE = 'reports.json'
BAN_CHAT_FILE = 'ban_chats.json'

# --- DATEN-MANAGEMENT ---
def load_data(file, default_type=dict):
    if not os.path.exists(file): return default_type()
    with open(file, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return default_type()

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

USERS = load_data(USER_FILE)
GROUPS = load_data(GROUP_FILE)
REPORTS = load_data(REPORT_FILE)
BAN_CHATS = load_data(BAN_CHAT_FILE)

@app.context_processor
def inject_globals():
    return dict(USERS=USERS, GROUPS=GROUPS, REPORTS=REPORTS, BAN_CHATS=BAN_CHATS, timedelta=timedelta)


@app.route('/api/get_latest_alarm')
def get_latest_alarm():
    # Hier prüfst du, ob ein neuer Alarm in deiner Datenbank/JSON ist
    # Beispiel-Rückgabe:
    return jsonify({
        "id": 123,
        "title": "🚨 NOTFALL-ALARM",
        "message": "Sanitäter zur Pausenhalle!",
        "type": "CRITICAL"
    })

# --- MIDDLEWARE ---
@app.before_request
def check_banned_middleware():
    my_email = session.get('email')
    allowed_paths = ['/logout', '/api/send_ban_appeal', '/static', '/login', '/register', '/banned']
    if any(request.path.startswith(path) for path in allowed_paths): return
    if my_email:
        user_data = USERS.get(my_email)
        if user_data and user_data.get('banned'):
            return redirect(url_for('banned', target_email=my_email))

# --- NAVIGATION & AUTH ---
@app.route('/')
def index():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if not user: return redirect(url_for('logout'))
    if user.get('role') == 'HAUPTADMIN': return redirect(url_for('management'))
    if not user.get('group'): return redirect(url_for('group_menu'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '').strip()
        user = USERS.get(email)
        if user and user['password'] == password:
            session.permanent = True
            session['email'] = email
            session['role'] = user.get('role', 'SANI')
            return redirect(url_for('index'))
        flash("E-Mail oder Passwort falsch!")
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name'); email = request.form.get('email', '').lower().strip(); pw = request.form.get('password', '').strip()
    if email in USERS: flash('E-Mail existiert bereits!')
    else:
        USERS[email] = {'name': name, 'password': pw, 'role': 'SANI', 'group': None, 'active_alarm': None, 'banned': False}
        save_data(USER_FILE, USERS); flash('Erfolg! Bitte einloggen.')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# --- PROFIL & UNTIS ---
@app.route('/profile')
def profile():
    if 'email' not in session: return redirect(url_for('login'))
    return render_template('profile.html', user=USERS.get(session['email']))

@app.route('/untis_hilfe')
def untis_hilfe():
    return """
    <div style="font-family:sans-serif; padding:30px; max-width:600px; margin:auto; line-height:1.6;">
        <h2 style="color:#2563eb;">So findest du deine User-ID:</h2>
        <p>Da WebUntis den Zugriff für Schüler einschränkt, musst du deine ID einmalig manuell eingeben:</p>
        <ol>
            <li>Melde dich am PC bei <b>WebUntis</b> an.</li>
            <li>Klicke auf deinen <b>Namen</b> (Profil) oben rechts.</li>
            <li>In der Web-Adresse (URL) deines Browsers steht ganz am Ende eine Zahl, z.B. <code>studentId=1613</code>.</li>
            <li>Kopiere diese Zahl (z.B. <b>1613</b>) und trage sie im Profil ein.</li>
        </ol>
        <a href="/profile" style="display:inline-block; margin-top:20px; padding:12px 25px; background:#2563eb; color:white; text-decoration:none; border-radius:8px; font-weight:bold;">Zurück zum Profil</a>
    </div>
    """

@app.route('/untis', methods=['GET', 'POST'])
def untis_view():
    my_email = session.get('email')
    if not my_email: 
        return redirect(url_for('login'))
    
    me = USERS.get(my_email)
    target_email = request.form.get('target_email', my_email)
    user_data = USERS.get(target_email, me)
    
    plan_data = []
    error_msg = None
    
    u_user = user_data.get('untis_user')
    u_pass = user_data.get('untis_password')
    u_id = user_data.get('untis_id')
    
    if u_user and u_pass and u_id:
        s = webuntis.Session(
            server='bb-ges-bonn.webuntis.com', 
            username=u_user, 
            password=u_pass, 
            school='bb-ges-bonn', 
            useragent="Mozilla/5.0"
        )
        try:
            s.login()
            # Zeitraum: Heute bis Morgen
            start_t = datetime.now()
            end_t = start_t + timedelta(days=1)
            
            timetable = s.timetable(start=start_t, end=end_t, student=u_id)
            
            for entry in timetable:
                sub = entry.subjects[0] if entry.subjects else None
                # Hier wird das Dictionary korrekt aufgebaut:
                plan_data.append({
                    'zeit_anzeige': f"{entry.start.strftime('%H:%M')} - {entry.end.strftime('%H:%M')}",
                    'start_sort': entry.start,
                    'subject': getattr(sub, 'name', 'Freistunde') if sub else "Freistunde",
                    'room': entry.rooms[0].name if entry.rooms else "---",
                    'teacher': entry.teachers[0].name if entry.teachers else "---",
                    'code': entry.code  # <--- Hier lag der Syntaxfehler (muss in den {} stehen)
                })
            
            plan_data.sort(key=lambda x: x['start_sort'])
            s.logout()
        except Exception as e: 
            error_msg = f"WebUntis Fehler: {str(e)}"
    else:
        error_msg = "Keine WebUntis-Logindaten im Profil hinterlegt."
    
    # Mitglieder der eigenen Gruppe für das Menü oben
    m_list = [dict(d, email=e) for e, d in USERS.items() if d.get('group') == me.get('group')]
    
    return render_template('untis.html', 
                           plan=plan_data, 
                           target=user_data.get('name'), 
                           members=m_list, 
                           error=error_msg,
                           user=me)


# In der app.py hinzufügen



@app.route('/api/save_untis', methods=['POST'])
def save_untis():
    my_email = session.get('email')
    if not my_email: return redirect(url_for('login'))
    USERS[my_email].update({'untis_user': request.form.get('untis_user'), 'untis_id': request.form.get('untis_id')})
    if request.form.get('untis_password'): USERS[my_email]['untis_password'] = request.form.get('untis_password')
    save_data(USER_FILE, USERS); return redirect(url_for('profile'))

# --- DASHBOARD & GRUPPEN ---
@app.route('/dashboard')
def dashboard():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    group_name = user.get('group')
    if not group_name or group_name not in GROUPS: return redirect(url_for('group_menu'))
    group = GROUPS.get(group_name)
    return render_template('dashboard.html', user=user, members_emails=group.get('members', []), all_users=USERS)

@app.route('/group_menu', methods=['GET', 'POST'])
def group_menu():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if request.method == 'POST':
        action = request.form.get('action'); g_name = request.form.get('group_name', '').strip()
        if action == 'create' and g_name:
            if g_name in GROUPS: flash('Name vergeben!')
            else:
                GROUPS[g_name] = {'admin': session['email'], 'members': [session['email']], 'messages': [], 'history': [], 'type': request.form.get('group_type'), 'password': request.form.get('group_password', '')}
                user.update({'group': g_name, 'role': 'ADMIN'}); save_data(USER_FILE, USERS); save_data(GROUP_FILE, GROUPS)
                return redirect(url_for('dashboard'))
        elif action == 'join':
            target = GROUPS.get(g_name)
            if target:
                if target['type'] == 'private' and target['password'] != request.form.get('join_password'): flash('Falsch!')
                else:
                    if session['email'] not in target['members']: target['members'].append(session['email'])
                    user['group'] = g_name; save_data(USER_FILE, USERS); save_data(GROUP_FILE, GROUPS)
                    return redirect(url_for('dashboard'))
    return render_template('group_menu.html', groups=GROUPS)

# --- CHAT & ALARM ---
@app.route('/chat')
def chat():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS[session['email']]; group = GROUPS.get(user.get('group'), {})
    return render_template('chat.html', user=user, messages=group.get('messages', []))

@app.route('/api/get_messages')
def get_messages():
    user = USERS.get(session.get('email'))
    if not user or not user.get('group'): return jsonify([])
    return jsonify(GROUPS.get(user['group'], {}).get('messages', []))

@app.route('/api/send_message', methods=['POST'])
def send_message():
    user = USERS.get(session.get('email')); group_name = user['group']
    new_msg = {'sender': user['name'], 'content': request.json.get('message'), 'time': datetime.now().strftime('%H:%M')}
    GROUPS[group_name].setdefault('messages', []).append(new_msg); save_data(GROUP_FILE, GROUPS); return jsonify({'status': 'ok'})

@app.route('/api/trigger_alarm', methods=['POST'])
def trigger_alarm():
    user = USERS.get(session.get('email'))
    group_name = user.get('group')
    data = request.json
    
    # Der Alarm-Eintrag mit der Bestätigungs-Liste
    alarm_entry = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S'),
        'from_name': user['name'],
        'message': data.get('message', '🚨 EINSATZ'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'date': datetime.now().strftime('%d.%m.%Y'),
        'confirmed_by': []  # Hier landen die Namen der Sanis
    }

    if group_name in GROUPS:
        GROUPS[group_name].setdefault('history', []).insert(0, alarm_entry)
        GROUPS[group_name]['history'] = GROUPS[group_name]['history'][:15]

    target = data.get('target', 'all')
    if target == 'all':
        for m in GROUPS[group_name]['members']:
            if m in USERS: USERS[m]['active_alarm'] = alarm_entry
    elif target in USERS:
        USERS[target]['active_alarm'] = alarm_entry
    
    save_data(USER_FILE, USERS)
    save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'ok'})

@app.route('/api/stop_alarm', methods=['POST'])
def stop_alarm():
    my_email = session.get('email')
    if my_email in USERS:
        user = USERS[my_email]
        group_name = user.get('group')
        
        # Sani in die Liste der Bestätigungen eintragen
        if group_name in GROUPS and GROUPS[group_name].get('history'):
            latest = GROUPS[group_name]['history'][0]
            if user['name'] not in latest.get('confirmed_by', []):
                latest.setdefault('confirmed_by', []).append(user['name'])
        
        USERS[my_email]['active_alarm'] = None
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
    return jsonify({'status': 'ok'})

@app.route('/alarm_log')
def alarm_log():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email']); group = GROUPS.get(user.get('group'), {})
    return render_template('alarm_log.html', history=group.get('history', []), user=user)

# --- MANAGEMENT & ADMIN ---
# --- ADMIN / HAUPTADMIN AKTIONEN ---

@app.route('/api/admin/dismiss_report', methods=['POST'])
def admin_dismiss_report():
    """ Löscht eine Meldung aus der Liste (Meldung erledigt) """
    if session.get('role') != 'HAUPTADMIN': 
        return jsonify({'status': 'error', 'message': 'Nicht autorisiert'}), 403
    
    target_email = request.json.get('email')
    if target_email in REPORTS:
        del REPORTS[target_email]
        save_data(REPORT_FILE, REPORTS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'message': 'Meldung nicht gefunden'}), 404

@app.route('/api/admin/delete_group', methods=['POST'])
def admin_delete_group():
    """ Löscht eine komplette Gruppe und setzt die Mitglieder auf 'Keine Gruppe' """
    if session.get('role') != 'HAUPTADMIN': 
        return jsonify({'status': 'error', 'message': 'Nicht autorisiert'}), 403
    
    g_name = request.json.get('group_name')
    if g_name in GROUPS:
        # Alle User finden, die in dieser Gruppe sind und Gruppe auf None setzen
        for email in USERS:
            if USERS[email].get('group') == g_name:
                USERS[email]['group'] = None
                # Wenn der User Admin war, wird er wieder zum SANI
                if USERS[email].get('role') == 'ADMIN':
                    USERS[email]['role'] = 'SANI'
        
        del GROUPS[g_name]
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'message': 'Gruppe nicht gefunden'}), 400

# --- AKTUALISIERTE MANAGEMENT ROUTE ---

@app.route('/management')
def management():
    if 'email' not in session: return redirect(url_for('login'))
    user = USERS.get(session['email'])
    if not user or user.get('role') not in ['ADMIN', 'HAUPTADMIN']: 
        return redirect(url_for('dashboard'))
    
    is_ha = (user['role'] == 'HAUPTADMIN')
    
    if is_ha:
        member_emails = list(USERS.keys())
        # Wir geben die Gruppen-Daten mit, damit wir im Template auf Passwörter zugreifen können
        return render_template('management.html', 
                               user=user, 
                               members=member_emails, 
                               is_hauptadmin=is_ha, 
                               all_groups=GROUPS) 
    else:
        member_emails = [e for e, u in USERS.items() if u.get('group') == user.get('group')]
        return render_template('management.html', 
                               user=user, 
                               members=member_emails, 
                               is_hauptadmin=is_ha)




@app.route('/api/admin/update_user', methods=['POST'])
def admin_update_user():
    if session.get('role') not in ['ADMIN', 'HAUPTADMIN']: return jsonify({'status': 'error'}), 403
    data = request.json; email = data.get('email')
    if email in USERS:
        if 'field' in data: USERS[email][data['field']] = data['value']
        if 'password' in data: USERS[email]['password'] = data['password']
        save_data(USER_FILE, USERS); return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'}), 404

@app.route('/api/admin/toggle_ban', methods=['POST'])
def toggle_ban():
    if session.get('role') not in ['ADMIN', 'HAUPTADMIN']: return jsonify({"status": "error"}), 403
    email = request.json.get('email')
    if email in USERS and USERS[email].get('role') != 'HAUPTADMIN':
        USERS[email]['banned'] = not USERS[email].get('banned', False)
        save_data(USER_FILE, USERS); return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404

@app.route('/api/admin/kick_user', methods=['POST'])
def kick_user():
    target = request.json.get('email'); admin = USERS.get(session.get('email'))
    if admin and admin.get('role') in ['ADMIN', 'HAUPTADMIN']:
        g = admin.get('group')
        if g in GROUPS and target in GROUPS[g]['members']:
            GROUPS[g]['members'].remove(target); USERS[target]['group'] = None
            save_data(USER_FILE, USERS); save_data(GROUP_FILE, GROUPS); return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400

# --- BAN SYSTEM & APPEALS ---
@app.route('/banned')
@app.route('/banned/<target_email>')
def banned(target_email=None):
    if 'email' not in session: 
        return redirect(url_for('login'))
    
    my_email = session['email']
    user_data = USERS.get(my_email)
    
    # Sicherheit: Wenn kein Ziel angegeben, ist man es selbst
    if not target_email:
        target_email = my_email

    # Logik für den Admin-Viewer-Modus:
    # Man muss Admin/Hauptadmin sein UND darf nicht selbst gerade gebannt sein
    # UND man muss sich das Profil eines ANDEREN ansehen.
    is_actually_banned = user_data.get('banned', False)
    is_admin_role = user_data.get('role') in ['ADMIN', 'HAUPTADMIN']
    
    is_admin_viewer = is_admin_role and not is_actually_banned and (target_email != my_email)

    return render_template('banned.html', 
                           target_email=target_email, 
                           is_admin_viewer=is_admin_viewer, 
                           BAN_CHATS=BAN_CHATS)

@app.route('/api/admin/delete_user', methods=['POST'])
def admin_delete_user():
    """ Löscht einen Benutzer komplett aus dem System """
    if session.get('role') != 'HAUPTADMIN': 
        return jsonify({'status': 'error', 'message': 'Nicht autorisiert'}), 403
    
    target_email = request.json.get('email')
    
    # Schutz vor Selbstlöschung oder Löschen des Inhabers
    if target_email == session.get('email') or target_email == 'yunusemreguevercin12@gmail.com':
        return jsonify({'status': 'error', 'message': 'Dieser User kann nicht gelöscht werden'}), 403

    if target_email in USERS:
        # 1. Aus Gruppe entfernen, falls vorhanden
        g_name = USERS[target_email].get('group')
        if g_name and g_name in GROUPS:
            if target_email in GROUPS[g_name]['members']:
                GROUPS[g_name]['members'].remove(target_email)
        
        # 2. Reports löschen
        if target_email in REPORTS:
            del REPORTS[target_email]
            
        # 3. Bann-Chats löschen
        if target_email in BAN_CHATS:
            del BAN_CHATS[target_email]

        # 4. User aus Haupt-Dictionary löschen
        del USERS[target_email]
        
        # Alles speichern
        save_data(USER_FILE, USERS)
        save_data(GROUP_FILE, GROUPS)
        save_data(REPORT_FILE, REPORTS)
        save_data(BAN_CHAT_FILE, BAN_CHATS)
        
        return jsonify({'status': 'ok'})
    
    return jsonify({'status': 'error', 'message': 'User nicht gefunden'}), 404

@app.route('/api/send_ban_appeal', methods=['POST'])
def send_ban_appeal():
    if 'email' not in session: return jsonify({'status': 'error'}), 403
    
    data = request.json
    target_email = data.get('target_email')
    message = data.get('message')
    
    if not message or not target_email:
        return jsonify({'status': 'error', 'message': 'Daten unvollständig'}), 400

    # Nachricht erstellen
    # In der app.py sicherstellen:
    new_msg = {
    'message': message,
    'is_admin': (session.get('role') in ['ADMIN', 'HAUPTADMIN']),
    'sender': session.get('email'), # <--- Das hier ist wichtig!
    'time': datetime.now().strftime("%H:%M"),
    'date': datetime.now().strftime("%d.%m.%Y")
    }
    
    if target_email not in BAN_CHATS:
        BAN_CHATS[target_email] = []
        
    BAN_CHATS[target_email].append(new_msg)
    save_data(BAN_CHAT_FILE, BAN_CHATS)
    
    return jsonify({'status': 'ok'})


@app.route('/api/report_user', methods=['POST'])
def report_user():
    target = request.json.get('target_email')
    REPORTS.setdefault(target, []).append({"from": USERS.get(session['email'], {}).get('name', 'Anonym'), "reason": request.json.get('reason'), "date": datetime.now().strftime("%d.%m.%Y")})
    save_data(REPORT_FILE, REPORTS); return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)