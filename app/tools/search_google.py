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

    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, params=params)

        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}

        data = response.json()

    organic = data.get("organic_results", [])[:5]
    return {
        "results": [
            {
                "title": r.get("title"),
                "snippet": r.get("snippet"),
                "link": r.get("link"),
            }
            for r in organic
        ]
    }
