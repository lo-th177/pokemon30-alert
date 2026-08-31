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

TIMEOUT = 30

# Petite pause entre les requêtes DracauGames
DRACAU_DELAY = 0.8

# Nombre maximum de tentatives après un 429
MAX_RETRIES_429 = 3


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": (
        "fr-FR,fr;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
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

# ==================================================
# BCD JEUX
# ==================================================

BCD_KNOWN_PRODUCTS = {

    "https://www.bcd-jeux.fr/pokemon-tcg/"
    "39006-pokemon-anniversaire-30-ans-coffret-"
    "etb-dresseur-d-elite-pokemon.html":
    "Pokémon Anniversaire 30 ans : "
    "Coffret ETB Dresseur d'élite"
}


URL_BCD_SEARCHES = [

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=pokemon+30+ans",

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=30e+anniversaire",

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=pokemon+anniversaire"

]


# ==================================================
# PIKA-BOUTIQUE
# ==================================================

PIKA_KNOWN_PRODUCTS = {

    "https://pika-boutique.fr/products/"
    "pack-n-1-30-ans-etb-x2-tripack-duopack-coffret-poster":
    "[PACK N°1] 30 ans - ETB + x2 tripack + "
    "duopack + coffret poster",

    "https://pika-boutique.fr/products/"
    "pack-n-2-30-ans-etb-coffret-amphinobi-coffret-nymphali":
    "[PACK N°2] 30 ans - ETB + Coffret Amphinobi "
    "+ Coffret Nymphali",

    "https://pika-boutique.fr/products/"
    "pack-n-3-30-ans-coffret-poster-x2-pokebox-duopack":
    "[PACK N°3] 30 ans - Coffret Poster + "
    "x2 Pokebox + Duopack"

}


URL_PIKA_SEARCHES = [

    "https://pika-boutique.fr/"
    "search?q=pokemon+30+ans",

    "https://pika-boutique.fr/"
    "search?q=30+ans",

    "https://pika-boutique.fr/"
    "search?q=30e+anniversaire"

]


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

session = requests.Session()

session.headers.update(HEADERS)


def get_page(
    url,
    retries=True,
    delay=0
):

    if delay > 0:
        time.sleep(delay)

    attempts = 1

    if retries:
        attempts = MAX_RETRIES_429 + 1

    for attempt in range(attempts):

        try:

            response = session.get(
                url,
                timeout=TIMEOUT
            )

            # ------------------------------------------
            # RATE LIMIT
            # ------------------------------------------

            if response.status_code == 429:

                if attempt >= attempts - 1:

                    print(
                        f"429 persistant : {url}"
                    )

                    return None

                retry_after = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                try:

                    wait_time = float(
                        retry_after
                    )

                except Exception:

                    wait_time = (
                        2 + attempt * 2
                    )

                wait_time = min(
                    wait_time,
                    8
                )

                print(
                    f"429 : attente "
                    f"{wait_time:.1f}s..."
                )

                time.sleep(
                    wait_time
                )

                continue

            response.raise_for_status()

            return response

        except Exception as error:

            if attempt >= attempts - 1:

                print(
                    f"Erreur récupération "
                    f"{url} : {error}"
                )

                return None

            time.sleep(
                1 + attempt
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

        response = session.post(

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
# FILTRE 30 ANS
# ==================================================

def is_pokemon_30(
    name,
    url
):

    text = (
        f"{name} {url}"
    ).lower()

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
        "30th anniversary"

    ]

    return any(
        word in text
        for word in keywords
    )


# ==================================================
# STATUT GÉNÉRAL
# ==================================================

def detect_status(text):

    text = text.lower()

    # IMPORTANT :
    # On vérifie d'abord les ruptures.

    if any(
        word in text
        for word in [

            "rupture temporaire",
            "rupture de stock",
            "hors stock",
            "épuisé",
            "epuise",
            "sold out"

        ]
    ):

        return "out_of_stock"


    # Précommande

    if any(
        word in text
        for word in [

            "précommander",
            "precommander",
            "précommande",
            "precommande"

        ]
    ):

        return "preorder"


    # Stock

    if any(
        word in text
        for word in [

            "ajouter au panier",
            "en stock",
            "stock très faible",
            "stock faible"

        ]
    ):

        return "in_stock"


    # Indisponibilité en dernier

    if any(
        word in text
        for word in [

            "indisponible",
            "livraison indisponible"

        ]
    ):

        return "out_of_stock"


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


    if any(
        word in action_text
        for word in [

            "précommander",
            "precommander",
            "précommande",
            "precommande"

        ]
    ):

        return "preorder"


    if (
        "ajouter au panier"
        in action_text
    ):

        return "in_stock"


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
            "/fr/produit/"
            not in href
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
            f"[Playin] "
            f"{name} -> {status}"
        )


    return products


