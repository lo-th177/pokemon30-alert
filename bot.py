import os
import json
import re
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

TIMEOUT = 25

# Petite pause entre les requêtes afin de limiter
# les risques de 429 sur les boutiques.
REQUEST_DELAY = 0.35

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": (
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Connection": "keep-alive"
}


# ==================================================
# URLS
# ==================================================

URL_PLAYIN = (
    "https://www.play-in.com/fr/extension/"
    "1500/30eme-anniversaire"
)

URL_DRACAUGAMES = (
    "https://www.dracaugames.com/"
    "collections/nouveautes"
)

URL_BCD_SEARCHES = [
    (
        "https://www.bcd-jeux.fr/recherche"
        "?controller=search&s=pokemon+30+ans"
    ),
    (
        "https://www.bcd-jeux.fr/recherche"
        "?controller=search&s=30e+anniversaire"
    ),
    (
        "https://www.bcd-jeux.fr/recherche"
        "?controller=search&s=pokemon+anniversaire"
    )
]

URL_PIKA_SEARCHES = [
    "https://pika-boutique.fr/search?q=pokemon+30+ans",
    "https://pika-boutique.fr/search?q=30+ans",
    "https://pika-boutique.fr/search?q=30e+anniversaire"
]


# ==================================================
# PRODUITS CONNUS
# ==================================================

BCD_KNOWN_PRODUCTS = {
    "https://www.bcd-jeux.fr/pokemon-tcg/"
    "39006-pokemon-anniversaire-30-ans-coffret-etb-dresseur-d-elite-pokemon.html":
        "Pokémon Anniversaire 30 ans : Coffret ETB Dresseur d'élite"
}


PIKA_KNOWN_PRODUCTS = {

    "https://pika-boutique.fr/products/"
    "pack-n-1-30-ans-etb-x2-tripack-duopack-coffret-poster":
        "[PACK N°1] 30 ans - ETB + x2 tripack + duopack + coffret poster",

    "https://pika-boutique.fr/products/"
    "pack-n-2-30-ans-etb-coffret-amphinobi-coffret-nymphali":
        "[PACK N°2] 30 ans - ETB + Coffret Amphinobi + Coffret Nymphali",

    "https://pika-boutique.fr/products/"
    "pack-n-3-30-ans-coffret-poster-x2-pokebox-duopack":
        "[PACK N°3] 30 ans - Coffret Poster + x2 Pokebox + Duopack"
}


# ==================================================
# SESSION HTTP
# ==================================================

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


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

def get_page(url, retries=2):

    for attempt in range(retries + 1):

        try:

            time.sleep(REQUEST_DELAY)

            response = SESSION.get(
                url,
                timeout=TIMEOUT
            )

            if response.status_code == 429:

                print(
                    f"⚠️ 429 sur {url}"
                )

                if attempt < retries:

                    wait_time = 2 + (
                        attempt * 3
                    )

                    print(
                        f"Attente {wait_time}s..."
                    )

                    time.sleep(wait_time)

                    continue

                return None

            response.raise_for_status()

            return response

        except requests.RequestException as error:

            print(
                f"Erreur récupération {url}: "
                f"{error}"
            )

            if attempt < retries:

                time.sleep(2)

    return None


# ==================================================
# TELEGRAM
# ==================================================

def send_telegram(message):

    if not TOKEN or not CHAT_ID:

        print(
            "⚠️ Secrets Telegram manquants."
        )

        return False

    try:

        response = SESSION.post(

            f"https://api.telegram.org/"
            f"bot{TOKEN}/sendMessage",

            data={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": False
            },

            timeout=20
        )

        response.raise_for_status()

        print(
            "📨 Alerte Telegram envoyée."
        )

        return True

    except Exception as error:

        print(
            f"Erreur Telegram : {error}"
        )

        return False


# ==================================================
# NORMALISATION
# ==================================================

def normalize(text):

    if not text:
        return ""

    text = text.lower()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ==================================================
# FILTRE POKÉMON 30 ANS
# ==================================================

def is_pokemon_30(name, url=""):

    text = normalize(
        f"{name} {url}"
    )

    has_pokemon = (
        "pokemon" in text
        or "pokémon" in text
    )

    anniversary_patterns = [

        r"\b30\s*ans\b",
        r"\b30e\s*anniversaire\b",
        r"\b30eme\s*anniversaire\b",
        r"\b30th\s*anniversary\b",
        r"30-ans",
        r"30_ans",
        r"30ans",
        r"30e-anniversaire",
        r"30eme-anniversaire",
        r"30th-anniversary"

    ]

    has_anniversary = any(
        re.search(
            pattern,
            text
        )
        for pattern in anniversary_patterns
    )

    return (
        has_pokemon
        and has_anniversary
    )


# ==================================================
# STATUT
# ==================================================

