import requests
import time


DEX_BASE = "https://api.dexscreener.com"

REQUEST_TIMEOUT = 20

# حداقل‌های اولیه Discovery
MIN_LIQUIDITY = 50_000
MIN_VOLUME_5M = 5_000
MIN_VOLUME_1H = 20_000

# تعداد کاندیداهای اولیه
MAX_TOKENS = 100

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Crypto-Pump-Scanner/1.0"
    }
)


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
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except Exception as exc:
        print(f"API error: {url}")
        print(exc)
        return None


# ============================================================
# DEXSCREENER DATA
# ============================================================

def get_latest_token_boosts():
    """
    دریافت توکن‌هایی که اخیراً Boost گرفته‌اند.
    این فقط Discovery است و به معنی سیگنال خرید نیست.
    """

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
    """
    دریافت pairهای مربوط به یک token.
    """

    url = (
        f"{DEX_BASE}/latest/dex/tokens/"
        f"{chain_id}/{token_address}"
    )

    # بعضی endpointها با مسیر مستقیم کار نمی‌کنند.
    # fallback به endpoint استاندارد token search
    data = get_json(url)

    if isinstance(data, dict):

        pairs = data.get("pairs")

        if isinstance(pairs, list):
            return pairs

    # fallback
    data = get_json(
        f"{DEX_BASE}/latest/dex/search",
        params={"q": token_address},
    )

    if isinstance(data, dict):

        pairs = data.get("pairs")

        if isinstance(pairs, list):
            return pairs

    return []


# ============================================================
# PAIR EXTRACTION
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

    pair_created_at = pair.get(
        "pairCreatedAt"
    )

    age_hours = calculate_age_hours(
        pair_created_at
    )

    base_token = pair.get("baseToken") or {}

    symbol = (
        base_token.get("symbol")
        or "UNKNOWN"
    )

    return {
        "symbol": symbol,
        "chain": pair.get("chainId") or "unknown",
        "url": pair.get("url") or "",

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

        "age_hours": age_hours,

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


def calculate_age_hours(timestamp_ms):

    if not timestamp_ms:
        return None

    try:
        now_ms = time.time() * 1000

        age_ms = now_ms - float(
            timestamp_ms
        )

        if age_ms < 0:
            return 0

        return age_ms / (
            1000 * 60 * 60
        )

    except Exception:
        return None


# ============================================================
# EARLY RADAR SCORING
# ============================================================

def score_candidate(data):

    score = 0

    reasons = []

    # ========================================================
    # LIQUIDITY
    # ========================================================

    liquidity = data["liquidity"]

    if liquidity >= 500_000:

        score += 15
        reasons.append(
            "Strong liquidity"
        )

    elif liquidity >= 200_000:

        score += 12
        reasons.append(
            "Good liquidity"
        )

    elif liquidity >= 100_000:

        score += 9
        reasons.append(
            "Acceptable liquidity"
        )

    elif liquidity >= MIN_LIQUIDITY:

        score += 5

    else:

        return 0, [
            "Liquidity too low"
        ]


    # ========================================================
    # VOLUME 1H
    # ========================================================

    volume_1h = data["volume_1h"]

    if volume_1h >= 1_000_000:

        score += 15
        reasons.append(
            "Very strong 1H volume"
        )

    elif volume_1h >= 500_000:

        score += 12
        reasons.append(
            "Strong 1H volume"
        )

    elif volume_1h >= 200_000:

        score += 9
        reasons.append(
            "Good 1H volume"
        )

    elif volume_1h >= MIN_VOLUME_1H:

        score += 5


    # ========================================================
    # VOLUME 5M
    # ========================================================

    volume_5m = data["volume_5m"]

    if volume_5m >= 100_000:

        score += 15
        reasons.append(
            "Very strong 5M volume"
        )

    elif volume_5m >= 50_000:

        score += 12
        reasons.append(
            "Strong 5M volume"
        )

    elif volume_5m >= 20_000:

        score += 9
        reasons.append(
            "Increasing 5M activity"
        )

    elif volume_5m >= MIN_VOLUME_5M:

        score += 5


    # ========================================================
    # BUY / SELL 5M
    # ========================================================

    bs5 = data["buy_sell_5m"]

    if bs5 >= 2.5:

        score += 15
        reasons.append(
            "Very strong buyer pressure 5M"
        )

    elif bs5 >= 1.8:

        score += 12
        reasons.append(
            "Strong buyer pressure 5M"
        )

    elif bs5 >= 1.3:

        score += 8
        reasons.append(
            "Positive buyer pressure 5M"
        )

    elif bs5 > 1:

        score += 4


    # ========================================================
    # BUY / SELL 1H
    # ========================================================

    bs1h = data["buy_sell_1h"]

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


    # ========================================================
    # SHORT TERM MOMENTUM
    # ========================================================

    change_5m = data["change_5m"]
    change_1h = data["change_1h"]

    if (
        change_5m > 0
        and change_1h > 0
    ):

        score += 10

        reasons.append(
            "5M + 1H momentum aligned"
        )

    elif change_5m > 0:

        score += 5

        reasons.append(
            "Positive 5M momentum"
        )


    # ========================================================
    # VOLUME ACCELERATION
    # ========================================================

    if volume_5m > 0 and volume_1h > 0:

        expected_5m = volume_1h / 12

        if volume_5m >= expected_5m * 2:

            score += 10

            reasons.append(
                "Abnormal short-term volume acceleration"
            )

        elif volume_5m >= expected_5m * 1.3:

            score += 6

            reasons.append(
                "Increasing short-term volume"
            )


    # ========================================================
    # 6H TREND
    # ========================================================

    if data["change_6h"] > 5:

        score += 5

        reasons.append(
            "Positive 6H trend"
        )

    elif data["change_6h"] > 0:

        score += 2


    # ========================================================
    # AGE
    # ========================================================

    age = data["age_hours"]

    if age is not None:

        if age <= 12:

            reasons.append(
                "Very early pair"
            )

        elif age <= 48:

            reasons.append(
                "Relatively young pair"
            )


    # ========================================================
    # DOUBLE BOTTOM PLACEHOLDER
    # ========================================================

    # فعلاً امتیاز Double Bottom نمی‌دهیم.
    # برای تشخیص واقعی آن به OHLC تاریخی نیاز داریم.
    #
    # این بخش در نسخه بعدی با داده کندلی واقعی فعال می‌شود.

    # ========================================================
    # CAP SCORE
    # ========================================================

    score = min(score, 100)

    return score, reasons


# ============================================================
# QUALITY FILTER
# ============================================================

def quality_filter(data):

    if data["liquidity"] < MIN_LIQUIDITY:
        return False

    if data["volume_5m"] < MIN_VOLUME_5M:
        return False

    if data["volume_1h"] < MIN_VOLUME_1H:
        return False

    if data["buy_sell_5m"] <= 1:
        return False

    return True


# ============================================================
# DISCOVERY
# ============================================================

def scan():

    print(
        "Starting Discovery Scanner..."
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
            token_address,
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

                if not quality_filter(
                    data
                ):
                    continue

                score, reasons = (
                    score_candidate(
                        data
                    )
                )

                if score < 35:
                    continue

                # ==========================================
                # STATUS
                # ==========================================

                if score >= 75:

                    status = (
                        "EARLY RADAR"
                    )

                else:

                    status = (
                        "EARLY RADAR"
                    )

                data["status"] = status
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
        reverse=True,
    )

    print(
        f"Final candidates: {len(candidates)}"
    )

    return candidates[:20]
