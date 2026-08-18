import requests
import time
from collections import Counter

# ============================================================
# CONFIG
# ============================================================

DEX_BASE = "https://api.dexscreener.com"
GT_BASE = "https://api.geckoterminal.com/api/v2"

REQUEST_TIMEOUT = 20

MIN_LIQUIDITY = 75_000
MIN_VOLUME_5M = 5_000
MIN_VOLUME_1H = 20_000

MAX_TOKENS = 100
MAX_CANDIDATES_FOR_OHLCV = 30

MIN_DISCOVERY_SCORE = 35
EARLY_RADAR_SCORE = 50

BUY_NOW_SCORE = 75
BUY_NOW_MIN_LIQUIDITY = 100_000
BUY_NOW_MIN_BS5 = 1.50
BUY_NOW_MIN_BS1H = 1.10
BUY_NOW_MIN_MA = 2

session = requests.Session()

session.headers.update({
    "User-Agent": "Crypto-Pump-Scanner/5.0",
    "Accept": "application/json"
})

REJECTION_COUNTER = Counter()


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


def record_rejection(reason):
    REJECTION_COUNTER[reason] += 1


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
        age_ms = (
            time.time() * 1000
            - float(timestamp_ms)
        )

        if age_ms < 0:
            return 0

        return age_ms / 3_600_000

    except Exception:
        return None


# ============================================================
# DISCOVERY
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
                "tokenAddress": token_address
            }

    return list(tokens.values())[:MAX_TOKENS]


# ============================================================
# TOKEN PAIRS
# ============================================================

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

    return []


# ============================================================
# EXTRACT PAIR
# ============================================================

def extract_pair_data(pair):

    price_change = pair.get("priceChange") or {}
    volume = pair.get("volume") or {}
    liquidity_data = pair.get("liquidity") or {}
    txns = pair.get("txns") or {}

    txns_5m = txns.get("m5") or {}
    txns_1h = txns.get("h1") or {}

    buys_5m = safe_int(txns_5m.get("buys"))
    sells_5m = safe_int(txns_5m.get("sells"))

    buys_1h = safe_int(txns_1h.get("buys"))
    sells_1h = safe_int(txns_1h.get("sells"))

    bs5 = buys_5m / max(sells_5m, 1)
    bs1h = buys_1h / max(sells_1h, 1)

    base_token = pair.get("baseToken") or {}

    return {

        "symbol":
            base_token.get("symbol") or "UNKNOWN",

        "chain":
            pair.get("chainId") or "unknown",

        "dex_id":
            pair.get("dexId") or "",

        "url":
            pair.get("url") or "",

        "price":
            safe_float(pair.get("priceUsd")),

        "volume_5m":
            safe_float(volume.get("m5")),

        "volume_1h":
            safe_float(volume.get("h1")),

        "liquidity":
            safe_float(liquidity_data.get("usd")),

        "buys_5m":
            buys_5m,

        "sells_5m":
            sells_5m,

        "buys_1h":
            buys_1h,

        "sells_1h":
            sells_1h,

        "buy_sell_5m":
            bs5,

        "buy_sell_1h":
            bs1h,

        "change_5m":
            safe_float(price_change.get("m5")),

        "change_1h":
            safe_float(price_change.get("h1")),

        "change_6h":
            safe_float(price_change.get("h6")),

        "change_24h":
            safe_float(price_change.get("h24")),

        "age_hours":
            calculate_age_hours(
                pair.get("pairCreatedAt")
            ),

        "pair_address":
            pair.get("pairAddress"),

        "base_address":
            base_token.get("address"),

        "fdv":
            safe_float(pair.get("fdv")),

        "market_cap":
            safe_float(pair.get("marketCap")),
    }


# ============================================================
# PRE-PUMP FILTER
# ============================================================

