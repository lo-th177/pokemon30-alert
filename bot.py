import os
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_products.json"

URL_PLAYIN = "https://www.play-in.com/fr/extension/1500/30eme-anniversaire"

URL_DRACAUGAMES = "https://www.dracaugames.com/collections/nouveautes"

URL_BCD = "https://www.bcd-jeux.fr/fabricant/276-pokemon"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36"
    )
}


# ==================================================
# MÉMOIRE
# ==================================================

def load_state():

    if not os.path.exists(SEEN_FILE):
        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            if isinstance(data, dict):
                return data

    except Exception as error:

        print(
            f"Erreur lecture mémoire : {error}"
        )

    return {}


def save_state(products):

    try:

        with open(
            SEEN_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                products,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        print(
            f"Erreur sauvegarde : {error}"
        )


# ==================================================
# INTERNET
# ==================================================

def get_page(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        return response

    except Exception as error:

        print(
            f"Erreur récupération {url} : {error}"
        )

        return None


# ==================================================
# TELEGRAM
# ==================================================

def send_telegram(message):

    if not TOKEN or not CHAT_ID:

        print(
            "Secrets Telegram manquants."
        )

        return False

    try:

        response = requests.post(

            f"https://api.telegram.org/bot"
            f"{TOKEN}/sendMessage",

            data={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": False
            },

            timeout=20
        )

        response.raise_for_status()

        return True

    except Exception as error:

        print(
            f"Erreur Telegram : {error}"
        )

        return False


# ==================================================
# FILTRE 30e ANNIVERSAIRE
# ==================================================

def is_real_pokemon_30_product(name, product_url):

    text = (
        f"{name} {product_url}"
    ).lower()

    pokemon_words = [
        "pokemon",
        "pokémon"
    ]

    anniversary_words = [
        "30-ans",
        "30_ans",
        "30ans",
        "30 ans",
        "30e-anniversaire",
        "30e anniversaire",
        "30eme-anniversaire",
        "30eme anniversaire",
        "30ème-anniversaire",
        "30ème anniversaire",
        "30th-anniversary",
        "30th anniversary",
        "30th-celebration",
        "30th celebration"
    ]

    has_pokemon = any(
        word in text
        for word in pokemon_words
    )

    has_anniversary = any(
        word in text
        for word in anniversary_words
    )

    return (
        has_pokemon
        and has_anniversary
    )


# ==================================================
# PLAYIN
# ==================================================

def get_playin_status(product_url):

    response = get_page(
        product_url
    )

    if response is None:
        return "unknown"

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    page_text = soup.get_text(
        " ",
        strip=True
    ).lower()

    actions = []

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
        ).lower()

        aria = element.get(
            "aria-label",
            ""
        ).lower()

        actions.append(
            f"{text} {value} {aria}"
        )

    action_text = " ".join(
        actions
    )

    if (
        "précommander" in action_text
        or "precommander" in action_text
        or "précommande" in action_text
        or "precommande" in action_text
    ):

        return "preorder"

    if (
        "ajouter au panier"
        in action_text
    ):

        return "in_stock"

    if (
        "rupture temporaire"
        in page_text

        or "rupture de stock"
        in page_text

        or "livraison indisponible"
        in page_text

        or "indisponible"
        in page_text
    ):

        return "out_of_stock"

    return "unknown"


def fetch_playin():

    response = get_page(
        URL_PLAYIN
    )

    if response is None:
        return {}

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

        if (
            "/fr/produit/"
            not in href

            or not name
        ):

            continue

        product_url = urljoin(
            URL_PLAYIN,
            href
        )

        if product_url in products:
            continue

        status = get_playin_status(
            product_url
        )

        products[product_url] = {
            "name": name,
            "shop": "Playin",
            "status": status
        }

        print(
            f"[Playin] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# DRACAUGAMES
# ==================================================

def get_dracaugames_status(text):

    text = text.lower()

    if re.search(
        r"en stock\s*\(\s*\d+",
        text
    ):

        return "in_stock"

    if (
        "stock très faible"
        in text
    ):

        return "in_stock"

    if (
        "stock faible"
        in text
    ):

        return "in_stock"

    if "en stock" in text:

        return "in_stock"

    if (
        "précommander" in text
        or "precommander" in text
        or "précommande" in text
        or "precommande" in text
    ):

        return "preorder"

    if (
        "épuisé" in text
        or "epuise" in text
        or "rupture de stock" in text
    ):

        return "out_of_stock"

    return "unknown"


def fetch_dracaugames():

    response = get_page(
        URL_DRACAUGAMES
    )

    if response is None:
        return {}

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    products = {}

    candidates = {}

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        if "/products/" not in href:
            continue

        product_url = urljoin(
            URL_DRACAUGAMES,
            href
        )

        name = link.get_text(
            " ",
            strip=True
        )

        if not name:
            continue

        if not is_real_pokemon_30_product(
            name,
            product_url
        ):

            continue

        candidates[product_url] = name

    print(
        f"[DracauGames] "
        f"Produits 30e anniversaire à vérifier : "
        f"{len(candidates)}"
    )

    for product_url, name in candidates.items():

        product_response = get_page(
            product_url
        )

        if product_response is None:
            continue

        product_soup = BeautifulSoup(
            product_response.text,
            "html.parser"
        )

        page_text = product_soup.get_text(
            " ",
            strip=True
        )

        status = get_dracaugames_status(
            page_text
        )

        products[product_url] = {
            "name": name,
            "shop": "DracauGames",
            "status": status
        }

        print(
            f"[DracauGames] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# BCD JEUX
# ==================================================

def get_bcd_status(text):

    text = text.lower()

    # Rupture avant "ajouter au panier"
    # car certains sites affichent les deux.

    if (
        "rupture de stock temporaire"
        in text

        or "rupture de stock"
        in text

        or "épuisé"
        in text

        or "epuise"
        in text
    ):

        return "out_of_stock"

    if (
        "précommande" in text
        or "precommande" in text
        or "précommander" in text
        or "precommander" in text
    ):

        return "preorder"

    if (
        "en stock"
        in text
    ):

        return "in_stock"

    if (
        "ajouter au panier"
        in text
    ):

        return "in_stock"

    return "unknown"


def fetch_bcd():

    response = get_page(
        URL_BCD
    )

    if response is None:
        return {}

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    products = {}

    candidates = {}

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link["href"]

        name = link.get_text(
            " ",
            strip=True
        )

        if not name:
            continue

        # Les fiches produits BCD
        # sont généralement des pages HTML.

        if (
            ".html"
            not in href
        ):

            continue

        product_url = urljoin(
            URL_BCD,
            href
        )

        if not is_real_pokemon_30_product(
            name,
            product_url
        ):

            continue

        candidates[
            product_url
        ] = name

    print(
        f"[BCD Jeux] "
        f"Produits 30e anniversaire à vérifier : "
        f"{len(candidates)}"
    )

    for product_url, name in candidates.items():

        product_response = get_page(
            product_url
        )

        if product_response is None:
            continue

        product_soup = BeautifulSoup(
            product_response.text,
            "html.parser"
        )

        page_text = product_soup.get_text(
            " ",
            strip=True
        )

        status = get_bcd_status(
            page_text
        )

        products[product_url] = {
            "name": name,
            "shop": "BCD Jeux",
            "status": status
        }

        print(
            f"[BCD Jeux] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# ALERTES
# ==================================================

def status_label(status):

    labels = {

        "in_stock":
            "🟢 EN STOCK",

        "preorder":
            "🟠 PRÉCOMMANDE",

        "out_of_stock":
            "🔴 RUPTURE / INDISPONIBLE",

        "unknown":
            "⚪ STATUT INCONNU"

    }

    return labels.get(
        status,
        "⚪ STATUT INCONNU"
    )


def detect_changes(
    previous,
    current
):

    new_products = {}

    status_changes = []

    for url, product in current.items():

        if url not in previous:

            new_products[
                url
            ] = product

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

            status_changes.append({

                "url": url,

                "name":
                    product["name"],

                "shop":
                    product["shop"],

                "old_status":
                    old_status,

                "new_status":
                    new_status

            })

    return (
        new_products,
        status_changes
    )


def send_alerts(
    new_products,
    changes
):

    for url, product in new_products.items():

        message = (

            "🚨 NOUVEAU PRODUIT "
            "POKÉMON 30e ANNIVERSAIRE !\n\n"

            f"🏪 {product['shop']}\n"

            f"📦 {product['name']}\n"

            f"{status_label(product['status'])}\n\n"

            f"🔗 {url}"

        )

        send_telegram(
            message
        )

    for change in changes:

        if (
            change["old_status"]
            == "out_of_stock"

            and

            change["new_status"]
            == "in_stock"
        ):

            title = (
                "🚨🚨 RETOUR EN STOCK ! 🚨🚨"
            )

        elif (
            change["new_status"]
            == "preorder"
        ):

            title = (
                "🔥 PRÉCOMMANDE OUVERTE ! 🔥"
            )

        else:

            title = (
                "🔔 CHANGEMENT DE STATUT"
            )

        message = (

            f"{title}\n\n"

            f"🏪 {change['shop']}\n"

            f"📦 {change['name']}\n\n"

            f"Avant : "
            f"{status_label(change['old_status'])}\n"

            f"Maintenant : "
            f"{status_label(change['new_status'])}\n\n"

            f"🔗 {change['url']}"

        )

        send_telegram(
            message
        )


# ==================================================
# PROGRAMME PRINCIPAL
# ==================================================

def main():

    print(
        "Début de la surveillance..."
    )

    previous_products = load_state()

    current_products = {}


    # PLAYIN

    playin_products = fetch_playin()

    current_products.update(
        playin_products
    )


    # DRACAUGAMES

    dracau_products = fetch_dracaugames()

    current_products.update(
        dracau_products
    )


    # BCD JEUX

    bcd_products = fetch_bcd()

    current_products.update(
        bcd_products
    )


    print(
        "\n=============================="
    )

    print(
        f"Produits Playin : "
        f"{len(playin_products)}"
    )

    print(
        f"Produits DracauGames : "
        f"{len(dracau_products)}"
    )

    print(
        f"Produits BCD Jeux : "
        f"{len(bcd_products)}"
    )

    print(
        f"Produits totaux : "
        f"{len(current_products)}"
    )

    print(
        "==============================\n"
    )


    new_products, status_changes = (
        detect_changes(
            previous_products,
            current_products
        )
    )


    send_alerts(
        new_products,
        status_changes
    )


    print(
        f"Nouveaux produits : "
        f"{len(new_products)}"
    )

    print(
        f"Changements de statut : "
        f"{len(status_changes)}"
    )


    save_state(
        current_products
    )


    print(
        "Surveillance terminée."
    )


if __name__ == "__main__":
    main()