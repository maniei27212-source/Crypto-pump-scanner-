import requests
import time
from datetime import datetime, timezone


DEXSCREENER = "https://api.dexscreener.com"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Crypto-Pump-Scanner/1.0"
})


def get_json(url, timeout=20):
    try:
        response = SESSION.get(url, timeout=timeout)

        if response.status_code == 429:
            print("[ERROR] DexScreener rate limit reached.")
            return None

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        print(f"[ERROR] API request failed: {exc}")
        return None


def get_latest_profiles():
    url = f"{DEXSCREENER}/token-profiles/latest/v1"

    data = get_json(url)

    if isinstance(data, list):
        return data

    return []


def get_token_pairs(chain_id, token_address):
    url = (
        f"{DEXSCREENER}/token-pairs/v1/"
        f"{chain_id}/{token_address}"
    )

    data = get_json(url)

    if isinstance(data, list):
        return data

    return []


def safe_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_age_hours(pair_created_at):
    if not pair_created_at:
        return None

    try:
        created = datetime.fromtimestamp(
            pair_created_at / 1000,
            tz=timezone.utc
        )

        now = datetime.now(timezone.utc)

        return max(
            0,
            (now - created).total_seconds() / 3600
        )

    except (TypeError, ValueError, OSError):
        return None


def score_pair(pair):

    score = 0
    reasons = []

    liquidity = safe_number(
        (pair.get("liquidity") or {}).get("usd")
    )

    volume = pair.get("volume") or {}

    volume_5m = safe_number(volume.get("m5"))
    volume_1h = safe_number(volume.get("h1"))
    volume_6h = safe_number(volume.get("h6"))
    volume_24h = safe_number(volume.get("h24"))

    price_change = pair.get("priceChange") or {}

    change_5m = safe_number(price_change.get("m5"))
    change_1h = safe_number(price_change.get("h1"))
    change_6h = safe_number(price_change.get("h6"))

    txns = pair.get("txns") or {}

    tx_5m = txns.get("m5") or {}
    tx_1h = txns.get("h1") or {}

    buys_5m = safe_number(tx_5m.get("buys"))
    sells_5m = safe_number(tx_5m.get("sells"))

    buys_1h = safe_number(tx_1h.get("buys"))
    sells_1h = safe_number(tx_1h.get("sells"))

    age_hours = calculate_age_hours(
        pair.get("pairCreatedAt")
    )

    # ==============================
    # LIQUIDITY
    # ==============================

    if liquidity >= 100_000:
        score +=
