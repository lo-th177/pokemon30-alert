import os
import json
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "1373516274"

URL_PLAYIN = "https://www.play-in.com/fr/extension/1500/30eme-anniversaire"
SEEN_FILE = "seen_products.json"

headers = {
    "User-Agent": "Mozilla/5.0"
}


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    print("Telegram :", response.text)


# Recuperation de la page Playin
response = requests.get(
    URL_PLAYIN,
    headers=headers,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# Recuperation des liens de la page
products = {}

for link in soup.find_all("a", href=True):
    name = link.get_text(" ", strip=True)
    href = link["href"]

    if name and len(name) > 5:
        if "/fr/" in href and "30eme-anniversaire" not in href:
            if href.startswith("/"):
                href = "https://www.play-in.com" + href

            products[name] = href


print(f"Produits trouves : {len(products)}")

# Lecture des produits deja connus
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r", encoding="utf-8") as file:
        seen = json.load(file)
else:
    seen = {}

# Recherche des nouveaux produits
new_products = {}

for name, link in products.items():
    if link not in seen.values():
        new_products[name] = link

# Premiere execution : on memorise sans envoyer 50 alertes
if not seen:
    message = (
        "🟢 Surveillance Playin active !\n\n"
        f"📦 {len(products)} elements detectes sur la page.\n"
        "Les produits actuels sont maintenant memorises."
    )

    send_telegram(message)

else:
    for name, link in new_products.items():
        message = (
            "🚨 NOUVEAU PRODUIT DETECTE !\n\n"
            f"🏪 Playin\n"
            f"📦 {name}\n\n"
            f"🔗 {link}"
        )

        send_telegram(message)

# Sauvegarde
with open(SEEN_FILE, "w", encoding="utf-8") as file:
    json.dump(products, file, ensure_ascii=False, indent=2)

print(f"Nouveaux produits : {len(new_products)}")