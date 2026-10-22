# SentinelLog-AI: Complete System Analysis & Project Documentation

> Comprehensive audit, architectural mapping, file-by-file inventory, implementation status, gap analysis, prioritized implementation roadmap, and developer guide for **SentinelLog-AI**.

---

## Table of Contents

1. [Executive Summary & System Architecture](#1-executive-summary--system-architecture)
2. [Exhaustive File-by-File Inventory](#2-exhaustive-file-by-file-inventory)
   - [2.1 Project Root](#21-project-root)
   - [2.2 Core Backend Infrastructure](#22-core-backend-infrastructure)
   - [2.3 Alembic Database Migrations](#23-alembic-database-migrations)
   - [2.4 Functional Modules](#24-functional-modules)
   - [2.5 Documentation & Architecture Assets](#25-documentation--architecture-assets)
3. [Implemented & Completed Features](#3-implemented--completed-features)
4. [Remaining & Missing Implementations (Gap Analysis)](#4-remaining--missing-implementations-gap-analysis)
5. [Prioritized Implementation Plan & Execution Roadmap](#5-prioritized-implementation-plan--execution-roadmap)
6. [Known Bugs & Critical Blockers](#6-known-bugs--critical-blockers)
7. [Environment & Setup Guide](#7-environment--setup-guide)

---

## 1. Executive Summary & System Architecture

**SentinelLog-AI** is a multi-tenant, AI-assisted Security Information and Event Management (SIEM) log analysis platform. Modern enterprise infrastructures generate massive volumes of routine system and security logs. Routing every log line through a Large Language Model (LLM) is computationally unfeasible and economically prohibitive. 

SentinelLog-AI operates on a tiered triage architecture:
1. **High-Volume Ingestion**: Ingests high-throughput raw security logs via FastAPI and buffers them into message queues (Redis Streams).
2. **First-Stage ML Triage**: Fast, lightweight Machine Learning classifiers categorize incoming events by severity and anomaly patterns into `LOW`, `MEDIUM`, and `HIGH` risk tiers.
3. **Second-Stage LLM Deep Analysis**: **Only high-risk anomalies** escape the ML filter and reach the LLM analysis tier. The LLM (powered by models like Qwen 2.5 72B via Hugging Face) unpacks the incident, classifies the attack vector, maps behavior to the **MITRE ATT&CK** matrix, and drafts human-readable mitigation recommendations.
4. **Human-in-the-Loop Decisioning**: Results are stored in PostgreSQL for presentation on an administrative dashboard, ensuring human oversight prior to any remediation action.

```
                    RAW SECURITY LOGS
                            │
                            ▼
                  ┌───────────────────┐
                  │ Log Parsing /     │
                  │ Ingestion API     │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │ Redis Streams     │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │ ML Risk Classifier│
                  │ (LinearSVC / ML)  │
                  └─────────┬─────────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
           LOW            MEDIUM          HIGH
             │              │              │
             │              │              ▼
             │              │     ┌──────────────────┐
             │              │     │ LLM Service      │
             │              │     │ (Qwen 2.5 72B)   │
             │              │     └────────┬─────────┘
             │              │              │
             │              │              ▼
             │              │     • Attack Explanation
             │              │     • MITRE ATT&CK Mapping
             │              │     • Response Recommendation
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                  ┌───────────────────┐
                  │ PostgreSQL Storage│
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │ Admin Dashboard UI│
                  └───────────────────┘
```

---

## 2. Exhaustive File-by-File Inventory

Every file across the repository has been analyzed for its purpose, functional dependencies, and usage context.

### 2.1 Project Root

| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`.gitignore`](file:///d:/SentinelLog-AI/.gitignore) | Git exclusions list. Ignores virtual environments (`.venv`), Python byte-caches (`__pycache__`), environment secrets (`.env`), dataset checkouts, and IDE configurations. | Used by Git during version control operations. |
| [`Readme.md`](file:///d:/SentinelLog-AI/Readme.md) | High-level architectural abstract, 5 core objectives, and ASCII diagram representing the raw log → ML → LLM → Dashboard pipeline. | Project repository landing page for developers and stakeholders. |
| [`requirements.txt`](file:///d:/SentinelLog-AI/requirements.txt) | Python package dependencies including FastAPI, Uvicorn, SQLAlchemy (asyncio), Asyncpg, Psycopg, Alembic, Passlib, Python-Jose, SlowAPI, Scikit-learn, PyTorch, and Hugging Face Hub. | Used by `pip install -r requirements.txt` to initialize Python runtimes. |

---

### 2.2 Core Backend Infrastructure

| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/.env`](file:///d:/SentinelLog-AI/backend/.env) | Local environment variables specifying database connection string, JWT secret key, algorithms, token lifetime intervals, and Hugging Face API key. | Loaded dynamically by `backend/app/core/config.py` via `python-dotenv`. |
| [`backend/.env.example`](file:///d:/SentinelLog-AI/backend/.env.example) | Placeholder environment template file (currently 0 bytes). Intended to document expected `.env` variables without exposing secrets. | To be copied as `.env` by developers during setup. |
| [`backend/app/main.py`](file:///d:/SentinelLog-AI/backend/app/main.py) | FastAPI application entry point. Instantiates the FastAPI app and registers top-level API routers (`health_router`, `llm_router`). | Executed by ASGI server (`uvicorn app.main:app --reload`). |
| [`backend/app/health.py`](file:///d:/SentinelLog-AI/backend/app/health.py) | Health check route (`GET /health`). Tests database connectivity by executing `SELECT 1` via SQLAlchemy async engine. | Registered in `main.py`; polled by container orchestrators, load balancers, or monitoring scripts. |
| [`backend/app/core/config.py`](file:///d:/SentinelLog-AI/backend/app/core/config.py) | Pydantic `BaseSettings` configuration object. Reads and validates environment variables from `backend/.env`. | Imported across backend modules (`database.py`, `security.py`, `health.py`, `llmSservices/api.py`). |
| [`backend/app/core/database.py`](file:///d:/SentinelLog-AI/backend/app/core/database.py) | Initializes SQLAlchemy declarative base `Base`, async engine via `create_async_engine`, session factory `AsyncSessionLocal`, and FastAPI dependency `get_db()`. | Imported by Alembic `env.py`, `health.py`, model definitions, and future repository layers. |
| [`backend/app/core/rate_limiter.py`](file:///d:/SentinelLog-AI/backend/app/core/rate_limiter.py) | Configures `slowapi.Limiter` using client remote IP addresses (`get_remote_address`) to safeguard endpoints against brute-force and DoS attacks. | Available for decorating endpoints in API routers (e.g. auth login, log ingestion). |
| [`backend/app/core/security.py`](file:///d:/SentinelLog-AI/backend/app/core/security.py) | Security and cryptography utilities. Provides password hashing (`bcrypt`), verification, JWT generation (`create_access_token`, `create_refresh_token`), and decoding (`decode_token`). | Imported by authentication and authorization services. |

---

### 2.3 Alembic Database Migrations

| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/app/alembic.ini`](file:///d:/SentinelLog-AI/backend/app/alembic.ini) | Alembic configuration file specifying directory locations, logging directives, and database URL references. | Invoked by Alembic CLI commands (`alembic upgrade`, `alembic revision`). |
| [`backend/app/alembic/env.py`](file:///d:/SentinelLog-AI/backend/app/alembic/env.py) | Alembic environment runner. Imports SQLAlchemy `Base` and model modules (`admin`, `organization`), translates async connection URLs to synchronous drivers (`psycopg`), and runs migrations. | Invoked automatically during migration runs. |
| [`backend/app/alembic/README`](file:///d:/SentinelLog-AI/backend/app/alembic/README) | Standard Alembic auto-generated readme template. | Internal Alembic reference. |
| [`backend/app/alembic/script.py.mako`](file:///d:/SentinelLog-AI/backend/app/alembic/script.py.mako) | Mako template file used by Alembic to scaffold new migration revision scripts. | Used internally by `alembic revision`. |
| [`backend/app/alembic/versions/3e7745dce2ac_initial_schema.py`](file:///d:/SentinelLog-AI/backend/app/alembic/versions/3e7745dce2ac_initial_schema.py) | Migration revision script generating initial tables: `organization` and `admin`, along with indexes and foreign key constraints. | Applied via `alembic upgrade head`. |
| [`backend/app/alembic/versions/bd1c36f6aafb_initial_migration.py`](file:///d:/SentinelLog-AI/backend/app/alembic/versions/bd1c36f6aafb_initial_migration.py) | Empty pass-through migration file. | Revision history node in Alembic chain. |
| [`backend/app/alembic/versions/d6ef470a1a17_fixed_the_admin_and_organization_bug.py`](file:///d:/SentinelLog-AI/backend/app/alembic/versions/d6ef470a1a17_fixed_the_admin_and_organization_bug.py) | Empty pass-through migration file. | Revision history node in Alembic chain. |

---

### 2.4 Functional Modules

#### Admin & Organization Modules
| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/app/modules/admin/models.py`](file:///d:/SentinelLog-AI/backend/app/modules/admin/models.py) | SQLAlchemy model `Admin`. Defines table `admin` with UUID primary key, name, email, phone, hashed password, employee ID, organization foreign key, and active/verified flags. | Linked to `Organization` model and imported in Alembic `env.py`. |
| [`backend/app/modules/organization/models.py`](file:///d:/SentinelLog-AI/backend/app/modules/organization/models.py) | SQLAlchemy model `Organization`. Defines table `organization` with UUID primary key, name, email, phone, hashed password, and status flags. Contains a relationship back to users. | Linked to `Admin` model and imported in Alembic `env.py`. |
| [`backend/app/modules/organization/schemas.py`](file:///d:/SentinelLog-AI/backend/app/modules/organization/schemas.py) | Pydantic models for organization registration, login, password changes, profiles, updates, and admin user creation (`RegisterOrganization`, `LoginOrganization`, `CreateAdmin`, etc.). | Used for request validation and response serialization in organization APIs. |
| [`backend/app/modules/organization/api.py`](file:///d:/SentinelLog-AI/backend/app/modules/organization/api.py) | Declares stubbed endpoint signatures for organization auth, profile updates, and admin user CRUD. Notice: defines standalone `FastAPI()` app instead of an `APIRouter()`; contains unfilled ellipses (`...`). | Intended to be converted to `APIRouter` and registered in `main.py`. |
| [`backend/app/modules/organization/repository.py`](file:///d:/SentinelLog-AI/backend/app/modules/organization/repository.py) | Empty stub file (0 bytes). Intended for direct SQLAlchemy async queries on `Organization` and `Admin`. | Needs implementation to back `services.py`. |
| [`backend/app/modules/organization/services.py`](file:///d:/SentinelLog-AI/backend/app/modules/organization/services.py) | Empty stub file (0 bytes). Intended for organization business logic, password verification, and admin provisioning. | Needs implementation to back `api.py`. |

#### Authentication Module
| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/app/modules/auth/schemas.py`](file:///d:/SentinelLog-AI/backend/app/modules/auth/schemas.py) | Pydantic schemas for authentication: `Token` (access, refresh, token_type), `TokenData` (email), and `LoginRequest` (email, password). | Request/response schemas for login and JWT verification. |
| [`backend/app/modules/auth/api.py`](file:///d:/SentinelLog-AI/backend/app/modules/auth/api.py) | Empty stub file (0 bytes). Intended for authentication endpoints (`/auth/login`, `/auth/refresh`, `/auth/logout`). | Needs router implementation and registration in `main.py`. |
| [`backend/app/modules/auth/dependencies.py`](file:///d:/SentinelLog-AI/backend/app/modules/auth/dependencies.py) | Empty stub file (0 bytes). Intended for FastAPI `Depends()` extractors (e.g., `get_current_admin`, `get_current_organization`, RBAC role checks). | Required across protected endpoints. |
| [`backend/app/modules/auth/service.py`](file:///d:/SentinelLog-AI/backend/app/modules/auth/service.py) | Empty stub file (0 bytes). Intended for credential verification, JWT issuance, and token revocation. | Needs implementation to back `api.py`. |

#### AI Machine Learning Model Module
| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/app/modules/aiModel/dataset/HDFS_2k.log_structured.csv`](file:///d:/SentinelLog-AI/backend/app/modules/aiModel/dataset/HDFS_2k.log_structured.csv) | Structured dataset consisting of 2,000 HDFS log records with 9 active columns (LineId, Date, Time, Pid, Level, Component, Content, EventId, EventTemplate). | Used as training and evaluation data by `main.ipynb`. |
| [`backend/app/modules/aiModel/main.ipynb`](file:///d:/SentinelLog-AI/backend/app/modules/aiModel/main.ipynb) | Jupyter research notebook. Preprocesses dataset, engineers time/frequency features, trains a scikit-learn `LinearSVC` pipeline, evaluates holdouts, and serializes the model. | Research and model artifact training script. |
| [`backend/app/modules/aiModel/hdfs_log_classifier.joblib`](file:///d:/SentinelLog-AI/backend/app/modules/aiModel/hdfs_log_classifier.joblib) | Serialized scikit-learn pipeline artifact (~84 KB) containing trained TF-IDF vectorizer, scaler, and LinearSVC model. | Loaded for log level / risk prediction. |
| [`backend/app/modules/aiModel/schemas.py`](file:///d:/SentinelLog-AI/backend/app/modules/aiModel/schemas.py) | Defines `ModelInput` schema (`content`, `component`, `hour`, `minute`, `second`, `time_gap`, `pid_freq`) and empty placeholder `ModelOutput`. | Validation schema for incoming log feature payloads. |
| [`backend/app/modules/aiModel/api.py`](file:///d:/SentinelLog-AI/backend/app/modules/aiModel/api.py) | APIRouter with `/model/log` endpoint stub. Loads joblib model using hardcoded path `D:\...`; route function `get_log` is unparameterized and returns `None`. Not registered in `main.py`. | Intended to expose ML classification via API. |

#### LLM Analysis Service Module
| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`backend/app/modules/llmSservices/schemas.py`](file:///d:/SentinelLog-AI/backend/app/modules/llmSservices/schemas.py) | Pydantic models: `LogAnalysisRequest` (`raw_log`, `log_type`, `machine`, `extra_context`) and `LLMOutput` (`message`). | Request validation and response typing for LLM analysis endpoints. |
| [`backend/app/modules/llmSservices/promt.py`](file:///d:/SentinelLog-AI/backend/app/modules/llmSservices/promt.py) | Cybersecurity analyst prompt builder. Injects log parameters into a system prompt requiring concise threat assessment without extraneous chatter. | Invoked by `llmSservices/api.py` during log analysis. |
| [`backend/app/modules/llmSservices/api.py`](file:///d:/SentinelLog-AI/backend/app/modules/llmSservices/api.py) | APIRouter `/llm` with `/health` and `/analyze` endpoints. Uses Hugging Face `InferenceClient` to query `Qwen/Qwen2.5-72B-Instruct`. | Registered directly in `main.py`. |

---

### 2.5 Documentation & Architecture Assets

| File Path | Description & Purpose | Where & How It Is Used |
| :--- | :--- | :--- |
| [`Docs/system-design.md`](file:///d:/SentinelLog-AI/Docs/system-design.md) | Comprehensive system architecture specification (SRS) with complete Mermaid diagrams covering Presentation, API, Redis Stream, ML, LLM, Database, and Security controls. | Core architectural reference for the entire system. |
| [`Docs/production_readiness_report.md`](file:///d:/SentinelLog-AI/Docs/production_readiness_report.md) | In-depth engineering audit of the ML classifier. Identifies scikit-learn version mismatch, data leakage, time feature edge cases, and lack of true anomaly labels. | ML engineering reference and deployment prerequisite list. |
| [`Docs/analysis-17-09-2026.md`](file:///d:/SentinelLog-AI/Docs/analysis-17-09-2026.md) | Previous architectural audit documenting project status (~20-25%), security flaws (prompt injection, exception leakage, missing secret fallbacks), and prioritized roadmap. | Historical progress tracking and audit baseline. |
| [`Docs/design.md`](file:///d:/SentinelLog-AI/Docs/design.md) | Microservice architectural proposals, background worker loop design (`worker.py`), database schema discussions for multi-tenancy, and LLM output parsing questions. | Architectural notes and decision record. |
| [`Docs/Alembic-Migration.md`](file:///d:/SentinelLog-AI/Docs/Alembic-Migration.md) | Developer guide detailing Alembic initialization, migration creation, schema upgrades, and `env.py` configuration. | Reference manual for managing database migrations. |
| [`Docs/database.md`](file:///d:/SentinelLog-AI/Docs/database.md) | Instructions for provisioning serverless PostgreSQL databases on Neon using the Neon CLI. | Database infrastructure provisioning reference. |
| [`Docs/docs.md`](file:///d:/SentinelLog-AI/Docs/docs.md) | Brief scratch note regarding TF-IDF and Linear SVM feature extraction. | Scratch notes. |
| [`Docs/Introduction.md`](file:///d:/SentinelLog-AI/Docs/Introduction.md) | Empty file (0 bytes). | Placeholder for project introduction. |
| [`Docs/Ml_model.md`](file:///d:/SentinelLog-AI/Docs/Ml_model.md) | Stub file (2 bytes). | Placeholder for ML documentation. |
| [`Docs/mermaid-diagram.png`](file:///d:/SentinelLog-AI/Docs/mermaid-diagram.png) | High-resolution visual rendering of system architecture Mermaid diagrams (~2.7 MB). | Visual design documentation. |
| [`Docs/authentication/plan.md`](file:///d:/SentinelLog-AI/Docs/authentication/plan.md) | Scratch requirements note outlining user auth flows (login, signup, JWT expiration, auto-refresh, and rate limiting). | Functional requirements for auth module. |
| [`Docs/Design/admin_database.md`](file:///d:/SentinelLog-AI/Docs/Design/admin_database.md) | Detailed schema specification table for the `admin` database entity. | Database design reference for admin model. |
| [`Docs/Design/organization_database.md`](file:///d:/SentinelLog-AI/Docs/Design/organization_database.md) | Detailed schema specification table for the `organization` database entity. | Database design reference for organization model. |
| [`Docs/Design/toekn_database.md`](file:///d:/SentinelLog-AI/Docs/Design/toekn_database.md) | Detailed schema specification table for the polymorphic `token` database entity. | Database design reference for token session tracking. |
| [`Docs/Design/database.md`](file:///d:/SentinelLog-AI/Docs/Design/database.md) | SQLAlchemy code blueprint for polymorphic `Token` entity with check constraints linking either organization or admin. | Database implementation reference. |
| [`Docs/Design/log_database.md`](file:///d:/SentinelLog-AI/Docs/Design/log_database.md) | Empty file (0 bytes). | Placeholder for log database schema documentation. |
| [`Docs/llm-Docs/design.md`](file:///d:/SentinelLog-AI/Docs/llm-Docs/design.md) | Notes advising use of `@app.post` for JSON analysis and enforcing stateless LLM services. | LLM module design principles. |
| [`Docs/llm-Docs/Readme.md`](file:///d:/SentinelLog-AI/Docs/llm-Docs/Readme.md) | Hugging Face CLI setup guide and verified test input/output examples for Qwen 2.5 72B. | Verification testing documentation for LLM analysis. |

---

## 3. Implemented & Completed Features

The following features and components are currently implemented in the codebase:

1. **System & Architectural Design (95% Complete)**
   - Complete architectural blueprints documented in `Docs/system-design.md`.
   - Comprehensive multi-tenant schema specifications for Organization, Admin, Token, and Log tables.
   - Core triage concept established: High-volume raw logs → Fast ML classifier → High-risk only to LLM → Dashboard.

2. **LLM Analysis Integration (`llmSservices`) (85% Complete)**
   - Fully operational integration with Hugging Face Inference API calling `Qwen/Qwen2.5-72B-Instruct`.
   - Pydantic models for incoming requests (`LogAnalysisRequest`) and structured output (`LLMOutput`).
   - Domain-specific cybersecurity prompt builder (`promt.py`).
   - Active `/llm/health` and `/llm/analyze` routes registered and wired into `main.py`.
   - Verified real-world test payloads documented in `Docs/llm-Docs/Readme.md`.

3. **Core Database & Configuration Setup (75% Complete)**
   - Pydantic `BaseSettings` object reading configuration from `.env`.
   - SQLAlchemy async engine and async session maker (`database.py`).
   - Alembic migration environment configured (`alembic.ini`, `env.py`).
   - Initial database migration (`3e7745dce2ac_initial_schema.py`) creating PostgreSQL tables for `organization` and `admin`.
   - Health check endpoint (`GET /health`) actively verifying database connectivity with `SELECT 1`.

4. **Security & Cryptographic Primitives (70% Complete)**
   - Passlib bcrypt password hashing (`get_password_hash`) and verification (`verify_password`).
   - JWT creation (`create_access_token`, `create_refresh_token`) and decoding (`decode_token`) using Python-Jose.
   - SlowAPI rate limiter configured (`rate_limiter.py`).

5. **ML Model Research & Training Prototype (40% Complete)**
   - Structured HDFS log dataset checked into repository (`HDFS_2k.log_structured.csv`).
   - Feature engineering and pipeline training demonstrated in Jupyter notebook (`main.ipynb`).
   - Trained TF-IDF + LinearSVC model artifact exported to disk (`hdfs_log_classifier.joblib`).

---

## 4. Remaining & Missing Implementations (Gap Analysis)

The following areas are incomplete or completely unimplemented:

### 4.1 Authentication & Authorization Module (`backend/app/modules/auth/`)
- `api.py` (0 bytes): No login, signup, token refresh, or logout endpoints exist.
- `service.py` (0 bytes): No business logic for authenticating users, managing password checks, or token handling.
- `dependencies.py` (0 bytes): No FastAPI dependency functions (`get_current_user`, `get_current_admin`, role checks).
- `Token` Table: The polymorphic database model specified in `Docs/Design/toekn_database.md` has not been implemented as a SQLAlchemy class or migrated via Alembic.

### 4.2 Organization & Admin Module (`backend/app/modules/organization/`)
- `api.py`: Contains stub endpoints with `...` (ellipsis) and instantiates a disconnected `FastAPI()` app instead of an `APIRouter`. Not registered in `main.py`.
- `services.py` (0 bytes): No service layer implemented for tenant provisioning, admin creation, or profile edits.
- `repository.py` (0 bytes): No database query methods implemented.
- Relationship Bug: `Organization.users` in `modules/organization/models.py` references `"Users"` instead of `"Admin"`.

### 4.3 Log Ingestion & Orchestration Module
- **No Log Ingestion Endpoints**: There are no API routes to receive raw security logs (`POST /api/v1/logs`).
- **No Log Database Models**: The `Log` and `LLMExplanation` models described in the design documents have not been defined in SQLAlchemy or created in Alembic.
- **No Redis Stream Ingestion**: The asynchronous queue (`security_logs`) and consumer group mechanism detailed in `Docs/system-design.md` are not yet built.
- **No Background Worker**: The log consumer worker loop (`worker.py`) that reads from the queue, invokes the ML model, and pushes high-risk logs to the LLM is completely absent.

### 4.4 ML Inference Serving (`backend/app/modules/aiModel/`)
- `api.py`: Endpoint `get_log` does not accept inputs or call `model.predict()`. Hardcodes a local Windows absolute path (`D:\SentinelLog-AI\...`). Router is not registered in `main.py`.
- `schemas.py`: `ModelOutput` class is empty.
- **Scikit-Learn Version Incompatibility**: The serialized model (`hdfs_log_classifier.joblib`) was trained on scikit-learn 1.6.1 and fails unpickling under newer scikit-learn versions (`AttributeError: _RemainderColsList`).
- **Missing Raw Log Parser**: The ML model requires pre-calculated fields (`Hour`, `Minute`, `Second`, `Time_gap`, `Pid_freq`). There is no log parser to extract these features from raw log strings.

### 4.5 LLM Hardening
- **Unstructured Text Output**: The LLM returns freeform string text rather than structured JSON (e.g. `{ attack_type, mitre_technique, severity, recommendation }`).
- **Prompt Injection Vulnerability**: Raw log content is directly concatenated into the prompt string without delimiter boundaries or sanitization.
- **Missing MITRE ATT&CK Parsing**: The current prompt does not enforce explicit MITRE matrix tagging.

### 4.6 Client / Presentation Layer
- **No Frontend**: The Electron / React desktop application and Security Dashboard outlined in the SRS have not been initialized.

---

## 5. Prioritized Implementation Plan & Execution Roadmap

To take SentinelLog-AI from its current experimental prototype state to a functioning, end-to-end security platform, follow this prioritized execution plan:

```mermaid
flowchart TD
    subgraph PHASE1["Phase 1: Backend Foundation & Auth (Week 1)"]
        P1A["Fix Model Bugs & Database URLs"] --> P1B["Implement Polymorphic Token Model"]
        P1B --> P1C["Generate Alembic Migration"]
        P1C --> P1D["Implement Auth Module (Login, Refresh, RBAC)"]
        P1D --> P1E["Complete Organization & Admin CRUD APIs"]
    end

    subgraph PHASE2["Phase 2: Log Storage & ML Triage (Week 2)"]
        P2A["Implement Log & Explanation DB Models"] --> P2B["Build Production Log Parser"]
        P2B --> P2C["Retrain & Fix ML Joblib Pipeline"]
        P2C --> P2D["Implement ML Inference Service"]
    end

    subgraph PHASE3["Phase 3: Pipeline Orchestration & LLM Hardening (Week 3)"]
        P3A["Implement Log Ingestion API"] --> P3B["Build Redis Streams / Background Worker"]
        P3B --> P3C["Harden LLM Prompts & Enforce JSON Schema"]
        P3C --> P3D["Wire ML High-Risk Triage to LLM"]
    end

    subgraph PHASE4["Phase 4: Dashboard & Presentation (Week 4)"]
        P4A["Build Electron / React Dashboard"] --> P4B["Incident Review & MITRE ATT&CK Views"]
        P4B --> P4C["End-to-End Testing & Deployment"]
    end

    PHASE1 --> PHASE2
    PHASE2 --> PHASE3
    PHASE3 --> PHASE4
```

### Phase 1: Backend Foundation, Models & Authentication (Immediate Priority)
1. **Fix Model Relationship Bug**:
   - In `backend/app/modules/organization/models.py`, correct `users: Mapped[list["Users"]]` to reference `"Admin"`, aligning with `backend/app/modules/admin/models.py`.
2. **Align Async Database Driver**:
   - In `backend/.env`, ensure `DATABASE_URL` uses an asynchronous driver compatible with `create_async_engine` (e.g. `postgresql+asyncpg://...`), while keeping `alembic/env.py` converting to `postgresql+psycopg://` for synchronous migrations.
3. **Implement the `Token` Model**:
   - Create `backend/app/modules/auth/models.py` containing the `Token` entity with check constraint `check_token_owner` ensuring each token belongs to either an Organization or an Admin.
4. **Complete the Authentication Module**:
   - Implement `backend/app/modules/auth/service.py` with password validation, token issuing, and revocation.
   - Implement `backend/app/modules/auth/dependencies.py` with `get_current_admin` and `get_current_organization`.
   - Implement `backend/app/modules/auth/api.py` with `/auth/login`, `/auth/refresh`, and `/auth/logout`.
   - Register the auth router in `backend/app/main.py`.
5. **Complete Organization & Admin Endpoints**:
   - Refactor `backend/app/modules/organization/api.py` to use `APIRouter(prefix="/organization", tags=["Organization"])`.
   - Implement `repository.py` and `services.py` for organization and admin CRUD.
   - Register the organization router in `backend/app/main.py`.

### Phase 2: Log Storage, Ingestion & ML Pipeline (High Priority)
1. **Implement Log & Incident Models**:
   - Create models for `Log` (raw log, parsed content, source machine, timestamp, triage status: `LOW`, `MEDIUM`, `HIGH`) and `LLMExplanation` (incident explanation, attack type, MITRE technique, recommendation).
   - Create and apply an Alembic migration for the new tables.
2. **Fix & Package ML Classifier**:
   - Retrain or re-export `hdfs_log_classifier.joblib` using pinned scikit-learn and joblib versions matching the runtime environment.
   - Develop a production feature extractor and log parsing utility (`parse_raw_log`) that transforms raw log strings into the required dataframe format (`Content`, `Component`, `Hour`, `Minute`, `Second`, `Time_gap`, `Pid_freq`).
   - Fix `backend/app/modules/aiModel/api.py`: replace hardcoded path with dynamic path resolution (`Path(__file__).resolve().parent / "hdfs_log_classifier.joblib"`), complete `ModelOutput` schema, and implement prediction logic.
   - Register `/model` router in `backend/app/main.py`.

### Phase 3: Pipeline Orchestration & LLM Hardening (Medium Priority)
1. **Build Ingestion & Async Worker**:
   - Implement `POST /api/v1/logs` to receive and validate incoming log streams.
   - Integrate Redis Streams or an asynchronous worker loop (`worker.py`) that fetches unanalyzed logs, passes them through the ML model, and stores risk classifications.
2. **Harden the LLM Service**:
   - Update `llmSservices/promt.py` to use prompt boundaries (e.g., XML/Markdown blocks `<raw_log>...</raw_log>`) to prevent prompt injection.
   - Enforce structured JSON output (via Pydantic schema or Qwen JSON mode) with explicit fields: `attack_type`, `mitre_technique`, `severity`, and `recommended_action`.
   - Connect the worker so that any log flagged as `HIGH` risk by the ML model automatically triggers the LLM analysis endpoint and persists the result to `LLMExplanation`.

### Phase 4: UI Dashboard & Production Hardening (Final Phase)
1. **Develop the Admin Presentation Layer**:
   - Initialize the Electron / React frontend application.
   - Implement views for Live Event Ingestion, Incident Explorer, MITRE ATT&CK Matrix mapping, and Administrator Review/Approval actions.
2. **Production Deployment**:
   - Set up Docker Compose (`FastAPI`, `PostgreSQL`, `Redis`).
   - Configure CI/CD automated test suites and production environment variable management.

---

## 6. Known Bugs & Critical Blockers

Prior to production deployment, the following defects must be addressed:

| Severity | Defect Location | Description | Required Remediation |
| :--- | :--- | :--- | :--- |
| **BLOCKER** | `backend/app/modules/aiModel/api.py` | Model artifact unpickling fails with `AttributeError: _RemainderColsList` due to scikit-learn version mismatch between training and serving runtimes. | Retrain or re-export the joblib pipeline in the exact pinned deployment environment. |
| **BLOCKER** | `backend/app/modules/aiModel/api.py` | Hardcoded Windows path `r'D:\SentinelLog-AI\backend\app\modules\aiModel\hdfs_log_classifier.joblib'`. Fails immediately on Linux containers or any different drive path. | Use relative path resolution via `pathlib.Path(__file__).resolve().parent`. |
| **CRITICAL** | `backend/app/modules/organization/models.py` | Relationship declares `users: Mapped[list["Users"]]`, but model class is named `Admin`. Raises SQLAlchemy mapped relationship initialization error. | Change target to `Admin` and update foreign key / relationship names. |
| **HIGH** | `backend/app/modules/organization/api.py` | File defines a standalone `FastAPI()` app instead of an `APIRouter()`, and all endpoint functions contain empty stubs (`...`). | Refactor to `APIRouter`, implement service logic, and register router in `main.py`. |
| **HIGH** | `backend/app/core/config.py` & `.env` | `DATABASE_URL` in `.env` uses `postgresql+psycopg://...`. Passing this to SQLAlchemy `create_async_engine` without `asyncpg` or async driver configuration will fail at runtime. | Set `DATABASE_URL` to `postgresql+asyncpg://...` and let Alembic's `migration_url()` translate it for synchronous migrations. |
| **MEDIUM** | `backend/app/modules/llmSservices/promt.py` | Injects raw user log directly into prompt string without escaping or bounding tags. Vulnerable to adversarial prompt injection. | Wrap input in strict boundary delimiters and strip control instructions. |

---

## 7. Environment & Setup Guide

### 7.1 Prerequisites
- Python 3.11+
- PostgreSQL 15+ (Local or Neon Serverless)
- Redis 7+ (for async streaming queue)
- Hugging Face API Token (with access to `Qwen/Qwen2.5-72B-Instruct`)

### 7.2 Installation Steps

1. **Clone Repository & Setup Virtual Environment**:
   ```bash
   git clone https://github.com/KDhyanaSamaga/SentinelLog-AI.git
   cd SentinelLog-AI
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1   # On Windows
   # source .venv/bin/activate    # On Linux/macOS
   ```

2. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy or configure `backend/.env`:
   ```ini
   DATABASE_URL="postgresql+asyncpg://admin:password@localhost:5432/sentinellog"
   SECRET_KEY="your-production-secret-key-at-least-32-chars"
   ALGORITHM="HS256"
   ACCESS_TOKEN_EXPIRE_MINUTES=15
   REFRESH_TOKEN_EXPIRE_DAYS=7
   AUTO_REFRESH_THRESHOLD_SECONDS=300
   HF_TOKEN="hf_your_actual_token_here"
   ```

4. **Run Database Migrations**:
   ```bash
   cd backend/app
   alembic upgrade head
   ```

5. **Start the API Server**:
   ```bash
   # From SentinelLog-AI/backend:
   uvicorn app.main:app --reload --port 8000
   ```

6. **Verify API Endpoints**:
   - Interactive Swagger API Documentation: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`
   - LLM Health Check: `http://localhost:8000/llm/health`
