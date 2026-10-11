import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

WMO_CODES = {
    0: "☀️ Klar", 1: "🌤️ Überwiegend klar", 2: "⛅ Teilweise bewölkt", 3: "☁️ Bewölkt",
    45: "🌫️ Nebel", 48: "🌫️ Eisnebel",
    51: "🌦️ Leichter Niesel", 53: "🌦️ Mäßiger Niesel", 55: "🌧️ Starker Niesel",
    61: "🌧️ Leichter Regen", 63: "🌧️ Mäßiger Regen", 65: "🌧️ Starker Regen",
    71: "🌨️ Leichter Schnee", 73: "🌨️ Mäßiger Schnee", 75: "❄️ Starker Schnee",
    80: "🌦️ Leichte Schauer", 81: "🌧️ Mäßige Schauer", 82: "⛈️ Starke Schauer",
    95: "⛈️ Gewitter", 96: "⛈️ Gewitter mit Hagel", 99: "⛈️ Starkes Gewitter mit Hagel",
}


async def geocode(city: str) -> dict | None:
    """Resolve city name to lat/lon via Open-Meteo geocoding."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"name": city, "count": 1, "language": "de"})
            data = resp.json()
            results = data.get("results")
            if results:
                r = results[0]
                return {
                    "name": r.get("name"),
                    "country": r.get("country"),
                    "lat": r["latitude"],
                    "lon": r["longitude"],
                    "timezone": r.get("timezone", "auto"),
                }
    except Exception as e:
        logger.error(f"Geocoding failed for '{city}': {e}")
    return None


async def get_weather(city: str) -> dict | None:
    """Fetch current weather and 3-day forecast from Open-Meteo."""
    location = await geocode(city)
    if not location:
        return None

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "forecast_days": 3,
        "timezone": location["timezone"],
        "wind_speed_unit": "kmh",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        current = data["current"]
        daily = data["daily"]

        return {
            "city": f"{location['name']}, {location['country']}",
            "current": {
                "temp": current["temperature_2m"],
                "feels_like": current["apparent_temperature"],
                "humidity": current["relative_humidity_2m"],
                "precipitation": current["precipitation"],
                "wind": current["wind_speed_10m"],
                "condition": WMO_CODES.get(current["weather_code"], "❓ Unbekannt"),
            },
            "forecast": [
                {
                    "date": daily["time"][i],
                    "max": daily["temperature_2m_max"][i],
                    "min": daily["temperature_2m_min"][i],
                    "rain": daily["precipitation_sum"][i],
                    "condition": WMO_CODES.get(daily["weather_code"][i], "❓"),
                }
                for i in range(3)
            ],
        }
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return None


def format_weather(data: dict) -> str:
    c = data["current"]
    lines = [
        f"🌍 *{data['city']}*\n",
        f"{c['condition']}",
        f"🌡️ {c['temp']}°C (gefühlt {c['feels_like']}°C)",
        f"💧 Luftfeuchtigkeit: {c['humidity']}%",
        f"🌧️ Niederschlag: {c['precipitation']} mm",
        f"💨 Wind: {c['wind']} km/h\n",
        f"*3-Tage-Vorschau:*",
    ]
    for day in data["forecast"]:
        lines.append(f"📅 {day['date']}: {day['condition']} {day['min']}–{day['max']}°C, 🌧️ {day['rain']}mm")
    return "\n".join(lines)


def format_weather_for_llm(data: dict) -> str:
    c = data["current"]
    lines = [f"[Wetterdaten {data['city']}]",
             f"Aktuell: {c['condition']}, {c['temp']}°C (gefühlt {c['feels_like']}°C), Luftfeuchtigkeit {c['humidity']}%, Wind {c['wind']} km/h, Niederschlag {c['precipitation']}mm"]
    for day in data["forecast"]:
        lines.append(f"{day['date']}: {day['condition']}, {day['min']}-{day['max']}°C, Regen {day['rain']}mm")
    return "\n".join(lines)
