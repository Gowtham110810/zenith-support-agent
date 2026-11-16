import sqlite3
import urllib.parse
import pandas as pd
import streamlit as st
import central_core
import support_engine
import lead_hunter

st.set_page_config(page_title="Zenith AI Support Agent", page_icon="🎧", layout="wide")
central_core.init_databases()

st.title("🎧 AI Customer Support & B2B Lead Hunter")
st.caption("Rank 1 B2B Automation: Auto-discover local businesses and pitch your live AI support agent.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Customer Chat Portal",
    "📚 Knowledge Base Upload",
    "🚨 Escalation Desk",
    "🎯 Auto-Lead Hunter"
])

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

with tab4:
    st.subheader("Discover Clients & Send From zenith.ai.gowtham@gmail.com")
    with st.form("hunt_form"):
        col1, col2, col3 = st.columns([2, 2, 1])
        category = col1.text_input("Business Niche", value="Dental Clinics")
        city = col2.text_input("Target City", value="Hyderabad")
        max_scan = col3.number_input("Leads to Find", min_value=1, max_value=6, value=3)
        hunt_btn = st.form_submit_button("🚀 Find Clients")

    if hunt_btn:
        with st.spinner(f"Scanning {category} in {city} without chat widgets..."):
            leads = lead_hunter.hunt_support_leads(category, city, int(max_scan))

        if leads:
            st.success(f"Found {len(leads)} hot lead(s) with verified email addresses!")
            for idx, lead in enumerate(leads):
                with st.expander(f"Lead #{idx+1}: {lead['business_name']} ({lead['url']})", expanded=True):
                    target_email = lead["emails"][0]
                    st.write(f"**Target Email:** `{target_email}`")
                    pitch = st.text_area("Generated Pitch:", value=lead["pitch"], height=160, key=f"pitch_{idx}")

                    subject = urllib.parse.quote(f"24/7 AI Support Assistant for {lead['business_name']}")
                    body = urllib.parse.quote(pitch)
                    gmail_url = (
                        f"https://mail.google.com/mail/?authuser=zenith.ai.gowtham@gmail.com"
                        f"&view=cm&fs=1&to={urllib.parse.quote(target_email)}&su={subject}&body={body}"
                    )

                    st.markdown(
                        f'<a href="{gmail_url}" target="_blank">'
                        f'<button style="background-color:#10B981;color:white;border:none;padding:10px 18px;border-radius:6px;cursor:pointer;font-weight:600;">'
                        f'✉️ Open Pre-Filled Email in Gmail (zenith.ai.gowtham@gmail.com)'
                        f'</button></a>',
                        unsafe_allow_html=True
                    )
        else:
            st.warning("No leads with public emails found in that small sample. Try increasing 'Leads to Find' or changing the niche.")
