import os
import requests

from Scanner import scan


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    response.raise_for_status()


def format_candidate(item):
    status = item["status"]

    emoji = "🟡" if status == "EARLY RADAR" else "🔵"

    age = item["age_hours"]

    if age is None:
        age_text = "Unknown"
    else:
        age_text = f"{age:.1f}h"

    return (
        f"{emoji} {status}\n\n"
        f"🪙 {item['symbol']}\n"
        f"Chain: {item['chain']}\n"
        f"Score: {item['score']}/100\n\n"

        f"📊 Volume 5M: ${item['volume_5m']:,.0f}\n"
        f"📈 Volume 1H: ${item['volume_1h']:,.0f}\n"
        f"💧 Liquidity: ${item['liquidity']:,.0f}\n\n"

        f"🟢 Buy/Sell 5M: {item['buy_sell_5m']:.2f}\n"
        f"🟢 Buy/Sell 1H: {item['buy_sell_1h']:.2f}\n\n"

        f"📈 Price 5M: {item['change_5m']:+.2f}%\n"
        f"📈 Price 1H: {item['change_1h']:+.2f}%\n"
        f"📈 Price 6H: {item['change_6h']:+.2f}%\n\n"

        f"⏱ Pair age: {age_text}\n\n"

        f"🔎 Reasons:\n"
        + "\n".join(
            f"• {reason}"
            for reason in item["reasons"][:6]
        )
        + "\n\n"
        f"🔗 {item['url']}"
    )


def main():
    print("Starting Crypto Pump Scanner...")

    results = scan()

    print(f"Candidates found: {len(results)}")

    if not results:
        send_telegram(
            "🔎 Crypto Pump Scanner\n\n"
            "فعلاً کاندیدای قابل‌توجهی در Discovery/Early Radar پیدا نشد."
        )
        return

    # فقط بهترین کاندیداها ارسال شوند
    top_results = results[:5]

    message = (
        "🚨 CRYPTO PUMP SCANNER\n"
        "Discovery / Early Radar\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for item in top_results:
        message += format_candidate(item)
        message += "\n\n━━━━━━━━━━━━━━━━━━\n\n"

    message += (
        "⚠️ این نسخه هنوز BUY NOW صادر نمی‌کند.\n"
        "سیگنال‌ها برای Early Radar هستند و قبل از ورود "
        "نیاز به Confirmation دارند."
    )

    send_telegram(message)

    print("Telegram alert sent successfully.")


if __name__ == "__main__":
    main()