def pre_pump_filter(data):

    reasons = []

    liquidity = data["liquidity"]
    volume_5m = data["volume_5m"]
    volume_1h = data["volume_1h"]

    bs5 = data["buy_sell_5m"]
    bs1h = data["buy_sell_1h"]

    change_5m = data["change_5m"]
    change_1h = data["change_1h"]
    change_6h = data["change_6h"]

    if liquidity < MIN_LIQUIDITY:
        reasons.append(
            f"Liquidity ${liquidity:,.0f} < ${MIN_LIQUIDITY:,.0f}"
        )

    if volume_5m < MIN_VOLUME_5M:
        reasons.append(
            f"5M volume ${volume_5m:,.0f} too low"
        )

    if volume_1h < MIN_VOLUME_1H:
        reasons.append(
            f"1H volume ${volume_1h:,.0f} too low"
        )

    if change_1h <= -20:
        reasons.append("1H heavy negative momentum")

    if change_5m >= 60:
        reasons.append("5M already pumped >60%")

    if change_1h >= 100:
        reasons.append("1H already pumped >100%")

    if change_6h >= 500:
        reasons.append("6H already heavily extended")

    if bs5 < 1.10:
        reasons.append(
            f"Weak 5M buyers ({bs5:.2f})"
        )

    if bs1h < 0.80:
        reasons.append(
            f"Weak 1H buyer/seller ratio ({bs1h:.2f})"
        )

    return len(reasons) == 0, reasons


# ============================================================
# BASE SCORE
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

    # Liquidity
    if liquidity >= 500_000:
        score += 15
        reasons.append("Very strong liquidity")

    elif liquidity >= 250_000:
        score += 13
        reasons.append("Strong liquidity")

    elif liquidity >= 150_000:
        score += 10
        reasons.append("Good liquidity")

    elif liquidity >= 75_000:
        score += 6
        reasons.append("Acceptable liquidity")

    # 1H volume
    if volume_1h >= 1_000_000:
        score += 12
        reasons.append("Very strong 1H volume")

    elif volume_1h >= 500_000:
        score += 10
        reasons.append("Strong 1H volume")

    elif volume_1h >= 200_000:
        score += 8
        reasons.append("Good 1H volume")

    else:
        score += 4

    # 5M volume
    if volume_5m >= 100_000:
        score += 12
        reasons.append("Strong 5M volume")

    elif volume_5m >= 50_000:
        score += 10
        reasons.append("Increasing 5M activity")

    elif volume_5m >= 20_000:
        score += 7
        reasons.append("Good 5M activity")

    else:
        score += 3

    # Buyers 5M
    if bs5 >= 2.5:
        score += 18
        reasons.append("Very strong buyer pressure 5M")

    elif bs5 >= 2.0:
        score += 15
        reasons.append("Strong buyer pressure 5M")

    elif bs5 >= 1.5:
        score += 11
        reasons.append("Good buyer pressure 5M")

    elif bs5 >= 1.3:
        score += 7
        reasons.append("Positive buyer pressure 5M")

    elif bs5 >= 1.1:
        score += 3

    # Buyers 1H
    if bs1h >= 2:
        score += 10
        reasons.append("Strong buyer pressure 1H")

    elif bs1h >= 1.5:
        score += 8
        reasons.append("Positive buyer pressure 1H")

    elif bs1h >= 1.2:
        score += 5

    elif bs1h >= 1:
        score += 2

    # 5M momentum
    if 0 < change_5m <= 10:
        score += 8
        reasons.append("Healthy early 5M momentum")

    elif 10 < change_5m <= 20:
        score += 5
        reasons.append("Moderate 5M momentum")

    elif change_5m < 0:
        score += 1

    # 1H momentum
    if 0 < change_1h <= 15:
        score += 8
        reasons.append("Healthy early 1H momentum")

    elif 15 < change_1h <= 30:
        score += 5
        reasons.append("Moderate 1H momentum")

    elif change_1h > 50:
        score -= 5
        reasons.append("Already extended on 1H")

    # 6H
    if 0 < change_6h <= 50:
        score += 6
        reasons.append("Healthy 6H trend")

    elif 50 < change_6h <= 150:
        score += 3
        reasons.append("Strong but extended 6H trend")

    elif change_6h > 150:
        score -= 4
        reasons.append("6H move already extended")

    # Volume acceleration
    volume_ratio = 0

    if volume_1h > 0:

        expected_5m = volume_1h / 12

        volume_ratio = (
            volume_5m /
            max(expected_5m, 1)
        )

        if volume_ratio >= 2:
            score += 12
            reasons.append(
                "Abnormal short-term volume acceleration"
            )

        elif volume_ratio >= 1.5:
            score += 9
            reasons.append(
                "Strong volume acceleration"
            )

        elif volume_ratio >= 1.2:
            score += 5
            reasons.append(
                "Increasing volume"
            )

    data["volume_ratio"] = volume_ratio

    # Age
    age = data["age_hours"]

    if age is not None:

        if age <= 6:
            score += 5
            reasons.append("Very early pair")

        elif age <= 12:
            score += 4
            reasons.append("Early pair")

        elif age <= 24:
            score += 2

    # Extension penalties
    if change_5m > 30:
        score -= 8
        reasons.append("5M price already extended")

    if change_1h > 40:
        score -= 8
        reasons.append("1H price already extended")

    if change_6h > 200:
        score -= 10
        reasons.append(
            "6H price already heavily extended"
        )

    score = max(0, min(score, 100))

    return score, reasons


