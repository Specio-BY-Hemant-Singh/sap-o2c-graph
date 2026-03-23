import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd

# --- 1. PAGE CONFIGURATION & STYLING ---
st.set_page_config(page_title="SAP O2C Graph Agent", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    .stTextInput > div > div > input { background-color: #0d1117; color: white; border: 1px solid #30363D; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SECURE CONNECTIVITY ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
model = genai.GenerativeModel('gemini-Embedding-1')

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
                    
                    # Ultra-Bright Colors for Dark Mode Contrast
                    entity_colors = {
                        "ORDER": "#FF3333",      # Bright Red
                        "DELIVERY": "#3399FF",   # Bright Blue
                        "BILLING": "#FFCC00",    # Bright Yellow
                        "ACCOUNTING": "#00CC66", # Bright Green
                        "PAYMENT": "#E0E0E0",    # Light Grey
                        "MATERIAL": "#9933FF"    # Bright Purple
                    }

                    # Step D: Node Creation (Crash-Proof)
                    for col in df.columns:
                        color = "#888888" 
                        for key in entity_colors:
                            if key in col.upper(): color = entity_colors[key]
                        
                        for val in df[col].dropna().unique():
                            if pd.isna(val) or str(val).strip().lower() == 'nan' or str(val).strip() == '':
                                continue
                            
                            node_id = str(val)
                            if node_id not in seen:
                                # Using safe string parameters guaranteed not to crash the frontend
                                nodes.append(Node(id=node_id, label=f"{col}\n{node_id}", color=color, size=25, shape="dot"))
                                seen.add(node_id)

                    # Step E: Edge Creation (Solid White for Visibility)
                    for i in range(len(df.columns) - 1):
                        for _, row in df.iterrows():
                            u, v = row[i], row[i+1]
                            if pd.notna(u) and pd.notna(v):
                                u_str, v_str = str(u).strip(), str(v).strip()
                                if u_str.lower() != 'nan' and v_str.lower() != 'nan' and u_str != "" and v_str != "":
                                    # White lines, thick width
                                    edges.append(Edge(source=u_str, target=v_str, color="#FFFFFF", width=2))

                    # Step F: Massive Interactive Canvas
                    # Using integer 800 for height to ensure it actually resizes!
                    config = Config(
                        width=1500, 
                        height=800, 
                        directed=True, 
                        physics=True, 
                        hierarchical=False, 
                        nodeHighlightBehavior=True, 
                        highlightColor="#F7A7A6"
                    )
                    
                    # By default, agraph supports Zoom (scroll wheel) and Pan (click & drag)
                    agraph(nodes=nodes, edges=edges, config=config)

                    # Step G: Technical Audit Trail
                    with st.expander("Technical Trace (View SQL & Data)"):
                        st.code(sql, language="sql")
                        st.dataframe(df)

        except Exception as e:
            st.error(f"System Error: {str(e)}")

# --- 6. FOOTER ---
st.markdown("---")
st.caption(" FDE Submission | Architecture: Snowflake + Gemini + Streamlit")
