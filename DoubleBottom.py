def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def detect_double_bottom(candles):
    """
    Detect a basic double-bottom structure.

    Candle format:
    [timestamp, open, high, low, close, volume]

    Returns:
        dict or None
    """

    if not candles or len(candles) < 20:
        return None

    # قدیمی -> جدید
    data = list(reversed(candles))

    lows = []

    for i in range(2, len(data) - 2):

        current_low = safe_float(data[i][3])

        if current_low is None:
            continue

        left_1 = safe_float(data[i - 1][3])
        left_2 = safe_float(data[i - 2][3])
        right_1 = safe_float(data[i + 1][3])
        right_2 = safe_float(data[i + 2][3])

        if None in (
            left_1,
            left_2,
            right_1,
            right_2,
        ):
            continue

        # Local low
        if (
            current_low <= left_1
            and current_low <= left_2
            and current_low <= right_1
            and current_low <= right_2
        ):
            lows.append({
                "index": i,
                "price": current_low,
            })

    if len(lows) < 2:
        return None

    # بررسی جفت کف‌های نزدیک
    for first in lows:

        for second in lows:

            if second["index"] <= first["index"]:
                continue

            distance = (
                second["index"]
                - first["index"]
            )

            # کف‌ها نباید خیلی نزدیک یا خیلی دور باشند
            if distance < 4 or distance > 40:
                continue

            first_low = first["price"]
            second_low = second["price"]

            # اختلاف دو کف
            difference = (
                abs(second_low - first_low)
                / first_low
            )

            # حداکثر 5٪ اختلاف
            if difference > 0.05:
                continue

            # قله بین دو کف
            middle_high = None

            for j in range(
                first["index"] + 1,
                second["index"]
            ):

                high = safe_float(
                    data[j][2]
                )

                if high is None:
                    continue

                if (
                    middle_high is None
                    or high > middle_high
                ):
                    middle_high = high

            if middle_high is None:
                continue

            # قله باید حداقل 3٪ بالاتر از کف‌ها باشد
            average_low = (
                first_low + second_low
            ) / 2

            rise = (
                middle_high - average_low
            ) / average_low

            if rise < 0.03:
                continue

            # قیمت فعلی
            current_close = safe_float(
                data[-1][4]
            )

            if current_close is None:
                continue

            # Neckline = قله بین دو کف
            neckline = middle_high

            distance_to_neckline = (
                neckline - current_close
            ) / neckline

            # اگر خیلی پایین‌تر از neckline باشد
            if distance_to_neckline > 0.15:
                continue

            return {
                "detected": True,
                "first_bottom": first_low,
                "second_bottom": second_low,
                "middle_high": middle_high,
                "neckline": neckline,
                "current_price": current_close,
                "bottom_difference_pct":
                    difference * 100,
                "distance_to_neckline_pct":
                    distance_to_neckline * 100,
            }

    return None
