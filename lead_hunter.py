import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_automated_email(target_email, subject, body):
    """Sends an email securely in the background using Gmail SMTP."""
    sender = SENDER_EMAIL
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    
    if not password:
        return False, "App Password missing from Streamlit secrets."
        
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = target_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)
