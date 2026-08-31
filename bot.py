import os
import json
import re
import time
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_products.json"

TIMEOUT = 20

# Nombre maximum de connexions simultanées.
# 6 permet d'accélérer sans envoyer trop de requêtes.
MAX_WORKERS = 6


# ==================================================
# URLS
# ==================================================

URL_PLAYIN = (
    "https://www.play-in.com/fr/extension/"
    "1500/30eme-anniversaire"
)

URL_DRACAUGAMES = (
    "https://www.dracaugames.com"
)

URL_BCD_SEARCHES = [

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=pokemon+30+ans",

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=30e+anniversaire",

    "https://www.bcd-jeux.fr/recherche"
    "?controller=search&s=pokemon+anniversaire"

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
    "39006-pokemon-anniversaire-30-ans-"
    "coffret-etb-dresseur-d-elite-pokemon.html":

    "Pokémon Anniversaire 30 ans : "
    "Coffret ETB Dresseur d'élite"

}


PIKA_KNOWN_PRODUCTS = {

    "https://pika-boutique.fr/products/"
    "pack-n-1-30-ans-etb-x2-tripack-"
    "duopack-coffret-poster":

    "[PACK N°1] 30 ans - ETB + x2 tripack "
    "+ duopack + coffret poster",


    "https://pika-boutique.fr/products/"
    "pack-n-2-30-ans-etb-coffret-amphinobi-"
    "coffret-nymphali":

    "[PACK N°2] 30 ans - ETB + Coffret "
    "Amphinobi + Coffret Nymphali",


    "https://pika-boutique.fr/products/"
    "pack-n-3-30-ans-coffret-poster-"
    "x2-pokebox-duopack":

    "[PACK N°3] 30 ans - Coffret Poster "
    "+ x2 Pokebox + Duopack"

}


# ==================================================
# RECHERCHES DRACAUGAMES
# ==================================================

DRACAUGAMES_SEARCHES = [

    "30 ans",
    "30eme anniversaire",
    "30e anniversaire",
    "30th anniversary",
    "anniversaire 30"

]


# ==================================================
# HEADERS
# ==================================================

HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
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

    "Cache-Control": "no-cache",

    "Pragma": "no-cache"

}


# ==================================================
# SESSION HTTP
# ==================================================

SESSION = requests.Session()

SESSION.headers.update(
    HEADERS
)


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

        temp_file = SEEN_FILE + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                products,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_file,
            SEEN_FILE
        )

    except Exception as error:

        print(
            f"Erreur sauvegarde : {error}"
        )


# ==================================================
# INTERNET
# ==================================================

def get_page(url, retries=2):

    for attempt in range(
        retries + 1
    ):

        try:

            response = SESSION.get(
                url,
                timeout=TIMEOUT
            )

            if response.status_code == 429:

                wait_time = 2 + (
                    attempt * 3
                )

                print(
                    f"429 sur {url} - "
                    f"attente {wait_time}s"
                )

                time.sleep(
                    wait_time
                )

                continue

            response.raise_for_status()

            return response

        except Exception as error:

            if attempt >= retries:

                print(
                    f"Erreur récupération "
                    f"{url} : {error}"
                )

                return None

            time.sleep(1)

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

        response = SESSION.post(

            f"https://api.telegram.org/"
            f"bot{TOKEN}/sendMessage",

            data={

                "chat_id": CHAT_ID,

                "text": message,

                "disable_web_page_preview": False

            },

            timeout=15

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
# FILTRE POKÉMON 30 ANS
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
        keyword in text
        for keyword in keywords
    )


# ==================================================
# NORMALISATION TEXTE
# ==================================================

def normalize_text(text):

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip().lower()


# ==================================================
# DÉTECTION DU STATUT
# ==================================================

def detect_status(text):

    text = normalize_text(
        text
    )


    # ----------------------------------------------
    # RUPTURE
    # ----------------------------------------------

    out_words = [

        "rupture de stock",

        "rupture temporaire",

        "hors stock",

        "épuisé",

        "epuise",

        "sold out",

        "indisponible",

        "livraison indisponible"

    ]

    if any(
        word in text
        for word in out_words
    ):

        return "out_of_stock"


    # ----------------------------------------------
    # PRÉCOMMANDE
    # ----------------------------------------------

    preorder_words = [

        "précommander",

        "precommander",

        "précommande",

        "precommande"

    ]

    if any(
        word in text
        for word in preorder_words
    ):

        return "preorder"


    # ----------------------------------------------
    # STOCK
    # ----------------------------------------------

    stock_words = [

        "ajouter au panier",

        "en stock",

        "stock très faible",

        "stock faible"

    ]

    if any(
        word in text
        for word in stock_words
    ):

        return "in_stock"


    return "unknown"


