import sqlite3
import urllib.parse
import pandas as pd
import streamlit as st
import central_core
import support_engine
import lead_hunter

st.set_page_config(page_title="Zenith AI Support Agent", page_icon="🎧", layout="wide")
central_core.init_databases()

if "hunted_leads" not in st.session_state:
    st.session_state.hunted_leads = []

st.title("🎧 AI Customer Support & B2B Lead Hunter")
st.caption("Rank 1 B2B Automation: Unlimited lead discovery with a safe 5-email/day sending cap.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Customer Chat Portal",
    "📚 Knowledge Base Upload",
    "🚨 Escalation Desk",
    "🎯 Auto-Lead Hunter"
])

# --- TAB 1: CUSTOMER FACING ---
with tab1:
    st.subheader("How can we help you today?")
    with st.form("customer_form"):
        email = st.text_input("Your Email Address")
        query = st.text_area("How can we assist you?")
        submitted = st.form_submit_button("Ask Support")

    if submitted and email and query:
        with st.spinner("Checking knowledge base..."):
            response, status = support_engine.process_customer_query(email, query)
        if status == "RESOLVED":
            st.success("✅ Answer Found")
            st.info(response)
        else:
            st.warning("⚠️ Ticket Escalated")
            st.info(response)

# --- TAB 2: BUSINESS KNOWLEDGE BASE ---
with tab2:
    st.subheader("Upload Company Knowledge")
    with st.form("kb_form"):
        kb_text = st.text_area("Paste documentation here", height=200)
        kb_submit = st.form_submit_button("Add to Knowledge Base")

    if kb_submit and kb_text:
        support_engine.add_to_knowledge_base(kb_text)
        st.success("Knowledge Base updated successfully!")

    st.write("**Current Knowledge Base:**")
    st.code(support_engine.get_knowledge_base()[:1000] or "Knowledge Base is currently empty.")

# --- TAB 3: ESCALATION DESK ---
with tab3:
    st.subheader("Live Ticket Desk")
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    df_tickets = pd.read_sql_query(
        "SELECT id, status, customer_email, query, ai_response, created_at FROM tickets ORDER BY id DESC",
        conn
    )
    conn.close()
    if not df_tickets.empty:
        st.dataframe(df_tickets, use_container_width=True)
    else:
        st.info("No customer tickets logged yet.")

