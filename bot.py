import os
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "1373516274"

BOUTIQUES = [
    "Playin",
    "DracauGames",
    "Parkage",
    "Le Coin des Barons",
    "Pikastore",
    "Masterset",
    "Fnac",
    "Cultura",
    "L'Antre Temps",
    "Les Gentlemen du Jeu",
    "BCD Jeux",
    "Philibert",
    "King Jouet",
    "Smyths Toys",
    "La Grande Recre",
    "1001Hobbies",
    "VCollect",
    "Figurines-Goodies",
    "Amazon France"
]

message = (
    "🤖 Bot Pokemon 30e anniversaire demarre !\n\n"
    f"🏪 {len(BOUTIQUES)} boutiques configurees.\n"
    "🔍 Surveillance en preparation."
)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

response = requests.post(
    url,
    data={
        "chat_id": CHAT_ID,
        "text": message
    },
    timeout=20
)

print(response.text)