# ==================================================
# DRACAUGAMES
# ==================================================

def extract_dracaugames_candidates(
    soup
):

    candidates = {}


    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href",
            ""
        )

        if "/products/" not in href:
            continue


        url = urljoin(
            URL_DRACAUGAMES,
            href
        ).split("?")[0]


        # ------------------------------------------
        # Nom direct
        # ------------------------------------------

        name = link.get_text(
            " ",
            strip=True
        )


        # ------------------------------------------
        # Chercher également le titre
        # dans les attributs Shopify
        # ------------------------------------------

        if not name:

            for attribute in [
                "title",
                "aria-label"
            ]:

                value = link.get(
                    attribute,
                    ""
                ).strip()

                if value:
                    name = value
                    break


        if not name:
            continue


        # ------------------------------------------
        # FILTRE STRICT 30 ANS
        # ------------------------------------------

        if not is_pokemon_30(
            name,
            url
        ):
            continue


        candidates[url] = name


    return candidates


def get_dracaugames_status(
    text
):

    return detect_status(
        text
    )


def fetch_dracaugames(
    previous_products
):

    print(
        "[DracauGames] "
        "Recherche des produits 30 ans..."
    )


    response = get_page(
        URL_DRACAUGAMES
    )


    if response is None:

        print(
            "[DracauGames] "
            "Collection inaccessible."
        )

        # ------------------------------------------
        # Si le site bloque temporairement,
        # on conserve les produits DracauGames
        # déjà connus.
        # ------------------------------------------

        previous = {}

        for url, product in (
            previous_products.items()
        ):

            if (
                product.get("shop")
                == "DracauGames"
            ):

                previous[url] = product


        print(
            f"[DracauGames] "
            f"{len(previous)} produit(s) "
            f"conservé(s) depuis la mémoire."
        )

        return previous


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    candidates = (
        extract_dracaugames_candidates(
            soup
        )
    )


    print(
        f"[DracauGames] "
        f"Produits 30 ans trouvés : "
        f"{len(candidates)}"
    )


    products = {}


    # ----------------------------------------------
    # On vérifie uniquement les produits réellement
    # identifiés comme 30 ans.
    # ----------------------------------------------

    for url, name in candidates.items():

        response = get_page(
            url,
            retries=True,
            delay=DRACAU_DELAY
        )


        if response is None:

            # Si la fiche est temporairement
            # bloquée, utiliser le statut précédent.

            old = previous_products.get(
                url
            )

            if (
                old
                and old.get("shop")
                == "DracauGames"
            ):

                products[url] = old

                print(
                    f"[DracauGames] "
                    f"{name} -> "
                    f"{old.get('status', 'unknown')} "
                    f"(mémoire)"
                )

            continue


        product_soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # ------------------------------------------
        # Récupération du meilleur titre possible
        # ------------------------------------------

        title = name


        h1 = product_soup.find(
            "h1"
        )


        if h1:

            h1_text = h1.get_text(
                " ",
                strip=True
            )

            if h1_text:
                title = h1_text


        # ------------------------------------------
        # Statut
        # ------------------------------------------

        page_text = (
            product_soup.get_text(
                " ",
                strip=True
            )
        )


        status = get_dracaugames_status(
            page_text
        )


        products[url] = {

            "name": title,
            "shop": "DracauGames",
            "status": status

        }


        print(
            f"[DracauGames] "
            f"{title} -> {status}"
        )


    # ----------------------------------------------
    # CONSERVATION DES PRODUITS PRÉCÉDEMMENT
    # CONNUS MAIS ABSENTS TEMPORAIREMENT DE LA PAGE
    # ----------------------------------------------

    for url, old_product in (
        previous_products.items()
    ):

        if (
            old_product.get("shop")
            != "DracauGames"
        ):
            continue


        if url in products:
            continue


        if is_pokemon_30(
            old_product.get("name", ""),
            url
        ):

            products[url] = old_product


            print(
                f"[DracauGames] "
                f"{old_product.get('name')} "
                f"-> "
                f"{old_product.get('status', 'unknown')} "
                f"(mémoire)"
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


        if (
            title
            and title.lower()
            not in [
                "menu",
                "bcd jeux"
            ]
        ):

            return title


    h1 = soup.find(
        "h1"
    )


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
        f"[BCD Jeux] "
        f"Produits potentiels : "
        f"{len(candidates)}"
    )


    products = {}


    for url, fallback in (
        candidates.items()
    ):

        response = get_page(
            url
        )


        if response is None:
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


    for url, fallback in (
        candidates.items()
    ):

        response = get_page(
            url
        )


        if response is None:
            continue


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        h1 = soup.find(
            "h1"
        )


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
            "status": status

        }


        print(
            f"[Pika-boutique] "
            f"{name} -> {status}"
        )


    return products


