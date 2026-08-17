import requests


BASE_URL = "https://api.geckoterminal.com/api/v2"


def get_ohlcv(network, pool_address, timeframe, aggregate):
    url = (
        f"{BASE_URL}/networks/{network}"
        f"/pools/{pool_address}"
        f"/ohlcv/{timeframe}"
    )

    params = {
        "aggregate": aggregate,
        "limit": 100,
        "currency": "usd",
    }

    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "Crypto-Pump-Scanner/1.0",
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data


def main():

    # HBULL pool address
    network = "solana"

    pool_address = (
        "edx18gjcdijqslaja2pp5c2vma3btrrx4utxkejufrtq"
    )

    print("Testing GeckoTerminal OHLCV...")
    print()

    # 15-minute candles
    data = get_ohlcv(
        network,
        pool_address,
        "minute",
        15,
    )

    candles = (
        data.get("data", {})
        .get("attributes", {})
        .get("ohlcv_list", [])
    )

    print(
        f"15M candles received: {len(candles)}"
    )

    if not candles:
        print(
            "❌ No OHLCV data returned."
        )
        return

    print()
    print("Latest candles:")
    print("----------------")

    # API may return newest first.
    for candle in candles[:5]:

        timestamp = candle[0]
        open_price = candle[1]
        high = candle[2]
        low = candle[3]
        close = candle[4]
        volume = candle[5]

        print(
            f"Time: {timestamp}"
        )

        print(
            f"O: {open_price} | "
            f"H: {high} | "
            f"L: {low} | "
            f"C: {close} | "
            f"V: {volume}"
        )

        print()

    print(
        "✅ OHLCV test successful."
    )


if __name__ == "__main__":
    main()
