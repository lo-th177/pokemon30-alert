import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "1373516274"

URL_PLAYIN = "https://www.play-in.com/fr/extension/1500/30eme-anniversaire"
SEEN_FILE = "seen_products.json"

HEADERS = {
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

    response.raise_for_status()


# Recuperation de la page Playin
response = requests.get(
    URL_PLAYIN,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

products = {}

# On garde uniquement les vrais liens produits Playin
for link in soup.find_all("a", href=True):

    href = link["href"]
    name = link.get_text(" ", strip=True)

    if "/fr/produit/" not in href:
        continue

    if not name:
        continue

    href = urljoin(URL_PLAYIN, href)

    # On évite les doublons
    products[href] = name


print(f"Vrais produits Playin trouves : {len(products)}")


# Lecture des produits deja memorises
if os.path.exists(SEEN_FILE):

    with open(SEEN_FILE, "r", encoding="utf-8") as file:
        seen = json.load(file)

else:
    seen = {}


# Detection des nouveaux produits
new_products = {
    url: name
    for url, name in products.items()
    if url not in seen
}


# Premiere execution avec le nouveau filtre
if not seen:

    message = (
        "🟢 Surveillance Playin active !\n\n"
        f"📦 {len(products)} vrais produits detectes.\n"
        "La liste est maintenant memorisee."
    )

    send_telegram(message)

else:

    for product_url, product_name in new_products.items():

        message = (
            "🚨 NOUVEAU PRODUIT POKEMON 30e ANNIVERSAIRE !\n\n"
            "🏪 Playin\n"
            f"📦 {product_name}\n\n"
            f"🔗 {product_url}"
        )

        send_telegram(message)


# Sauvegarde
with open(SEEN_FILE, "w", encoding="utf-8") as file:

    json.dump(
        products,
        file,
        ensure_ascii=False,
        indent=2
    )


print(f"Nouveaux produits : {len(new_products)}")