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
    url = f"{DEXSCREENER}/token-pairs/v1/{chain_id}/{token_address}"

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
        score += 15
        reasons.append("strong liquidity")

    elif liquidity >= 50_000:
        score += 10
        reasons.append("acceptable liquidity")

    elif liquidity >= 20_000:
        score += 5
        reasons.append("low but usable liquidity")

    else:
        reasons.append("very low liquidity")

    # ==============================
    # VOLUME 1H
    # ==============================

    if volume_1h >= 100_000:
        score += 15
        reasons.append("strong 1H volume")

    elif volume_1h >= 25_000:
        score += 10
        reasons.append("rising 1H volume")

    elif volume_1h >= 5_000:
        score += 5
        reasons.append("active 1H volume")

    # ==============================
    # VOLUME 5M
    # ==============================

    if volume_5m >= 10_000:
        score += 10
        reasons.append("active 5M volume")

    elif volume_5m >= 2_500:
        score += 5
        reasons.append("rising 5M volume")

    # ==============================
    # BUY / SELL PRESSURE
    # ==============================

    buy_sell_5m = buys_5m / max(sells_5m, 1)
    buy_sell_1h = buys_1h / max(sells_1h, 1)

    if buy_sell_5m >= 2.0:
        score += 15
        reasons.append("very strong 5M buyer pressure")

    elif buy_sell_5m >= 1.5:
        score += 10
        reasons.append("strong 5M buyer pressure")

    elif buy_sell_5m >= 1.15:
        score += 5
        reasons.append("positive 5M buyer pressure")

    if buy_sell_1h >= 1.5:
        score += 10
        reasons.append("strong 1H buyer pressure")

    elif buy_sell_1h >= 1.15:
        score += 5
        reasons.append("positive 1H buyer pressure")

    # ==============================
    # PRICE MOMENTUM
    # ==============================

    if 0 < change_5m <= 8:
        score += 5
        reasons.append("early 5M momentum")

    if 0 < change_1h <= 15:
        score += 5
        reasons.append("healthy 1H momentum")

    # ==============================
    # AVOID EXTENDED PUMPS
    # ==============================

    if change_1h > 30:
        score -= 10
        reasons.append("already extended on 1H")

    if change_6h > 80:
        score -= 10
        reasons.append("large previous move")

    # ==============================
    # PAIR AGE
    # ==============================

    if age_hours is not None:

        if age_hours <= 12:
            score += 5
            reasons.append("very young pair")

        elif age_hours <= 48:
            score += 3
            reasons.append("young pair")

    # ==============================
    # FINAL SCORE
    # ==============================

    score = max(0, min(score, 100))

    if score >= 70:
        status = "EARLY RADAR"

    elif score >= 50:
        status = "DISCOVERY"

    else:
        status = "IGNORE"

    return {
        "score": score,
