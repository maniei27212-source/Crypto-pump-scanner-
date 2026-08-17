import requests
import time


DEX_BASE = "https://api.dexscreener.com"
REQUEST_TIMEOUT = 20

MIN_LIQUIDITY = 75_000
MIN_VOLUME_5M = 5_000
MIN_VOLUME_1H = 20_000

MAX_TOKENS = 100

session = requests.Session()
session.headers.update({
    "User-Agent": "Crypto-Pump-Scanner/2.0"
})


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def get_json(url, params=None):
    try:
        response = session.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    except Exception as exc:
        print(f"API error: {url}")
        print(exc)
        return None


# ============================================================
# AGE
# ============================================================

def calculate_age_hours(timestamp_ms):

    if not timestamp_ms:
        return None

    try:
        now_ms = time.time() * 1000
        age_ms = now_ms - float(timestamp_ms)

        if age_ms < 0:
            return 0

        return age_ms / (1000 * 60 * 60)

    except Exception:
        return None


# ============================================================
# DISCOVERY SOURCES
# ============================================================

def get_latest_token_boosts():

    urls = [
        f"{DEX_BASE}/token-boosts/latest/v1",
        f"{DEX_BASE}/token-boosts/top/v1",
        f"{DEX_BASE}/token-profiles/latest/v1",
    ]

    tokens = {}

    for url in urls:

        data = get_json(url)

        if not isinstance(data, list):
            continue

        for item in data:

            chain_id = item.get("chainId")
            token_address = item.get("tokenAddress")

            if not chain_id or not token_address:
                continue

            key = f"{chain_id}:{token_address}"

            tokens[key] = {
                "chainId": chain_id,
                "tokenAddress": token_address,
            }

    return list(tokens.values())[:MAX_TOKENS]


def get_token_pairs(chain_id, token_address):

    url = (
        f"{DEX_BASE}/latest/dex/tokens/"
        f"{token_address}"
    )

    data = get_json(url)

    if isinstance(data, dict):

        pairs = data.get("pairs")

        if isinstance(pairs, list):
            return pairs

    data = get_json(
        f"{DEX_BASE}/latest/dex/search",
        params={"q": token_address}
    )

    if isinstance(data, dict):

        pairs = data.get("pairs")

        if isinstance(pairs, list):
            return pairs

    return []


# ============================================================
# EXTRACT PAIR
# ============================================================

def extract_pair_data(pair):

    price_change = pair.get("priceChange") or {}

    change_5m = safe_float(
        price_change.get("m5")
    )

    change_1h = safe_float(
        price_change.get("h1")
    )

    change_6h = safe_float(
        price_change.get("h6")
    )

    change_24h = safe_float(
        price_change.get("h24")
    )

    volume = pair.get("volume") or {}

    volume_5m = safe_float(
        volume.get("m5")
    )

    volume_1h = safe_float(
        volume.get("h1")
    )

    liquidity_data = pair.get("liquidity") or {}

    liquidity = safe_float(
        liquidity_data.get("usd")
    )

    txns = pair.get("txns") or {}

    txns_5m = txns.get("m5") or {}
    txns_1h = txns.get("h1") or {}

    buys_5m = safe_int(
        txns_5m.get("buys")
    )

    sells_5m = safe_int(
        txns_5m.get("sells")
    )

    buys_1h = safe_int(
        txns_1h.get("buys")
    )

    sells_1h = safe_int(
        txns_1h.get("sells")
    )

    buy_sell_5m = (
        buys_5m / max(sells_5m, 1)
    )

    buy_sell_1h = (
        buys_1h / max(sells_1h, 1)
    )

    base_token = pair.get("baseToken") or {}

    symbol = (
        base_token.get("symbol")
        or "UNKNOWN"
    )

    return {
        "symbol": symbol,

        "chain": pair.get(
            "chainId"
        ) or "unknown",

        "url": pair.get(
            "url"
        ) or "",

        "price": safe_float(
            pair.get("priceUsd")
        ),

        "volume_5m": volume_5m,
        "volume_1h": volume_1h,

        "liquidity": liquidity,

        "buys_5m": buys_5m,
        "sells_5m": sells_5m,

        "buys_1h": buys_1h,
        "sells_1h": sells_1h,

        "buy_sell_5m": buy_sell_5m,
        "buy_sell_1h": buy_sell_1h,

        "change_5m": change_5m,
        "change_1h": change_1h,
        "change_6h": change_6h,
        "change_24h": change_24h,

        "age_hours": calculate_age_hours(
            pair.get("pairCreatedAt")
        ),

        "pair_address": pair.get(
            "pairAddress"
        ),

        "fdv": safe_float(
            pair.get("fdv")
        ),

        "market_cap": safe_float(
            pair.get("marketCap")
        ),
    }


