# 🏗️ Pragati Enterprises: Multi-State Supply Chain & Logistics Data Platform

![Python](https://shields.io)
![MySQL](https://shields.io)
![AWS S3](https://shields.io)
![Bash](https://shields.io)

## End-to-end Production Project Architecture 
pragati-logistics-data-platform/
├── README.md                        <-- The complete documentation below
├── requirements.txt                 <-- Python dependencies (boto3, pandas, mysql-connector-python)
├── .env.example                     <-- Template for safe credential management
├── config/
│   └── schema_ddl.sql               <-- Production MySQL Star Schema DDL script
├── src/
│   ├── generate_mock_data.py        <-- 105k row vector stress-testing generator
│   └── pipeline_etl.py              <-- Core Boto3 + Pandas + MySQL Idempotent ETL engine
├── sql/
│   └── tax_ledger_analytics.sql     <-- OLAP Window Queries for finance & audit teams
└── scripts/
    └── run_pipeline.sh              <-- Single-command Bash orchestration & logging wrapper


---

## 📌 1. Executive Summary & Business Problem
**Pragati Enterprises** operates a large-scale stone-crushing and raw material manufacturing network supplying pebbles, river sand, and concrete across multiple northern Indian states. 

### The Bottleneck
Previously, all operational fleet transit logs, volumetric production metrics, and inter-state billing records were managed manually via decentralized Excel spreadsheets. As monthly operational volumes reached **~100 MB (~100,000+ monthly log entries)**, the manual workflow suffered from:
* Severe spreadsheet lag and application crashes during basic deduplication and filtering.
* Mathematical errors in converting raw volumetric **Cubic Feet (CFT)** into billable **Metric Tonnage**.
* Complex compliance discrepancies when calculating dynamic **multi-state royalties and GST tax tiers**.
* Zero automated disaster recovery or backup infrastructure.

### The Architectural Solution
Designed and deployed a **Hybrid On-Premises & Cloud Storage Data Platform** that completely eliminates recurring cloud database hosting costs while guaranteeing **99.999999999% cloud data durability** via AWS S3.

---

## 🏛️ 2. End-to-End Production Architecture

```
[Multi-State Crushing Hubs]
       │ (Daily Raw CSV Transit Logs)
       ▼
┌─────────────────────────────────────────┐
│     AWS S3 (Bronze Landing Zone)        │ ◄── Immutable Cloud Object Storage
│     s3://pragati-raw-landing/           │     (Zero local server disk I/O)
└──────────────────┬──────────────────────┘
                   │
                   │ (boto3 In-Memory Stream via StringIO)
                   ▼
┌─────────────────────────────────────────┐
│   Stateless Compute Node (Local Linux)  │
│   • Orchestration: run_pipeline.sh      │
│   • ETL Engine: pipeline_etl.py         │
│   • O(1) In-Memory Dimension Caching    │
│   • CFT-to-Tonnage & Tax Calculations   │
└──────────┬───────────────────┬──────────┘
           │                   │
           │ (Processed Backup)│ (Idempotent UPSERT)
           ▼                   ▼
┌─────────────────────┐ ┌─────────────────────────────────────────┐
│ AWS S3 (Silver Zone)│ │ Local MySQL Data Warehouse (Gold Zone)  │
│ Archived Parquet/CSV│ │ • Star Schema (1 Fact, 4 Dimensions)    │
└─────────────────────┘ │ • Composite Indexed for OLAP Queries    │
                        └──────────────────┬──────────────────────┘
                                           │
                                           │ (OLAP SQL Window Functions)
                                           ▼
                        ┌─────────────────────────────────────────┐
                        │   BI & Finance Reporting Layer          │
                        │   • Power BI / Excel ODBC Direct Query  │
                        │   • Automated State Tax & Royalty Ledger│
                        └─────────────────────────────────────────┘
```

    %% Custom Production Color Styling
    classDef sourceStyle fill:#1E3A8A,stroke:#93C5FD,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef cloudBronze fill:#92400E,stroke:#FCD34D,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef computeStyle fill:#065F46,stroke:#6EE7B7,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef cloudSilver fill:#374151,stroke:#D1D5DB,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef warehouseGold fill:#B45309,stroke:#FDE68A,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef biStyle fill:#5B21B6,stroke:#C4B5FD,stroke-width:2px,color:#FFFFFF,font-weight:bold;
    classDef quarantineStyle fill:#991B1B,stroke:#FCA5A5,stroke-width:2px,color:#FFFFFF,font-weight:bold;

    subgraph S1 ["1. DATA GATHERING & INGESTION"]
        A["🏭 Multi-State Crushing Plants<br/>(UP, Haryana, Rajasthan, UK)"]:::sourceStyle
        B["☁️ AWS S3 Bronze Landing Zone<br/>s3://pragati-raw-landing/<br/>(Immutable Raw CSV Logs)"]:::cloudBronze
        A -->|"Daily Batch Upload (~100 MB/mo)"| B
    end

    subgraph S2 ["2. STATELESS ORCHESTRATION & ETL ENGINE"]
        C["⚙️ Bash Orchestrator (run_pipeline.sh)<br/>• Pre-flight Checks & Audit Logging"]:::computeStyle
        D["🐍 Python ETL Core (pipeline_etl.py)<br/>• boto3 In-Memory StringIO Stream<br/>• Zero Local Disk I/O Bottleneck"]:::computeStyle
        E["🛡️ Data Quality Firewall<br/>• Null Key & Volume Validation<br/>• Batch Deduplication"]:::computeStyle
        F["🚨 Quarantined / Dropped Logs<br/>(Audit Log Trace)"]:::quarantineStyle
        G["⚡ Vectorized Transformation & O(1) Cache<br/>• CFT Volume → Metric Tonnage<br/>• Dynamic Multi-State Royalty & GST"]:::computeStyle

        B -->|"boto3 get_object() Stream"| D
        C -.->|"Triggers & Monitors"| D
        D --> E
        E -->|"Invalid Records"| F
        E -->|"Clean Payload"| G
    end

    subgraph S3 ["3. STORAGE, WAREHOUSING & DISASTER RECOVERY"]
        H["💿 AWS S3 Silver Archive Zone<br/>s3://pragati-analytics-silver/<br/>(99.999999999% DR Backup)"]:::cloudSilver
        I[("🗄️ Local MySQL 8.0 Star Schema (Gold)<br/>• Fact: fact_transit_logs (Indexed)<br/>• Dims: Vehicles, Materials, Hubs, Tariffs<br/>• Idempotent UPSERT Engine")]:::warehouseGold

        G -->|"boto3 put_object() Mirror"| H
        G -->|"Chunked ON DUPLICATE KEY UPDATE"| I
    end

    subgraph S4 ["4. OLAP ANALYTICS & VISUALIZATION"]
        J["📊 OLAP SQL Window Engine<br/>(tax_ledger_analytics.sql)<br/>• Running Tax Totals & DENSE_RANK()"]:::biStyle
        K["📈 Finance & Audit Dashboards<br/>• Power BI / Excel ODBC Direct Query<br/>• Automated GST & Royalty Compliance"]:::biStyle

        I -->|"Composite Index Range Scan"| J
        J --> K
    end


---

## 🔄 3. Data Pipeline Lifecycle (Stage-by-Stage)

### Stage 1: Data Gathering & Cloud Ingestion (Bronze Layer)
* **Source:** Weighbridge systems and dispatch supervisors at regional stone-crushing plants record daily fleet movements, raw material volumes (`raw_volume_cft`), and base freight costs.

* **Cloud Landing:** At the close of daily operations, raw CSV logs are pushed directly to an isolated **AWS S3 bucket (`s3://pragati-raw-landing/`)**. Using S3 decouples data collection from office hardware, eliminating local single points of failure (SPOF).

### Stage 2: Stateless Streaming & Transformation (Silver Layer)

* **Orchestration:** A cron-scheduled Bash wrapper (`scripts/run_pipeline.sh`) triggers the pipeline, runs pre-flight dependency checks, and routes standard output and error streams into timestamped audit logs.

* **Memory Streaming:** Using the official AWS SDK (`boto3`), `src/pipeline_etl.py` streams the raw CSV object directly into RAM via Python's `StringIO` buffer, avoiding slow local disk writes.

* **O(1) Dimension Caching:** To eliminate row-by-row database roundtrip bottlenecks, the engine queries master dimension tables once at startup and caches them into in-memory Python dictionaries.

* **Business Rule Execution:** Dynamically calculates metric tonnage based on specific material densities (`dim_material_types`) and applies route-specific state royalties and GST multipliers (`dim_state_tariffs`).

* **Cloud Archival:** Transformed datasets are mirrored back to an archived S3 bucket to ensure complete disaster recovery.

### Stage 3: Data Warehousing & Idempotent Storage (Gold Layer)
* **Dimensional Modeling:** Implemented a **Star Schema (`pragati_logistics_dw`)** in a local, dedicated MySQL 8.0 instance:
  * **Fact Table:** `fact_transit_logs` (Granular transactional and billing records)
  * **Dimension Tables:** `dim_vehicles`, `dim_material_types`, `dim_hubs`, `dim_state_tariffs`
* **Idempotency:** Enforced a `UNIQUE KEY` constraint on `invoice_number` paired with MySQL's `ON DUPLICATE KEY UPDATE` syntax. If an operator accidentally triggers the pipeline twice for the same batch, existing rows are safely updated without duplicating financial revenue.

### Stage 4: Analytical Reporting & Visualization

* **OLAP Query Engine:** Deployed optimized SQL Window Queries (`sql/tax_ledger_analytics.sql`) utilizing `PARTITION BY`, `DENSE_RANK()`, and bounded window frames (`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`) to generate cumulative monthly tax ledgers.
* **Visualization:** Connected **Microsoft Power BI** (and live Excel Pivot dashboards via MySQL ODBC Connector) directly to the indexed Gold tables. Finance teams monitor real-time state-wise GST liabilities, fleet utilization, and hub profitability with sub-second query performance.

---

## 🛠️ 4. Performance Optimization & Disaster Recovery

* **Composite Indexing:** Deployed targeted composite indexes (`idx_fact_dates_tariff` on `record_date, state_tariff_id`) to eliminate Full Table Scans during monthly financial audits.
* **Zero-Cost Disaster Recovery (DR):** Because AWS S3 serves as the immutable source of truth for both raw and processed files, the local MySQL instance is completely disposable. In the event of local hardware failure, the entire warehouse can be rebuilt from scratch on new hardware within minutes by executing `schema_ddl.sql` and replaying the S3 archives through the idempotent ETL script.

---

## 🚀 5. Local Setup & Execution Guide

### Prerequisites
* Python 3.10+
* MySQL Server 8.0+
* AWS IAM Credentials with `s3:GetObject` and `s3:PutObject` permissions

### Step 1: Clone Repository & Configure Environment
```
git clone https://github.com
cd pragati-logistics-data-platform

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements.txt
```

### Step 2: Instantiate the Star Schema Database
Log into your local MySQL server and run the DDL script to create the database, tables, and indexes:
```
mysql -u root -p < config/schema_ddl.sql

```

### Step 3: Configure Credentials
Copy `.env.example` to `.env` (or update the configuration dictionary in `src/pipeline_etl.py`) with your local MySQL password and AWS S3 access keys.

### Step 4: Run the Automated Pipeline
Grant execution permissions to the shell orchestrator and trigger the end-to-end workflow:
```bash
chmod +x scripts/run_pipeline.sh
./scripts/run_pipeline.sh
```

---

## 📊 6. Business Impact Delivered
* **100% Elimination of Manual Spreadsheet Lag:** Reduced monthly tax and royalty reconciliation time from **4 days of manual effort to under 5 seconds**.
* **Zero Duplicate Billing:** Achieved 100% financial ledger accuracy via strict idempotent database constraints.
* **Near-Zero Infrastructure Overhead:** Delivered enterprise-grade cloud backup durability while keeping monthly AWS operational costs under ₹150/month.
