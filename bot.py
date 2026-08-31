import os
import json
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_products.json"

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ==================================================
# URLS
# ==================================================

URL_PLAYIN = (
    "https://www.play-in.com/fr/extension/1500/"
    "30eme-anniversaire"
)

URL_DRACAUGAMES = (
    "https://www.dracaugames.com/collections/nouveautes"
)

BCD_KNOWN_PRODUCTS = {
    "https://www.bcd-jeux.fr/pokemon-tcg/39006-pokemon-anniversaire-30-ans-coffret-etb-dresseur-d-elite-pokemon.html":
    "Pokémon Anniversaire 30 ans : Coffret ETB Dresseur d’élite"
}

URL_BCD_SEARCHES = [
    "https://www.bcd-jeux.fr/recherche?controller=search&s=pokemon+30+ans",
    "https://www.bcd-jeux.fr/recherche?controller=search&s=30e+anniversaire",
    "https://www.bcd-jeux.fr/recherche?controller=search&s=pokemon+anniversaire",
]

PIKA_KNOWN_PRODUCTS = {
    "https://pika-boutique.fr/products/pack-n-1-30-ans-etb-x2-tripack-duopack-coffret-poster":
    "[PACK N°1] 30 ans - ETB + x2 tripack + duopack + coffret poster",

    "https://pika-boutique.fr/products/pack-n-2-30-ans-etb-coffret-amphinobi-coffret-nymphali":
    "[PACK N°2] 30 ans - ETB + Coffret Amphinobi + Coffret Nymphali",

    "https://pika-boutique.fr/products/pack-n-3-30-ans-coffret-poster-x2-pokebox-duopack":
    "[PACK N°3] 30 ans - Coffret Poster + x2 Pokebox + Duopack",
}

URL_PIKA_SEARCHES = [
    "https://pika-boutique.fr/search?q=pokemon+30+ans",
    "https://pika-boutique.fr/search?q=30+ans",
    "https://pika-boutique.fr/search?q=30e+anniversaire",
]


# ==================================================
# MÉMOIRE
# ==================================================

def load_state():
    if not os.path.exists(SEEN_FILE):
        return {}

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

    except Exception as error:
        print(f"Erreur lecture mémoire : {error}")

    return {}


def save_state(products):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as file:
            json.dump(
                products,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:
        print(f"Erreur sauvegarde mémoire : {error}")


# ==================================================
# INTERNET
# ==================================================

def get_page(url, retries=2, delay=3):
    for attempt in range(retries + 1):

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT
            )

            if response.status_code == 429:

                print(
                    f"429 détecté : {url}"
                )

                if attempt < retries:
                    time.sleep(delay * (attempt + 1))
                    continue

                return None

            response.raise_for_status()
            return response

        except Exception as error:

            print(
                f"Erreur récupération {url} : {error}"
            )

            if attempt < retries:
                time.sleep(delay)

    return None


# ==================================================
# TELEGRAM
# ==================================================

def send_telegram(message):

    if not TOKEN or not CHAT_ID:
        print("Secrets Telegram manquants.")
        return False

    try:

        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": False,
            },
            timeout=20
        )

        response.raise_for_status()

        print("📨 Alerte Telegram envoyée.")

        return True

    except Exception as error:

        print(
            f"Erreur Telegram : {error}"
        )

        return False


# ==================================================
# FILTRE POKÉMON 30 ANS
# ==================================================

def is_pokemon_30(name, url):

    text = (
        f"{name} {url}"
        .lower()
        .replace("’", "'")
    )

    keywords = [
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
    ]

    return any(
        keyword in text
        for keyword in keywords
    )


# ==================================================
# STATUT
# ==================================================

def detect_status(text):

    text = (
        text
        .lower()
        .replace("’", "'")
    )

    # Précommande en priorité.
    if any(word in text for word in [
        "précommander",
        "precommander",
        "précommande",
        "precommande",
    ]):
        return "preorder"

    # Disponible.
    if any(word in text for word in [
        "ajouter au panier",
        "ajoutez au panier",
        "en stock",
        "stock très faible",
        "stock faible",
    ]):
        return "in_stock"

    # Rupture.
    if any(word in text for word in [
        "rupture temporaire",
        "rupture de stock",
        "hors stock",
        "épuisé",
        "epuise",
        "sold out",
        "indisponible",
        "livraison indisponible",
    ]):
        return "out_of_stock"

    return "unknown"


def status_label(status):

    labels = {
        "in_stock": "🟢 EN STOCK",
        "preorder": "🟠 PRÉCOMMANDE",
        "out_of_stock": "🔴 RUPTURE / ÉPUISÉ",
        "unknown": "⚪ STATUT INCONNU",
    }

    return labels.get(
        status,
        "⚪ STATUT INCONNU"
    )