# ==================================================
# LABEL STATUT
# ==================================================

def status_label(
    status
):

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
# DÉTECTION DES CHANGEMENTS
# ==================================================

def detect_changes(
    previous,
    current
):

    new_products = {}

    changes = []


    for url, product in (
        current.items()
    ):

        # ------------------------------------------
        # NOUVEAU PRODUIT
        # ------------------------------------------

        if url not in previous:

            new_products[url] = product

            continue


        old_status = previous[
            url
        ].get(
            "status",
            "unknown"
        )


        new_status = product.get(
            "status",
            "unknown"
        )


        # ------------------------------------------
        # Éviter les faux changements UNKNOWN
        # ------------------------------------------

        if (
            old_status != new_status
            and new_status != "unknown"
        ):

            changes.append({

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
        changes
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

    for url, product in (
        new_products.items()
    ):

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
    # CHANGEMENTS DE STATUT
    # ----------------------------------------------

    for change in changes:

        old_status = (
            change["old_status"]
        )

        new_status = (
            change["new_status"]
        )


        if (
            old_status
            == "out_of_stock"

            and

            new_status
            == "in_stock"
        ):

            title = (
                "🚨🚨 RETOUR EN STOCK ! 🚨🚨"
            )


        elif (
            old_status
            == "unknown"

            and

            new_status
            == "in_stock"
        ):

            title = (
                "🚨 PRODUIT DISPONIBLE ! 🚨"
            )


        elif (
            new_status
            == "preorder"
        ):

            title = (
                "🔥 PRÉCOMMANDE OUVERTE ! 🔥"
            )


        elif (
            new_status
            == "in_stock"
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


        send_telegram(
            message
        )


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


    # ----------------------------------------------
    # MÉMOIRE
    # ----------------------------------------------

    previous_products = load_state()


    # ----------------------------------------------
    # PLAYIN
    # ----------------------------------------------

    playin_products = (
        fetch_playin()
    )


    # ----------------------------------------------
    # DRACAUGAMES
    # ----------------------------------------------

    dracau_products = (
        fetch_dracaugames(
            previous_products
        )
    )


    # ----------------------------------------------
    # BCD
    # ----------------------------------------------

    bcd_products = (
        fetch_bcd()
    )


    # ----------------------------------------------
    # PIKA
    # ----------------------------------------------

    pika_products = (
        fetch_pika()
    )


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
    # CHANGEMENTS
    # ----------------------------------------------

    new_products, status_changes = (
        detect_changes(
            previous_products,
            current_products
        )
    )


    # ----------------------------------------------
    # ALERTES TELEGRAM
    # ----------------------------------------------

    send_alerts(
        new_products,
        status_changes
    )


    # ----------------------------------------------
    # STATISTIQUES
    # ----------------------------------------------

    print(
        f"\nNouveaux produits : "
        f"{len(new_products)}"
    )


    print(
        f"Changements de statut : "
        f"{len(status_changes)}"
    )


    # ----------------------------------------------
    # SAUVEGARDE
    # ----------------------------------------------

    save_state(
        current_products
    )


    elapsed = (
        time.time()
        - start_time
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


# ==================================================
# LANCEMENT
# ==================================================

if __name__ == "__main__":

    main()