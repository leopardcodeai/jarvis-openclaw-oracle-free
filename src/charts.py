import asyncio
import io
import logging
from datetime import datetime, timedelta

import httpx
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

logger = logging.getLogger(__name__)

WEATHER_PERIODS = {"24h": 1, "48h": 2, "7d": 7, "14d": 14}


async def _geocode(city: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "de"}
            )
            results = r.json().get("results")
            if results:
                return {"lat": results[0]["latitude"], "lon": results[0]["longitude"],
                        "name": results[0]["name"], "country": results[0].get("country", ""),
                        "timezone": results[0].get("timezone", "auto")}
    except Exception as e:
        logger.error(f"Geocode failed: {e}")
    return None


async def weather_chart(city: str, period: str = "24h") -> tuple[io.BytesIO | None, dict]:
    """Generate temperature + precipitation chart for a city via Open-Meteo."""
    loc = await _geocode(city)
    if not loc:
        return None, {}

    past_days = WEATHER_PERIODS.get(period.lower(), 1)
    forecast_days = 1 if past_days <= 2 else 0

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": loc["lat"], "longitude": loc["lon"],
                    "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
                    "past_days": past_days, "forecast_days": forecast_days,
                    "timezone": loc["timezone"], "wind_speed_unit": "kmh",
                }
            )
            data = resp.json()
    except Exception as e:
        logger.error(f"Weather chart fetch failed: {e}")
        return None, {}

    hourly = data.get("hourly", {})
    times_raw = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    feels = hourly.get("apparent_temperature", [])
    precip = hourly.get("precipitation", [])
    humidity = hourly.get("relative_humidity_2m", [])

    if not times_raw or not temps:
        return None, {}

    # Parse timestamps and limit to requested window
    now = datetime.now()
    cutoff = now - timedelta(hours=past_days * 24)
    dates, t_vals, f_vals, p_vals, h_vals = [], [], [], [], []
    for i, ts in enumerate(times_raw):
        try:
            dt = datetime.fromisoformat(ts)
        except:
            continue
        if dt < cutoff or dt > now + timedelta(hours=forecast_days * 24):
            continue
        dates.append(dt)
        t_vals.append(temps[i] if i < len(temps) else None)
        f_vals.append(feels[i] if i < len(feels) else None)
        p_vals.append(precip[i] if i < len(precip) else 0)
        h_vals.append(humidity[i] if i < len(humidity) else None)

    if len(dates) < 2:
        return None, {}

    # ── Render ──
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 7),
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
        facecolor="#0d1117"
    )

    ax1.set_facecolor("#0d1117")
    # Temperature
    ax1.plot(dates, t_vals, color="#00d4ff", linewidth=2.2, label="Temperatur °C", zorder=4)
    ax1.fill_between(dates, t_vals, alpha=0.15, color="#00d4ff", zorder=2)
    # Feels like
    ax1.plot(dates, f_vals, color="#ffaa00", linewidth=1.2, linestyle="--",
             alpha=0.8, label="Gefühlt °C", zorder=3)

    # Zero line
    ax1.axhline(0, color="#ff4444", linewidth=0.8, linestyle=":", alpha=0.5)

    # Min/Max annotations
    valid_t = [(d, v) for d, v in zip(dates, t_vals) if v is not None]
    if valid_t:
        max_dt, max_t = max(valid_t, key=lambda x: x[1])
        min_dt, min_t = min(valid_t, key=lambda x: x[1])
        ax1.annotate(f"▲ {max_t:.1f}°C", xy=(max_dt, max_t), xytext=(0, 10),
                     textcoords="offset points", color="#ffdd57", fontsize=9, ha="center")
        ax1.annotate(f"▼ {min_t:.1f}°C", xy=(min_dt, min_t), xytext=(0, -16),
                     textcoords="offset points", color="#ff6b6b", fontsize=9, ha="center")

    current_t = next((v for v in reversed(t_vals) if v is not None), None)
    title_str = f"🌡️ {loc['name']}, {loc['country']}  –  {period.upper()}"
    if current_t is not None:
        title_str += f"   |   Aktuell: {current_t:.1f}°C"

    ax1.set_title(title_str, fontsize=13, color="white", pad=12, fontweight="bold")
    ax1.set_ylabel("°C", color="#8b949e", fontsize=11)
    ax1.tick_params(colors="#8b949e", labelbottom=False)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}°"))
    ax1.legend(fontsize=9, loc="upper left", facecolor="#161b22", edgecolor="#30363d")
    ax1.grid(color="#21262d", linewidth=0.5)
    ax1.spines[:].set_edgecolor("#21262d")

    # ── Precipitation bars ──
    ax2.set_facecolor("#0d1117")
    ax2.bar(dates, p_vals, color="#4488ff88", width=0.03 if period == "24h" else 0.1,
            label="Niederschlag mm")
    ax2.set_ylabel("mm", color="#8b949e", fontsize=8)
    ax2.tick_params(colors="#8b949e", labelsize=8)
    ax2.grid(color="#21262d", linewidth=0.3)
    ax2.spines[:].set_edgecolor("#21262d")

    # X-axis
    fmt = "%H:%M" if past_days <= 2 else "%d.%m %H:%M"
    ax2.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", color="#8b949e", fontsize=8)

    fig.patch.set_facecolor("#0d1117")
    plt.tight_layout(pad=1.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#0d1117", edgecolor="none")
    plt.close(fig)
    buf.seek(0)

    meta = {
        "city": f"{loc['name']}, {loc['country']}",
        "period": period,
        "current_temp": current_t,
        "max_temp": max_t if valid_t else None,
        "min_temp": min_t if valid_t else None,
        "total_precip": round(sum(p for p in p_vals if p), 2),
    }
    return buf, meta


def format_weather_chart_summary(meta: dict) -> str:
    city = meta.get("city", "")
    curr = f"{meta['current_temp']:.1f}°C" if meta.get("current_temp") is not None else "?"
    hi = f"{meta['max_temp']:.1f}°C" if meta.get("max_temp") is not None else "?"
    lo = f"{meta['min_temp']:.1f}°C" if meta.get("min_temp") is not None else "?"
    rain = meta.get("total_precip", 0)
    return (
        f"🌡️ *{city}* – {meta['period'].upper()}\n"
        f"🌡️ Aktuell: {curr}  |  ▲ {hi}  |  ▼ {lo}\n"
        f"🌧️ Niederschlag gesamt: {rain} mm"
    )

PERIOD_DAYS = {
    "1w": 7, "7d": 7,
    "1m": 30, "30d": 30,
    "3m": 90, "90d": 90,
    "6m": 180,
    "1y": 365, "ytd": 365,
    "2y": 730,
    "5y": 1825,
}

COINGECKO_IDS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "xrp": "ripple", "ripple": "ripple",
    "bnb": "binancecoin",
    "avax": "avalanche-2", "avalanche": "avalanche-2",
    "dot": "polkadot", "polkadot": "polkadot",
    "link": "chainlink", "chainlink": "chainlink",
}


