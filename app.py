import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd

# --- 1. PAGE CONFIGURATION ---
# Removed forced CSS so the app respects the user's Light/Dark theme choice natively
st.set_page_config(page_title="SAP O2C Graph Agent", layout="wide")

# --- 2. SECURE CONNECTIVITY ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash-lite')

def run_query(query):
    with snowflake.connector.connect(
        user=st.secrets["SF_USER"],
        password=st.secrets["SF_PASSWORD"],
        account=st.secrets["SF_ACCOUNT"],
        warehouse=st.secrets["SF_WAREHOUSE"],
        database=st.secrets["SF_DATABASE"],
        schema=st.secrets["SF_SCHEMA"]
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetch_pandas_all()

# --- 3. L9 SEMANTIC MAP ---
METADATA_PROMPT = """
You are a Senior SAP Data Architect. Write Snowflake SQL for the O2C flow.
IMPORTANT: Wrap ALL column names in double quotes. Do NOT invent column names.

USE ONLY THESE TABLES AND COLUMNS:
1. SALES_ORDER_HEADERS: "salesOrder", "soldToParty", "totalNetAmount"
2. SALES_ORDER_ITEMS: "salesOrder", "material", "netAmount"
3. DELIVERY_ITEMS: "deliveryDocument", "referenceSdDocument" (links to "salesOrder")
4. BILLING_ITEMS: "billingDocument", "referenceSdDocument" (links to "deliveryDocument")
5. JOURNAL_ENTRIES: "accountingDocument", "referenceDocument" (links to "billingDocument")
6. PAYMENTS: "accountingDocument", "clearingAccountingDocument", "amountInTransactionCurrency"

SQL LOGIC RULES:
- Use UPPER(LTRIM(CAST("column" AS STRING), '0')) on BOTH sides of all JOIN conditions to handle leading zeros.
- If asked a non-SAP or off-topic question, return EXACTLY: SELECT 'UNSUPPORTED_QUERY'
- Return ONLY the raw SQL code. No markdown formatting, no backticks.
"""

# --- 4. UI SIDEBAR ---
with st.sidebar:
    st.title("🕸️ Graph Agent")
    st.markdown("Analyze the **Order-to-Cash** process.")
    
    user_input = st.text_input("Ask a question:", value="Trace flow for Order 740506")
    run_btn = st.button("🚀 Generate Graph", use_container_width=True)
    
    st.divider()
    st.subheader("Process Shortcuts")
    broken_btn = st.button("🚩 Identify Broken Flows", use_container_width=True)
    top_btn = st.button("📦 Top Products", use_container_width=True)

# Determine which query to run
active_query = None
if run_btn and user_input:
    active_query = user_input
elif broken_btn:
    active_query = "Show sales orders that have no entries in DELIVERY_ITEMS"
elif top_btn:
    active_query = "Which materials in SALES_ORDER_ITEMS have the most billing documents?"

# --- 5. EXECUTION & GRAPH ENGINE ---
st.title("SAP Order-to-Cash Knowledge Graph")
st.caption("FDE Submission | Process Mining & Semantic Discovery")

if active_query:
    with st.spinner("🤖 Processing Knowledge Graph..."):
        try:
            # Step A: Text-to-SQL
            ai_response = model.generate_content(f"{METADATA_PROMPT}\nUser Request: {active_query}")
            sql = ai_response.text.strip().replace("```sql", "").replace("```", "").strip()
            
            # Step B: Guardrail Check
            if "UNSUPPORTED_QUERY" in sql.upper():
                st.warning("This system is designed to answer questions related to the provided dataset only.")
            else:
                # Step C: Execute Query
                df = run_query(sql)

                if df.empty:
                    st.info("No matching data found in Snowflake for this request.")
                else:
                    nodes, edges, seen = [],[], set()
                    
                    # Theme-Agnostic Colors (Look great on Light AND Dark modes)
                    entity_colors = {
                        "ORDER": "#E74C3C",      # Red
                        "DELIVERY": "#3498DB",   # Blue
                        "BILLING": "#F1C40F",    # Yellow
                        "ACCOUNTING": "#2ECC71", # Green
                        "PAYMENT": "#95A5A6",    # Grey
                        "MATERIAL": "#9B59B6"    # Purple
                    }

                    # Step D: Node Creation
                    for col in df.columns:
                        color = "#BDC3C7" 
                        for key in entity_colors:
                            if key in col.upper(): color = entity_colors[key]
                        
                        for val in df[col].dropna().unique():
                            if pd.isna(val) or str(val).strip().lower() == 'nan' or str(val).strip() == '':
                                continue
                            
                            node_id = str(val)
                            if node_id not in seen:
                                # Added font styling to ensure text is visible on light/dark backgrounds
                                nodes.append(Node(
                                    id=node_id, 
                                    label=f"{col}\n{node_id}", 
                                    color=color, 
                                    size=25, 
                                    shape="dot",
                                    font={"color": "#2C3E50", "size": 14, "face": "Arial", "background": "rgba(255,255,255,0.7)"}
                                ))
                                seen.add(node_id)

                    # Step E: Edge Creation
                    for i in range(len(df.columns) - 1):
                        for _, row in df.iterrows():
                            u, v = row[i], row[i+1]
                            if pd.notna(u) and pd.notna(v):
                                u_str, v_str = str(u).strip(), str(v).strip()
                                if u_str.lower() != 'nan' and v_str.lower() != 'nan' and u_str != "" and v_str != "":
                                    # Changed edge color to Slate Gray so it's visible on White and Black backgrounds
                                    edges.append(Edge(source=u_str, target=v_str, color="#5D6D7E", width=2))

                    # Helpful UI prompt if the user runs a 1-column query
                    if len(df.columns) == 1:
                        st.info("ℹ️ Note: This query returned a single list of items. To see connecting lines, ask a question that traces a flow between two or more document types.")

                    # Step F: Massive Interactive Canvas
                    config = Config(
                        width="100%", 
                        height=800, 
                        directed=True, 
                        physics=True, 
                        hierarchical=False, 
                        nodeHighlightBehavior=True, 
                        highlightColor="#F7A7A6"
                    )
                    
                    agraph(nodes=nodes, edges=edges, config=config)

                    # Step G: Technical Audit Trail
                    with st.expander("Technical Trace (View SQL & Data)"):
                        st.code(sql, language="sql")
                        st.dataframe(df)

        except Exception as e:
            st.error(f"System Error: {str(e)}")

# --- 6. FOOTER ---
st.markdown("---")
st.caption("Senior FDE Submission | Architecture: Snowflake + Gemini + Streamlit")
