import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="SAP O2C Knowledge Graph", layout="wide")

# Custom CSS for a more "Enterprise" look
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    .stTextInput > div > div > input { background-color: #1A1C24; color: white; border: 1px solid #3E424B; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONNECTIVITY ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

@st.cache_resource
def get_sf_conn():
    return snowflake.connector.connect(
        user=st.secrets["SF_USER"], password=st.secrets["SF_PASSWORD"],
        account=st.secrets["SF_ACCOUNT"], warehouse=st.secrets["SF_WAREHOUSE"],
        database=st.secrets["SF_DATABASE"], schema=st.secrets["SF_SCHEMA"]
    )

def run_query(query):
    with get_sf_conn().cursor() as cur:
        cur.execute(query)
        return cur.fetch_pandas_all()

# --- 3. REFINED SEMANTIC MAP (Fixes the SQL Error) ---
METADATA_PROMPT = """
You are a Senior SAP Data Architect. Write Snowflake SQL for the O2C flow.
IMPORTANT: Wrap ALL column names in double quotes.

SCHEMA LINKS (The "Golden Path"):
1. SALES_ORDER_HEADERS: Key is "salesOrder"
2. DELIVERY_ITEMS: Link "referenceSdDocument" matches SALES_ORDER_HEADERS."salesOrder"
3. BILLING_ITEMS: Link "referenceSdDocument" matches DELIVERY_ITEMS."deliveryDocument"
4. JOURNAL_ENTRIES: Link "referenceDocument" matches BILLING_ITEMS."billingDocument"
5. PAYMENTS: Link "accountingDocument" matches JOURNAL_ENTRIES."accountingDocument"

SQL RULES:
- Return ONLY SQL.
- Use LTRIM(CAST("col" AS STRING), '0') for ALL joins to handle leading zeros.
- To 'Trace', join through the ITEMS tables to find the links, but select Header IDs for the final graph.
- If the user asks for materials, include SALES_ORDER_ITEMS."material".
"""

# --- 4. UI ---
st.title("🕸️ SAP Order-to-Cash Knowledge Graph")
st.caption("AI-Powered Process Mining & Relationship Discovery")

with st.sidebar:
    st.header("Graph Agent")
    user_input = st.text_input("Analyze:", placeholder="Trace flow for Order 740506")
    
    st.divider()
    if st.button("🚩 Broken Flows (No Delivery)"):
        user_input = "Show me Sales Orders that exist in SALES_ORDER_HEADERS but have no entry in DELIVERY_ITEMS"
    if st.button("📦 Top Products"):
        user_input = "Which materials in SALES_ORDER_ITEMS have the most billing documents?"

# --- 5. THE GRAPH ENGINE ---
if user_input:
    with st.spinner("🤖 AI Agent navigating Snowflake..."):
        try:
            # Step A: AI Reasoning
            response = model.generate_content(f"{METADATA_PROMPT}\nUser Request: {user_input}")
            sql = response.text.strip().replace("```sql", "").replace("```", "")
            
            # Step B: Execution
            df = run_query(sql)

            if df.empty:
                st.info("No data found for this path. Try a different document ID.")
            else:
                nodes, edges, seen = [], [], set()
                
                # Step C: Aesthetic Color & Icon Mapping
                colors = {
                    "ORDER": "#FF4B4B", "DELIVERY": "#29B5E8", 
                    "BILLING": "#FFD166", "ACCOUNTING": "#06D6A0", 
                    "PAYMENT": "#FFFFFF", "MATERIAL": "#B19CD9"
                }

                # Step D: Node Construction
                for col in df.columns:
                    # Logic to identify node level for hierarchical layout
                    level = 0
                    if "ORDER" in col.upper(): level = 1
                    if "DELIVERY" in col.upper(): level = 2
                    if "BILLING" in col.upper(): level = 3
                    if "ACCOUNTING" in col.upper(): level = 4
                    if "PAYMENT" in col.upper(): level = 5

                    for val in df[col].dropna().unique():
                        node_id = str(val)
                        if node_id not in seen:
                            color = "#999999"
                            for key in colors:
                                if key in col.upper(): color = colors[key]
                            
                            nodes.append(Node(
                                id=node_id, label=f"{col}\n{node_id}", 
                                color=color, size=20, font={'color': 'white', 'size': 12}
                            ))
                            seen.add(node_id)

                # Step E: Edge Construction
                for i in range(len(df.columns) - 1):
                    for _, row in df.iterrows():
                        u, v = str(row[i]), str(row[i+1])
                        if u != "None" and v != "None" and u != "" and v != "":
                            edges.append(Edge(source=u, target=v, color="#4E535E", width=2))

                # Step F: Appealing Configuration (Hierarchical Flow)
                config = Config(
                    width=1200, height=600, 
                    directed=True, 
                    hierarchical=True, # This makes the graph look like a process flow
                    direction="LR",   # Left to Right
                    nodeHighlightBehavior=True, 
                    highlightColor="#F7A7A6",
                    collapsible=False,
                    physics=False # Static layout for process flows is much cleaner
                )
                
                agraph(nodes=nodes, edges=edges, config=config)
                
                # Step G: Audit Trail
                with st.expander("Technical Audit (SQL & Data)"):
                    st.code(sql, language="sql")
                    st.dataframe(df)

        except Exception as e:
            st.error(f"SQL Error: {str(e)}")

st.markdown("---")
st.caption(" Forward Deployed Engineer | Hemant Singh | Final Submission")
