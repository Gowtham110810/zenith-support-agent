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
import discovery_engine

CHAT_WIDGET_SCRIPTS = [
    "embed.tawk.to", "static.zdassets.com", "widget.intercom.io",
    "client.crisp.chat", "code.tidio.co", "livechatinc.com"
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

def extract_emails_from_site(target_url, soup, html_text):
    ignored_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
    cleaned_html = html_text.replace("[at]", "@").replace("(at)", "@")
    raw_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", cleaned_html))

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:"):
            raw_emails.add(href.replace("mailto:", "").split("?")[0].strip())

    def filter_valid(email_set):
        return [
            e.lower().strip(".") for e in email_set
            if not e.lower().endswith(ignored_ext)
            and not any(bad in e.lower() for bad in ["example.com", "sentry", "wixpress", "domain.com"])
        ]

    valid = filter_valid(raw_emails)
    if valid:
        return list(dict.fromkeys(valid))[:2]

    parsed = urllib.parse.urlparse(target_url)
    base_root = f"{parsed.scheme}://{parsed.netloc}"
    contact_paths = ["/contact", "/contact-us", "/about"]

    for path in contact_paths:
        try:
            c_url = urllib.parse.urljoin(base_root, path)
            c_resp = requests.get(c_url, headers=HEADERS, timeout=5)
            c_clean = c_resp.text.replace("[at]", "@")
            c_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", c_clean))
            valid_c = filter_valid(c_emails)
            if valid_c:
                return list(dict.fromkeys(valid_c))[:2]
        except Exception:
            continue

    return []

def generate_pitch_and_package(url, category, city):
    try:
        if not url.startswith("http"):
            url = "https://" + url

        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code >= 400:
            return None

        html_lower = resp.text.lower()
        soup = BeautifulSoup(resp.text, "html.parser")

        if any(widget in html_lower for widget in CHAT_WIDGET_SCRIPTS):
            return None

        valid_emails = extract_emails_from_site(url, soup, resp.text)
        if not valid_emails:
            return None

        primary_email = valid_emails[0].lower().strip()
        if is_already_contacted(primary_email):
            return None

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

        return {
            "business_name": business_name,
            "url": clean_domain,
            "emails": valid_emails,
            "pitch": pitch
        }
    except Exception:
        return None

def hunt_direct_urls(category, city, raw_urls_text):
    init_outreach_table()
    urls = [u.strip() for u in raw_urls_text.replace(",", "\n").split("\n") if u.strip()]
    hot_leads = []
    for url in urls:
        lead = generate_pitch_and_package(url, category, city)
        if lead:
            hot_leads.append(lead)
    return hot_leads

def hunt_support_leads(category, city):
    """The fully automated engine using the new discovery_engine file."""
    init_outreach_table()
    
    # Let discovery_engine do the deep thinking and IP-block bypassing
    urls = discovery_engine.deep_discover_urls(category, city)
    
    hot_leads = []
    for url in urls:
        lead = generate_pitch_and_package(url, category, city)
        if lead:
            hot_leads.append(lead)

    return hot_leads

def send_automated_email(business_name, url, target_email, subject, body):
    init_outreach_table()
    target_email = target_email.lower().strip()

    sent_today = get_today_sent_count()
    if sent_today >= DAILY_EMAIL_LIMIT:
        return False, f"Daily limit reached ({DAILY_EMAIL_LIMIT}/{DAILY_EMAIL_LIMIT} emails sent today)."

    if is_already_contacted(target_email):
        return False, "Already sent an email to this address previously."

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
