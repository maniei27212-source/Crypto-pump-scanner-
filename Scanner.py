def scan():
    profiles = get_latest_profiles()

    print(f"[DEBUG] Profiles received: {len(profiles)}")

    if not profiles:
        print("[DEBUG] No profiles received from DexScreener.")
        return []

    results = []

    profiles_checked = 0
    pairs_found = 0
    ignored_count = 0
    discovery_count = 0
    early_radar_count = 0

    # محدودیت اولیه برای جلوگیری از فشار روی API
    for profile in profiles[:30]:

        profiles_checked += 1

        chain_id = profile.get("chainId")
        token_address = profile.get("tokenAddress")

        if not chain_id or not token_address:
            print("[DEBUG] Profile missing chain/token address.")
            continue

        pairs = get_token_pairs(chain_id, token_address)

        if not pairs:
            continue

        pairs_found += len(pairs)

        # انتخاب Pair با بیشترین Liquidity
        pairs.sort(
            key=lambda p: safe_number(
                (p.get("liquidity") or {}).get("usd")
            ),
            reverse=True
        )

        pair = pairs[0]

        analysis = score_pair(pair)

        if analysis["status"] == "IGNORE":
            ignored_count += 1
            continue

        if analysis["status"] == "DISCOVERY":
            discovery_count += 1

        elif analysis["status"] == "EARLY RADAR":
            early_radar_count += 1

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

    print("")
    print("========== SCANNER DEBUG ==========")
    print(f"Profiles received : {len(profiles)}")
    print(f"Profiles checked  : {profiles_checked}")
    print(f"Pairs found       : {pairs_found}")
    print(f"Discovery         : {discovery_count}")
    print(f"Early Radar       : {early_radar_count}")
    print(f"Ignored           : {ignored_count}")
    print(f"Final candidates  : {len(results)}")
    print("===================================")
    print("")

    # نمایش 10 مورد برتر برای بررسی
    for item in results[:10]:
        print(
            f"[DEBUG] "
            f"{item['status']} | "
            f"{item['symbol']} | "
            f"Score={item['score']} | "
            f"Liquidity=${item['liquidity']:,.0f} | "
            f"Vol1H=${item['volume_1h']:,.0f} | "
            f"Buy/Sell5M={item['buy_sell_5m']:.2f}"
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
