import httpx
from config import Settings
from langchain_core.tools import tool


@tool
def google_search(query: str) -> dict:
    """
    Search the web using Google. Use this when the user asks about general knowledge questions.
    Args:
        query: The search query
    Returns:
        Search results as a dictionary
    """
    url = "https://serpapi.com/search"

    params = {"q": query, "api_key": Settings.SERPAPI_APIKEY}

    with httpx.Client() as client:
        response = client.get(url, params=params)
        data = response.json()

    return data
