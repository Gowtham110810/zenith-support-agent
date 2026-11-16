import os
import re
import base64
import sqlite3
import smtplib
import urllib.parse
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
import central_core

DIRECTORY_BLACKLIST = {
    "justdial.com", "practo.com", "sulekha.com", "indiamart.com", "lybrate.com",
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "wikipedia.org",
    "yelp.com", "tripadvisor.com", "tripadvisor.in", "google.com", "whatclinic.com",
    "zomato.com", "swiggy.com", "credihealth.com", "apollo247.com", "threebestrated.in",
    "jdmagicbox.com", "magicbricks.com", "99acres.com", "housing.com", "bing.com",
    "duckduckgo.com", "microsoft.com", "cloudflare.com", "w3.org", "schema.org"
}

CHAT_WIDGET_SCRIPTS = [
    "embed.tawk.to", "static.zdassets.com", "widget.intercom.io",
    "client.crisp.chat", "code.tidio.co", "livechatinc.com"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

DEMO_URL = "https://zenith-support-agent-u6xxkp7actgzbcuubdbaiz.streamlit.app"
SENDER_EMAIL = "zenith.ai.gowtham@gmail.com"
DAILY_EMAIL_LIMIT = 5


def init_outreach_table():
    central_core.init_databases()
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS outreach_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT,
            url TEXT,
            target_email TEXT UNIQUE,
            subject TEXT,
            pitch TEXT,
            sent_date TEXT,
            sent_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_today_sent_count():
    init_outreach_table()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM outreach_logs WHERE sent_date = ?", (today_str,))
    count = cur.fetchone()[0]
    conn.close()
    return count


def is_already_contacted(target_email):
    init_outreach_table()
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM outreach_logs WHERE target_email = ?", (target_email.lower().strip(),))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def is_valid_business_url(url):
    if not url or not url.startswith("http"):
        return False
    netloc = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    if not netloc or "." not in netloc:
        return False
    return not any(b in netloc for b in DIRECTORY_BLACKLIST)


def decode_bing_url(href):
    """Decodes Bing tracking redirect links into direct business URLs."""
    if "bing.com/ck/a" in href and "u=" in href:
        try:
            u_param = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("u", [""])[0]
            if u_param.startswith("a1"):
                b64 = u_param[2:]
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                return base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return href


def get_business_urls(category, city):
    """Multi-engine scraper (Bing + DuckDuckGo Lite + DuckDuckGo HTML) with no URL cap."""
    candidates = []
    seen_domains = set()

    def add_url(raw_url):
        if not is_valid_business_url(raw_url):
            return
        netloc = urllib.parse.urlparse(raw_url).netloc.lower().replace("www.", "")
        if netloc not in seen_domains:
            seen_domains.add(netloc)
            candidates.append(raw_url)

    queries = [
        f'{category} in {city} contact email -justdial -practo -sulekha',
        f'{category} {city} "contact us" "@" -justdial -practo',
        f'best {category} in {city} official website'
    ]

    # 1. Bing Web Search (Rarely blocks Streamlit Cloud IPs)
    for q in queries:
        try:
            b_url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=30"
            resp = requests.get(b_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                decoded = decode_bing_url(a["href"])
                if decoded.startswith("http") and "bing.com" not in decoded and "microsoft.com" not in decoded:
                    add_url(decoded)
        except Exception:
            continue

    # 2. DuckDuckGo Lite & HTML Search
    for q in queries[:2]:
        try:
            d_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            resp = requests.get(d_url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                raw_href = a["href"]
                target = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query).get("uddg", [raw_href])[0]
                add_url(target)
        except Exception:
            continue

    return candidates


def extract_emails_from_site(target_url, soup, html_text):
    """Extracts public emails from the landed page, homepage, and /contact page."""
    ignored_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff", ".ttf")
    cleaned_html = html_text.replace("[at]", "@").replace("(at)", "@").replace(" [at] ", "@")
    raw_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", cleaned_html))

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:"):
            raw_emails.add(href.replace("mailto:", "").split("?")[0].strip())

    def filter_valid(email_set):
        return [
            e.lower().strip(".") for e in email_set
            if not e.lower().endswith(ignored_ext)
            and not any(bad in e.lower() for bad in ["example.com", "sentry", "wixpress", "wordpress", "domain.com", "email.com"])
        ]

    valid = filter_valid(raw_emails)
    if valid:
        return list(dict.fromkeys(valid))[:3]

    # Check /contact or /about links on the same domain
    parsed = urllib.parse.urlparse(target_url)
    base_root = f"{parsed.scheme}://{parsed.netloc}"
    contact_paths = ["/contact", "/contact-us", "/about", "/about-us"]

    for a in soup.find_all("a", href=True):
        href_low = a["href"].lower()
        if "contact" in href_low or "about" in href_low or "reach" in href_low:
            contact_paths.insert(0, a["href"])
            break

    for path in contact_paths[:2]:
        try:
            c_url = urllib.parse.urljoin(base_root, path)
            c_resp = requests.get(c_url, headers=HEADERS, timeout=6)
            c_clean = c_resp.text.replace("[at]", "@").replace("(at)", "@")
            c_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", c_clean))
            valid_c = filter_valid(c_emails)
            if valid_c:
                return list(dict.fromkeys(valid_c))[:3]
        except Exception:
            continue

    # Fallback: If the business website is live and valid but hides its email behind JS, use info@domain
    netloc = parsed.netloc.lower().replace("www.", "")
    if netloc and "." in netloc:
        return [f"info@{netloc}"]

    return []


def hunt_support_leads(category, city):
    """Scans all discovered business websites with no lead cap."""
    init_outreach_table()
    urls = get_business_urls(category, city)
    hot_leads = []

    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code >= 400:
                continue

            html_lower = resp.text.lower()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Only skip if an actual chat widget script is embedded
            if any(widget in html_lower for widget in CHAT_WIDGET_SCRIPTS):
                continue

            valid_emails = extract_emails_from_site(url, soup, resp.text)
            if not valid_emails:
                continue

            primary_email = valid_emails[0].lower().strip()
            if is_already_contacted(primary_email):
                continue

            parsed = urllib.parse.urlparse(url)
            clean_domain = f"{parsed.scheme}://{parsed.netloc}"
            title_tag = soup.find("title")
            business_name = (
                title_tag.get_text(strip=True).split("|")[0].split("-")[0].strip()[:50]
                if title_tag and title_tag.get_text(strip=True)
                else parsed.netloc.replace("www.", "")
            )

            pitch = (
                f"Hi {business_name} Team,\n\n"
                f"I visited your website ({clean_domain}) and noticed you don't currently have a 24/7 AI support assistant to answer customer questions instantly. "
                f"I built a custom AI Support Agent for {category} in {city} that answers common questions strictly from your own FAQs and escalates complex inquiries to your staff.\n\n"
                f"You can test my live working demo right here: {DEMO_URL}\n\n"
                f"Best regards,\nGowtham | Zenith AI\n{SENDER_EMAIL}"
            )

            hot_leads.append({
                "business_name": business_name,
                "url": clean_domain,
                "emails": valid_emails,
                "pitch": pitch
            })
        except Exception:
            continue

    return hot_leads


def send_automated_email(business_name, url, target_email, subject, body):
    """Enforces the strict 5-email daily cap while sending via Gmail SMTP."""
    init_outreach_table()
    target_email = target_email.lower().strip()

    sent_today = get_today_sent_count()
    if sent_today >= DAILY_EMAIL_LIMIT:
        return False, f"Daily limit reached ({DAILY_EMAIL_LIMIT}/{DAILY_EMAIL_LIMIT} emails sent today). Try again tomorrow!"

    if is_already_contacted(target_email):
        return False, f"Already sent an email to {target_email} previously."

    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
    if not password:
        return False, "GMAIL_APP_PASSWORD is missing in Streamlit Secrets."

    msg = MIMEMultipart()
    msg["From"] = f"Gowtham | Zenith AI <{SENDER_EMAIL}>"
    msg["To"] = target_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.starttls()
        server.login(SENDER_EMAIL, password)
        server.send_message(msg)
        server.quit()

        now_utc = datetime.now(timezone.utc)
        conn = sqlite3.connect(central_core.SUPPORT_DB)
        cur = conn.cursor()
        cur.execute(
            """INSERT OR IGNORE INTO outreach_logs 
               (business_name, url, target_email, subject, pitch, sent_date, sent_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (business_name, url, target_email, subject, body, now_utc.strftime("%Y-%m-%d"), now_utc.isoformat())
        )
        conn.commit()
        conn.close()

        return True, f"Sent! ({sent_today + 1}/{DAILY_EMAIL_LIMIT} daily quota used)"
    except Exception as e:
        return False, f"SMTP Error: {str(e)}"
