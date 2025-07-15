import requests

# API endpoint for klines
API_KLINES = "https://api.mexc.com/api/v3/klines"
session = requests.Session()

def get_klines(symbol: str, interval: str, limit: int):
    """Trả về danh sách nến [open, high, low, close, volume, ...]"""
    url = f"{API_KLINES}?symbol={symbol}USDT&interval={interval}&limit={limit}"
    resp = session.get(url, timeout=5)
    return resp.json() if resp.ok else []

def is_type_a(symbol: str) -> bool:
    """Coin mới lên sàn <1h: 3 nến 5m tăng >5% OR 5 nến 1m tăng >3%"""
    k5 = get_klines(symbol, '5m', 3)
    cond5 = len(k5) == 3 and all((float(c[4]) - float(c[1])) / float(c[1]) * 100 > 5 for c in k5)
    k1 = get_klines(symbol, '1m', 5)
    cond1 = len(k1) == 5 and all((float(c[4]) - float(c[1])) / float(c[1]) * 100 > 3 for c in k1)
    return cond5 or cond1

def is_type_b(symbol: str) -> bool:
    """Coin đã lên sàn >1h: nhiều pattern OR"""
    k30 = get_klines(symbol, '30m', 3)
    cond30 = len(k30) == 3 and all((float(c[4]) - float(c[1])) / float(c[1]) * 100 > 5 for c in k30)
    k15 = get_klines(symbol, '15m', 3)
    cond15 = len(k15) == 3 and sum((float(c[4]) - float(c[1])) / float(c[1]) * 100 for c in k15) >= 15
    k5 = get_klines(symbol, '5m', 7)
    cond5 = len(k5) == 7 and all(float(c[4]) > float(c[1]) for c in k5)
    k1_9 = get_klines(symbol, '1m', 9)
    cond9 = len(k1_9) == 9 and sum((float(c[4]) - float(c[1])) / float(c[1]) * 100 for c in k1_9) > 20
    k1_3 = get_klines(symbol, '1m', 3)
    cond31 = len(k1_3) == 3 and all((float(c[4]) - float(c[1])) / float(c[1]) * 100 > 10 for c in k1_3)
    return cond30 or cond15 or cond5 or cond9 or cond31

def passes_conditions(symbol: str) -> bool:
    """Trả True nếu symbol thỏa Type A hoặc Type B"""
    try:
        return is_type_a(symbol) or is_type_b(symbol)
    except Exception:
        return False
