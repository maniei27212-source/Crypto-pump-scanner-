import requests
import time


# ============================================================
# CONFIG
# ============================================================

DEX_BASE = "https://api.dexscreener.com"
BINANCE_BASE = "https://api.binance.com"

REQUEST_TIMEOUT = 20

MIN_LIQUIDITY = 75_000
MIN_VOLUME_5M = 5_000
MIN_VOLUME_1H = 20_000

MAX_TOKENS = 100
MAX_CANDIDATES_FOR_OHLCV = 30

session = requests.Session()
session.headers.update({
    "User-Agent": "Crypto-Pump-Scanner/3.0"
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

    change_5m = safe_float(price_change.get("m5"))
    change_1h = safe_float(price_change.get("h1"))
    change_6h = safe_float(price_change.get("h6"))
    change_24h = safe_float(price_change.get("h24"))

    volume = pair.get("volume") or {}

    volume_5m = safe_float(volume.get("m5"))
    volume_1h = safe_float(volume.get("h1"))

    liquidity_data = pair.get("liquidity") or {}

    liquidity = safe_float(
        liquidity_data.get("usd")
    )

    txns = pair.get("txns") or {}

    txns_5m = txns.get("m5") or {}
    txns_1h = txns.get("h1") or {}

    buys_5m = safe_int(txns_5m.get("buys"))
    sells_5m = safe_int(txns_5m.get("sells"))

    buys_1h = safe_int(txns_1h.get("buys"))
    sells_1h = safe_int(txns_1h.get("sells"))

    buy_sell_5m = buys_5m / max(sells_5m, 1)
    buy_sell_1h = buys_1h / max(sells_1h, 1)

    base_token = pair.get("baseToken") or {}

    symbol = (
        base_token.get("symbol")
        or "UNKNOWN"
    )

    return {
        "symbol": symbol,

        "chain": pair.get("chainId") or "unknown",

        "dex_id": pair.get("dexId") or "",

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

        "age_hours": calculate_age_hours(
            pair.get("pairCreatedAt")
        ),

        "pair_address": pair.get(
            "pairAddress"
        ),

        "base_address": base_token.get(
            "address"
        ),

        "fdv": safe_float(
            pair.get("fdv")
        ),

        "market_cap": safe_float(
            pair.get("marketCap")
        ),
    }


# ============================================================
# PRE-PUMP FILTER
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

    if liquidity < MIN_LIQUIDITY:
        return False

    if volume_5m < MIN_VOLUME_5M:
        return False

    if volume_1h < MIN_VOLUME_1H:
        return False

    if change_1h <= -20:
        return False

    if change_5m >= 60:
        return False

    if change_1h >= 100:
        return False

    if change_6h >= 500:
        return False

    if bs5 < 1.10:
        return False

    if bs1h < 0.80:
        return False

    return True


# ============================================================
# BASE SCORING
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

    # 1H Volume
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

    # 5M Volume
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

    # Buyer strength 5M
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

    # Buyer strength 1H
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

    # 6H structure
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
    if volume_1h > 0:

        expected_5m = volume_1h / 12

        ratio = volume_5m / max(
            expected_5m,
            1
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
        reasons.append("6H price already heavily extended")

    score = max(
        0,
        min(score, 100)
    )

    return score, reasons


# ============================================================
# BINANCE SYMBOL
# ============================================================

def normalize_symbol(symbol):

    if not symbol:
        return ""

    symbol = symbol.upper()

    replacements = [
        "1000",
        "1000000",
    ]

    for prefix in replacements:
        if symbol.startswith(prefix):
            symbol = symbol[len(prefix):]

    return symbol


def get_binance_symbol(symbol):

    symbol = normalize_symbol(symbol)

    if not symbol:
        return None

    candidates = [
        f"{symbol}USDT",
        f"{symbol}USDC",
    ]

    for candidate in candidates:

        data = get_json(
            f"{BINANCE_BASE}/api/v3/exchangeInfo"
        )

        if not isinstance(data, dict):
            return None

        symbols = data.get("symbols") or []

        for item in symbols:

            if (
                item.get("symbol") == candidate
                and item.get("status") == "TRADING"
            ):
                return candidate

        # No match
        return None

    return None


# ============================================================
# BINANCE KLINES
# ============================================================

def get_klines(symbol, interval, limit=200):

    if not symbol:
        return []

    data = get_json(
        f"{BINANCE_BASE}/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
    )

    if not isinstance(data, list):
        return []

    candles = []

    for row in data:

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

    return candles


# ============================================================
# MA200
# ============================================================

def calculate_ma200(candles):

    if len(candles) < 200:
        return None

    closes = [
        candle["close"]
        for candle in candles[-200:]
    ]

    if not closes:
        return None

    return sum(closes) / len(closes)


# ============================================================
# LOCAL LOWS / HIGHS
# ============================================================

def find_local_lows(candles):

    lows = []

    if len(candles) < 5:
        return lows

    for i in range(2, len(candles) - 2):

        current = candles[i]["low"]

        left_1 = candles[i - 1]["low"]
        left_2 = candles[i - 2]["low"]

        right_1 = candles[i + 1]["low"]
        right_2 = candles[i + 2]["low"]

        if (
            current <= left_1
            and current <= left_2
            and current <= right_1
            and current <= right_2
        ):
            lows.append(i)

    return lows


def find_local_high(candles, start, end):

    if end <= start:
        return None

    highest_index = start

    for i in range(start, min(end + 1, len(candles))):

        if (
            candles[i]["high"]
            > candles[highest_index]["high"]
        ):
            highest_index = i

    return highest_index


# ============================================================
# DOUBLE BOTTOM DETECTION
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
        "reason": "",
    }

    if len(candles) < 30:
        return result

    lows = find_local_lows(candles)

    if len(lows) < 2:
        return result

    # بررسی چند جفت آخر
    recent_lows = lows[-8:]

    best = None

    for first_pos in range(len(recent_lows) - 1):

        i = recent_lows[first_pos]

        for second_pos in range(
            first_pos + 1,
            len(recent_lows)
        ):

            j = recent_lows[second_pos]

            # فاصله حداقل 5 کندل
            if j - i < 5:
                continue

            # فاصله بیش از حد زیاد نباشد
            if j - i > 80:
                continue

            low1 = candles[i]["low"]
            low2 = candles[j]["low"]

            if low1 <= 0 or low2 <= 0:
                continue

            difference = abs(
                low1 - low2
            ) / max(
                low1,
                low2
            ) * 100

            # کف‌ها باید نزدیک باشند
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

            # عمق مناسب
            depth1 = (
                neckline - low1
            ) / neckline * 100

            depth2 = (
                neckline - low2
            ) / neckline * 100

            if depth1 < 2 or depth2 < 2:
                continue

            best = {
                "i": i,
                "j": j,
                "low1": low1,
                "low2": low2,
                "neckline": neckline,
                "difference": difference,
            }

    if best is None:
        return result

    current = candles[-1]
    previous = candles[-2]

    current_close = current["close"]

    neckline = best["neckline"]

    breakout_pct = (
        (current_close - neckline)
        / neckline
        * 100
    )

    previous_close = previous["close"]

    # حجم متوسط 20 کندل
    volumes = [
        c["volume"]
        for c in candles[-21:-1]
    ]

    average_volume = (
        sum(volumes) / len(volumes)
        if volumes
        else 0
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

    # ========================================================
    # CONFIRMED BREAKOUT
    # ========================================================

    if (
        current_close > neckline
        and previous_close <= neckline
        and volume_confirmed
    ):

        result["confirmed"] = True
        result["status"] = "BUY NOW"
        result["reason"] = (
            "Double Bottom neckline breakout "
            "with volume confirmation"
        )

        return result

    # ========================================================
    # PRE-BREAKOUT
    # ========================================================

    distance_to_neckline = (
        (neckline - current_close)
        / neckline
        * 100
    )

    if (
        0 <= distance_to_neckline <= 5
        and current_close < neckline
    ):

        result["status"] = "EARLY RADAR"
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

    symbol = data["symbol"]

    binance_symbol = get_binance_symbol(
        symbol
    )

    if not binance_symbol:
        return data

    data["binance_symbol"] = binance_symbol

    # 5M
    candles_5m = get_klines(
        binance_symbol,
        "5m",
        220
    )

    # 1H
    candles_1h = get_klines(
        binance_symbol,
        "1h",
        220
    )

    # 4H
    candles_4h = get_klines(
        binance_symbol,
        "4h",
        220
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

    data["double_bottom_5m"] = db_5m
    data["double_bottom_1h"] = db_1h
    data["double_bottom_4h"] = db_4h

    # MA200
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

    # ========================================================
    # MA200 STATUS
    # ========================================================

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

    # ========================================================
    # DOUBLE BOTTOM PRIORITY
    # ========================================================

    confirmed = (
        db_5m["confirmed"]
        or db_1h["confirmed"]
        or db_4h["confirmed"]
    )

    early = (
        db_5m["detected"]
        or db_1h["detected"]
        or db_4h["detected"]
    )

    data["double_bottom_confirmed"] = confirmed
    data["double_bottom_detected"] = early

    # ========================================================
    # FINAL STATUS
    # ========================================================

    if confirmed:

        # BUY NOW requires additional confirmation
        if (
            data["buy_sell_5m"] >= 1.3
            and data["liquidity"] >= MIN_LIQUIDITY
            and ma_score >= 1
        ):

            data["status"] = "BUY NOW"

        else:

            data["status"] = "CONFIRMED DB"

    elif early:

        data["status"] = "EARLY RADAR"

    else:

        data["status"] = "EARLY RADAR"

    return data


# ============================================================
# FINAL SCORE
# ============================================================

def apply_technical_score(data):

    score = data.get("score", 0)
    reasons = data.get(
        "reasons",
        []
    )

    # Double Bottom
    if data.get(
        "double_bottom_detected"
    ):

        score += 8

        reasons.append(
            "Double Bottom detected"
        )

    # Confirmed Double Bottom
    if data.get(
        "double_bottom_confirmed"
    ):

        score += 12

        reasons.append(
            "Double Bottom neckline breakout"
        )

    # MA200
    ma_score = data.get(
        "ma_score",
        0
    )

    if ma_score >= 3:

        score += 8

        reasons.append(
            "Price above MA200 on 5M/1H/4H"
        )

    elif ma_score == 2:

        score += 5

        reasons.append(
            "Price above MA200 on 2 timeframes"
        )

    elif ma_score == 1:

        score += 2

    score = max(
        0,
        min(score, 100)
    )

    data["score"] = score
    data["reasons"] = reasons

    return data


# ============================================================
# SCAN
# ============================================================

def scan():

    print(
        "Starting Crypto Pump Scanner v3..."
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

                if not pre_pump_filter(
                    data
                ):
                    continue

                score, reasons = (
                    score_candidate(data)
                )

                if score < 40:
                    continue

                data["score"] = score
                data["reasons"] = reasons
                data["status"] = (
                    "EARLY RADAR"
                )

                candidates.append(data)

            except Exception as exc:

                print(
                    "Candidate processing error:"
                )

                print(exc)

    # ========================================================
    # SORT BEFORE OHLCV
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

    candidates = candidates[
        :MAX_CANDIDATES_FOR_OHLCV
    ]

    print(
        "Running OHLCV / Double Bottom analysis..."
    )

    analyzed = []

    for data in candidates:

        try:

            data = analyze_ohlcv(
                data
            )

            data = apply_technical_score(
                data
            )

            analyzed.append(data)

        except Exception as exc:

            print(
                f"OHLCV error "
                f"{data.get('symbol')}:"
            )

            print(exc)

            analyzed.append(data)

    # ========================================================
    # FINAL SORT
    # ========================================================

    status_priority = {
        "BUY NOW": 3,
        "CONFIRMED DB": 2,
        "EARLY RADAR": 1,
    }

    analyzed.sort(
        key=lambda x: (
            status_priority.get(
                x.get("status"),
                0
            ),
            x.get("score", 0),
            x.get(
                "buy_sell_5m",
                0
            ),
            x.get(
                "volume_5m",
                0
            ),
        ),
        reverse=True
    )

    print(
        f"Final candidates: "
        f"{len(analyzed)}"
    )

    # ========================================================
    # PRINT IMPORTANT SIGNALS
    # ========================================================

    for item in analyzed[:20]:

        print(
            f"{item['symbol']} | "
            f"{item.get('status')} | "
            f"Score: {item.get('score')} | "
            f"BS5M: {item.get('buy_sell_5m', 0):.2f} | "
            f"Liquidity: ${item.get('liquidity', 0):,.0f}"
        )

    return analyzed[:20]