# ==================================================
# PLAYIN
# ==================================================

def get_playin_status(url):

    response = get_page(url)

    if response is None:
        return "unknown"

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    actions = []

    for element in soup.find_all(
        ["button", "input", "a"]
    ):

        text = element.get_text(
            " ",
            strip=True
        ).lower()

        value = str(
            element.get("value", "")
        ).lower()

        aria = str(
            element.get("aria-label", "")
        ).lower()

        actions.append(
            f"{text} {value} {aria}"
        )

    action_text = " ".join(actions)

    if any(word in action_text for word in [
        "précommander",
        "precommander",
        "précommande",
        "precommande",
    ]):
        return "preorder"

    if any(word in action_text for word in [
        "ajouter au panier",
        "ajoutez au panier",
    ]):
        return "in_stock"

    page_text = soup.get_text(
        " ",
        strip=True
    )

    return detect_status(page_text)


def fetch_playin():

    response = get_page(URL_PLAYIN)

    if response is None:
        return {}

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

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

        if "/fr/produit/" not in href:
            continue

        if not name:
            continue

        url = urljoin(
            URL_PLAYIN,
            href
        ).split("?")[0]

        if not is_pokemon_30(
            name,
            url
        ):
            continue

        candidates[url] = name

    print(
        f"[Playin] Produits 30 ans : "
        f"{len(candidates)}"
    )

    products = {}

    for url, name in candidates.items():

        status = get_playin_status(url)

        products[url] = {
            "name": name,
            "shop": "Playin",
            "status": status,
        }

        print(
            f"[Playin] {name} -> {status}"
        )

    return products


# ==================================================
# DRACAUGAMES
# ==================================================

def fetch_dracaugames():

    print(
        "[DracauGames] Recherche des "
        "produits 30 ans..."
    )

    response = get_page(
        URL_DRACAUGAMES,
        retries=1,
        delay=5
    )

    if response is None:

        print(
            "[DracauGames] Collection "
            "inaccessible."
        )

        return {}

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

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

        if "/products/" not in href:
            continue

        if not name:
            continue

        url = urljoin(
            URL_DRACAUGAMES,
            href
        ).split("?")[0]

        if not is_pokemon_30(
            name,
            url
        ):
            continue

        candidates[url] = name

    print(
        f"[DracauGames] Produits candidats : "
        f"{len(candidates)}"
    )

    products = {}

    # Maximum 15 pages produit par exécution
    # afin d'éviter les 429.
    limited_candidates = list(
        candidates.items()
    )[:15]

    for index, (url, name) in enumerate(
        limited_candidates,
        start=1
    ):

        print(
            f"[DracauGames] Vérification "
            f"{index}/{len(limited_candidates)}"
        )

        response = get_page(
            url,
            retries=1,
            delay=4
        )

        if response is None:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        page_text = soup.get_text(
            " ",
            strip=True
        )

        # Vérification supplémentaire
        # directement sur la page produit.
        if not is_pokemon_30(
            name,
            page_text
        ):
            continue

        status = detect_status(
            page_text
        )

        products[url] = {
            "name": name,
            "shop": "DracauGames",
            "status": status,
        }

        print(
            f"[DracauGames] "
            f"{name} -> {status}"
        )

        time.sleep(1)

    print(
        f"[DracauGames] Produits 30 ans "
        f"détectés : {len(products)}"
    )

    return products


# ==================================================
# BCD JEUX
# ==================================================

def get_title(soup, fallback):

    meta = soup.find(
        "meta",
        property="og:title"
    )

    if meta:

        title = meta.get(
            "content",
            ""
        ).strip()

        if title and title.lower() not in [
            "menu",
            "bcd jeux",
        ]:
            return title

    h1 = soup.find("h1")

    if h1:

        title = h1.get_text(
            " ",
            strip=True
        )

        if title:
            return title

    return fallback


