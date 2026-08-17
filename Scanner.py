import requests
import time


# ==========================================
# SETTINGS
# ==========================================

MIN_LIQUIDITY = 100_000
MIN_VOLUME_5M = 5_000
MIN_VOLUME_1H = 20_000

DISCOVERY_SCORE = 45
EARLY_RADAR_SCORE = 60

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/search"


# ==========================================
# HELPERS
# ==========================================

def safe_float(value):
    try:
        if value is None:
            return 0.0
        return float(value)
    except:
        return 0.0


def calculate_age_hours(pair_created_at):
    if not pair_created_at:
        return 999999

    try:
        created_ms = int(pair_created_at)
        now_ms = int(time.time() * 1000)
        age_hours = (now_ms - created_ms) / 1000 / 60 / 60
        return age_hours
    except:
        return 999999


def get_pairs():
    try:
        response = requests.get(
            DEXSCREENER_API,
            params={"q": "USDT"},
            timeout=20
        )

        response.raise_for_status()

        data = response.json()
        return data.get("pairs", [])

    except Exception as e:
        print(f"API Error: {e}")
        return []


# ==========================================
# SCORE
# ==========================================

def calculate_score(pair):

    score = 0

    liquidity_data = pair.get("liquidity") or {}
    volume_data = pair.get("volume") or {}
    txns_data = pair.get("txns") or {}

    liquidity = safe_float(
        liquidity_data.get("usd")
    )

    volume_5m = safe_float(
        volume_data.get("m5")
    )

    volume_1h = safe_float(
        volume_data.get("h1")
    )

    volume_6h = safe_float(
        volume_data.get("h6")
    )

    volume_24h = safe_float(
        volume_data.get("h24")
    )

    price_change = pair.get("priceChange") or {}

    change_5m = safe_float(
        price_change.get("m5")
    )

    change_1h = safe_float(
        price_change.get("
