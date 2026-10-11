import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

COINGECKO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
    "bnb": "binancecoin",
    "avalanche": "avalanche-2", "avax": "avalanche-2",
    "polkadot": "polkadot", "dot": "polkadot",
    "chainlink": "chainlink", "link": "chainlink",
}


async def get_crypto_price(coin: str) -> dict | None:
    """Fetch crypto price from CoinGecko (no API key needed)."""
    coin_id = COINGECKO_IDS.get(coin.lower(), coin.lower())
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd,eur",
        "include_24hr_change": "true",
        "include_market_cap": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if coin_id not in data:
                return None
            d = data[coin_id]
            return {
                "coin": coin_id,
                "name": coin.upper(),
                "price_usd": d.get("usd"),
                "price_eur": d.get("eur"),
                "change_24h": d.get("usd_24h_change"),
                "market_cap_usd": d.get("usd_market_cap"),
            }
    except Exception as e:
        logger.error(f"CoinGecko failed for '{coin}': {e}")
        return None


def _get_stock_sync(ticker: str) -> dict | None:
    """Synchronous yfinance stock fetch."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="1d")
        current = float(hist["Close"].iloc[-1]) if not hist.empty else info.get("currentPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change = ((current - prev_close) / prev_close * 100) if current and prev_close else None
        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName", ticker),
            "price": current,
            "currency": info.get("currency", "USD"),
            "change_pct": change,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
        }
    except Exception as e:
        logger.error(f"yfinance failed for '{ticker}': {e}")
        return None


async def get_stock_price(ticker: str) -> dict | None:
    """Async wrapper for yfinance stock data."""
    return await asyncio.get_event_loop().run_in_executor(None, _get_stock_sync, ticker)


def format_crypto(data: dict) -> str:
    change = data.get("change_24h")
    arrow = "📈" if change and change > 0 else "📉"
    change_str = f"{change:+.2f}%" if change is not None else "N/A"
    mcap = data.get("market_cap_usd")
    mcap_str = f"${mcap/1e9:.1f}B" if mcap else "N/A"
    return (
        f"🪙 *{data['name']}*\n"
        f"💵 ${data['price_usd']:,.2f} | 💶 €{data['price_eur']:,.2f}\n"
        f"{arrow} 24h: {change_str}\n"
        f"📊 Market Cap: {mcap_str}"
    )


def format_stock(data: dict) -> str:
    change = data.get("change_pct")
    arrow = "📈" if change and change > 0 else "📉"
    change_str = f"{change:+.2f}%" if change is not None else "N/A"
    pe = data.get("pe_ratio")
    pe_str = f"{pe:.1f}" if pe else "N/A"
    mcap = data.get("market_cap")
    mcap_str = f"${mcap/1e9:.1f}B" if mcap else "N/A"
    return (
        f"📈 *{data['name']} ({data['ticker']})*\n"
        f"💵 {data['currency']} {data['price']:,.2f}\n"
        f"{arrow} Tagesänderung: {change_str}\n"
        f"📊 Market Cap: {mcap_str} | KGV: {pe_str}"
    )


def format_for_llm(data: dict, kind: str) -> str:
    if kind == "crypto":
        return (f"[Kryptodaten {data['name']}] Preis: ${data['price_usd']:,.2f} / €{data['price_eur']:,.2f}, "
                f"24h-Änderung: {data.get('change_24h', 'N/A'):.2f}%")
    else:
        return (f"[Aktiendaten {data['name']} ({data['ticker']})] Preis: {data['currency']} {data['price']:,.2f}, "
                f"Tagesänderung: {data.get('change_pct', 'N/A'):.2f}%")
