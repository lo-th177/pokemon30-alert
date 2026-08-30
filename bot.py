import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

URL_PLAYIN = "https://www.play-in.com/fr/extension/1500/30eme-anniversaire"
SEEN_FILE = "seen_products.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def load_state():
    """Charge les produits mémorisés."""
    if not os.path.exists(SEEN_FILE):
        return {}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

    except (json.JSONDecodeError, OSError) as error:
        print(f"Erreur lecture mémoire : {error}")

    return {}


def save_state(products):
    """Sauvegarde les produits détectés."""
    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2
        )


def send_telegram(message):
    """Envoie une alerte Telegram."""
    if not TOKEN or not CHAT_ID:
        print("Secrets Telegram manquants.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": False
            },
            timeout=20
        )

        response.raise_for_status()
        return True

    except requests.RequestException as error:
        print(f"Erreur Telegram : {error}")
        return False


def fetch_playin():
    """Récupère les produits présents sur Playin."""

    try:
        response = requests.get(
            URL_PLAYIN,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"Erreur Playin : {error}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    products = {}

    for link in soup.find_all("a", href=True):

        href = link["href"]
        name = link.get_text(" ", strip=True)

        if "/fr/produit/" not in href:
            continue

        if not name:
            continue

        product_url = urljoin(URL_PLAYIN, href)

        products[product_url] = {
            "name": name,
            "shop": "Playin"
        }

    return products


def detect_new_products(previous, current):
    """Détecte les nouveaux produits."""

    return {
        url: data
        for url, data in current.items()
        if url not in previous
    }


def main():

    if not TOKEN:
        print("ERREUR : TELEGRAM_BOT_TOKEN manquant.")
        return

    if not CHAT_ID:
        print("ERREUR : TELEGRAM_CHAT_ID manquant.")
        return

    previous_products = load_state()

    current_products = fetch_playin()

    if current_products is None:
        print("Impossible de récupérer Playin.")
        return

    print(f"Produits Playin détectés : {len(current_products)}")

    # Première exécution
    if not previous_products:

        message = (
            "🟢 Surveillance Playin active !\n\n"
            f"📦 {len(current_products)} produits détectés.\n\n"
            "La liste est maintenant mémorisée."
        )

        send_telegram(message)

    else:

        new_products = detect_new_products(
            previous_products,
            current_products
        )

        for product_url, product_data in new_products.items():

            message = (
                "🚨 NOUVEAU PRODUIT POKÉMON 30e ANNIVERSAIRE !\n\n"
                "🏪 Playin\n"
                f"📦 {product_data['name']}\n\n"
                f"🔗 {product_url}"
            )

            send_telegram(message)

        print(f"Nouveaux produits : {len(new_products)}")

    save_state(current_products)

    print("Surveillance terminée.")


if __name__ == "__main__":
    main()