# ============================================================
# PRE-PUMP HARD FILTER
# ============================================================

def pre_pump_filter(data):

    liquidity = data["liquidity"]
    volume_5m = data["volume_5m"]
    volume_1h = data["volume_1h"]

    bs5 = data["buy_sell_5m"]
    bs1h = data["buy_sell_1h"]

    change_5m = data["change_5m"]
    change_1h = data["change_1h"]
    change_6h = data["change_6h"]

    # --------------------------------------------------------
    # Liquidity
    # --------------------------------------------------------

    if liquidity < MIN_LIQUIDITY:
        return False

    # --------------------------------------------------------
    # Minimum activity
    # --------------------------------------------------------

    if volume_5m < MIN_VOLUME_5M:
        return False

    if volume_1h < MIN_VOLUME_1H:
        return False

    # --------------------------------------------------------
    # Strong negative 1H = reject
    # --------------------------------------------------------

    if change_1h <= -20:
        return False

    # --------------------------------------------------------
    # Already heavily pumped = reject
    # --------------------------------------------------------

    if change_5m >= 60:
        return False

    if change_1h >= 100:
        return False

    if change_6h >= 500:
        return False

    # --------------------------------------------------------
    # Buyer pressure
    # --------------------------------------------------------

    if bs5 < 1.10:
        return False

    # 1H can temporarily be below 1,
    # but very weak 1H pressure is rejected.

    if bs1h < 0.80:
        return False

    return True


# ============================================================
# PRE-PUMP SCORING
# ============================================================

