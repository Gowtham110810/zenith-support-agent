import sqlite3
from datetime import datetime, timezone
import central_core

def add_to_knowledge_base(text):
    central_core.init_databases()
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO knowledge_base (content, added_at) VALUES (?, ?)", 
                (text, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def get_knowledge_base():
    central_core.init_databases()
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute("SELECT content FROM knowledge_base")
    rows = cur.fetchall()
    conn.close()
    return "\n\n---\n\n".join([r[0] for r in rows])

def process_customer_query(email, query):
    central_core.init_databases()
    kb_context = get_knowledge_base()
    
    if not kb_context:
        response = "Our knowledge base is currently empty. I am escalating this to a human agent."
        status = "ESCALATED"
    else:
        prompt = f"""
        You are a helpful, professional AI customer support agent for a company. 
        Read the company knowledge base below. Then, answer the customer's query strictly using ONLY the provided knowledge base.
        
        If the answer is NOT explicitly contained in the knowledge base, do not guess. Instead, reply with exactly this exact phrase and nothing else:
        [ESCALATE_TO_HUMAN]
        
        COMPANY KNOWLEDGE BASE:
        {kb_context}
        
        CUSTOMER QUERY:
        {query}
        """
        
        ai_response = central_core.call_gemini(prompt)
        
        if "[ESCALATE_TO_HUMAN]" in ai_response:
            response = "I couldn't find the exact answer to that in my current documentation. I have escalated your ticket to our human support team, and they will email you shortly."
            status = "ESCALATED"
        else:
            response = ai_response
            status = "RESOLVED"

    # Log the ticket
    conn = sqlite3.connect(central_core.SUPPORT_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (customer_email, query, ai_response, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (email, query, response, status, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    
    return response, status
