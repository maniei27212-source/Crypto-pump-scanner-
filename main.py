import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

message = "✅ Crypto Pump Scanner فعال شد!\n\nاتصال GitHub Actions → Telegram با موفقیت انجام شد."

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

response = requests.post(
    url,
    data={
        "chat_id": CHAT_ID,
        "text": message,
    },
    timeout=20,
)

response.raise_for_status()

print("Telegram message sent successfully.")
