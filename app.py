import streamlit as st
import snowflake.connector
import google.generativeai as genai
from streamlit_agraph import agraph, Node, Edge, Config

# --- CONFIGURATION ---
genai.configure(api_key=st.secrets["GEMINI_KEY"])
# Try using the 'latest' tag which is more reliable across regions
model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

def get_db_connection():
    return snowflake.connector.connect(
        user=st.secrets["SF_USER"],
        password=st.secrets["SF_PASSWORD"],
        account=st.secrets["SF_ACCOUNT"],
        warehouse="COMPUTE_WH",
        database="O2C_GRAPH",
        schema="RAW_DATA"
    )

# --- THE BRAIN: SEMANTIC PROMPT ---
# This tells Gemini exactly how to link your tables
METADATA_PROMPT = """
You are a SAP Data Expert. Generate Snowflake SQL to answer the user's request.
SCHEMA MAP:
1. SALES_ORDER_HEADERS (SALESORDER, SOLDTOPARTY, TOTALNETAMOUNT)
2. DELIVERY_HEADERS (DELIVERYDOCUMENT, REFERENCESDDOCUMENT) -> REFERENCESDDOCUMENT links to SALES_ORDER_HEADERS.SALESORDER
3. BILLING_HEADERS (BILLINGDOCUMENT, REFERENCESDDOCUMENT) -> REFERENCESDDOCUMENT links to DELIVERY_HEADERS.DELIVERYDOCUMENT
4. JOURNAL_ENTRIES (ACCOUNTINGDOCUMENT, REFERENCEDOCUMENT) -> REFERENCEDOCUMENT links to BILLING_HEADERS.BILLINGDOCUMENT
5. PAYMENTS (ACCOUNTINGDOCUMENT, CLEARINGACCOUNTINGDOCUMENT) -> ACCOUNTINGDOCUMENT links to JOURNAL_ENTRIES.ACCOUNTINGDOCUMENT

OUTPUT RULES:
- Return ONLY the SQL.
- Use JOINs to trace the flow.
- If the user asks to 'Trace', select the IDs from all related tables.
"""

st.set_page_config(layout="wide")
st.title("🕸️ SAP Order-to-Cash Knowledge Graph")

# Sidebar for Chat
with st.sidebar:
    st.header("Chat with Graph")
    user_input = st.text_input("Analyze anything (e.g. 'Trace flow for Sales Order 740506')")

if user_input:
    # 1. AI generates the SQL
    response = model.generate_content(f"{METADATA_PROMPT} \n User Request: {user_input}")
    sql_query = response.text.replace("```sql", "").replace("```", "").strip()
    
    # 2. Fetch data from Snowflake
    conn = get_db_connection()
    df = conn.cursor().execute(sql_query).fetch_pandas_all()
    
    # 3. Build the Graph Nodes and Edges
    nodes = []
    edges = []
    
    # Logic to create nodes from the dataframe columns
    for col in df.columns:
        for val in df[col].unique():
            if val:
                nodes.append(Node(id=str(val), label=f"{col}: {val}", size=15))
    
    # Simple logic to link consecutive columns in the result
    for i in range(len(df.columns) - 1):
        for _, row in df.iterrows():
            if row[i] and row[i+1]:
                edges.append(Edge(source=str(row[i]), target=str(row[i+1])))

    # 4. Display Graph
    config = Config(width=900, height=600, directed=True, physics=True)
    agraph(nodes=nodes, edges=edges, config=config)
    
    st.write("### Data Source")
    st.dataframe(df)
