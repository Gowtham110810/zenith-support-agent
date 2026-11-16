import sqlite3
import urllib.parse
import pandas as pd
import streamlit as st
import central_core
import support_engine
import lead_hunter

st.set_page_config(page_title="Zenith AI Support Agent", page_icon="🎧", layout="wide")
central_core.init_databases()
lead_hunter.init_outreach_table()

if "hunted_leads" not in st.session_state:
    st.session_state.hunted_leads = []

st.title("🎧 AI Customer Support & B2B Lead Hunter")
st.caption("Rank 1 B2B Automation: Auto-discover local businesses and auto-send up to 5 pitches per day.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Customer Chat Portal",
    "📚 Knowledge Base Upload",
    "🚨 Escalation Desk",
    "🎯 Auto-Lead Hunter (5/Day Cap)"
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

# --- TAB 4: AUTO LEAD HUNTER & SENDER ---
with tab4:
    st.subheader("Automated Client Discovery & Outreach (zenith.ai.gowtham@gmail.com)")

    sent_today = lead_hunter.get_today_sent_count()
    remaining_quota = max(0, lead_hunter.DAILY_EMAIL_LIMIT - sent_today)

    m1, m2, m3 = st.columns(3)
    m1.metric("Daily Limit", f"{lead_hunter.DAILY_EMAIL_LIMIT} Emails / Day")
    m2.metric("Sent Today", sent_today)
    m3.metric("Remaining Today", remaining_quota)

    with st.form("hunt_form"):
        col1, col2, col3 = st.columns([2, 2, 1])
        category = col1.text_input("Business Niche", value="Dental Clinics")
        city = col2.text_input("Target City", value="Hyderabad")
        max_scan = col3.number_input("Leads to Find", min_value=1, max_value=5, value=5)
        hunt_btn = st.form_submit_button("🔍 Step 1: Find Clients")

    if hunt_btn:
        with st.spinner(f"Scanning {category} in {city} without chat widgets..."):
            st.session_state.hunted_leads = lead_hunter.hunt_support_leads(category, city, int(max_scan))
        if not st.session_state.hunted_leads:
            st.warning("No new uncontacted leads found in that scan. Try another niche or city!")

    leads = st.session_state.hunted_leads
    if leads:
        st.success(f"Loaded {len(leads)} uncontacted lead(s) ready for outreach.")

        # 1-Click Batch Auto-Send Button (Respects 5/day limit)
        if remaining_quota > 0:
            if st.button(f"⚡ Auto-Send All ({min(len(leads), remaining_quota)} Emails Within Daily Cap)"):
                for idx, lead in enumerate(leads):
                    if lead_hunter.get_today_sent_count() >= lead_hunter.DAILY_EMAIL_LIMIT:
                        st.warning("Reached 5/5 daily email limit! Stopping batch.")
                        break
                    target_email = lead["emails"][0]
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
            st.warning("🔒 Daily limit of 5 automated emails reached. Outreach will unlock tomorrow.")

        # Individual Lead Cards
        for idx, lead in enumerate(leads):
            target_email = lead["emails"][0]
            already_sent = lead_hunter.is_already_contacted(target_email)
            status_badge = "✅ SENT" if already_sent else "🟢 READY"

            with st.expander(f"{status_badge} | {lead['business_name']} ({lead['url']})", expanded=not already_sent):
                st.write(f"**Target Email:** `{target_email}`")
                pitch = st.text_area("Generated Pitch:", value=lead["pitch"], height=150, key=f"pitch_{idx}")
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
                        f'↗️ Fallback: Open in Gmail Tab'
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