# ============================================================
# GECKOTERMINAL NETWORK
# ============================================================

def get_gt_network(chain):

    mapping = {
        "solana": "solana",
        "ethereum": "eth",
        "bsc": "bsc",
        "base": "base",
        "arbitrum": "arbitrum",
        "polygon": "polygon_pos",
        "avalanche": "avax",
        "optimism": "optimism",
        "sui": "sui_network",
    }

    return mapping.get(
        str(chain).lower(),
        str(chain).lower()
    )


# ============================================================
# GECKOTERMINAL POOL LOOKUP
# ============================================================

def get_pool_ohlcv(pair):

    chain = pair.get("chain", "")
    pair_address = pair.get("pair_address")

    if not chain or not pair_address:
        return {}

    network = get_gt_network(chain)

    url = (
        f"{GT_BASE}/networks/"
        f"{network}/pools/"
        f"{pair_address}/ohlcv/"
        f"minute"
    )

    data = get_json(
        url,
        params={
            "aggregate": 5,
            "limit": 220
        }
    )

    if not isinstance(data, dict):
        return {}

    attrs = (
        data.get("data", {})
        .get("attributes", {})
    )

    ohlcv = attrs.get("ohlcv_list")

    if not isinstance(ohlcv, list):
        return {}

    candles = []

    for row in ohlcv:

        if len(row) < 6:
            continue

        candles.append({
            "open_time": safe_int(row[0]),
            "open": safe_float(row[1]),
            "high": safe_float(row[2]),
            "low": safe_float(row[3]),
            "close": safe_float(row[4]),
            "volume": safe_float(row[5]),
        })

    candles.sort(
        key=lambda x: x["open_time"]
    )

    return {
        "5m": candles
    }


# ============================================================
# RESAMPLE CANDLES
# ============================================================

def resample_candles(candles, group_size):

    if not candles:
        return []

    result = []

    for i in range(
        0,
        len(candles),
        group_size
    ):

        group = candles[
            i:i + group_size
        ]

        if len(group) < group_size:
            continue

        result.append({
            "open_time":
                group[0]["open_time"],

            "open":
                group[0]["open"],

            "high":
                max(
                    x["high"]
                    for x in group
                ),

            "low":
                min(
                    x["low"]
                    for x in group
                ),

            "close":
                group[-1]["close"],

            "volume":
                sum(
                    x["volume"]
                    for x in group
                )
        })

    return result


# ============================================================
# MA200
# ============================================================

def calculate_ma200(candles):

    if len(candles) < 200:
        return None

    closes = [
        x["close"]
        for x in candles[-200:]
    ]

    return sum(closes) / len(closes)


# ============================================================
# LOCAL LOWS
# ============================================================

def find_local_lows(candles):

    lows = []

    if len(candles) < 5:
        return lows

    for i in range(
        2,
        len(candles) - 2
    ):

        current = candles[i]["low"]

        if (
            current <= candles[i - 1]["low"]
            and current <= candles[i - 2]["low"]
            and current <= candles[i + 1]["low"]
            and current <= candles[i + 2]["low"]
        ):
            lows.append(i)

    return lows


def find_local_high(candles, start, end):

    if end <= start:
        return None

    if start >= len(candles):
        return None

    highest_index = start

    for i in range(
        start,
        min(end + 1, len(candles))
    ):

        if (
            candles[i]["high"]
            >
            candles[highest_index]["high"]
        ):
            highest_index = i

    return highest_index


# ============================================================
# DOUBLE BOTTOM
# ============================================================

