import urllib.parse
import requests
from bs4 import BeautifulSoup
import central_core

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

DIRECTORY_BLACKLIST = {
    "justdial.com", "practo.com", "sulekha.com", "indiamart.com", "lybrate.com",
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "wikipedia.org",
    "yelp.com", "tripadvisor.com", "tripadvisor.in", "google.com", "whatclinic.com",
    "zomato.com", "swiggy.com", "credihealth.com", "apollo247.com", "threebestrated.in",
    "jdmagicbox.com", "magicbricks.com", "99acres.com", "housing.com", "bing.com",
    "duckduckgo.com", "microsoft.com", "cloudflare.com", "w3.org", "schema.org"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def generate_smart_queries(category, city):
    """Uses Gemini to 'think deep' and generate hyper-targeted search queries to avoid directories."""
    prompt = f"""
    I need to find the official standalone websites of '{category}' located in '{city}'.
    Generate 3 highly specific search engine queries that filter out directories (like JustDial, Practo) and return direct business websites.
    Output ONLY the 3 queries, one per line. Do not include bullet points, numbers, or quotes.
    """
    response = central_core.call_gemini(prompt)
    
    queries = []
    if response and "Error" not in response:
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        for line in lines:
            clean_line = line.replace("-", "").replace('"', "").replace("'", "").strip()
            if clean_line and len(clean_line) > 5:
                queries.append(clean_line)
                
    if len(queries) < 2:
        queries = [
            f'{category} in {city} "contact us" -justdial -practo',
            f'top {category} {city} official website',
            f'{category} {city} email address website'
        ]
        
    return queries[:3]

def scrape_yahoo(query):
    """Yahoo Search fallback because it rarely blocks Streamlit Cloud IPs."""
    urls = []
    try:
        url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "yahoo.com" not in href:
                urls.append(href)
    except Exception:
        pass
    return urls

def deep_discover_urls(category, city):
    """The core engine that gathers URLs from multiple unblocked sources."""
    queries = generate_smart_queries(category, city)
    candidates = set()
    
    # Method 1: DuckDuckGo Advanced API (Bypasses HTML blocks)
    if DDGS:
        try:
            ddgs = DDGS()
            for q in queries:
                results = ddgs.text(q, max_results=12)
                for r in results:
                    href = r.get("href", "")
                    if href:
                        candidates.add(href)
        except Exception:
            pass
            
    # Method 2: Yahoo Search Fallback (Streamlit-friendly)
    for q in queries:
        for url in scrape_yahoo(q):
            candidates.add(url)
            
    # Filter and clean the discovered URLs
    final_urls = []
    seen_domains = set()
    
    for url in candidates:
        if not url.startswith("http"): continue
        
        try:
            netloc = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
            if not netloc or "." not in netloc: continue
            if any(b in netloc for b in DIRECTORY_BLACKLIST): continue
            
            if netloc not in seen_domains:
                seen_domains.add(netloc)
                final_urls.append(url)
        except Exception:
            continue
            
    return final_urls
