import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="SAP O2C Knowledge Graph", layout="wide")

# --- 2. SECURE CONFIGURATION ---
try:
    genai.configure(api_key=st.secrets["GEMINI_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error("AI Configuration Error. Check Streamlit Secrets.")

@st.cache_resource
def get_sf_conn():
    return snowflake.connector.connect(
        user=st.secrets["SF_USER"],
        password=st.secrets["SF_PASSWORD"],
        account=st.secrets["SF_ACCOUNT"],
        warehouse=st.secrets["SF_WAREHOUSE"],
        database=st.secrets["SF_DATABASE"],
        schema=st.secrets["SF_SCHEMA"]
    )

def run_query(query):
    with get_sf_conn().cursor() as cur:
        cur.execute(query)
        return cur.fetch_pandas_all()

# --- 3. THE "GOLDEN" SEMANTIC PROMPT ---
# Updated with your actual column names: salesOrder, material, etc.
METADATA_PROMPT = """
You are a Senior SAP Data Engineer. Write Snowflake SQL for the Order-to-Cash process.
CRITICAL: All column names MUST be in double quotes (e.g. "salesOrder").

TABLE MAP:
- SALES_ORDER_HEADERS: Key "salesOrder", "soldToParty"
- SALES_ORDER_ITEMS: Key "salesOrder", "material", "netAmount"
- DELIVERY_HEADERS: Key "deliveryDocument", "referenceSdDocument" (links to "salesOrder")
- BILLING_HEADERS: Key "billingDocument", "referenceSdDocument" (links to "deliveryDocument")
- JOURNAL_ENTRIES: Key "accountingDocument", "referenceDocument" (links to "billingDocument")
- PAYMENTS: Key "accountingDocument", "clearingAccountingDocument"

SQL RULES:
1. Return ONLY SQL. No markdown.
2. Use UPPER(LTRIM(CAST("column" AS STRING), '0')) for all JOINs.
3. If the user asks for 'Trace', join the relevant headers in sequence.
4. If they ask for 'Products' or 'Items', join SALES_ORDER_ITEMS.
"""

# --- 4. UI COMPONENTS ---
st.title("🕸️ SAP Order-to-Cash Knowledge Graph")
st.markdown("---")

with st.sidebar:
    st.header("Graph Agent")
    user_input = st.text_input("Analyze anything:", placeholder="Trace flow for Order 740506")
    
    st.divider()
    if st.button("🚩 Identify Broken Flows"):
        user_input = "Show me sales orders that have no linked delivery documents"
    if st.button("📦 Top Products"):
        user_input = "Which materials are associated with the most billing documents?"

# --- 5. GRAPH ENGINE ---
if user_input:
    with st.spinner("AI Agent querying Snowflake..."):
        try:
            # Step A: AI Reasoning
            response = model.generate_content(f"{METADATA_PROMPT}\nUser Request: {user_input}")
            sql = response.text.strip().replace("```sql", "").replace("```", "")
            
            # Step B: Data Fetch
            df = run_query(sql)

            if df.empty:
                st.info("No data found for this path.")
            else:
                nodes, edges, seen = [], [], set()
                
                # Step C: Entity Color Mapping
                colors = {
                    "salesOrder": "#FF4B4B", 
                    "deliveryDocument": "#29B5E8", 
                    "billingDocument": "#FFD166", 
                    "accountingDocument": "#06D6A0",
                    "material": "#7D3C98" # Purple for Products
                }

                # Step D: Dynamic Graph Construction
                for col in df.columns:
                    for val in df[col].dropna().unique():
                        node_id = str(val)
                        if node_id not in seen:
                            # Use logic to find correct color
                            color = "#999999"
                            for key in colors:
                                if key.lower() in col.lower(): color = colors[key]
                            
                            nodes.append(Node(id=node_id, label=f"{col}: {node_id}", color=color, size=15))
                            seen.add(node_id)

                for i in range(len(df.columns) - 1):
                    for _, row in df.iterrows():
                        u, v = str(row[i]), str(row[i+1])
                        if u != "None" and v != "None" and u != "" and v != "":
                            edges.append(Edge(source=u, target=v))

                # Step E: Rendering
                agraph(nodes=nodes, edges=edges, config=Config(width=1000, height=600, directed=True, physics=True))
                
                with st.expander("Technical Audit Trail"):
                    st.code(sql, language="sql")
                    st.dataframe(df)

        except Exception as e:
            st.error(f"Error: {str(e)}")

st.markdown("---")
st.caption("Final L9 FDE Submission | Optimized for camelCase SAP Schemas")