# ==================================================
# STATUT PLAYIN
# ==================================================

def get_playin_status(url):

    response = get_page(
        url
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
    )


    actions = []


    for element in soup.find_all(
        [
            "button",
            "input",
            "a"
        ]
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


    action_text = " ".join(
        actions
    )


    if any(
        word in action_text.lower()
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
        in action_text.lower()
    ):

        return "in_stock"


    return detect_status(
        page_text
    )


# ==================================================
# PLAYIN
# ==================================================

def fetch_playin():

    print(
        "[Playin] Recherche des "
        "produits 30 ans..."
    )


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

        href = link.get(
            "href",
            ""
        )

        name = link.get_text(
            " ",
            strip=True
        )


        if (
            "/fr/produit/"
            not in href
        ):

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


        candidates[
            url
        ] = name


    print(
        f"[Playin] Produits 30 ans : "
        f"{len(candidates)}"
    )


    products = {}


    def check_product(item):

        url, name = item

        status = get_playin_status(
            url
        )

        return (
            url,
            name,
            status
        )


    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                check_product,
                item
            )

            for item
            in candidates.items()

        ]


        for future in as_completed(
            futures
        ):

            try:

                url, name, status = (
                    future.result()
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

            except Exception as error:

                print(
                    f"[Playin] Erreur : "
                    f"{error}"
                )


    return products


# ==================================================
# DRACAUGAMES
# ==================================================

def fetch_dracaugames_search(
    search_term
):

    encoded = quote(
        search_term
    )

    url = (
        f"{URL_DRACAUGAMES}/search"
        f"?q={encoded}"
    )


    response = get_page(
        url
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

        href = link.get(
            "href",
            ""
        )

        name = link.get_text(
            " ",
            strip=True
        )


        if "/products/" not in href:

            continue


        url = urljoin(
            URL_DRACAUGAMES,
            href
        ).split("?")[0]


        if not name:

            continue


        if not is_pokemon_30(
            name,
            url
        ):

            continue


        candidates[
            url
        ] = name


    return candidates


def fetch_dracaugames():

    print(
        "[DracauGames] Recherche "
        "des produits 30 ans..."
    )


    candidates = {}


    # On utilise plusieurs recherches
    # ciblées au lieu de parcourir
    # toute la collection nouveautés.

    for search_term in (
        DRACAUGAMES_SEARCHES
    ):

        print(
            f"[DracauGames] Recherche : "
            f"{search_term}"
        )


        results = (
            fetch_dracaugames_search(
                search_term
            )
        )


        candidates.update(
            results
        )


    print(
        "[DracauGames] Produits "
        f"candidats : {len(candidates)}"
    )


    if not candidates:

        print(
            "[DracauGames] "
            "Aucun produit 30 ans trouvé."
        )

        return {}


    products = {}


    def check_product(item):

        url, name = item

        response = get_page(
            url
        )

        if response is None:

            return (
                url,
                name,
                "unknown"
            )


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        text = soup.get_text(
            " ",
            strip=True
        )


        status = detect_status(
            text
        )


        return (
            url,
            name,
            status
        )


    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                check_product,
                item
            )

            for item
            in candidates.items()

        ]


        for future in as_completed(
            futures
        ):

            try:

                url, name, status = (
                    future.result()
                )


                if status == "unknown":

                    continue


                products[url] = {

                    "name": name,

                    "shop": "DracauGames",

                    "status": status

                }


                print(
                    f"[DracauGames] "
                    f"{name} -> {status}"
                )


            except Exception as error:

                print(
                    f"[DracauGames] "
                    f"Erreur : {error}"
                )


    print(
        "[DracauGames] Produits 30 ans "
        f"détectés : {len(products)}"
    )


    return products


# ==================================================
# BCD JEUX
# ==================================================