def detect_status(text):

    text = normalize(text)

    # PRIORITÉ AUX ACTIONS DE VENTE

    if any(word in text for word in [
        "ajouter au panier",
        "ajout au panier",
        "add to cart"
    ]):

        return "in_stock"

    if any(word in text for word in [
        "precommander",
        "precommande"
    ]):

        return "preorder"

    if any(word in text for word in [
        "rupture temporaire",
        "rupture de stock",
        "hors stock",
        "epuise",
        "sold out",
        "indisponible",
        "livraison indisponible"
    ]):

        return "out_of_stock"

    if any(word in text for word in [
        "stock tres faible",
        "stock faible",
        "en stock"
    ]):

        return "in_stock"

    return "unknown"


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

    page_text = soup.get_text(
        " ",
        strip=True
    )

    actions = []

    for element in soup.find_all(
        ["button", "input", "a"]
    ):

        text = element.get_text(
            " ",
            strip=True
        )

        value = element.get(
            "value",
            ""
        )

        aria = element.get(
            "aria-label",
            ""
        )

        actions.append(
            f"{text} {value} {aria}"
        )

    action_text = " ".join(actions)

    status = detect_status(
        action_text
    )

    if status != "unknown":
        return status

    return detect_status(
        page_text
    )


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

        if (
            "/fr/produit/" not in href
            or not name
        ):
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

        status = get_playin_status(
            url
        )

        products[url] = {
            "name": name,
            "shop": "Playin",
            "status": status
        }

        print(
            f"[Playin] {name} -> {status}"
        )

    return products


# ==================================================
# DRACAUGAMES
# ==================================================

