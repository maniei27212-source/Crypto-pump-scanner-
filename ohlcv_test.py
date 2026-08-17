import requests


DEX_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/"
    "solana/edx18gjcdijqslaja2pp5c2vma3btrrx4utxkejufrtq"
)

GECKO_BASE = "https://api.geckoterminal.com/api/v2"


def get_dex_pair():
    response = requests.get(
        DEX_URL,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    pairs = data.get("pairs") or []

    if not pairs:
        raise RuntimeError(
            "DexScreener returned no pair."
        )

    return pairs[0]


def find_gecko_pools(token_address):
    url = (
        f"{GECKO_BASE}/networks/solana/"
        f"tokens/{token_address}/pools"
    )

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Crypto-Pump-Scanner/1.0",
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def get_ohlcv(pool_address):
    url = (
        f"{GECKO_BASE}/networks/solana/"
        f"pools/{pool_address}/ohlcv/minute"
    )

    params = {
        "aggregate": 15,
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

    return response.json()


def main():

    print("1. Getting HBULL pair from DexScreener...")

    pair = get_dex_pair()

    base_token = pair.get("baseToken") or {}

    token_address = base_token.get("address")
    symbol = base_token.get("symbol")

    print(f"Token: {symbol}")
    print(f"Token address: {token_address}")
    print()

    if not token_address:
        raise RuntimeError(
            "Could not find token address."
        )

    print("2. Finding GeckoTerminal pools...")

    pools_data = find_gecko_pools(
        token_address
    )

    pools = (
        pools_data
        .get("data")
        or []
    )

    print(
        f"Pools found: {len(pools)}"
    )

    if not pools:
        print(
            "❌ No GeckoTerminal pools found."
        )
        return

    # انتخاب اولین pool فعلاً فقط برای تست
    pool = pools[0]

    pool_id = pool.get("id")

    print(
        f"Selected pool: {pool_id}"
    )

    if not pool_id:
        raise RuntimeError(
            "Pool ID not found."
        )

    # GeckoTerminal pool ID معمولاً به شکل:
    # solana_POOL_ADDRESS
    if "_" in pool_id:
        pool_address = pool_id.split(
            "_", 1
        )[1]
    else:
        pool_address = pool_id

    print(
        f"Pool address: {pool_address}"
    )
    print()

    print(
        "3. Getting 15M OHLCV..."
    )

    ohlcv_data = get_ohlcv(
        pool_address
    )

    candles = (
        ohlcv_data
        .get("data", {})
        .get("attributes", {})
        .get("ohlcv_list", [])
    )

    print(
        f"15M candles received: "
        f"{len(candles)}"
    )

    if not candles:
        print(
            "❌ No OHLCV data."
        )
        return

    print()
    print("Latest candles:")
    print("----------------")

    for candle in candles[:5]:

        print(
            f"Time: {candle[0]}"
        )

        print(
            f"O: {candle[1]} | "
            f"H: {candle[2]} | "
            f"L: {candle[3]} | "
            f"C: {candle[4]} | "
            f"V: {candle[5]}"
        )

        print()

    print(
        "✅ OHLCV TEST SUCCESSFUL"
    )


if __name__ == "__main__":
    main()
