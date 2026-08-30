import os
import json
import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_products.json"


URL_PLAYIN = (
    "https://www.play-in.com/fr/extension/"
    "1500/30eme-anniversaire"
)


URL_DRACAUGAMES = (
    "https://www.dracaugames.com/"
    "collections/nouveautes"
)


# Recherche BCD

URL_BCD_SEARCHES = [

    "https://www.bcd-jeux.fr/"
    "recherche?controller=search&s=Pokemon+30+ans",

    "https://www.bcd-jeux.fr/"
    "recherche?controller=search&s=Pokemon+anniversaire",

    "https://www.bcd-jeux.fr/"
    "recherche?controller=search&s=30+ans"
]


# Pages BCD déjà connues.
# Même si la recherche BCD ne retourne rien,
# ces produits restent surveillés.

BCD_KNOWN_PRODUCTS = [

    (
        "https://www.bcd-jeux.fr/"
        "pokemon-tcg/39006-"
        "pokemon-anniversaire-30-ans-"
        "coffret-etb-dresseur-d-elite-"
        "pokemon.html"
    )
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120.0.0.0 Safari/537.36"
    ),

    "Accept-Language": (
        "fr-FR,fr;q=0.9,"
        "en-US;q=0.8,en;q=0.7"
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
            f"Erreur récupération {url} : "
            f"{error}"
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

        return True

    except Exception as error:

        print(
            f"Erreur Telegram : {error}"
        )

        return False


# ==================================================
# FILTRE PRODUITS POKÉMON 30 ANS
# ==================================================

def is_real_pokemon_30_product(
    name,
    product_url
):

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

        and

        has_anniversary

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

        "précommander"
        in action_text

        or

        "precommander"
        in action_text

        or

        "précommande"
        in action_text

        or

        "precommande"
        in action_text

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

        or

        "rupture de stock"
        in page_text

        or

        "livraison indisponible"
        in page_text

        or

        "indisponible"
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

            or

            not name

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

        "précommander"
        in text

        or

        "precommander"
        in text

        or

        "précommande"
        in text

        or

        "precommande"
        in text

    ):

        return "preorder"


    if (

        "épuisé"
        in text

        or

        "epuise"
        in text

        or

        "rupture de stock"
        in text

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


        candidates[
            product_url
        ] = name


    print(

        "[DracauGames] "
        "Produits 30e anniversaire "
        f"à vérifier : {len(candidates)}"

    )


    for (
        product_url,
        name
    ) in candidates.items():


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

def get_bcd_product_name(
    soup,
    product_url
):

    # Titre principal

    title = soup.find("h1")

    if title:

        name = title.get_text(
            " ",
            strip=True
        )

        if name:
            return name


    # Meta OpenGraph

    meta = soup.find(
        "meta",
        property="og:title"
    )

    if meta:

        name = meta.get(
            "content",
            ""
        ).strip()

        if name:
            return name


    # Balise title

    title_tag = soup.find("title")

    if title_tag:

        name = title_tag.get_text(
            " ",
            strip=True
        )

        if name:
            return name


    # Secours : URL

    return product_url


def get_bcd_status(text):

    text = text.lower()


    # Rupture en priorité

    if (

        "rupture de stock temporaire"
        in text

        or

        "rupture de stock"
        in text

        or

        "hors stock"
        in text

        or

        "épuisé"
        in text

        or

        "epuise"
        in text

    ):

        return "out_of_stock"


    # Précommande

    if (

        "précommande"
        in text

        or

        "precommande"
        in text

        or

        "précommander"
        in text

        or

        "precommander"
        in text

    ):

        return "preorder"


    # Stock

    if (

        "en stock"
        in text

        or

        "ajouter au panier"
        in text

        or

        "ajouter au panier"
        in text

    ):

        return "in_stock"


    return "unknown"


def fetch_bcd_product(
    product_url
):

    response = get_page(
        product_url
    )


    if response is None:
        return None


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    name = get_bcd_product_name(
        soup,
        product_url
    )


    page_text = soup.get_text(
        " ",
        strip=True
    )


    status = get_bcd_status(
        page_text
    )


    return {

        "name": name,

        "shop": "BCD Jeux",

        "status": status

    }


def fetch_bcd():

    products = {}

    candidates = set()


    # ----------------------------------------------
    # 1. PAGES BCD CONNUES
    # ----------------------------------------------

    for product_url in BCD_KNOWN_PRODUCTS:

        candidates.add(
            product_url
        )


    # ----------------------------------------------
    # 2. RECHERCHES BCD
    # ----------------------------------------------

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


            if ".html" not in href:
                continue


            product_url = urljoin(
                search_url,
                href
            )


            name = link.get_text(
                " ",
                strip=True
            )


            # On accepte le filtre
            # nom + URL.

            if is_real_pokemon_30_product(
                name,
                product_url
            ):

                candidates.add(
                    product_url
                )


    print(

        "[BCD Jeux] "
        "Produits potentiels "
        f"à vérifier : {len(candidates)}"

    )


    # ----------------------------------------------
    # 3. VÉRIFICATION DES PRODUITS
    # ----------------------------------------------

    for product_url in candidates:


        product = fetch_bcd_product(
            product_url
        )


        if product is None:
            continue


        name = product["name"]


        # Les URL connues sont toujours
        # surveillées même si le titre
        # ne contient pas exactement
        # les mots-clés.

        is_known_product = (
            product_url
            in BCD_KNOWN_PRODUCTS
        )


        if (

            not is_known_product

            and

            not is_real_pokemon_30_product(
                name,
                product_url
            )

        ):

            continue


        products[product_url] = product


        print(

            f"[BCD Jeux] "
            f"{name} -> "
            f"{product['status']}"

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


    for (
        url,
        product
    ) in current.items():


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


        if (

            old_status != new_status

            and

            new_status != "unknown"

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


    # Nouveaux produits

    for (
        url,
        product
    ) in new_products.items():


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


    # Changements

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