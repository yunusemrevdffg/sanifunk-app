// Chat automatisch nach unten scrollen
const chatBox = document.getElementById('chat-box');
if (chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('chat-msg');
    const text = input.value.strip();
    if (!text) return;

    fetch('/api/send_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
    })
    .then(res => res.json())
    .then(data => {
        // Seite neu laden um die Nachricht in der Liste zu sehen
        location.reload(); 
    });
}

function sendCriticalAlarm() {
    navigator.geolocation.getCurrentPosition((pos) => {
        alert("🚨 ALARM AUSGELÖST!\nGPS: " + pos.coords.latitude + ", " + pos.coords.longitude);
        const audio = new Audio('/static/audio/alarm.mp3');
        audio.play();
    });
}