def detect_double_bottom(candles):

    result = {
        "detected": False,
        "confirmed": False,
        "neckline": 0.0,
        "low1": 0.0,
        "low2": 0.0,
        "distance_pct": 0.0,
        "breakout_pct": 0.0,
        "volume_confirmed": False,
        "status": "NONE",
        "reason": ""
    }

    if len(candles) < 30:

        result["reason"] = (
            "Not enough candles"
        )

        return result

    lows = find_local_lows(candles)

    if len(lows) < 2:

        result["reason"] = (
            "Not enough local lows"
        )

        return result

    recent_lows = lows[-8:]
    best = None

    for first_pos in range(
        len(recent_lows) - 1
    ):

        i = recent_lows[first_pos]

        for second_pos in range(
            first_pos + 1,
            len(recent_lows)
        ):

            j = recent_lows[second_pos]

            if j - i < 5:
                continue

            if j - i > 80:
                continue

            low1 = candles[i]["low"]
            low2 = candles[j]["low"]

            if low1 <= 0 or low2 <= 0:
                continue

            difference = (
                abs(low1 - low2)
                / max(low1, low2)
                * 100
            )

            if difference > 8:
                continue

            neckline_index = find_local_high(
                candles,
                i,
                j
            )

            if neckline_index is None:
                continue

            neckline = candles[
                neckline_index
            ]["high"]

            if neckline <= max(low1, low2):
                continue

            depth1 = (
                (neckline - low1)
                / neckline
                * 100
            )

            depth2 = (
                (neckline - low2)
                / neckline
                * 100
            )

            if depth1 < 2 or depth2 < 2:
                continue

            best = {
                "i": i,
                "j": j,
                "low1": low1,
                "low2": low2,
                "neckline": neckline,
                "difference": difference
            }

    if best is None:

        result["reason"] = (
            "No valid Double Bottom structure"
        )

        return result

    current = candles[-1]
    previous = candles[-2]

    current_close = current["close"]
    previous_close = previous["close"]

    neckline = best["neckline"]

    breakout_pct = (
        (current_close - neckline)
        / neckline
        * 100
    )

    volumes = [
        c["volume"]
        for c in candles[-21:-1]
    ]

    average_volume = (
        sum(volumes) / len(volumes)
        if volumes else 0
    )

    volume_confirmed = (
        average_volume > 0
        and current["volume"]
        >= average_volume * 1.5
    )

    result["detected"] = True
    result["low1"] = best["low1"]
    result["low2"] = best["low2"]
    result["neckline"] = neckline
    result["distance_pct"] = best["difference"]
    result["breakout_pct"] = breakout_pct
    result["volume_confirmed"] = volume_confirmed

    if (
        current_close > neckline
        and previous_close <= neckline
        and volume_confirmed
    ):

        result["confirmed"] = True
        result["status"] = "CONFIRMED"

        result["reason"] = (
            "Double Bottom neckline breakout "
            "with volume confirmation"
        )

        return result

    distance_to_neckline = (
        (neckline - current_close)
        / neckline
        * 100
    )

    if (
        0 <= distance_to_neckline <= 5
        and current_close < neckline
    ):

        result["status"] = "NEAR BREAKOUT"

        result["reason"] = (
            "Double Bottom near neckline"
        )

    else:

        result["status"] = "FORMING"

        result["reason"] = (
            "Double Bottom structure forming"
        )

    return result


# ============================================================
# OHLCV ANALYSIS
# ============================================================

