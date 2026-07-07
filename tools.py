from langchain.tools import tool
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient
import os
from dotenv import load_dotenv
from rich import print
load_dotenv()

@tool
def web_search(query: str) -> str:
    """Search the web for recent and reliable information on a topic. Returns Titles, URLs and snippets of the top results."""
    try:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            return "Search failed: TAVILY_API_KEY not set on the server."
        client = TavilyClient(api_key=key)
        results = client.search(query=query, max_results=5)
        output = []
        for r in results["results"]:
            output.append(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['content'][:300]}\n")
        return "\n-----\n".join(output)
    except Exception as e:
        return f"Search failed: {str(e)}"

# print(web_search.invoke("What is the latest news on AI?"))

@tool
def scrape_url(url: str) -> str:
    """Scrape and return clean text content from a given url for deeper reading."""
    try:
       resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
       soup = BeautifulSoup(resp.text, 'html.parser')
       for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()
       return soup.get_text(separator="\n", strip=True)[:3000]  # Return first 3000 chars for brevity
    except Exception as e:
        return f"Error scraping the web page: {str(e)}"
    