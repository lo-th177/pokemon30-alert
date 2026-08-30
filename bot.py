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

    if not os.path.exists(SEEN_FILE):
        return {}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return normalize_state(data)

    except (json.JSONDecodeError, OSError) as error:
        print(f"Erreur lecture mémoire : {error}")

    return {}


def normalize_state(data):

    normalized = {}

    for url, product in data.items():

        if isinstance(product, str):

            normalized[url] = {
                "name": product,
                "shop": "Playin",
                "status": "unknown"
            }

        elif isinstance(product, dict):

            normalized[url] = {
                "name": product.get("name", "Produit inconnu"),
                "shop": product.get("shop", "Playin"),
                "status": product.get("status", "unknown")
            }

    return normalized


def save_state(products):

    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as file:
            json.dump(
                products,
                file,
                ensure_ascii=False,
                indent=2
            )

    except OSError as error:
        print(f"Erreur sauvegarde mémoire : {error}")


def send_telegram(message):

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


def get_product_status(product_url):

    try:
        response = requests.get(
            product_url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as error:
        print(f"Erreur récupération produit : {error}")

        return "unknown"

    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text(
        " ",
        strip=True
    ).lower()

    # Recherche des boutons et actions réelles
    purchase_texts = []

    for element in soup.find_all(
        ["button", "input", "a"]
    ):

        text = element.get_text(
            " ",
            strip=True
        ).lower()

        value = element.get(
            "value",
            ""
        ).strip().lower()

        aria = element.get(
            "aria-label",
            ""
        ).strip().lower()

        combined = f"{text} {value} {aria}"

        if combined:
            purchase_texts.append(combined)

    purchase_actions = " ".join(
        purchase_texts
    )

    # PRIORITÉ 1 : véritable précommande
    if (
        "précommander" in purchase_actions
        or "precommander" in purchase_actions
        or "précommande" in purchase_actions
        or "precommande" in purchase_actions
    ):
        return "preorder"

    # PRIORITÉ 2 : véritable ajout au panier
    if (
        "ajouter au panier" in purchase_actions
        or "ajouter au panier" in page_text
    ):
        return "in_stock"

    # PRIORITÉ 3 : messages explicites d'indisponibilité
    if (
        "rupture temporaire en livraison" in page_text
        or "rupture de stock" in page_text
        or "livraison indisponible" in page_text
        or "indisponible" in page_text
    ):
        return "out_of_stock"

    return "unknown"


def fetch_playin():

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

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    products = {}

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        name = link.get_text(
            " ",
            strip=True
        )

        if "/fr/produit/" not in href:
            continue

        if not name:
            continue

        product_url = urljoin(
            URL_PLAYIN,
            href
        )

        if product_url in products:
            continue

        status = get_product_status(
            product_url
        )

        products[product_url] = {
            "name": name,
            "shop": "Playin",
            "status": status
        }

        print(
            f"{name} -> {status}"
        )

    return products


def status_label(status):

    labels = {
        "in_stock": "🟢 EN STOCK",
        "preorder": "🟠 PRÉCOMMANDE",
        "out_of_stock": "🔴 RUPTURE / INDISPONIBLE",
        "unknown": "⚪ STATUT INCONNU"
    }

    return labels.get(
        status,
        "⚪ STATUT INCONNU"
    )


def detect_changes(previous, current):

    new_products = {}

    status_changes = []

    for url, product in current.items():

        if url not in previous:

            new_products[url] = product

            continue

        old_status = previous[url].get(
            "status",
            "unknown"
        )

        new_status = product.get(
            "status",
            "unknown"
        )

        if (
            old_status != new_status
            and new_status != "unknown"
        ):

            status_changes.append(
                {
                    "url": url,
                    "name": product["name"],
                    "old_status": old_status,
                    "new_status": new_status
                }
            )

    return new_products, status_changes


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

    print(
        f"Produits Playin détectés : "
        f"{len(current_products)}"
    )

    new_products, status_changes = detect_changes(
        previous_products,
        current_products
    )

    for product_url, product in new_products.items():

        message = (
            "🚨 NOUVEAU PRODUIT "
            "POKÉMON 30e ANNIVERSAIRE !\n\n"
            "🏪 Playin\n"
            f"📦 {product['name']}\n"
            f"{status_label(product['status'])}\n\n"
            f"🔗 {product_url}"
        )

        send_telegram(message)

    for change in status_changes:

        if (
            change["old_status"] == "out_of_stock"
            and change["new_status"] == "in_stock"
        ):

            title = "🚨🚨 RETOUR EN STOCK ! 🚨🚨"

        elif change["new_status"] == "preorder":

            title = "🔥🔥 PRÉCOMMANDE OUVERTE ! 🔥🔥"

        else:

            title = "🔔 CHANGEMENT DE STATUT"

        message = (
            f"{title}\n\n"
            "🏪 Playin\n"
            f"📦 {change['name']}\n\n"
            f"Avant : {status_label(change['old_status'])}\n"
            f"Maintenant : {status_label(change['new_status'])}\n\n"
            f"🔗 {change['url']}"
        )

        send_telegram(message)

    print(f"Nouveaux produits : {len(new_products)}")
    print(f"Changements de statut : {len(status_changes)}")

    save_state(current_products)

    print("Surveillance terminée.")


if __name__ == "__main__":
    main()