def analyze_ohlcv(data):

    data["ohlcv_available"] = False
    data["ma_score"] = 0
    data["technical_points"] = 0

    data["double_bottom_5m"] = {}
    data["double_bottom_1h"] = {}
    data["double_bottom_4h"] = {}

    data["double_bottom_detected"] = False
    data["double_bottom_confirmed"] = False

    gt_data = get_pool_ohlcv(data)

    candles_5m = gt_data.get("5m", [])

    if len(candles_5m) < 30:

        data["ohlcv_reason"] = (
            "Insufficient GeckoTerminal OHLCV"
        )

        return data

    candles_1h = resample_candles(
        candles_5m,
        12
    )

    candles_4h = resample_candles(
        candles_5m,
        48
    )

    db_5m = detect_double_bottom(
        candles_5m
    )

    db_1h = detect_double_bottom(
        candles_1h
    )

    db_4h = detect_double_bottom(
        candles_4h
    )

    data["ohlcv_available"] = True

    data["double_bottom_5m"] = db_5m
    data["double_bottom_1h"] = db_1h
    data["double_bottom_4h"] = db_4h

    data["ma200_5m"] = calculate_ma200(
        candles_5m
    )

    data["ma200_1h"] = calculate_ma200(
        candles_1h
    )

    data["ma200_4h"] = calculate_ma200(
        candles_4h
    )

    price = data["price"]

    ma_score = 0

    if (
        price > 0
        and data["ma200_5m"]
        and price > data["ma200_5m"]
    ):
        ma_score += 1

    if (
        price > 0
        and data["ma200_1h"]
        and price > data["ma200_1h"]
    ):
        ma_score += 1

    if (
        price > 0
        and data["ma200_4h"]
        and price > data["ma200_4h"]
    ):
        ma_score += 1

    data["ma_score"] = ma_score

    detected = (
        db_5m.get("detected", False)
        or db_1h.get("detected", False)
        or db_4h.get("detected", False)
    )

    confirmed = (
        db_5m.get("confirmed", False)
        or db_1h.get("confirmed", False)
        or db_4h.get("confirmed", False)
    )

    data["double_bottom_detected"] = detected
    data["double_bottom_confirmed"] = confirmed

    technical_points = 0

    if ma_score >= 3:
        technical_points += 15

    elif ma_score == 2:
        technical_points += 10

    elif ma_score == 1:
        technical_points += 5

    if detected:
        technical_points += 8
        data["technical_signal"] = (
            "Double Bottom detected"
        )

    else:
        data["technical_signal"] = (
            "No Double Bottom - not rejected"
        )

    if confirmed:
        technical_points += 7

    data["technical_points"] = technical_points

    return data


# ============================================================
# TECHNICAL SCORE
# ============================================================

def apply_technical_score(data):

    score = data.get("score", 0)

    reasons = list(
        data.get("reasons", [])
    )

    if data.get(
        "double_bottom_detected",
        False
    ):

        score += 8

        reasons.append(
            "BONUS: Double Bottom detected"
        )

    if data.get(
        "double_bottom_confirmed",
        False
    ):

        score += 7

        reasons.append(
            "BONUS: Double Bottom breakout confirmed"
        )

    ma_score = data.get(
        "ma_score",
        0
    )

    if ma_score >= 3:

        score += 10

        reasons.append(
            "Strong MA200 alignment 5M/1H/4H"
        )

    elif ma_score == 2:

        score += 7

        reasons.append(
            "MA200 alignment on 2 timeframes"
        )

    elif ma_score == 1:

        score += 3

        reasons.append(
            "MA200 alignment on 1 timeframe"
        )

    else:

        reasons.append(
            "MA200 confirmation weak"
        )

    data["score"] = max(
        0,
        min(score, 100)
    )

    data["reasons"] = reasons

    return data


# ============================================================
# BUY NOW
# ============================================================

def evaluate_buy_now(data):

    failures = []

    score = data.get("score", 0)
    liquidity = data.get("liquidity", 0)

    bs5 = data.get(
        "buy_sell_5m",
        0
    )

    bs1h = data.get(
        "buy_sell_1h",
        0
    )

    ma_score = data.get(
        "ma_score",
        0
    )

    volume_ratio = data.get(
        "volume_ratio",
        0
    )

    change_5m = data.get(
        "change_5m",
        0
    )

    change_1h = data.get(
        "change_1h",
        0
    )

    if score < BUY_NOW_SCORE:
        failures.append(
            f"Score {score} < {BUY_NOW_SCORE}"
        )

    if liquidity < BUY_NOW_MIN_LIQUIDITY:
        failures.append(
            f"Liquidity ${liquidity:,.0f} < "
            f"${BUY_NOW_MIN_LIQUIDITY:,.0f}"
        )

    if bs5 < BUY_NOW_MIN_BS5:
        failures.append(
            f"5M buyer ratio {bs5:.2f} < "
            f"{BUY_NOW_MIN_BS5}"
        )

    if bs1h < BUY_NOW_MIN_BS1H:
        failures.append(
            f"1H buyer ratio {bs1h:.2f} < "
            f"{BUY_NOW_MIN_BS1H}"
        )

    if ma_score < BUY_NOW_MIN_MA:
        failures.append(
            f"MA200 alignment {ma_score}/3"
        )

    if volume_ratio < 1.20:
        failures.append(
            f"Volume acceleration "
            f"{volume_ratio:.2f}x < 1.20x"
        )

    if change_5m > 25:
        failures.append(
            f"5M already extended "
            f"+{change_5m:.1f}%"
        )

    if change_1h > 50:
        failures.append(
            f"1H already extended "
            f"+{change_1h:.1f}%"
        )

    return len(failures) == 0, failures


