import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import central_core

DIRECTORY_BLACKLIST = {
    "justdial.com", "practo.com", "sulekha.com", "indiamart.com", "lybrate.com",
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "wikipedia.org",
    "yelp.com", "tripadvisor.com", "tripadvisor.in", "google.com", "whatclinic.com",
    "zomato.com", "swiggy.com", "credihealth.com", "apollo247.com", "threebestrated.in"
}

CHAT_WIDGET_SCRIPTS = [
    "zendesk", "intercom", "tawk.to", "crisp.chat", "tidio", "hubspot", "livechat", "freshchat"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

DEMO_URL = "https://zenith-support-agent-u6xxkp7actgzbcuubdbaiz.streamlit.app"
SENDER_EMAIL = "zenith.ai.gowtham@gmail.com"

def get_business_urls(category, city, max_results=8):
    """Finds standalone local business websites via search."""
    candidates = []
    seen_domains = set()
    queries = [
        f'{category} in {city} "contact" -justdial -practo -sulekha',
        f'best {category} {city} official website'
    ]
    for q in queries:
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", class_="result__a", href=True):
                raw_href = a["href"]
                target = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query).get("uddg", [raw_href])[0]
                if not target.startswith("http"):
                    continue
                netloc = urllib.parse.urlparse(target).netloc.lower().replace("www.", "")
                if not netloc or any(b in netloc for b in DIRECTORY_BLACKLIST):
                    continue
                if netloc not in seen_domains:
                    seen_domains.add(netloc)
                    candidates.append(f"https://{netloc}")
                if len(candidates) >= max_results:
                    return candidates
        except Exception:
            continue
    return candidates

def extract_emails_from_site(base_url, soup, html_text):
    """Extracts public emails from homepage and contact page."""
    ignored_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
    raw_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", html_text))

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:"):
            raw_emails.add(href.replace("mailto:", "").split("?")[0].strip())

    valid = [
        e.lower() for e in raw_emails
        if not e.lower().endswith(ignored_ext) and "example.com" not in e.lower() and "sentry" not in e.lower()
    ]
    if valid:
        return list(dict.fromkeys(valid))[:2]

    # Check /contact page if homepage had no email
    for a in soup.find_all("a", href=True):
        if "contact" in a["href"].lower():
            try:
                contact_url = urllib.parse.urljoin(base_url, a["href"])
                c_resp = requests.get(contact_url, headers=HEADERS, timeout=6)
                c_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", c_resp.text))
                valid_c = [
                    e.lower() for e in c_emails
                    if not e.lower().endswith(ignored_ext) and "example.com" not in e.lower()
                ]
                if valid_c:
                    return list(dict.fromkeys(valid_c))[:2]
            except Exception:
                pass
            break
    return []

def hunt_support_leads(category, city, max_scan=3):
    """Finds businesses without a chat widget, extracts emails, and writes a pitch."""
    urls = get_business_urls(category, city, max_results=max_scan * 3)
    hot_leads = []

    for url in urls:
        if len(hot_leads) >= max_scan:
            break
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            html_lower = resp.text.lower()
            soup = BeautifulSoup(resp.text, "html.parser")

            if any(widget in html_lower for widget in CHAT_WIDGET_SCRIPTS):
                continue

            valid_emails = extract_emails_from_site(url, soup, resp.text)
            if not valid_emails:
                continue

            title_tag = soup.find("title")
            business_name = title_tag.get_text(strip=True).split("|")[0].split("-")[0].strip()[:50] if title_tag else url

            prompt = f"""
            Write a polite, 3-sentence cold email to {business_name} ({url}) in {city}.
            1. Mention you visited their website and noticed they don't have a 24/7 AI support assistant to answer customer questions instantly.
            2. Explain that you built a custom AI Support Agent for {category} that answers common questions strictly from their own FAQs and escalates complex inquiries to their team.
            3. Invite them to test your live working demo at {DEMO_URL} and sign off as:
            Gowtham | Zenith AI ({SENDER_EMAIL})
            Return ONLY the plain email body text.
            """
            pitch = central_core.call_gemini(prompt)
            if "Error:" in pitch or "System Error:" in pitch:
                pitch = (
                    f"Hi {business_name} Team,\n\n"
                    f"I visited {url} and noticed you don't currently have a 24/7 AI support chat to answer visitor questions instantly. "
                    f"I built a custom AI Customer Support Agent for {category} in {city} that answers common inquiries strictly from your FAQ documents and escalates complex tickets to your staff.\n\n"
                    f"You can test my live working prototype here: {DEMO_URL}\n\n"
                    f"Best regards,\nGowtham | Zenith AI\n{SENDER_EMAIL}"
                )

            hot_leads.append({
                "business_name": business_name,
                "url": url,
                "emails": valid_emails,
                "pitch": pitch
            })
        except Exception:
            continue

    return hot_leads
