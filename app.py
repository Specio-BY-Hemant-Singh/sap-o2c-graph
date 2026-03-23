import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="SAP O2C Graph AI", layout="wide", initial_sidebar_state="expanded")

# --- 2. API & MODEL SETUP ---
# Using the most stable model string to avoid 'NotFound' errors
try:
    genai.configure(api_key=st.secrets["GEMINI_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("Gemini API Configuration Failed. Check your Secrets.")

# --- 3. SNOWFLAKE CONNECTION (CACHED) ---
@st.cache_resource
def get_snowflake_conn():
    return snowflake.connector.connect(
        user=st.secrets["SF_USER"],
        password=st.secrets["SF_PASSWORD"],
        account=st.secrets["SF_ACCOUNT"],
        warehouse=st.secrets["SF_WAREHOUSE"],
        database=st.secrets["SF_DATABASE"],
        schema=st.secrets["SF_SCHEMA"]
    )

def run_query(query):
    conn = get_snowflake_conn()
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetch_pandas_all()

# --- 4. THE L9 SEMANTIC PROMPT (GUARDRAILS INCLUDED) ---
METADATA_PROMPT = """
You are a Senior SAP Functional Consultant and Data Engineer. 
Your goal is to write Snowflake SQL that joins tables to trace the Order-to-Cash (O2C) flow.

TABLE SCHEMA:
- SALES_ORDER_HEADERS: Primary Key is SALESORDER.
- DELIVERY_HEADERS: Primary Key is DELIVERYDOCUMENT. Join: REFERENCESDDOCUMENT = SALES_ORDER_HEADERS.SALESORDER
- BILLING_HEADERS: Primary Key is BILLINGDOCUMENT. Join: REFERENCESDDOCUMENT = DELIVERY_HEADERS.DELIVERYDOCUMENT
- JOURNAL_ENTRIES: Primary Key is ACCOUNTINGDOCUMENT. Join: REFERENCEDOCUMENT = BILLING_HEADERS.BILLINGDOCUMENT
- PAYMENTS: Primary Key is ACCOUNTINGDOCUMENT. Join: ACCOUNTINGDOCUMENT = JOURNAL_ENTRIES.ACCOUNTINGDOCUMENT

SQL RULES:
1. Return ONLY the SQL code. No preamble, no markdown backticks.
2. Use LTRIM(column, '0') on all ID columns to ensure joins match correctly.
3. If the user asks something unrelated to SAP O2C data, return: SELECT 'UNSUPPORTED_QUERY'
4. Always select the Document IDs in order: SalesOrder, DeliveryDocument, BillingDocument, AccountingDocument.
"""

# --- 5. UI COMPONENTS ---
st.title("🕸️ SAP Order-to-Cash Knowledge Graph")
st.markdown("---")

# Sidebar for Interaction
with st.sidebar:
    st.header("Chat with Graph")
    st.markdown("Ask questions about your SAP data flow.")
    user_input = st.text_input("Query (e.g., 'Trace Sales Order 740506')", key="user_query")
    
    st.divider()
    st.subheader("System Guardrails")
    st.caption("✅ Grounded in Snowflake Data")
    st.caption("✅ Restricted to O2C Domain")
    
    if st.button("🚩 Identify Broken Flows"):
        user_input = "Find Sales Orders that have no linked Delivery Documents"

# --- 6. CORE LOGIC: TEXT-TO-SQL-TO-GRAPH ---
if user_input:
    with st.spinner("Generating Graph..."):
        try:
            # Step A: AI generates SQL
            prompt = f"{METADATA_PROMPT}\nUser Request: {user_input}"
            ai_response = model.generate_content(prompt)
            sql = ai_response.text.strip().replace("```sql", "").replace("```", "")

            if "UNSUPPORTED_QUERY" in sql:
                st.warning("This system is designed to answer questions related to the SAP O2C dataset only.")
            else:
                # Step B: Execute SQL
                df = run_query(sql)

                if df.empty:
                    st.info("No records found for this specific query in Snowflake.")
                else:
                    # Step C: Build Graph Visualization
                    nodes = []
                    edges = []
                    seen_nodes = set()

                    # Color Palette for SAP Entities
                    colors = {
                        "SALESORDER": "#FF4B4B",    # Red
                        "DELIVERY": "#29B5E8",      # Blue
                        "BILLING": "#FFD166",       # Yellow
                        "ACCOUNTING": "#06D6A0",    # Green
                        "PAYMENT": "#073B4C"        # Dark Blue
                    }

                    # Create Nodes
                    for col in df.columns:
                        # Determine node type for coloring
                        node_type = "SALESORDER"
                        if "DELIVERY" in col.upper(): node_type = "DELIVERY"
                        if "BILLING" in col.upper(): node_type = "BILLING"
                        if "ACCOUNTING" in col.upper() or "JOURNAL" in col.upper(): node_type = "ACCOUNTING"
                        
                        for val in df[col].dropna().unique():
                            node_id = str(val)
                            if node_id not in seen_nodes:
                                nodes.append(Node(
                                    id=node_id, 
                                    label=f"{col}: {node_id}", 
                                    color=colors.get(node_type, "#999999"),
                                    size=15
                                ))
                                seen_nodes.add(node_id)

                    # Create Edges (Sequential Linking)
                    for i in range(len(df.columns) - 1):
                        for _, row in df.iterrows():
                            src, tgt = str(row[i]), str(row[i+1])
                            if src != "None" and tgt != "None" and src != "" and tgt != "":
                                edges.append(Edge(source=src, target=tgt))

                    # Step D: Render Graph
                    config = Config(
                        width=1000, 
                        height=600, 
                        directed=True, 
                        physics=True, 
                        hierarchical=False,
                        nodeHighlightBehavior=True,
                        highlightColor="#F7A7A6"
                    )
                    
                    agraph(nodes=nodes, edges=edges, config=config)

                    # Step E: Data Transparency
                    with st.expander("View Technical Details"):
                        st.subheader("Generated SQL")
                        st.code(sql, language="sql")
                        st.subheader("Raw Dataframe")
                        st.dataframe(df)

        except Exception as e:
            st.error(f"An error occurred: {type(e).__name__}")
            with st.expander("Debug Trace"):
                st.exception(e)

# --- 7. FOOTER ---
st.markdown("---")
st.caption("L9 Forward Deployed Engineer | Snowflake + Gemini 1.5 Flash + Streamlit")
