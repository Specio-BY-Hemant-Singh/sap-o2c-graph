# 🕸️ SAP Order-to-Cash (O2C) Knowledge Graph Agent

## 🚀 Live Demo

> ⚡ **Try the application here:**
> 👉 **https://sap0graph0by0specio.streamlit.app/**

---

## 📌 Overview

Enterprise SAP systems store Order-to-Cash (O2C) data across highly normalized and fragmented relational tables. This makes end-to-end traceability, analytics, and process mining complex and inefficient.

This project builds a **Dynamic Knowledge Graph Layer on top of Snowflake**, enabling:

* Natural language querying of SAP data
* Automated SQL generation using LLMs
* Interactive graph visualization of business processes

---

## 🏗️ Architecture & Tech Stack

| Layer               | Technology                   |
| ------------------- | ---------------------------- |
| Data Warehouse      | Snowflake                    |
| LLM Engine          | Google Gemini 2.5 Flash Lite |
| Backend + UI        | Streamlit                    |
| Graph Visualization | streamlit-agraph (vis.js)    |

---

## 🧠 Key Design Principles

### 1. Relational-to-Graph Projection

Instead of using Neo4j or other graph databases:

* Data remains in **Snowflake**
* Graph is constructed **in-memory**
* Eliminates ETL overhead and sync issues
* Enables **zero-copy analytics**

---

### 2. Semantic Prompt Layer (Text-to-SQL)

The LLM is tightly controlled using:

* Explicit table relationships
* Predefined join paths
* Data normalization rules (handling SAP leading zeros)

Example normalization rule:

```sql
UPPER(LTRIM(CAST(column AS STRING), '0'))
```

This ensures:

* Accurate joins
* No hallucinated relationships
* Production-grade SQL generation

---

### 3. Strict Guardrails

To prevent misuse:

* Only O2C-related queries are allowed
* Out-of-scope queries return:

  ```
  UNSUPPORTED_QUERY
  ```
* Backend enforces domain restriction at runtime

---

## 💡 Core Capabilities

### 🔍 End-to-End Traceability

**Query:**

```
Trace the full flow for Sales Order 740506
```

**Output:**
Order → Delivery → Billing → Accounting → Payment

---

### ⚠️ Process Gap Detection

**Query:**

```
Show sales orders without deliveries
```

**Output:**
Identifies fulfillment bottlenecks

---

### 📊 Cross-Module Analytics

**Query:**

```
Which materials have the highest billing frequency?
```

**Output:**
Aggregated insights across SD and FI modules

---

## 🛠️ Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/sap-o2c-graph.git
cd sap-o2c-graph
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Configure Secrets

Create `.streamlit/secrets.toml`:

```toml
GEMINI_KEY = "your_key"

SF_USER = "your_user"
SF_PASSWORD = "your_password"
SF_ACCOUNT = "your_account"

SF_WAREHOUSE = "COMPUTE_WH"
SF_DATABASE = "O2C_GRAPH"
SF_SCHEMA = "RAW_DATA"
```

---

### 4. Run Locally

```bash
streamlit run app.py
```

---

## 📁 Project Deliverables

* ✅ Live Demo (Streamlit)
* ✅ Source Code
* ✅ AI Session Logs (recommended for evaluation)
* ✅ Architecture Documentation

---

## 🎯 Value Proposition

This system demonstrates:

* Enterprise-grade **LLM + Data integration**
* **Zero-ETL graph analytics**
* Scalable approach to **process intelligence in SAP**
* Practical Forward Deployed Engineer (FDE) problem-solving


---