# ── Data fetching ─────────────────────────────────────────────────────────────

async def _fetch_crypto_history(coin_id: str, days: int) -> list[dict] | None:
    """Fetch OHLC + price history from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily" if days > 30 else "hourly"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        prices = data.get("prices", [])
        volumes = {v[0]: v[1] for v in data.get("total_volumes", [])}
        return [
            {
                "ts": p[0],
                "date": datetime.fromtimestamp(p[0] / 1000),
                "price": p[1],
                "volume": volumes.get(p[0], 0),
            }
            for p in prices
        ]
    except Exception as e:
        logger.error(f"CoinGecko history failed: {e}")
        return None


def _fetch_stock_history_sync(ticker: str, period: str) -> list[dict] | None:
    try:
        import yfinance as yf
        yf_period = {"7d": "7d", "30d": "1mo", "90d": "3mo", "180d": "6mo",
                     "1y": "1y", "2y": "2y", "5y": "5y"}.get(period, "1y")
        hist = yf.Ticker(ticker).history(period=yf_period)
        if hist.empty:
            return None
        return [
            {
                "date": idx.to_pydatetime(),
                "price": row["Close"],
                "volume": row["Volume"],
                "high": row["High"],
                "low": row["Low"],
            }
            for idx, row in hist.iterrows()
        ]
    except Exception as e:
        logger.error(f"yfinance history failed: {e}")
        return None


async def fetch_stock_history(ticker: str, period: str = "1y") -> list[dict] | None:
    return await asyncio.get_event_loop().run_in_executor(
        None, _fetch_stock_history_sync, ticker, period
    )


# ── Chart rendering ───────────────────────────────────────────────────────────

def _moving_average(values: list[float], window: int) -> list[float | None]:
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(sum(values[i - window + 1:i + 1]) / window)
    return result


def _render_chart(
    dates: list[datetime],
    prices: list[float],
    volumes: list[float],
    title: str,
    currency: str = "USD",
    color: str = "#00d4ff",
) -> io.BytesIO:
    """Render a price + volume chart and return as PNG BytesIO."""
    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 7),
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
        facecolor="#0d1117"
    )

    # ── Price line ──
    ax1.set_facecolor("#0d1117")
    ax1.plot(dates, prices, color=color, linewidth=1.8, zorder=3)
    ax1.fill_between(dates, prices, alpha=0.15, color=color, zorder=2)

    # Moving averages
    if len(prices) >= 20:
        ma20 = _moving_average(prices, 20)
        ma_dates = [d for d, v in zip(dates, ma20) if v is not None]
        ma_vals = [v for v in ma20 if v is not None]
        ax1.plot(ma_dates, ma_vals, color="#ffaa00", linewidth=1.0,
                 linestyle="--", alpha=0.7, label="MA20", zorder=4)

    if len(prices) >= 50:
        ma50 = _moving_average(prices, 50)
        ma_dates50 = [d for d, v in zip(dates, ma50) if v is not None]
        ma_vals50 = [v for v in ma50 if v is not None]
        ax1.plot(ma_dates50, ma_vals50, color="#ff6b6b", linewidth=1.0,
                 linestyle="--", alpha=0.7, label="MA50", zorder=4)
        ax1.legend(fontsize=9, loc="upper left", facecolor="#161b22", edgecolor="#30363d")

    # Price annotations
    max_price = max(prices)
    min_price = min(prices)
    max_idx = prices.index(max_price)
    min_idx = prices.index(min_price)
    current = prices[-1]
    change_pct = (current - prices[0]) / prices[0] * 100
    arrow = "▲" if change_pct >= 0 else "▼"
    change_color = "#00ff88" if change_pct >= 0 else "#ff4444"

    ax1.annotate(f"▲ ${max_price:,.0f}", xy=(dates[max_idx], max_price),
                 xytext=(0, 12), textcoords="offset points",
                 color="#ffdd57", fontsize=8, ha="center")
    ax1.annotate(f"▼ ${min_price:,.0f}", xy=(dates[min_idx], min_price),
                 xytext=(0, -16), textcoords="offset points",
                 color="#ff6b6b", fontsize=8, ha="center")

    ax1.set_title(
        f"{title}   |   ${current:,.2f}   {arrow} {change_pct:+.1f}%",
        fontsize=14, color="white", pad=12, fontweight="bold"
    )
    ax1.set_ylabel(currency, color="#8b949e", fontsize=10)
    ax1.tick_params(colors="#8b949e", labelbottom=False)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x:,.0f}" if x >= 1 else f"${x:.4f}"
    ))
    ax1.grid(color="#21262d", linewidth=0.5, zorder=1)
    ax1.spines[:].set_edgecolor("#21262d")

    # ── Volume bars ──
    ax2.set_facecolor("#0d1117")
    bar_colors = [
        "#00ff8844" if prices[i] >= prices[i - 1] else "#ff444444"
        for i in range(len(prices))
    ]
    ax2.bar(dates, volumes, color=bar_colors, width=0.8 if len(dates) < 100 else 0.4)
    ax2.set_ylabel("Vol", color="#8b949e", fontsize=8)
    ax2.tick_params(colors="#8b949e", labelsize=8)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"{x/1e9:.1f}B" if x >= 1e9 else f"{x/1e6:.0f}M" if x >= 1e6 else f"{x/1e3:.0f}K"
    ))
    ax2.grid(color="#21262d", linewidth=0.3)
    ax2.spines[:].set_edgecolor("#21262d")

    # X-axis date format
    ax2.xaxis.set_major_formatter(mdates.DateFormatter(
        "%b %Y" if len(dates) > 60 else "%d %b"
    ))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", color="#8b949e")

    fig.patch.set_facecolor("#0d1117")
    plt.tight_layout(pad=1.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#0d1117", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Public API ────────────────────────────────────────────────────────────────

async def crypto_chart(coin: str, period: str = "1y") -> tuple[io.BytesIO | None, dict]:
    """Generate crypto price chart. Returns (image_buffer, metadata)."""
    coin_id = COINGECKO_IDS.get(coin.lower(), coin.lower())
    days = PERIOD_DAYS.get(period.lower(), 365)

    data = await _fetch_crypto_history(coin_id, days)
    if not data or len(data) < 2:
        return None, {}

    dates = [d["date"] for d in data]
    prices = [d["price"] for d in data]
    volumes = [d["volume"] for d in data]

    title = f"{coin.upper()} / USD  ({period})"
    color_map = {"bitcoin": "#f7931a", "ethereum": "#627eea", "solana": "#9945ff"}
    color = color_map.get(coin_id, "#00d4ff")

    buf = await asyncio.get_event_loop().run_in_executor(
        None, _render_chart, dates, prices, volumes, title, "USD", color
    )

    change = (prices[-1] - prices[0]) / prices[0] * 100
    return buf, {
        "coin": coin.upper(), "current": prices[-1], "start": prices[0],
        "high": max(prices), "low": min(prices), "change_pct": change, "period": period
    }


async def stock_chart(ticker: str, period: str = "1y") -> tuple[io.BytesIO | None, dict]:
    """Generate stock price chart. Returns (image_buffer, metadata)."""
    data = await fetch_stock_history(ticker.upper(), period)
    if not data or len(data) < 2:
        return None, {}

    dates = [d["date"] for d in data]
    prices = [d["price"] for d in data]
    volumes = [d["volume"] for d in data]

    title = f"{ticker.upper()}  ({period})"
    buf = await asyncio.get_event_loop().run_in_executor(
        None, _render_chart, dates, prices, volumes, title, "USD", "#00d4ff"
    )

    change = (prices[-1] - prices[0]) / prices[0] * 100
    return buf, {
        "ticker": ticker.upper(), "current": prices[-1], "start": prices[0],
        "high": max(prices), "low": min(prices), "change_pct": change, "period": period
    }


def format_chart_summary(meta: dict, kind: str = "crypto") -> str:
    """Short text summary to accompany the chart."""
    arrow = "📈" if meta["change_pct"] >= 0 else "📉"
    name = meta.get("coin") or meta.get("ticker", "")
    change_color = "+" if meta["change_pct"] >= 0 else ""
    return (
        f"{arrow} *{name}* – {meta['period'].upper()}\n"
        f"💵 Aktuell: ${meta['current']:,.2f}\n"
        f"📊 Hoch: ${meta['high']:,.2f} | Tief: ${meta['low']:,.2f}\n"
        f"📅 Veränderung: {change_color}{meta['change_pct']:.1f}%"
    )
