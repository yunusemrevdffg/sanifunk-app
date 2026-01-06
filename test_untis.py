import webuntis

s = webuntis.Session(
    server='bb-ges-bonn.webuntis.com',
    username='güveyun8142',
    password='yunuspro8.',
    school='bb-ges-bonn',
    # Dieser Teil hier ist zwingend erforderlich:
    useragent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
)

try:
    s.login()
    print("✅ Login erfolgreich!")
    # Zeigt dir an, wer du laut Untis bist
    print(f"Name im System: {s.get_self().surname}, {s.get_self().forename}")
    s.logout()
except Exception as e:
    print(f"❌ Fehler: {e}")