def score_candidate(data):

    score = 0
    reasons = []

    liquidity = data["liquidity"]
    volume_5m = data["volume_5m"]
    volume_1h = data["volume_1h"]

    bs5 = data["buy_sell_5m"]
    bs1h = data["buy_sell_1h"]

    change_5m = data["change_5m"]
    change_1h = data["change_1h"]
    change_6h = data["change_6h"]

    # ========================================================
    # LIQUIDITY
    # ========================================================

    if liquidity >= 500_000:

        score += 15

        reasons.append(
            "Very strong liquidity"
        )

    elif liquidity >= 250_000:

        score += 13

        reasons.append(
            "Strong liquidity"
        )

    elif liquidity >= 150_000:

        score += 10

        reasons.append(
            "Good liquidity"
        )

    elif liquidity >= 75_000:

        score += 6

        reasons.append(
            "Acceptable liquidity"
        )


    # ========================================================
    # 1H VOLUME
    # ========================================================

    if volume_1h >= 1_000_000:

        score += 12

        reasons.append(
            "Very strong 1H volume"
        )

    elif volume_1h >= 500_000:

        score += 10

        reasons.append(
            "Strong 1H volume"
        )

    elif volume_1h >= 200_000:

        score += 8

        reasons.append(
            "Good 1H volume"
        )

    else:

        score += 4


    # ========================================================
    # 5M VOLUME
    # ========================================================

    if volume_5m >= 100_000:

        score += 12

        reasons.append(
            "Strong 5M volume"
        )

    elif volume_5m >= 50_000:

        score += 10

        reasons.append(
            "Increasing 5M activity"
        )

    elif volume_5m >= 20_000:

        score += 7

        reasons.append(
            "Good 5M activity"
        )

    else:

        score += 3


    # ========================================================
    # BUYER STRENGTH 5M
    # ========================================================

    if bs5 >= 2.5:

        score += 18

        reasons.append(
            "Very strong buyer pressure 5M"
        )

    elif bs5 >= 2.0:

        score += 15

        reasons.append(
            "Strong buyer pressure 5M"
        )

    elif bs5 >= 1.5:

        score += 11

        reasons.append(
            "Good buyer pressure 5M"
        )

    elif bs5 >= 1.3:

        score += 7

        reasons.append(
            "Positive buyer pressure 5M"
        )

    elif bs5 >= 1.1:

        score += 3


    # ========================================================
    # BUYER STRENGTH 1H
    # ========================================================

    if bs1h >= 2:

        score += 10

        reasons.append(
            "Strong buyer pressure 1H"
        )

    elif bs1h >= 1.5:

        score += 8

        reasons.append(
            "Positive buyer pressure 1H"
        )

    elif bs1h >= 1.2:

        score += 5

    elif bs1h >= 1:

        score += 2


    # ========================================================
    # PRE-PUMP PRICE STRUCTURE
    # ========================================================

    # حرکت کم ولی مثبت برای ما بهتر از پامپ شدید است.

    if 0 < change_5m <= 10:

        score += 8

        reasons.append(
            "Healthy early 5M momentum"
        )

    elif 10 < change_5m <= 20:

        score += 5

        reasons.append(
            "Moderate 5M momentum"
        )

    elif change_5m < 0:

        score += 1


    if 0 < change_1h <= 15:

        score += 8

        reasons.append(
            "Healthy early 1H momentum"
        )

    elif 15 < change_1h <= 30:

        score += 5

        reasons.append(
            "Moderate 1H momentum"
        )

    elif change_1h > 50:

        # already moving too fast
        score -= 5

        reasons.append(
            "Already extended on 1H"
        )


    # ========================================================
    # 6H STRUCTURE
    # ========================================================

    if 0 < change_6h <= 50:

        score += 6

        reasons.append(
            "Healthy 6H trend"
        )

    elif 50 < change_6h <= 150:

        score += 3

        reasons.append(
            "Strong but extended 6H trend"
        )

    elif change_6h > 150:

        score -= 4

        reasons.append(
            "6H move already extended"
        )


    # ========================================================
    # VOLUME ACCELERATION
    # ========================================================

    if volume_1h > 0:

        expected_5m = volume_1h / 12

        ratio = (
            volume_5m /
            max(expected_5m, 1)
        )

        if ratio >= 2:

            score += 12

            reasons.append(
                "Abnormal short-term volume acceleration"
            )

        elif ratio >= 1.5:

            score += 9

            reasons.append(
                "Strong volume acceleration"
            )

        elif ratio >= 1.2:

            score += 5

            reasons.append(
                "Increasing volume"
            )


    # ========================================================
    # EARLY AGE BONUS
    # ========================================================

    age = data["age_hours"]

    if age is not None:

        if age <= 6:

            score += 5

            reasons.append(
                "Very early pair"
            )

        elif age <= 12:

            score += 4

            reasons.append(
                "Early pair"
            )

        elif age <= 24:

            score += 2


    # ========================================================
    # EXTENSION PENALTY
    # ========================================================

    if change_5m > 30:

        score -= 8

        reasons.append(
            "5M price already extended"
        )

    if change_1h > 40:

        score -= 8

        reasons.append(
            "1H price already extended"
        )

    if change_6h > 200:

        score -= 10

        reasons.append(
            "6H price already heavily extended"
        )


    # ========================================================
    # SCORE LIMIT
    # ========================================================

    score = max(
        0,
        min(score, 100)
    )

    return score, reasons


# ============================================================
# DISCOVERY
# ============================================================

def scan():

    print(
        "Starting Pre-Pump Discovery Scanner..."
    )

    tokens = get_latest_token_boosts()

    print(
        f"Discovery tokens found: {len(tokens)}"
    )

    candidates = []
    seen_pairs = set()

    for token in tokens:

        chain_id = token["chainId"]
        token_address = token[
            "tokenAddress"
        ]

        pairs = get_token_pairs(
            chain_id,
            token_address
        )

        for pair in pairs:

            pair_address = pair.get(
                "pairAddress"
            )

            if not pair_address:
                continue

            if pair_address in seen_pairs:
                continue

            seen_pairs.add(
                pair_address
            )

            try:

                data = extract_pair_data(
                    pair
                )

                # ------------------------------------------------
                # PRE-PUMP HARD FILTER
                # ------------------------------------------------

                if not pre_pump_filter(data):
                    continue

                score, reasons = (
                    score_candidate(data)
                )

                # ------------------------------------------------
                # Minimum meaningful score
                # ------------------------------------------------

                if score < 40:
                    continue

                data["status"] = (
                    "EARLY RADAR"
                )

                data["score"] = score
                data["reasons"] = reasons

                candidates.append(
                    data
                )

            except Exception as exc:

                print(
                    "Candidate processing error:"
                )

                print(exc)

    # ========================================================
    # SORT
    # ========================================================

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["buy_sell_5m"],
            x["volume_5m"],
            x["liquidity"],
        ),
        reverse=True
    )

    print(
        f"Final pre-pump candidates: "
        f"{len(candidates)}"
    )

    return candidates[:20]