# ============================================================
# EARLY RADAR
# ============================================================

def evaluate_early_radar(data):

    score = data.get("score", 0)

    bs5 = data.get(
        "buy_sell_5m",
        0
    )

    volume_ratio = data.get(
        "volume_ratio",
        0
    )

    liquidity = data.get(
        "liquidity",
        0
    )

    change_5m = data.get(
        "change_5m",
        0
    )

    reasons = []

    if score >= EARLY_RADAR_SCORE:
        reasons.append(
            f"Score {score}"
        )

    if bs5 >= 1.5:
        reasons.append(
            f"Strong buyers {bs5:.2f}"
        )

    if volume_ratio >= 1.3:
        reasons.append(
            f"Volume acceleration "
            f"{volume_ratio:.2f}x"
        )

    if liquidity >= 100_000:
        reasons.append(
            "Healthy liquidity"
        )

    if 0 <= change_5m <= 20:
        reasons.append(
            "Early 5M momentum"
        )

    if (
        score >= EARLY_RADAR_SCORE
        or (
            bs5 >= 1.5
            and volume_ratio >= 1.3
        )
        or (
            bs5 >= 1.7
            and liquidity >= 100_000
        )
    ):
        return True, reasons

    return False, [
        "Insufficient Early Radar strength"
    ]


# ============================================================
# STATUS
# ============================================================

def determine_status(data):

    buy_now, failures = evaluate_buy_now(data)

    if buy_now:

        data["status"] = "BUY NOW"

        data["status_reason"] = (
            "All major Buy Now confirmations passed"
        )

        data["buy_now_failures"] = []

        return data

    early, early_reasons = (
        evaluate_early_radar(data)
    )

    if early:

        data["status"] = "EARLY RADAR"

        data["status_reason"] = (
            "Strong pre-pump setup; "
            "waiting for confirmation"
        )

        data["early_reasons"] = early_reasons
        data["buy_now_failures"] = failures

        return data

    data["status"] = "WATCHLIST"

    data["status_reason"] = (
        "Interesting but not strong enough"
    )

    data["buy_now_failures"] = failures

    return data


# ============================================================
# MAIN SCAN
# ============================================================

