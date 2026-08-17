from DoubleBottom import detect_double_bottom


def make_candle(timestamp, open_price, high, low, close, volume):
    return [
        timestamp,
        open_price,
        high,
        low,
        close,
        volume,
    ]


def main():

    candles = [
        make_candle(1, 100, 102, 98, 101, 1000),
        make_candle(2, 101, 103, 99, 102, 1000),
        make_candle(3, 102, 104, 97, 100, 1200),

        # Bottom 1
        make_candle(4, 100, 101, 90, 92, 1500),
        make_candle(5, 92, 95, 89, 94, 1800),

        # Recovery / Neckline
        make_candle(6, 94, 100, 93, 99, 2000),
        make_candle(7, 99, 106, 98, 104, 2500),
        make_candle(8, 104, 108, 103, 107, 2200),

        # Pullback
        make_candle(9, 107, 108, 99, 101, 1800),
        make_candle(10, 101, 103, 96, 98, 1600),

        # Bottom 2
        make_candle(11, 98, 100, 90.5, 93, 1900),
        make_candle(12, 93, 97, 91, 96, 2100),

        # Recovery
        make_candle(13, 96, 101, 95, 100, 2300),
        make_candle(14, 100, 105, 99, 104, 2600),
        make_candle(15, 104, 108, 103, 107, 2800),

        make_candle(16, 107, 109, 106, 108, 3000),
        make_candle(17, 108, 110, 107, 109, 3200),
        make_candle(18, 109, 111, 108, 110, 3500),
        make_candle(19, 110, 112, 109, 111, 3700),
        make_candle(20, 111, 113, 110, 112, 4000),
    ]

    result = detect_double_bottom(candles)

    print()
    print("DOUBLE BOTTOM TEST")
    print("===================")
    print()

    if result is None:
        print("❌ Double Bottom NOT detected.")
        return

    print("✅ Double Bottom detected!")
    print()

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
