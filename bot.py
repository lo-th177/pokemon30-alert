import os
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "1373516274"

URL_PLAYIN = "https://www.play-in.com/fr/extension/1500/30eme-anniversaire"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(
    URL_PLAYIN,
    headers=headers,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

text = soup.get_text(" ", strip=True)

message = (
    "🔍 TEST SURVEILLANCE PLAYIN\n\n"
    "Le bot a bien consulte la page Pokemon 30e anniversaire.\n\n"
    f"Statut du site : {response.status_code}"
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

telegram = requests.post(
    url,
    data={
        "chat_id": CHAT_ID,
        "text": message
    },
    timeout=20
)

print("Playin :", response.status_code)
print("Telegram :", telegram.text)