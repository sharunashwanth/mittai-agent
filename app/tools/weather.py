import httpx
from config import Settings
from langchain_core.tools import tool


@tool()
def get_current_weather(city: str) -> dict:
    """
    Get the current weather of a city
    Args:
        city: The city to get the weather of
    Returns:
        The weather of the city in dictionary
    """
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {"q": city, "units": "metric", "appid": Settings.OPENWEATHERMAP_APIKEY}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}

        data = response.json()

    return data


@tool
def get_weather_forecast(city: str) -> dict:
    """
    Get the 5 day 3 hourly weather forecast of a city
    Args:
        city: The city to get the weather forecast of
    Returns:
        The weather forecast of the city in dictionary
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {"q": city, "units": "metric", "appid": Settings.OPENWEATHERMAP_APIKEY}

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}

        data = response.json()

    return data