def scan():

    global REJECTION_COUNTER

    REJECTION_COUNTER = Counter()

    print(
        "Starting Crypto Pump Scanner v5..."
    )

    tokens = get_latest_token_boosts()

    print(
        f"Discovery tokens found: {len(tokens)}"
    )

    candidates = []
    seen_pairs = set()

    for token in tokens:

        chain_id = token["chainId"]
        token_address = token["tokenAddress"]

        pairs = get_token_pairs(
            chain_id,
            token_address
        )

        if not pairs:
            record_rejection(
                "No trading pair found"
            )
            continue

        for pair in pairs:

            pair_address = pair.get(
                "pairAddress"
            )

            if not pair_address:
                continue

            if pair_address in seen_pairs:
                continue

            seen_pairs.add(pair_address)

            try:

                data = extract_pair_data(
                    pair
                )

                passed, reasons = (
                    pre_pump_filter(data)
                )

                if not passed:

                    for reason in reasons:
                        record_rejection(reason)

                    continue

                score, reasons = (
                    score_candidate(data)
                )

                if score < MIN_DISCOVERY_SCORE:

                    record_rejection(
                        f"Base score {score} < "
                        f"{MIN_DISCOVERY_SCORE}"
                    )

                    continue

                data["score"] = score
                data["reasons"] = reasons

                candidates.append(data)

            except Exception as exc:

                record_rejection(
                    "Candidate processing error"
                )

                print(
                    "Candidate processing error:"
                )

                print(exc)

    candidates.sort(
        key=lambda x: (
            x.get("score", 0),
            x.get("buy_sell_5m", 0),
            x.get("volume_5m", 0),
            x.get("liquidity", 0)
        ),
        reverse=True
    )

    print(
        f"Pre-OHLCV candidates: "
        f"{len(candidates)}"
    )

    ohlcv_candidates = candidates[
        :MAX_CANDIDATES_FOR_OHLCV
    ]

    print(
        "Running OHLCV / Double Bottom analysis..."
    )

    analyzed = []

    for data in ohlcv_candidates:

        try:

            data = analyze_ohlcv(data)
            data = apply_technical_score(data)
            data = determine_status(data)

            analyzed.append(data)

        except Exception as exc:

            print(
                f"OHLCV error "
                f"{data.get('symbol')}:"
            )

            print(exc)

            data["status"] = "EARLY RADAR"

            data["status_reason"] = (
                "OHLCV analysis failed; "
                "base scanner signal retained"
            )

            analyzed.append(data)

    priority = {
        "BUY NOW": 3,
        "EARLY RADAR": 2,
        "WATCHLIST": 1
    }

    analyzed.sort(
        key=lambda x: (
            priority.get(
                x.get("status"),
                0
            ),
            x.get("score", 0),
            x.get("buy_sell_5m", 0),
            x.get("volume_5m", 0)
        ),
        reverse=True
    )

    buy_now_count = sum(
        x.get("status") == "BUY NOW"
        for x in analyzed
    )

    early_count = sum(
        x.get("status") == "EARLY RADAR"
        for x in analyzed
    )

    watch_count = sum(
        x.get("status") == "WATCHLIST"
        for x in analyzed
    )

    print("")
    print("==============================")
    print("FINAL SCANNER RESULT")
    print("==============================")

    print(
        f"Final candidates: {len(analyzed)}"
    )

    print(
        f"BUY NOW: {buy_now_count}"
    )

    print(
        f"EARLY RADAR: {early_count}"
    )

    print(
        f"WATCHLIST: {watch_count}"
    )

    print("")
    print("TOP SIGNALS:")

    for item in analyzed[:20]:

        db = ""

        if item.get(
            "double_bottom_confirmed",
            False
        ):
            db = " | DB CONFIRMED"

        elif item.get(
            "double_bottom_detected",
            False
        ):
            db = " | DB BONUS"

        print(
            f"{item['symbol']} | "
            f"{item.get('status')} | "
            f"Score: {item.get('score')} | "
            f"BS5M: "
            f"{item.get('buy_sell_5m', 0):.2f} | "
            f"BS1H: "
            f"{item.get('buy_sell_1h', 0):.2f} | "
            f"VolAccel: "
            f"{item.get('volume_ratio', 0):.2f}x | "
            f"MA: "
            f"{item.get('ma_score', 0)}/3 | "
            f"Liq: "
            f"${item.get('liquidity', 0):,.0f}"
            f"{db}"
        )

    print("")
    print("BUY NOW DETAILS:")

    buy_items = [
        x for x in analyzed
        if x.get("status") == "BUY NOW"
    ]

    if not buy_items:

        print(
            "No token currently satisfies "
            "all strict BUY NOW conditions."
        )

    else:

        for item in buy_items:

            print(
                f"BUY NOW -> "
                f"{item['symbol']} | "
                f"Score {item['score']} | "
                f"{item.get('status_reason')}"
            )

    print("")
    print("EARLY RADAR:")

    early_items = [
        x for x in analyzed
        if x.get("status") == "EARLY RADAR"
    ]

    if not early_items:

        print(
            "No strong Early Radar setup."
        )

    else:

        for item in early_items:

            print(
                f"EARLY -> "
                f"{item['symbol']} | "
                f"Score {item['score']} | "
                f"BS5M "
                f"{item.get('buy_sell_5m', 0):.2f} | "
                f"Vol "
                f"{item.get('volume_ratio', 0):.2f}x | "
                f"MA "
                f"{item.get('ma_score', 0)}/3"
            )

    print("")
    print("REJECTION / DIAGNOSTIC REPORT:")

    if not REJECTION_COUNTER:

        print(
            "No pre-filter rejection recorded."
        )

    else:

        for reason, count in (
            REJECTION_COUNTER.most_common(15)
        ):

            print(
                f"- {count}x | {reason}"
            )

    print("")
    print("WHY TOP TOKENS DID NOT REACH BUY NOW:")

    for item in analyzed[:10]:

        if item.get("status") != "BUY NOW":

            failures = item.get(
                "buy_now_failures",
                []
            )

            print(
                f"{item['symbol']} | "
                f"{item.get('status')} | "
                f"{' ; '.join(failures[:6])}"
            )

    return analyzed[:20]