# --- TAB 4: UNLIMITED LEAD HUNTER + 5/DAY SENDER ---
with tab4:
    st.subheader("Client Discovery & Automated Outreach (zenith.ai.gowtham@gmail.com)")

    sent_today = lead_hunter.get_today_sent_count()
    remaining_quota = max(0, lead_hunter.DAILY_EMAIL_LIMIT - sent_today)

    m1, m2, m3 = st.columns(3)
    m1.metric("Daily Sending Limit", f"{lead_hunter.DAILY_EMAIL_LIMIT} Emails / Day")
    m2.metric("Sent Today", sent_today)
    m3.metric("Remaining Quota Today", remaining_quota)

    st.divider()
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("### Method A: Search Engine Auto-Scan")
        st.caption("Let the server scan DuckDuckGo/Bing. (Can be blocked by search engines).")
        with st.form("hunt_form_auto"):
            category_a = st.text_input("Business Niche", value="Dental Clinics")
            city_a = st.text_input("Target City", value="Hyderabad")
            hunt_btn_auto = st.form_submit_button("🔍 Auto-Scan for Clients")
            
        if hunt_btn_auto:
            with st.spinner(f"Scanning search engines for {category_a} in {city_a}..."):
                st.session_state.hunted_leads = lead_hunter.hunt_support_leads(category_a, city_a)
            if not st.session_state.hunted_leads:
                st.warning("Search engines blocked the request or returned no valid emails. Use Method B!")

    with col_b:
        st.markdown("### Method B: Direct URL Injector (Bulletproof)")
        st.caption("Paste website URLs directly from Google Maps. Bypasses search blocks completely.")
        with st.form("hunt_form_direct"):
            category_b = st.text_input("Business Niche", value="Dental Clinics", key="cat_b")
            city_b = st.text_input("Target City", value="Hyderabad", key="city_b")
            raw_urls = st.text_area("Paste Website URLs (One per line)", placeholder="https://clinic1.com\nhttps://clinic2.in")
            hunt_btn_direct = st.form_submit_button("⚡ Extract Emails & Generate Pitches")
            
        if hunt_btn_direct and raw_urls:
            with st.spinner("Crawling pasted URLs to extract emails..."):
                st.session_state.hunted_leads = lead_hunter.hunt_direct_urls(category_b, city_b, raw_urls)
            if not st.session_state.hunted_leads:
                st.warning("Could not extract any valid public emails from the URLs provided.")

    leads = st.session_state.hunted_leads
    if leads:
        st.divider()
        st.success(f"Successfully processed {len(leads)} business lead(s)! You can auto-send up to {remaining_quota} more email(s) today.")

        if remaining_quota > 0:
            if st.button(f"🚀 Auto-Send Top {min(len(leads), remaining_quota)} Emails Now"):
                for idx, lead in enumerate(leads):
                    if lead_hunter.get_today_sent_count() >= lead_hunter.DAILY_EMAIL_LIMIT:
                        st.warning("Reached 5/5 daily email limit! Stopping batch.")
                        break
                    target_email = lead["emails"][0]
                    if lead_hunter.is_already_contacted(target_email):
                        continue
                    subject = f"24/7 AI Support Assistant for {lead['business_name']}"
                    pitch_text = st.session_state.get(f"pitch_{idx}", lead["pitch"])
                    ok, msg = lead_hunter.send_automated_email(
                        lead["business_name"], lead["url"], target_email, subject, pitch_text
                    )
                    if ok:
                        st.toast(f"✅ Sent to {target_email}")
                    else:
                        st.error(f"❌ {target_email}: {msg}")
                st.rerun()
        else:
            st.warning("🔒 Daily limit of 5 automated emails reached. You can still browse leads or send manually via Gmail.")

        for idx, lead in enumerate(leads):
            target_email = lead["emails"][0]
            already_sent = lead_hunter.is_already_contacted(target_email)
            status_badge = "✅ SENT" if already_sent else "🟢 READY"

            with st.expander(f"{status_badge} | #{idx+1}: {lead['business_name']} ({lead['url']})", expanded=(idx < 5 and not already_sent)):
                st.write(f"**Target Email:** `{target_email}`")
                pitch = st.text_area("Pitch:", value=lead["pitch"], height=150, key=f"pitch_{idx}")
                subject = f"24/7 AI Support Assistant for {lead['business_name']}"

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        f"🚀 Auto-Send via SMTP to {target_email}",
                        key=f"send_{idx}",
                        disabled=(already_sent or remaining_quota == 0)
                    ):
                        with st.spinner("Sending email in the background..."):
                            ok, msg = lead_hunter.send_automated_email(
                                lead["business_name"], lead["url"], target_email, subject, pitch
                            )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                with c2:
                    gmail_url = (
                        f"https://mail.google.com/mail/?authuser=zenith.ai.gowtham@gmail.com"
                        f"&view=cm&fs=1&to={urllib.parse.quote(target_email)}"
                        f"&su={urllib.parse.quote(subject)}&body={urllib.parse.quote(pitch)}"
                    )
                    st.markdown(
                        f'<a href="{gmail_url}" target="_blank">'
                        f'<button style="background-color:#334155;color:white;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;">'
                        f'↗️ Open in Gmail Tab'
                        f'</button></a>',
                        unsafe_allow_html=True
                    )

    st.divider()
    st.subheader("📬 Sent Outreach History")
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    df_sent = pd.read_sql_query(
        "SELECT sent_date, business_name, target_email, url, sent_at FROM outreach_logs ORDER BY id DESC",
        conn
    )
    conn.close()
    if not df_sent.empty:
        st.dataframe(df_sent, use_container_width=True)
    else:
        st.info("No automated outreach emails sent yet.")
