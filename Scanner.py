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