def fetch_bcd():

    candidates = dict(
        BCD_KNOWN_PRODUCTS
    )

    for search_url in URL_BCD_SEARCHES:

        response = get_page(
            search_url
        )

        if response is None:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for link in soup.find_all(
            "a",
            href=True
        ):

            href = link["href"]

            name = link.get_text(
                " ",
                strip=True
            )

            if ".html" not in href:
                continue

            url = urljoin(
                search_url,
                href
            ).split("?")[0]

            if is_pokemon_30(
                name,
                url
            ):
                candidates[url] = name

    print(
        f"[BCD Jeux] Produits potentiels : "
        f"{len(candidates)}"
    )

    products = {}

    for url, fallback in candidates.items():

        response = get_page(url)

        if response is None:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        name = get_title(
            soup,
            fallback
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        status = detect_status(
            text
        )

        products[url] = {
            "name": name,
            "shop": "BCD Jeux",
            "status": status,
        }

        print(
            f"[BCD Jeux] {name} -> {status}"
        )

    return products


# ==================================================
# PIKA-BOUTIQUE
# ==================================================

def fetch_pika():

    candidates = dict(
        PIKA_KNOWN_PRODUCTS
    )

    for search_url in URL_PIKA_SEARCHES:

        response = get_page(
            search_url
        )

        if response is None:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for link in soup.find_all(
            "a",
            href=True
        ):

            href = link["href"]

            name = link.get_text(
                " ",
                strip=True
            )

            if "/products/" not in href:
                continue

            url = urljoin(
                search_url,
                href
            ).split("?")[0]

            if is_pokemon_30(
                name,
                url
            ):
                candidates[url] = name

    print(
        f"[Pika-boutique] "
        f"Produits potentiels : "
        f"{len(candidates)}"
    )

    products = {}

    for url, fallback in candidates.items():

        response = get_page(url)

        if response is None:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        h1 = soup.find("h1")

        if h1:

            name = h1.get_text(
                " ",
                strip=True
            )

        else:

            name = fallback

        text = soup.get_text(
            " ",
            strip=True
        )

        status = detect_status(
            text
        )

        products[url] = {
            "name": name,
            "shop": "Pika-boutique",
            "status": status,
        }

        print(
            f"[Pika-boutique] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# CHANGEMENTS
# ==================================================

def detect_changes(
    previous,
    current
):

    new_products = {}
    changes = []

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

            changes.append({
                "url": url,
                "name": product["name"],
                "shop": product["shop"],
                "old_status": old_status,
                "new_status": new_status,
            })

    return (
        new_products,
        changes
    )


# ==================================================
# ALERTES TELEGRAM
# ==================================================

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

        send_telegram(message)

    for change in changes:

        old_status = change[
            "old_status"
        ]

        new_status = change[
            "new_status"
        ]

        if (
            old_status == "out_of_stock"
            and new_status == "in_stock"
        ):

            title = (
                "🚨🚨 RETOUR EN STOCK ! 🚨🚨"
            )

        elif (
            old_status != "preorder"
            and new_status == "preorder"
        ):

            title = (
                "🔥 PRÉCOMMANDE OUVERTE ! 🔥"
            )

        elif (
            old_status != "in_stock"
            and new_status == "in_stock"
        ):

            title = (
                "🟢 PRODUIT DISPONIBLE !"
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
            f"{status_label(old_status)}\n"
            f"Maintenant : "
            f"{status_label(new_status)}\n\n"
            f"🔗 {change['url']}"
        )

        send_telegram(message)


# ==================================================
# PROGRAMME PRINCIPAL
# ==================================================

def main():

    start_time = time.time()

    print(
        "================================"
    )

    print(
        "🐉 POKÉMON 30 ALERT"
    )

    print(
        "Début de la surveillance..."
    )

    print(
        "================================"
    )

    previous_products = load_state()

    # --------------------------------------------------
    # PLAYIN
    # --------------------------------------------------

    playin_products = fetch_playin()

    # --------------------------------------------------
    # DRACAUGAMES
    # --------------------------------------------------

    dracau_products = fetch_dracaugames()

    # --------------------------------------------------
    # BCD
    # --------------------------------------------------

    bcd_products = fetch_bcd()

    # --------------------------------------------------
    # PIKA
    # --------------------------------------------------

    pika_products = fetch_pika()

    # --------------------------------------------------
    # FUSION
    # --------------------------------------------------

    current_products = {}

    current_products.update(
        playin_products
    )

    current_products.update(
        dracau_products
    )

    current_products.update(
        bcd_products
    )

    current_products.update(
        pika_products
    )

    print(
        "\n================================"
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
        f"Produits Pika-boutique : "
        f"{len(pika_products)}"
    )

    print(
        f"Produits totaux : "
        f"{len(current_products)}"
    )

    print(
        "================================"
    )

    # --------------------------------------------------
    # COMPARAISON
    # --------------------------------------------------

    new_products, status_changes = (
        detect_changes(
            previous_products,
            current_products
        )
    )

    # --------------------------------------------------
    # ALERTES
    # --------------------------------------------------

    send_alerts(
        new_products,
        status_changes
    )

    # --------------------------------------------------
    # MÉMOIRE
    # --------------------------------------------------

    save_state(
        current_products
    )

    elapsed = (
        time.time() - start_time
    )

    print()

    print(
        f"Nouveaux produits : "
        f"{len(new_products)}"
    )

    print(
        f"Changements de statut : "
        f"{len(status_changes)}"
    )

    print(
        f"Temps d'exécution : "
        f"{elapsed:.1f} secondes"
    )

    print()

    print(
        "================================"
    )

    print(
        "✅ Surveillance terminée."
    )

    print(
        "================================"
    )


if __name__ == "__main__":
    main()
