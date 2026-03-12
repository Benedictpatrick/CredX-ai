# CredAI

**AI-Powered Corporate Credit Decisioning Platform**

CredAI is an intelligent credit underwriting system designed for modern lending workflows. It ingests borrower documents and financial data, performs fraud and research analysis, runs an explainable underwriting pipeline, and generates a committee-ready **Credit Appraisal Memo (CAM)**.

The platform compresses a traditionally slow and manual credit evaluation process into a structured, machine-assisted decision pipeline.

---

# Overview

Corporate lending teams often work across fragmented data sources, manual financial analysis, and slow decision cycles.

CredAI provides a unified system that automates:

* Borrower document ingestion
* Financial data extraction and analysis
* Fraud detection
* External intelligence gathering
* Explainable credit risk scoring
* Automated CAM generation

The result is a faster and more consistent underwriting workflow with transparent reasoning.

---

# System Capabilities

CredAI performs end-to-end preparation of credit recommendations.

Core capabilities include:

* **Document ingestion** for PDFs and financial statements
* **Bank statement and GST synthesis**
* **Fraud detection** using graph-oriented reasoning
* **Secondary research** on litigation, regulatory filings, and news
* **Primary diligence inputs** such as site visits and management interviews
* **Five Cs credit analysis**
* **Bull vs Bear underwriting debate simulation**
* **Reflexion loops for self-critique and improvement**
* **Explainable decisioning**
* **Credit Appraisal Memo generation**

---
## System Architecture
flowchart LR

subgraph User Layer
A[Operator Console - Next.js]
B[Streamlit Dashboard]
end

subgraph API Layer
C[FastAPI Backend]
end

subgraph Orchestration
D[LangGraph Orchestrator]
end

subgraph Intelligence Modules
E[Document Ingestor]
F[Fraud Engine]
G[Research Agent]
H[Underwriter - Five Cs]
I[Bull vs Bear Debate]
J[Reflexion Loop]
end

subgraph Output Layer
K[Decision Engine]
L[CAM Generator]
end

subgraph Data Layer
M[(SQLite Database)]
N[(Vector Store - Chroma)]
O[(Document Storage)]
end

A --> C
B --> C
C --> D

D --> E
D --> F
D --> G
D --> H
D --> I
D --> J

E --> M
F --> M
G --> N
H --> M

J --> K
K --> L

L --> A
L --> B

## Credit Decision Pipeline

flowchart TD

A[Loan Application Submitted]

B[Document Upload]
C[PDF Parsing & Financial Extraction]

D[Fraud Detection]
E[External Research Intelligence]

F[Five Cs Credit Analysis]

G[Bull vs Bear Debate]

H[Reflexion Self Critique]

I[Final Decision]

J[CAM Generation]

A --> B
B --> C
C --> D
C --> E

D --> F
E --> F

F --> G
G --> H

H --> I
I --> J

## Agent Decision Workflow

sequenceDiagram

participant User
participant API
participant Orchestrator
participant Ingestor
participant Fraud
participant Research
participant Underwriter
participant Debate
participant Reflexion
participant Decision

User->>API: Submit Loan Application
API->>Orchestrator: Start Pipeline

Orchestrator->>Ingestor: Parse Documents
Ingestor-->>Orchestrator: Structured Financial Data

Orchestrator->>Fraud: Detect Anomalies
Fraud-->>Orchestrator: Fraud Risk Signals

Orchestrator->>Research: Gather Intelligence
Research-->>Orchestrator: Litigation / News / MCA

Orchestrator->>Underwriter: Compute Five Cs
Underwriter-->>Orchestrator: Risk Score

Orchestrator->>Debate: Bull vs Bear Analysis
Debate-->>Orchestrator: Argument Synthesis

Orchestrator->>Reflexion: Critique Decision
Reflexion-->>Orchestrator: Improved Output

Orchestrator->>Decision: Final Recommendation
Decision-->>User: CAM + Credit Decision




# Output Produced

The system generates a structured credit recommendation including:

* Decision status
* Recommended sanction amount
* Suggested interest rate
* Risk premium
* Risk grade
* Approval conditions or rejection reasons
* Complete **CAM document export (DOCX)**

Possible decisions include:

* `APPROVED`
* `CONDITIONAL_APPROVAL`
* `REJECTED`
* `REFERRED_TO_COMMITTEE`

---

# Core Architecture

CredAI uses a hierarchical orchestrator that coordinates multiple specialized agents.

