import webuntis
s = webuntis.Session(
    server='bb-ges-bonn.webuntis.com',
    username='güveyun8142',
    password='yunuspro8.',
    school='bb-ges-bonn',
    useragent="Mozilla/5.0"
)
s.login()
# Dieser Befehl zeigt uns deine versteckte ID
print(f"DEINE ID IST: {s._user_id}")
s.logout()