def fetch_bcd():

    candidates = dict(
        BCD_KNOWN_PRODUCTS
    )


    for search_url in (
        URL_BCD_SEARCHES
    ):

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

            href = link.get(
                "href",
                ""
            )

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


            candidates[
                url
            ] = name


    print(
        "[BCD Jeux] Produits potentiels : "
        f"{len(candidates)}"
    )


    products = {}


    def check_product(item):

        url, fallback = item

        response = get_page(
            url
        )


        if response is None:

            return None


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        name = fallback


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

                name = title


        if name == fallback:

            h1 = soup.find(
                "h1"
            )


            if h1:

                title = h1.get_text(
                    " ",
                    strip=True
                )


                if title:

                    name = title


        text = soup.get_text(
            " ",
            strip=True
        )


        status = detect_status(
            text
        )


        return (
            url,
            name,
            status
        )


    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                check_product,
                item
            )

            for item
            in candidates.items()

        ]


        for future in as_completed(
            futures
        ):

            try:

                result = future.result()


                if result is None:

                    continue


                url, name, status = result


                products[url] = {

                    "name": name,

                    "shop": "BCD Jeux",

                    "status": status

                }


                print(
                    f"[BCD Jeux] "
                    f"{name} -> {status}"
                )


            except Exception as error:

                print(
                    f"[BCD Jeux] "
                    f"Erreur : {error}"
                )


    return products


# ==================================================
# PIKA-BOUTIQUE
# ==================================================

def fetch_pika():

    candidates = dict(
        PIKA_KNOWN_PRODUCTS
    )


    for search_url in (
        URL_PIKA_SEARCHES
    ):

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

            href = link.get(
                "href",
                ""
            )

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


            if not is_pokemon_30(
                name,
                url
            ):

                continue


            candidates[
                url
            ] = name


    print(
        "[Pika-boutique] "
        "Produits potentiels : "
        f"{len(candidates)}"
    )


    products = {}


    def check_product(item):

        url, fallback = item

        response = get_page(
            url
        )


        if response is None:

            return None


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        name = fallback


        h1 = soup.find(
            "h1"
        )


        if h1:

            title = h1.get_text(
                " ",
                strip=True
            )


            if title:

                name = title


        else:

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

                    name = title


        text = soup.get_text(
            " ",
            strip=True
        )


        status = detect_status(
            text
        )


        return (
            url,
            name,
            status
        )


    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                check_product,
                item
            )

            for item
            in candidates.items()

        ]


        for future in as_completed(
            futures
        ):

            try:

                result = future.result()


                if result is None:

                    continue


                url, name, status = result


                products[url] = {

                    "name": name,

                    "shop": "Pika-boutique",

                    "status": status

                }


                print(
                    f"[Pika-boutique] "
                    f"{name} -> {status}"
                )


            except Exception as error:

                print(
                    f"[Pika-boutique] "
                    f"Erreur : {error}"
                )


    return products


# ==================================================
# LABEL STATUT
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
# DÉTECTION DES CHANGEMENTS
# ==================================================

def detect_changes(
    previous,
    current
):

    new_products = {}

    status_changes = []


    for url, product in (
        current.items()
    ):

        if url not in previous:

            new_products[
                url
            ] = product

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


        # On ignore unknown pour éviter
        # de provoquer de fausses alertes.

        if new_status == "unknown":

            continue


        if old_status != new_status:

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


        elif (
            old_status
            == "preorder"

            and

            new_status
            == "out_of_stock"
        ):

            title = (
                "🔴 PRÉCOMMANDE FERMÉE"
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


    previous_products = (
        load_state()
    )


    # ==================================================
    # RECHERCHE DES BOUTIQUES
    # ==================================================

    playin_products = (
        fetch_playin()
    )


    dracau_products = (
        fetch_dracaugames()
    )


    bcd_products = (
        fetch_bcd()
    )


    pika_products = (
        fetch_pika()
    )


    # ==================================================
    # FUSION
    # ==================================================

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


    # ==================================================
    # RÉSUMÉ
    # ==================================================

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


    # ==================================================
    # CHANGEMENTS
    # ==================================================

    new_products, status_changes = (
        detect_changes(
            previous_products,
            current_products
        )
    )


    # ==================================================
    # ALERTES
    # ==================================================

    send_alerts(
        new_products,
        status_changes
    )


    # ==================================================
    # RÉSULTAT
    # ==================================================

    print()

    print(
        f"Nouveaux produits : "
        f"{len(new_products)}"
    )

    print(
        f"Changements de statut : "
        f"{len(status_changes)}"
    )


    # ==================================================
    # SAUVEGARDE
    # ==================================================

    save_state(
        current_products
    )


    elapsed = (
        time.time()
        - start_time
    )


    print()

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