Pipeline flow:

```
Application
     ↓
Ingestion
     ↓
Fraud + Research Analysis
     ↓
Underwriting (Five Cs)
     ↓
Bull vs Bear Debate
     ↓
Reflexion Loop
     ↓
Final Decision + CAM Generation
```

Each module contributes structured signals used in the final underwriting decision.

---

# Repository Structure

```
credai/
│
├── src/
│   ├── api/                FastAPI application and endpoints
│   ├── orchestrator/       LangGraph orchestration and reflexion loops
│   ├── ingestor/           Document parsing and financial extraction
│   ├── fraud_engine/       Fraud detection and graph analysis
│   ├── research_agent/     Litigation, MCA, and news intelligence
│   ├── recommendation/     Risk scoring, debate engine, CAM generator
│   ├── services/           Application state persistence
│   └── utils/              Shared utilities and helpers
│
├── web/                    Next.js operator console
├── dashboard/              Legacy Streamlit dashboard
├── config/                 Settings and prompts
├── data/                   Uploads, vector store, and database
├── deployment/             Deployment assets
│
├── run.py                  Starts backend + Streamlit
└── docker-compose.yml      Local stack with Ollama
```

---

# System Interfaces

## Modern Operator Console

Located in the `web/` directory and built with **Next.js 14**.

Main routes include:

* `/command-deck` – portfolio surveillance
* `/decision-workbench` – underwriting review
* `/fraud-detective` – anomaly detection
* `/research-dossier` – external intelligence
* `/pipeline-monitor` – agent activity
* `/intake-studio` – application submission

---

## Backend API

Built using **FastAPI**.

Important endpoints:

```
GET    /health
GET    /info

POST   /api/applications
GET    /api/applications

POST   /api/applications/{app_id}/upload
POST   /api/applications/{app_id}/site-visit
POST   /api/applications/{app_id}/interview

POST   /api/applications/{app_id}/run

GET    /api/applications/{app_id}/status
GET    /api/applications/{app_id}/decision
GET    /api/applications/{app_id}/cam
GET    /api/applications/{app_id}/cam.docx

GET    /api/applications/{app_id}/fraud
GET    /api/applications/{app_id}/research
GET    /api/applications/{app_id}/xai
GET    /api/applications/{app_id}/debate
GET    /api/applications/{app_id}/audit-trail
```

---

# Technology Stack

## Backend

* Python 3.11+
* FastAPI
* LangGraph / LangChain
* SQLAlchemy
* SQLite
* ChromaDB
* PyTorch
* XGBoost / LightGBM
* SHAP explainability
* PyMuPDF / Camelot / Tabula
* python-docx

---

## Frontend

* Next.js 14
* TypeScript
* Tailwind CSS
* Zustand
* TanStack Query
* Radix UI
* Lightweight Charts

---

## Optional Model Serving

Local LLM inference can be run using **Ollama**.

Default models:

```
llama3.1:8b
llava:13b
nomic-embed-text
```

The system includes fallback behavior when models are unavailable.

---

# Local Development Setup

## Backend

Create virtual environment and install dependencies:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the API:

```
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

API documentation:

```
http://localhost:8000/docs
```

---

## Frontend

From the `web` directory:

```
npm install
npm run dev
```

Open:

```
http://localhost:3000
```

---

## Streamlit Dashboard

Run the legacy dashboard:

```
streamlit run dashboard/app.py
```

Open:

```
http://localhost:8501
```

---

# Docker Deployment

Run the stack using Docker Compose:

```
docker compose up --build
```

Services exposed:

```
API        → http://localhost:8000
Streamlit  → http://localhost:8501
Ollama     → http://localhost:11434
```

The Next.js frontend should be run separately.

---

# Data Persistence

Runtime data is stored under:

```
data/
```

Key directories:

```
data/uploads/
data/vector_store/
data/experience_library/
data/titan_credit.db
```

The backend stores application state in the SQLite database.

---

# Development Workflow

Recommended workflow:

1. Run the FastAPI backend
2. Run the Next.js frontend
3. Submit applications via the UI
4. Execute the decision pipeline
5. Review results in the decision workbench
6. Export the CAM document

---

# Project Purpose

Corporate credit underwriting is often slow, fragmented, and opaque.

CredAI aims to transform that workflow into an **explainable AI-assisted credit operating system** that improves:

* decision speed
* risk visibility
* underwriting consistency
* documentation quality

---

# License

MIT License