def get_dracaugames_title(
    soup,
    fallback
):

    for selector in [
        "h1",
        "meta[property='og:title']",
        "title"
    ]:

        element = soup.select_one(
            selector
        )

        if element is None:
            continue

        if element.name == "meta":

            title = element.get(
                "content",
                ""
            ).strip()

        else:

            title = element.get_text(
                " ",
                strip=True
            )

        if title:

            return title

    return fallback


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

    candidates = {}

    # --------------------------------------------------
    # IMPORTANT :
    # On regarde uniquement les liens produits
    # dont le NOM lui-même correspond au 30e.
    #
    # Cela évite les faux positifs provoqués par
    # du texte présent ailleurs dans la page.
    # --------------------------------------------------

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
            "/products/" not in href
            or not name
        ):
            continue

        url = urljoin(
            URL_DRACAUGAMES,
            href
        ).split("?")[0]

        if not is_pokemon_30(
            name,
            ""
        ):
            continue

        candidates[url] = name

    print(
        f"[DracauGames] Produits 30 ans "
        f"détectés dans la collection : "
        f"{len(candidates)}"
    )

    products = {}

    for url, fallback_name in candidates.items():

        # Une seule tentative normale ici.
        # Pas de boucle massive de requêtes.

        response = get_page(
            url,
            retries=1
        )

        if response is None:

            print(
                f"[DracauGames] "
                f"⚠️ Fiche inaccessible : "
                f"{fallback_name}"
            )

            # On conserve le produit avec statut
            # inconnu plutôt que de le supprimer.

            products[url] = {
                "name": fallback_name,
                "shop": "DracauGames",
                "status": "unknown"
            }

            continue

        product_soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        name = get_dracaugames_title(
            product_soup,
            fallback_name
        )

        page_text = product_soup.get_text(
            " ",
            strip=True
        )

        status = detect_status(
            page_text
        )

        products[url] = {
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

def get_bcd_title(
    soup,
    fallback
):

    meta = soup.find(
        "meta",
        property="og:title"
    )

    if meta:

        title = meta.get(
            "content",
            ""
        ).strip()

        if title:

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

            if not is_pokemon_30(
                name,
                url
            ):
                continue

            candidates[url] = name

    print(
        f"[BCD Jeux] Produits potentiels : "
        f"{len(candidates)}"
    )

    products = {}

    for url, fallback in candidates.items():

        response = get_page(url)

        if response is None:

            print(
                f"[BCD Jeux] "
                f"⚠️ Fiche inaccessible : "
                f"{fallback}"
            )

            products[url] = {
                "name": fallback,
                "shop": "BCD Jeux",
                "status": "unknown"
            }

            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        name = get_bcd_title(
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
            "status": status
        }

        print(
            f"[BCD Jeux] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# PIKA-BOUTIQUE
# ==================================================

def get_pika_title(
    soup,
    fallback
):

    h1 = soup.find("h1")

    if h1:

        title = h1.get_text(
            " ",
            strip=True
        )

        if title:
            return title

    meta = soup.find(
        "meta",
        property="og:title"
    )

    if meta:

        title = meta.get(
            "content",
            ""
        ).strip()

        if title:
            return title

    return fallback


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

            if (
                "/products/" not in href
                or not name
            ):
                continue

            url = urljoin(
                search_url,
                href
            ).split("?")[0]

            if not is_pokemon_30(
                name,
                url
            ):
                continue

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

            print(
                f"[Pika-boutique] "
                f"⚠️ Fiche inaccessible : "
                f"{fallback}"
            )

            products[url] = {
                "name": fallback,
                "shop": "Pika-boutique",
                "status": "unknown"
            }

            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        name = get_pika_title(
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
            "shop": "Pika-boutique",
            "status": status
        }

        print(
            f"[Pika-boutique] "
            f"{name} -> {status}"
        )

    return products


# ==================================================
# LIBELLÉS
# ==================================================

def status_label(status):

    labels = {

        "in_stock":
            "🟢 EN STOCK",

        "preorder":
            "🟠 PRÉCOMMANDE",

        "out_of_stock":
            "🔴 RUPTURE / ÉPUISÉ",

        "unknown":
            "⚪ STATUT INCONNU"
    }

    return labels.get(
        status,
        "⚪ STATUT INCONNU"
    )


# ==================================================
# CHANGEMENTS
# ==================================================

def detect_changes(
    previous,
    current
):

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

        # Un statut unknown ne doit jamais
        # provoquer une fausse alerte.

        if (
            new_status == "unknown"
            or old_status == new_status
        ):
            continue

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


# ==================================================
# ALERTES
# ==================================================

def send_alerts(
    new_products,
    changes
):

    # ----------------------------------------------
    # NOUVEAUX PRODUITS
    # ----------------------------------------------

    for url, product in new_products.items():

        # Un nouveau produit dont le statut est
        # inconnu reste signalé : le produit lui-même
        # est nouveau.

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

    # ----------------------------------------------
    # CHANGEMENTS
    # ----------------------------------------------

    for change in changes:

        old_status = change[
            "old_status"
        ]

        new_status = change[
            "new_status"
        ]

        # RETOUR EN STOCK

        if (
            old_status == "out_of_stock"
            and new_status == "in_stock"
        ):

            title = (
                "🚨🚨 RETOUR EN STOCK ! 🚨🚨"
            )

        # RUPTURE -> PRÉCOMMANDE

        elif (
            old_status == "out_of_stock"
            and new_status == "preorder"
        ):

            title = (
                "🔥🔥 PRÉCOMMANDE OUVERTE ! 🔥🔥"
            )

        # UNKNOWN -> STOCK
        # Utile lorsqu'une première vérification
        # n'avait pas réussi à lire le statut.

        elif (
            old_status == "unknown"
            and new_status == "in_stock"
        ):

            title = (
                "🟢 PRODUIT DISPONIBLE !"
            )

        elif (
            old_status == "unknown"
            and new_status == "preorder"
        ):

            title = (
                "🔥 PRÉCOMMANDE OUVERTE ! 🔥"
            )

        # AUTRE CHANGEMENT

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

        send_telegram(
            message
        )


# ==================================================
# PROTECTION MÉMOIRE CONTRE LES ERREURS TEMPORAIRES
# ==================================================

def merge_with_previous(
    previous,
    current
):

    merged = dict(current)

    # Si une boutique n'a pas réussi à vérifier
    # un produit déjà connu, on garde l'ancien statut.
    #
    # Cela évite qu'un 429 fasse artificiellement
    # disparaître un produit ou transforme son statut.

    for url, old_product in previous.items():

        if url not in merged:
            continue

        new_product = merged[url]

        if new_product.get(
            "status"
        ) == "unknown":

            merged[url] = {

                "name":
                    new_product.get(
                        "name",
                        old_product.get(
                            "name",
                            ""
                        )
                    ),

                "shop":
                    new_product.get(
                        "shop",
                        old_product.get(
                            "shop",
                            ""
                        )
                    ),

                "status":
                    old_product.get(
                        "status",
                        "unknown"
                    )
            }

    return merged


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

    # ----------------------------------------------
    # PLAYIN
    # ----------------------------------------------

    playin_products = fetch_playin()

    # ----------------------------------------------
    # DRACAUGAMES
    # ----------------------------------------------

    dracau_products = fetch_dracaugames()

    # ----------------------------------------------
    # BCD
    # ----------------------------------------------

    bcd_products = fetch_bcd()

    # ----------------------------------------------
    # PIKA
    # ----------------------------------------------

    pika_products = fetch_pika()

    # ----------------------------------------------
    # FUSION
    # ----------------------------------------------

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

    # ----------------------------------------------
    # PROTECTION CONTRE 429 / ERREURS
    # ----------------------------------------------

    current_products = merge_with_previous(
        previous_products,
        current_products
    )

    # ----------------------------------------------
    # RÉSUMÉ
    # ----------------------------------------------

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

    # ----------------------------------------------
    # DÉTECTION
    # ----------------------------------------------

    new_products, status_changes = detect_changes(
        previous_products,
        current_products
    )

    # ----------------------------------------------
    # ALERTES
    # ----------------------------------------------

    send_alerts(
        new_products,
        status_changes
    )

    # ----------------------------------------------
    # LOG
    # ----------------------------------------------

    print(
        f"\nNouveaux produits : "
        f"{len(new_products)}"
    )

    print(
        f"Changements de statut : "
        f"{len(status_changes)}"
    )

    elapsed = time.time() - start_time

    print(
        f"Temps d'exécution : "
        f"{elapsed:.1f} secondes"
    )

    # ----------------------------------------------
    # SAUVEGARDE
    # ----------------------------------------------

    save_state(
        current_products
    )

    print(
        "\n✅ Surveillance terminée."
    )


# ==================================================
# LANCEMENT
# ==================================================

if __name__ == "__main__":

    main()