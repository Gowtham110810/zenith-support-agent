import os
import re
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
    "jdmagicbox.com", "magicbricks.com", "99acres.com", "housing.com"
}

CHAT_WIDGET_SCRIPTS = [
    "zendesk", "intercom", "tawk.to", "crisp.chat", "tidio", "hubspot", "livechat", "freshchat"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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


def get_business_urls(category, city):
    """Pulls all possible URLs from multiple deep queries without early limits."""
    candidates = []
    seen_domains = set()
    
    # 3 distinct queries to maximize discovery
    queries = [
        f'{category} in {city} "contact" -justdial -practo',
        f'best {category} {city} official website',
        f'{category} {city} email address'
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
        except Exception:
            continue
            
    return candidates


def extract_emails_from_site(base_url, soup, html_text):
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

    for a in soup.find_all("a", href=True):
        if "contact" in a["href"].lower() or "about" in a["href"].lower():
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


def hunt_support_leads(category, city, max_scan=5):
    init_outreach_table()
    urls = get_business_urls(category, city)
    hot_leads = []

    for url in urls:
        # Stop immediately once we have the requested number of hot leads
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

            primary_email = valid_emails[0].lower().strip()
            if is_already_contacted(primary_email):
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


def send_automated_email(business_name, url, target_email, subject, body):
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
