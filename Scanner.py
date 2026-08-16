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
            print("DexScreener rate limit reached.")
            return None

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        print(f"API error: {exc}")
        return None


def get_latest_profiles():
    url = f"{DEXSCREENER}/token-profiles/latest/v1"
    data = get_json(url)

    if not data:
        return []

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
        return max(0, (now - created).total_seconds() / 3600)
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

    pair_age = calculate_age_hours(pair.get("pairCreatedAt"))

    # -------------------------------------------------
    # Liquidity
    # -------------------------------------------------

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

    # -------------------------------------------------
    # Volume
    # -------------------------------------------------

    if volume_1h >= 100_000:
        score += 15
        reasons.append("strong 1H volume")
    elif volume_1h >= 25_000:
        score += 10
        reasons.append("rising 1H volume")
    elif volume_1h >= 5_000:
        score += 5

    if volume_5m >= 10_000:
        score += 10
        reasons.append("active 5M volume")
    elif volume_5m >= 2_500:
        score += 5

    # -------------------------------------------------
    # Buy pressure
    # -------------------------------------------------

    buy_sell_5m = (
        buys_5m / max(sells_5m, 1)
    )

    buy_sell_1h = (
        buys_1h / max(sells_1h, 1)
    )

    if buy_sell_5m >= 2.0:
        score += 15
        reasons.append("very strong 5M buyer pressure")
    elif buy_sell_5m >= 1.5:
        score += 10
        reasons.append("strong 5M buyer pressure")
    elif buy_sell_5m >= 1.15:
        score += 5

    if buy_sell_1h >= 1.5:
        score += 10
        reasons.append("strong 1H buyer pressure")
    elif buy_sell_1h >= 1.15:
        score += 5

    # -------------------------------------------------
    # Price acceleration
    # -------------------------------------------------

    if 0 < change_5m <= 8:
        score += 5
        reasons.append("early 5M momentum")

    if 0 < change_1h <= 15:
        score += 5
        reasons.append("healthy 1H momentum")

    # Avoid rewarding already extreme pumps.
    if change_1h > 30:
        score -= 10
        reasons.append("already extended on 1H")

    if change_6h > 80:
        score -= 10
        reasons.append("large prior move")

    # -------------------------------------------------
    # Young pair bonus
    # -------------------------------------------------

    if pair_age is not None:
        if pair_age <= 12:
            score += 5
            reasons.append("very young pair")
        elif pair_age <= 48:
            score += 3
            reasons.append("young pair")

    score = max(0, min(score, 100))

    if score >= 70:
        status = "EARLY RADAR"
    elif score >= 50:
        status = "DISCOVERY"
    else:
        status = "IGNORE"

    return {
        "score": score,
        "status": status,
        "reasons": reasons,
        "liquidity": liquidity,
        "volume_5m": volume_5m,
        "volume_1h": volume_1h,
        "volume_6h": volume_6h,
        "volume_24h": volume_24h,
        "change_5m": change_5m,
        "change_1h": change_1h,
        "change_6h": change_6h,
        "buy_sell_5m": buy_sell_5m,
        "buy_sell_1h": buy_sell_1h,
        "age_hours": pair_age,
    }


def scan():
    profiles = get_latest_profiles()

    if not profiles:
        print("No DexScreener profiles returned.")
        return []

    results = []

    # Safety limit so the first version never makes excessive requests.
    for profile in profiles[:30]:

        chain_id = profile.get("chainId")
        token_address = profile.get("tokenAddress")

        if not chain_id or not token_address:
            continue

        pairs = get_token_pairs(chain_id, token_address)

        if not pairs:
            continue

        # Select the pair with the strongest liquidity.
        pairs.sort(
            key=lambda p: safe_number(
                (p.get("liquidity") or {}).get("usd")
            ),
            reverse=True
        )

        pair = pairs[0]

        analysis = score_pair(pair)

        if analysis["status"] == "IGNORE":
            continue

        base = pair.get("baseToken") or {}

        results.append({
            "symbol": base.get("symbol", "UNKNOWN"),
            "name": base.get("name", "Unknown"),
            "chain": chain_id,
            "pair_address": pair.get("pairAddress"),
            "url": pair.get("url"),
            **analysis
        })

        time.sleep(0.15)

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results


if __name__ == "__main__":
    results = scan()

    print(f"Candidates found: {len(results)}")

    for item in results[:20]:
        print(
            f"{item['status']} | "
            f"{item['symbol']} | "
            f"Score {item['score']} | "
            f"Liquidity ${item['liquidity']:,.0f} | "
            f"1H Vol ${item['volume_1h']:,.0f} | "
            f"Buy/Sell 5M {item['buy_sell_5m']:.2f}"
  )
