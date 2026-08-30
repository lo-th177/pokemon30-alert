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
            return normalize_state(data)

    except (json.JSONDecodeError, OSError) as error:
        print(f"Erreur lecture mémoire : {error}")

    return {}


def normalize_state(data):
    """
    Rend compatible l'ancien format :
    URL -> nom

    avec le nouveau format :
    URL -> {name, shop, status}
    """

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
    """Sauvegarde les produits détectés."""

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


def get_product_status(product_url):
    """
    Analyse la page d'un produit et détermine son statut.
    """

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

    page_text = soup.get_text(" ", strip=True).lower()

    # Rupture
    if (
        "rupture temporaire" in page_text
        or "rupture de stock" in page_text
        or "livraison indisponible" in page_text
    ):
        return "out_of_stock"

    # Précommande
    if (
        "précommande" in page_text
        or "pré-commande" in page_text
        or "sortie prévue" in page_text
    ):
        return "preorder"

    # Recherche d'un bouton d'ajout au panier
    buttons = soup.find_all(
        ["button", "input"]
    )

    for button in buttons:

        text = button.get_text(
            " ",
            strip=True
        ).lower()

        value = (
            button.get("value", "")
            .strip()
            .lower()
        )

        combined = f"{text} {value}"

        if (
            "ajouter au panier" in combined
            or "ajouter au panier" in page_text
        ):
            return "in_stock"

    return "unknown"


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

        # Évite les doublons
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
    """Retourne un libellé lisible."""

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
    """
    Détecte :
    - nouveaux produits
    - changements de statut
    """

    new_products = {}
    status_changes = []

    for url, product in current.items():

        # Nouveau produit
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

        # Première conversion ancien format
        # On mémorise sans alerter
        if old_status == "unknown":
            continue

        if (
            new_status != "unknown"
            and old_status != new_status
        ):

            status_changes.append(
                {
                    "url": url,
                    "name": product["name"],
                    "old_status": old_status,
                    "new_status": new_status
                }
            )

    return (
        new_products,
        status_changes
    )


def main():

    if not TOKEN:
        print(
            "ERREUR : "
            "TELEGRAM_BOT_TOKEN manquant."
        )
        return

    if not CHAT_ID:
        print(
            "ERREUR : "
            "TELEGRAM_CHAT_ID manquant."
        )
        return

    previous_products = load_state()

    current_products = fetch_playin()

    if current_products is None:
        print(
            "Impossible de récupérer Playin."
        )
        return

    print(
        f"Produits Playin détectés : "
        f"{len(current_products)}"
    )

    # Première exécution
    if not previous_products:

        message = (
            "🟢 Surveillance Playin active !\n\n"
            f"📦 {len(current_products)} "
            "produits détectés.\n\n"
            "Les produits et leurs statuts "
            "sont maintenant mémorisés."
        )

        send_telegram(message)

    else:

        (
            new_products,
            status_changes
        ) = detect_changes(
            previous_products,
            current_products
        )

        # Nouveaux produits
        for product_url, product in (
            new_products.items()
        ):

            message = (
                "🚨 NOUVEAU PRODUIT "
                "POKÉMON 30e ANNIVERSAIRE !\n\n"
                "🏪 Playin\n"
                f"📦 {product['name']}\n"
                f"{status_label(product['status'])}\n\n"
                f"🔗 {product_url}"
            )

            send_telegram(message)

        # Changements de statut
        for change in status_changes:

            # Alerte spéciale retour en stock
            if (
                change["old_status"]
                == "out_of_stock"
                and change["new_status"]
                == "in_stock"
            ):

                title = (
                    "🚨🚨 RETOUR EN STOCK ! 🚨🚨"
                )

            else:

                title = (
                    "🔔 CHANGEMENT DE STATUT"
                )

            message = (
                f"{title}\n\n"
                "🏪 Playin\n"
                f"📦 {change['name']}\n\n"
                f"Avant : "
                f"{status_label(change['old_status'])}\n"
                f"Maintenant : "
                f"{status_label(change['new_status'])}\n\n"
                f"🔗 {change['url']}"
            )

            send_telegram(message)

        print(
            f"Nouveaux produits : "
            f"{len(new_products)}"
        )

        print(
            f"Changements de statut : "
            f"{len(status_changes)}"
        )

    save_state(current_products)

    print(
        "Surveillance terminée."
    )


if __name__ == "__main__":
    main()