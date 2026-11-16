import sqlite3
import pandas as pd
import streamlit as st
import central_core
import support_engine

st.set_page_config(page_title="Zenith AI Support Agent", page_icon="🎧", layout="wide")
central_core.init_databases()

st.title("🎧 AI Customer Support & Ticketing System")
st.caption("Rank 1 B2B Automation: Connect this to a client's website to automate tier-1 support.")

tab1, tab2, tab3 = st.tabs(["💬 Customer Chat Portal", "📚 Knowledge Base Upload (Client)", "🚨 Escalation Desk (Client)"])

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
    st.write("Paste FAQs, return policies, shipping times, and product details here. The AI will ONLY use this context.")
    
    with st.form("kb_form"):
        kb_text = st.text_area("Paste documentation here", height=200)
        kb_submit = st.form_submit_button("Add to Knowledge Base")
        
    if kb_submit and kb_text:
        support_engine.add_to_knowledge_base(kb_text)
        st.success("Knowledge Base updated successfully!")
        
    st.divider()
    st.write("**Current Knowledge Base:**")
    kb_data = support_engine.get_knowledge_base()
    if kb_data:
        st.code(kb_data[:1000] + ("..." if len(kb_data) > 1000 else ""))
    else:
        st.write("Knowledge Base is currently empty.")

# --- TAB 3: ESCALATION DESK ---
with tab3:
    st.subheader("Live Ticket Desk")
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    df_tickets = pd.read_sql_query("SELECT id, status, customer_email, query, ai_response, created_at FROM tickets ORDER BY id DESC", conn)
    conn.close()
    
    if not df_tickets.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Queries", len(df_tickets))
        col2.metric("AI Resolved", len(df_tickets[df_tickets['status'] == 'RESOLVED']))
        col3.metric("Human Escalations", len(df_tickets[df_tickets['status'] == 'ESCALATED']))
        
        st.dataframe(df_tickets, use_container_width=True)
    else:
        st.info("No customer tickets logged yet.")
