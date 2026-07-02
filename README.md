# 🧠 EKOS — AI Enterprise Knowledge Operating System

> A production-grade, multi-agent RAG platform that unifies enterprise data (PDFs, Emails, Excel, SQL, Images, and more) into a single intelligent system powered by 10 specialized AI agents.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange?logo=mysql)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Orchestration-purple)
![Groq](https://img.shields.io/badge/Groq-LLM_Inference-red)

---

## 🚀 What Makes This Different

This is **NOT** another RAG chatbot. Instead of asking *"What's in this PDF?"*, users ask:

> **"Why did Machine X fail three times this month?"**

EKOS orchestrates **10 specialized AI agents** to search across documents, query databases, analyze images, traverse knowledge graphs, and verify facts — delivering cited, verified answers.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                 REACT FRONTEND                    │
│  Chat │ Documents │ Evaluation │ Admin │ Dashboard│
└──────────────────┬───────────────────────────────┘
                   │ REST API / SSE
┌──────────────────┴───────────────────────────────┐
│              FASTAPI BACKEND                      │
│  ┌────────────────────────────────────────────┐  │
│  │     MULTI-AGENT ORCHESTRATOR (LangGraph)   │  │
│  │  Planner → Retriever → SQL → Vision →      │  │
│  │  Graph → Reasoning → Critic → Fact Check → │  │
│  │  Memory → Report Generator                 │  │
│  └────────────────────────────────────────────┘  │
│  ┌─────────┐ ┌──────┐ ┌────────┐ ┌───────────┐ │
│  │  FAISS  │ │ BM25 │ │Reranker│ │ Knowledge │ │
│  │ (Dense) │ │(Sparse│ │        │ │   Graph   │ │
│  └─────────┘ └──────┘ └────────┘ └───────────┘ │
│  ┌─────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │  MySQL  │ │ File Storage │ │ FAISS Index  │ │
│  └─────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────────────────────────────┘
```

---

## 🤖 Agent System

| Agent | Role |
|-------|------|
| **Planner** | Decomposes complex queries into sub-tasks |
| **Retriever** | Hybrid RAG (FAISS + BM25 + Reranking) |
| **SQL Agent** | Natural language → SQL query execution |
| **Vision Agent** | Image analysis & OCR |
| **Graph Agent** | Knowledge graph traversal |
| **Memory Agent** | Conversation & long-term memory |
| **Reasoning Agent** | Evidence synthesis |
| **Critic Agent** | Answer quality assessment |
| **Fact Checker** | Claim verification against sources |
| **Report Generator** | Structured response formatting |

---

## 🛠️ Tech Stack (All Free Tier)

| Layer | Technology |
|-------|-----------|
| LLM | Groq Cloud (Llama 3, Mixtral) |
| Embeddings | Google Generative AI (text-embedding-004) |
| Vector Store | FAISS |
| Database | MySQL 8.0 |
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 |
| Agent Orchestration | LangGraph |
| Evaluation | RAGAS + DeepEval |
| Experiment Tracking | MLflow |
| CI/CD | GitHub Actions |

---

## 📦 Quick Start & End-to-End Docker Deployment

EKOS is fully containerized and ships with a `docker-compose.yml` file that orchestrates the entire application end-to-end (Frontend, Backend API, and MySQL Database). 

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- Groq API Key ([free](https://console.groq.com))
- Google AI API Key ([free](https://aistudio.google.com))

### 1. Environment Configuration
Navigate to the `backend` folder and create your environment file:
```bash
cd backend
cp .env.example .env
```
Edit the `.env` file and insert your respective API keys (`GROQ_API_KEY`, `GOOGLE_API_KEY`, etc.).

### 2. End-to-End Docker Deployment
From the **root directory** of the project, spin up the entire cluster:
```bash
docker-compose up --build -d
```
*What happens during this step?*
1. **MySQL Database**: The `db` container starts, initializes the `ekos_db`, and automatically runs the `setup_db.sql` and `seed_data.sql` scripts from the `backend/scripts` volume mount to populate the initial tables and schemas.
2. **FastAPI Backend**: The `backend` container builds its Python 3.11 environment, installs requirements, waits for the database to be healthy, and starts the Uvicorn ASGI server on port `8000`.
3. **React Frontend**: The `frontend` container builds a production optimized React bundle via Node.js and serves it using a lightweight Nginx web server on port `3000`.

### 3. Access the Application
Once the containers are running (verify with `docker-compose ps`), access the services at:
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MLflow Tracking Server** (if configured): [http://localhost:5000](http://localhost:5000)

### 4. Shutting Down
To stop the application and remove containers while preserving your database volumes:
```bash
docker-compose down
```
To wipe everything including the database volume, run `docker-compose down -v`.

---

## 📊 Evaluation Metrics

| Metric | Framework |
|--------|-----------|
| Answer Relevance | RAGAS |
| Faithfulness | RAGAS |
| Context Precision | RAGAS |
| Context Recall | RAGAS |
| Hallucination Rate | DeepEval |
| Latency | Custom |
| Agent Success Rate | Custom |
| Tool Selection Accuracy | Custom |

## 🔄 Step-by-Step Execution Flow (Scenario)

To understand how EKOS orchestrates its agent network, let's look at the lifecycle of a single user query:

> **User Query:** *"Why did Machine X (MCH-X001) fail in June 2024 and how much did it cost?"*

```mermaid
sequenceDiagram
    autonumber
    actor User as React Client
    participant API as FastAPI Gateway
    participant Plan as Planner Agent
    participant SQL as SQL Agent
    participant Ret as Retriever Agent
    participant KG as KG Agent
    participant Fact as Fact-Checker Agent
    participant UI as SSE Output

    User->>API: Submits query
    Note over API: PII Masking & Prompt Guard scan
    API->>Plan: Trigger LangGraph Orchestrator
    Note over Plan: Decomposes query into 3 parallel sub-tasks
    
    rect rgb(240, 245, 255)
        Note over Plan, KG: Parallel Agent Execution
        Plan->>SQL: Task 1: Find incident logs & costs
        SQL->>SQL: Generates SELECT queries on MySQL
        Plan->>Ret: Task 2: Search text docs & emails
        Ret->>Ret: Runs Hybrid Search (FAISS + BM25)
        Plan->>KG: Task 3: Map machine topology
        KG->>KG: Traverses JSON Knowledge Graph
    end

    SQL-->>Fact: Returns $4,500 cost & 4.5 hrs downtime
    Ret-->>Fact: Returns email thread mentioning clamp leak at junction B7
    KG-->>Fact: Returns location (Floor East, Line-3)
    
    Note over Fact: Cross-references LLM answer with raw data sources
    Fact-->>API: Validates response (Confidence: 98%)
    API-->>User: Streams answer via Server-Sent Events (SSE)
```

## 🏗️ Detailed Project Pipelines & Workflows

EKOS is driven by several robust, end-to-end pipelines working concurrently to maintain system state, ingest knowledge, orchestrate agents, evaluate outputs, and automate deployments.

### 1. The Multi-Agent Execution Pipeline (LangGraph Workflow)
The execution of a query follows a strict LangGraph-driven routing process:
1. **Inbound Security and Sanitization**: The request arrives via `POST /api/query`. The backend runs a Prompt Injection detection middleware and a PII mask filter to replace sensitive values (names, addresses) before sending anything to the LLMs.
2. **Long-Term Memory Search**: The `MemoryAgent` pulls recent conversation state and user profiles from the MySQL database to add relevant semantic context.
3. **Structured Plan Generation**: The `PlannerAgent` executes an LLM call to break the user query into component tasks. Each task specifies a target specialist agent (`RETRIEVER`, `SQL_AGENT`, `VISION`, or `GRAPH`) and key instructions.
4. **Conditional Routing Execution**:
   - If both unstructured data and structured metrics are needed, the orchestrator routes to the `RetrieverAgent` first, then the `SQLAgent`.
   - The specialist nodes run their tasks synchronously or in parallel, modifying the shared `AgentState` object.
5. **Synthesis & Reasoning**: The `ReasoningAgent` gathers the output text logs from the vector database, SQL return values, and knowledge graph relations, building a unified response.
6. **Double-Verification Quality Loop**:
   - The `CriticAgent` evaluates the response on relevance, coherence, and accuracy. If the score is below `0.6`, it sends instructions back to the `ReasoningAgent` for a single retry.
   - The `FactCheckerAgent` parses distinct factual claims and maps them to citations in the retrieved text to ensure no hallucinations occurred.
7. **Streaming Output Generator**: The `ReportGeneratorAgent` reformats the output into structured plaintext, removes markdown headers/bold signs, appends a dedicated "EVALUATION METRICS" footer, and streams the result to the React UI using Server-Sent Events (SSE).

---

### 2. The Knowledge Graph Pipeline
The Knowledge Graph in EKOS tracks the physical topology, human operators, and component relationships of the factory floor.
1. **Entity & Schema Definition**: Uses node schemas for Machines, Lines, Technicians, and Parts; with 10 edge relationship types (e.g., `part_of`, `maintained_by`).
2. **Activation**: When the `PlannerAgent` identifies queries referring to parts, locations, maintenance personnel, or dependency relationships, it schedules a `GRAPH` agent sub-task.
3. **Entity Term Extraction & Subgraph Traversal**: The `GraphAgent` extracts terms from the sub-task description, searches the `KnowledgeGraph` singleton (via NetworkX), and performs a Breadth-First Search (BFS) to extract neighboring entities.
4. **Context Synthesis**: Relationships are serialized and output as `graph_summary`. This is fed to the reasoning agent to explain mechanical chains-of-failure. The backend also exports the visual subgraph node-link structure to render interactive D3.js topology maps on the React frontend.

---

### 3. Ingestion & Retrieval Synchronization Pipeline (Hybrid RAG)
To search documents reliably, EKOS runs a dual-engine (dense + sparse) synchronization pipeline:
1. **Document Upload**: Raw files (PDFs, Word, Excel, Email threads) are uploaded through the FastAPI `/api/documents/upload` endpoint.
2. **Dynamic Text Extraction**: Uses specialized library hooks: `PyMuPDF` for PDFs, `python-docx` for Word, `pandas` for Excel, and `Tesseract OCR` for image scans.
3. **Recursive Chunking & Dense Embedding**: Extracted text is split into overlapping chunks and embedded using Google's `models/text-embedding-004` API to produce 768-dimensional vectors stored in a FAISS index.
4. **Sparse Indexing & Metadata Sync**: When search queries execute, the `SparseRetriever` checks local metadata caches and updates the `rank-bm25` index on the fly.
5. **Hybrid Retrieval with RRF**: Merges FAISS (Dense) and BM25 (Sparse) retrieval via Reciprocal Rank Fusion (RRF), followed by a cross-encoder model reranking to isolate the top 5 most relevant passages.

---

### 4. Evaluation & Telemetry Pipeline (RAGAS + DeepEval)
To ensure production reliability, every generated response goes through an evaluation pipeline:
1. **Metric Computation**: After a response is streamed to the user, background tasks trigger RAGAS and DeepEval to compute:
   - *Faithfulness* (Did the response hallucinate beyond retrieved context?)
   - *Answer Relevance* (Did it actually answer the user's question?)
   - *Context Precision/Recall* (Were the retrieved chunks high quality?)
2. **Experiment Tracking via MLflow**: Computed scores, along with LLM hyper-parameters (temperature, model name), latency metrics, and total token usage, are bundled and sent to an MLflow Tracking Server (`http://localhost:5000`).
3. **Continuous Monitoring**: Admins can view these metrics in the EKOS Admin Dashboard to identify degrading retrieval quality or poor model configurations over time.

---

### 5. CI/CD Pipeline (GitHub Actions)
The project leverages automated Continuous Integration and Continuous Deployment pipelines defined in `.github/workflows`:
1. **Backend CI (`backend-ci.yml`)**: On every push to `main` or pull request, a GitHub Action spins up a Python 3.11 runner, installs dependencies, lints the codebase with `ruff`, and executes the Pytest test suite, ensuring no breaking changes to the FastAPI routes or agent logic.
2. **Frontend CI (`frontend-ci.yml`)**: A separate workflow triggers for frontend changes, utilizing a Node.js runner to install dependencies and run a production build (`npm run build`) to catch compilation errors, linting issues, or breaking React component changes.

---

## 📁 Project Structure

```
enterprise-knowledge-os/
├── backend/
│   ├── app/
│   │   ├── agents/          # 10 AI agents + orchestrator
│   │   ├── api/             # FastAPI routes & middleware
│   │   ├── db/              # Database, vector store, knowledge graph
│   │   ├── evaluation/      # RAGAS, DeepEval, MLflow
│   │   ├── ingestion/       # Document parsing & embedding pipeline
│   │   ├── llm/             # Groq client & prompt management
│   │   ├── rag/             # Hybrid retrieval pipeline
│   │   ├── security/        # Auth, RBAC, PII masking
│   │   └── utils/           # Logging & exceptions
│   ├── prompts/             # Agent prompt templates (YAML)
│   ├── scripts/             # DB setup & seed scripts
│   ├── tests/               # Pytest test suite
│   └── data/                # Sample enterprise documents
├── frontend/
│   └── src/
│       ├── components/      # Reusable UI components
│       ├── pages/           # App pages
│       ├── services/        # API integration
│       ├── context/         # React context providers
│       └── hooks/           # Custom React hooks
└── .github/workflows/       # CI/CD pipelines
```

---

## 🔒 Security Features
- JWT authentication with refresh tokens
- Role-based access control (Admin, Analyst, Viewer)
- PII masking before LLM calls
- Prompt injection detection
- Rate limiting
- Audit logging

---

## 📜 License
MIT
