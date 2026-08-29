# System Architecture Document
## AI-Powered Criminal Network Analysis System

**Document Version:** 1.0
**Date:** August 23, 2026
**Status:** Draft for Review
**Related Documents:** PRD v1.0, SRS v1.0

---

## 1. Purpose and Design Principles

This document defines the recommended technical architecture for the AI-Powered Criminal Network Analysis System. It translates the functional and non-functional requirements from the SRS into a concrete, buildable system design.

**Guiding principles for this architecture:**
- **Practical over novel:** Use mature, well-supported technologies rather than bleeding-edge tools, since this system will run in a government/law-enforcement environment where long-term supportability and auditability matter more than novelty.
- **Secure by default:** Sensitive data (PII, financial records, case intelligence) drives every architectural decision — network isolation, encryption, and access control are foundational, not add-ons.
- **On-premise / air-gapped friendly:** The design assumes the system may need to run without internet access, so it avoids hard dependencies on external cloud AI APIs.
- **Modular, not micro-fragmented:** Components are separated by responsibility (ingestion, NLP, graph, analytics, UI) but the MVP does not need a large microservices sprawl. Start with a small number of well-bounded services; split further only when scale demands it.
- **Human-in-the-loop by design:** The architecture treats AI outputs (extracted entities, inferred relationships, alerts) as advisory data that flows through review queues, not as automatically-actioned facts.

---

## 2. High-Level Architecture Overview

The System follows a **layered, modular monolith-plus-services** architecture: a core application service handles most business logic (cases, entities, relationships, RBAC), while computationally distinct workloads (NLP extraction, graph analytics, pattern detection) run as separate, independently scalable services. This avoids the complexity of full microservices while still letting the heaviest workloads (NLP, graph computation) scale independently of the main application.

```
                                   ┌───────────────────────────┐
                                   │        Investigators /     │
                                   │   Analysts / Officials      │
                                   │   (Web Browser Client)      │
                                   └──────────────┬──────────────┘
                                                  │ HTTPS (TLS 1.2+)
                                   ┌──────────────▼──────────────┐
                                   │      API Gateway / BFF       │
                                   │  (Auth, Rate Limit, Routing) │
                                   └──────────────┬──────────────┘
                     ┌────────────────────────────┼────────────────────────────┐
                     │                             │                             │
          ┌──────────▼──────────┐      ┌───────────▼───────────┐     ┌──────────▼──────────┐
          │   Core App Service    │      │  NLP/Extraction Service │     │  Graph Analytics      │
          │ (Cases, Users, RBAC,  │      │  (NER, Entity Resolution)│     │  Service (Centrality, │
          │  Relationships, Alerts│      │                          │     │  Community Detection) │
          │  Ingestion Orchestr.) │      │                          │     │                        │
          └──────────┬──────────┘      └───────────┬───────────┘     └──────────┬──────────┘
                     │                             │                             │
        ┌────────────┴───────────┬─────────────────┴───────────┬─────────────────┘
        │                        │                              │
┌───────▼────────┐   ┌───────────▼───────────┐      ┌───────────▼───────────┐
│  Relational DB   │   │  Document/Object Store │      │   Graph Database        │
│ (Postgres)        │   │ (Raw files: FIRs, PDFs)│      │ (Neo4j / equivalent)    │
│ Users, Cases,      │   │                        │      │ Entities & Relationships│
│ Alerts, Audit Log  │   │                        │      │                        │
└────────────────┘   └────────────────────────┘      └────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   Message Queue        │
          │ (async ingestion,      │
          │  extraction, analytics  │
          │  jobs)                  │
          └────────────────────────┘
```

---

## 3. System Components

### 3.1 Client Layer — Web Application (Frontend)
- **Purpose:** Investigator/analyst-facing interface for search, graph visualization, entity profiles, alerts, and reporting.
- **Recommended stack:** React (with TypeScript) for the SPA; a graph-visualization library such as **Cytoscape.js** or **Sigma.js** for interactive network rendering (both handle thousands of nodes reasonably well without heavy custom WebGL work).
- **Why not more:** A native mobile app, offline mode, or a custom-built graph rendering engine are unnecessary for MVP — a browser-based SPA fully satisfies the SRS visualization requirements.

### 3.2 API Gateway / Backend-for-Frontend (BFF)
- **Purpose:** Single entry point for all client requests; handles authentication token validation, request routing to backend services, rate limiting, and request/response logging.
- **Recommended stack:** A lightweight API gateway (e.g., **NGINX** or **Kong**) in front of the Core App Service, or the Core App Service itself exposing a well-defined REST API if a dedicated gateway is not justified at initial scale.
- **Rationale:** For MVP scale (tens to low hundreds of concurrent users within a single agency), a full service-mesh/gateway product (e.g., Istio) is over-engineering; a simple reverse proxy with auth middleware is sufficient and easier to operate and audit.

### 3.3 Core Application Service
- **Purpose:** The central business-logic service. Owns:
  - User/role/permission management (RBAC)
  - Case management (create, assign, archive)
  - Entity and relationship CRUD (manual edits, merges/splits)
  - Alert lifecycle management
  - Ingestion orchestration (accepts uploads, validates, queues extraction jobs)
  - Audit logging
- **Recommended stack:** **Python (FastAPI)** or **Node.js (NestJS)** — both are well-supported, have mature auth/ORM libraries, and are easy to staff for a government IT team. FastAPI is a strong fit given the System's heavy overlap with the Python-based ML/NLP ecosystem (shared libraries, easier internal integration).
- **Database access:** Via ORM (e.g., SQLAlchemy for FastAPI) to the relational database.

### 3.4 NLP / Entity Extraction Service
- **Purpose:** Consumes unstructured/semi-structured documents (FIRs, surveillance reports, intelligence reports) from the queue, runs Named Entity Recognition (NER) and entity resolution, and writes extracted entities (with confidence scores) back to the Core App Service / Graph Database.
- **Recommended stack:**
  - **spaCy** or a fine-tuned **transformer-based NER model** (e.g., a locally-hosted BERT/RoBERTa variant fine-tuned on law-enforcement-style text) run via **Hugging Face Transformers**.
  - Deployed as a **self-hosted, on-premise inference service** — not a third-party cloud AI API — to satisfy data sovereignty requirements (SEC-8 in the SRS).
  - OCR support (e.g., **Tesseract**) for scanned FIRs/reports where needed.
- **Why this choice:** Open-source, well-documented NLP libraries with strong community support avoid vendor lock-in and are proven for entity extraction tasks; fine-tuning on domain-specific data (rather than building a custom model from scratch) is the practical middle ground.
- **Entity resolution:** A rules + similarity-scoring approach (e.g., fuzzy string matching via `rapidfuzz`, combined with attribute matching on phone numbers/addresses) is sufficient for MVP — a full probabilistic record-linkage framework (e.g., Splink) can be introduced later if match volumes and complexity justify it.

### 3.5 Graph Analytics Service
- **Purpose:** Runs graph algorithms — centrality (degree, betweenness, eigenvector), community detection, shortest-path — against the relationship graph, on demand or on a schedule, and returns results to the Core App Service for display.
- **Recommended stack:**
  - If using **Neo4j** as the graph database: leverage its built-in **Graph Data Science (GDS) library**, which provides centrality and community-detection algorithms natively, avoiding the need for a separate analytics engine for MVP.
  - Alternatively, for smaller deployments or if avoiding a dedicated graph database, use **Python + NetworkX** against graph data materialized from the relational store — simpler to operate, though it scales less well beyond ~100K–200K nodes.
- **Recommendation:** Start with **Neo4j + GDS** given the System's graph-centric nature; this avoids building custom graph algorithm implementations (a common over-engineering trap) and gives production-grade performance out of the box.

### 3.6 Pattern & Anomaly Detection Service
- **Purpose:** Evaluates configurable rules (cross-case entity appearance, communication bursts, circular financial transactions) against ingested data and the relationship graph, generating alerts.
- **Recommended approach for MVP:** A **rule-engine style service** (custom-built, using simple configurable thresholds stored in the relational database) rather than a full ML anomaly-detection pipeline. This matches the MVP scope defined in the PRD/SRS (rule-based detection first; ML-based anomaly detection deferred).
- **Implementation:** Runs as scheduled/triggered jobs (via the message queue) whenever new data is ingested or relationships change, rather than continuous real-time streaming — sufficient given the System is not processing live surveillance feeds in MVP.

### 3.7 Asynchronous Job Processing (Message Queue)
- **Purpose:** Decouples slow/heavy operations (document extraction, graph analytics runs, batch ingestion) from the synchronous request/response cycle, so the UI stays responsive and large jobs can be retried/monitored independently.
- **Recommended stack:** **Redis** (via a task queue library such as **Celery** for Python, or **BullMQ** for Node.js) for MVP scale. This is simpler to operate than a full distributed streaming platform like Kafka, which is unnecessary until data volumes or real-time requirements grow significantly (e.g., live surveillance feed ingestion, a deferred feature).
- **Escalation path:** If future phases add real-time SOCMINT or surveillance feed ingestion, Kafka (or similar) can be introduced at that point without redesigning the core application.

### 3.8 Data Storage Layer

| Store | Technology | Stores |
|---|---|---|
| **Relational database** | PostgreSQL | Users, roles, permissions, cases, alerts, audit logs, ingestion metadata, configuration |
| **Graph database** | Neo4j (Community or Enterprise, per licensing needs) | Entities (nodes) and relationships (edges), with properties (confidence scores, weights, timestamps) |
| **Object/document store** | On-premise object storage (e.g., **MinIO**, an S3-compatible self-hosted store) or a secured file server | Raw uploaded documents (FIRs, reports, PDFs), exported reports |
| **Search index (optional, for scale)** | **Elasticsearch/OpenSearch** | Full-text and fuzzy search across entities and documents, if PostgreSQL's native search proves insufficient at scale |

**Rationale for this split:** Using a dedicated graph database for entities/relationships (rather than modeling graphs in relational tables) is the one clear "non-negotiable" specialized component here, because graph traversal queries (shortest path, centrality, multi-hop relationship discovery) are core to the product and are inefficient in pure relational SQL at scale. Everything else uses well-understood, general-purpose stores to avoid unnecessary specialization.

### 3.9 Reporting / Export Module
- **Purpose:** Generates PDF exports of graph views and entity/network summaries.
- **Recommended stack:** Server-side rendering using a headless browser/rendering library (e.g., **Puppeteer** or **WeasyPrint**) to convert a rendered graph + summary template into a PDF.

---

## 4. API Design

### 4.1 API Style
- **REST over HTTPS**, using JSON payloads, versioned from the outset (`/api/v1/...`) to allow non-breaking evolution.
- GraphQL is deliberately **not** recommended for MVP: REST is simpler to secure, audit, and rate-limit per-endpoint, which matters more here than query flexibility. Graph traversal flexibility is instead handled by dedicated graph-query endpoints, not a general query language exposed to clients.

### 4.2 Representative API Groups

| API Group | Example Endpoints | Purpose |
|---|---|---|
| **Auth** | `POST /api/v1/auth/login`, `POST /api/v1/auth/mfa/verify`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout` | Authentication and session/token management |
| **Users & Roles** | `GET/POST /api/v1/users`, `PUT /api/v1/users/{id}/roles` | User and RBAC management (admin only) |
| **Cases** | `POST /api/v1/cases`, `GET /api/v1/cases/{id}`, `PUT /api/v1/cases/{id}/assign` | Case lifecycle and access assignment |
| **Ingestion** | `POST /api/v1/ingestion/upload`, `GET /api/v1/ingestion/{jobId}/status` | File upload and ingestion job tracking |
| **Entities** | `GET /api/v1/entities/{id}`, `POST /api/v1/entities`, `POST /api/v1/entities/{id}/merge` | Entity CRUD, resolution/merge actions |
| **Relationships** | `GET /api/v1/graph/{caseId}`, `POST /api/v1/relationships`, `DELETE /api/v1/relationships/{id}` | Relationship graph read/write |
| **Analytics** | `GET /api/v1/graph/{caseId}/centrality`, `GET /api/v1/graph/{caseId}/communities`, `GET /api/v1/graph/path?from=&to=` | Graph analytics queries |
| **Alerts** | `GET /api/v1/alerts`, `PUT /api/v1/alerts/{id}/status` | Pattern-detection alert management |
| **Reports** | `POST /api/v1/reports/export` | Report/PDF generation |
| **Audit** | `GET /api/v1/audit-log` | Audit trail access (Auditor role only) |

### 4.3 API Security Standards
- All endpoints require a valid **JWT (JSON Web Token)** issued at login, short-lived (e.g., 15–30 minutes), with refresh tokens for session continuation.
- Every endpoint enforces RBAC checks server-side (per SRS FR-9.1/FR-10.5) — never relying on the frontend to hide unauthorized actions.
- Input validation on every endpoint (schema validation via, e.g., Pydantic in FastAPI) to reject malformed requests before they reach business logic.

---

## 5. Authentication and Authorization Architecture

- **Identity provider:** Integrate with the agency's existing identity provider where one exists (e.g., **LDAP/Active Directory** via SAML or OpenID Connect), rather than building a fully custom user-management system from scratch. If no existing IdP is available, a self-hosted open-source IdP (e.g., **Keycloak**) provides SSO, MFA, and RBAC support out of the box.
- **MFA:** Enforced at the identity-provider layer (e.g., Keycloak's built-in OTP/MFA support) for all roles above Data Entry Staff, per SRS FR-10.2.
- **Session management:** JWT access tokens (short-lived) + refresh tokens (longer-lived, revocable), with server-side session invalidation supported for immediate access revocation (e.g., when a role is downgraded).
- **Authorization model:** RBAC implemented as a centralized policy check within the Core Application Service, referencing the permission matrix defined in the SRS. A dedicated policy-as-code engine (e.g., OPA/Open Policy Agent) is optional and can be introduced later if permission logic grows significantly more complex than the current role/case-assignment model — not necessary for MVP.

---

## 6. Data Flow

### 6.1 Ingestion & Extraction Flow
1. User uploads a document or structured file via the frontend → Core App Service.
2. Core App Service validates the file (format, schema, duplicate check), stores the raw file in the object store, and records ingestion metadata in PostgreSQL.
3. Core App Service publishes an "extraction job" message to the queue.
4. NLP/Extraction Service consumes the job, retrieves the file from object storage, runs NER + entity resolution, and produces extracted entities with confidence scores.
5. Extracted entities below the confidence threshold are written to a "pending review" state in PostgreSQL; higher-confidence entities/relationships are written directly into the Graph Database.
6. Core App Service notifies the user (via UI polling or a lightweight notification) that extraction is complete and review may be needed.

### 6.2 Relationship Graph & Analytics Flow
1. As entities and relationships are created/confirmed (via extraction or manual entry), the Core App Service writes/updates corresponding nodes and edges in the Graph Database.
2. When a user requests network analysis (centrality, communities, shortest path) via the frontend, the Core App Service forwards the request to the Graph Analytics Service (or directly queries Neo4j GDS procedures).
3. Results are returned to the frontend for visualization; computationally heavier jobs (e.g., full-network community detection on very large graphs) are queued asynchronously and results cached/stored for reuse rather than recomputed on every view.

### 6.3 Pattern Detection Flow
1. On new data ingestion or relationship changes, a job is queued for the Pattern & Anomaly Detection Service.
2. The service evaluates configured rules against the current graph/data state.
3. Matches generate Alert records in PostgreSQL, linked to the relevant entities/case.
4. Alerts appear in the investigator's alert queue in the frontend for review and status update.

---

## 7. Security Architecture

| Layer | Control |
|---|---|
| **Network** | Deployment within agency VPN/private network; no public internet exposure; firewall rules restricting inter-service traffic to required ports only |
| **Transport** | TLS 1.2+ enforced for all client-server and internal service-to-service traffic |
| **Data at rest** | AES-256 encryption for the database, object store, and backups |
| **Authentication** | MFA-enforced login via identity provider; strong password policy; account lockout after repeated failures |
| **Authorization** | Server-side RBAC enforcement on every API call; case-level data isolation |
| **Audit** | Append-only audit log capturing all data access, modifications, exports, and admin actions, stored separately from operational data to reduce tamper risk |
| **Input handling** | Server-side validation and sanitization on all inputs to prevent injection attacks |
| **AI/data sovereignty** | All NLP/ML inference run on self-hosted infrastructure; no case data sent to external third-party AI APIs |
| **Secrets management** | Centralized secrets store (e.g., **HashiCorp Vault** or cloud-native equivalent) for database credentials, API keys, and encryption keys — never hardcoded in source or config files |
| **Vulnerability management** | Regular dependency scanning (e.g., `pip-audit`, `npm audit`) and periodic penetration testing prior to major releases |

---

## 8. Deployment Architecture

### 8.1 Environment Strategy
Three standard environments are recommended: **Development → Staging/UAT → Production**, with production deployed within the agency's secured network (on-premise data center or a government-approved private cloud region).

### 8.2 Containerization and Orchestration
- **Containerization:** All services (Core App, NLP Service, Graph Analytics Service, Pattern Detection Service) packaged as **Docker containers** for consistent, reproducible deployment.
- **Orchestration:** **Kubernetes** is recommended if the agency already operates Kubernetes infrastructure or expects to scale across multiple nodes; otherwise, **Docker Compose** on a small number of well-provisioned servers is a practical, lower-operational-overhead starting point for MVP/pilot deployment. Kubernetes can be adopted later without major re-architecture, since services are already containerized.
- **Rationale:** Avoid committing to full Kubernetes complexity (service mesh, auto-scaling policies, etc.) before the pilot proves out usage patterns and real scale requirements — this is a key place over-engineering commonly creeps in for a first deployment.

### 8.3 CI/CD
- Standard CI/CD pipeline (e.g., **GitLab CI**, **Jenkins**, or **GitHub Actions** if permitted in the agency's environment) for automated build, test, and controlled deployment to staging/production, with mandatory manual approval gates for production releases given the sensitivity of the system.

### 8.4 Backup and Disaster Recovery
- Automated daily backups of PostgreSQL and Neo4j, with backups encrypted and stored in a separate secure location.
- Defined Recovery Point Objective (RPO) and Recovery Time Objective (RTO) targets to be agreed with agency stakeholders (e.g., RPO ≤ 24 hours, RTO ≤ 4 hours as a reasonable MVP starting target).
- Periodic restore testing to validate backup integrity.

---

## 9. Monitoring and Observability

| Concern | Recommended Approach |
|---|---|
| **Application metrics** | Prometheus (metrics collection) + Grafana (dashboards) for service health, request latency, queue depth, job success/failure rates |
| **Logging** | Centralized log aggregation (e.g., the ELK/OpenSearch stack, or a lighter-weight alternative like Loki) for application and security logs, separate from the immutable audit log described in Section 7 |
| **Alerting** | Threshold-based alerts (e.g., via Grafana Alerting or Alertmanager) for service downtime, high error rates, queue backlogs, and failed ingestion jobs, routed to the operations team |
| **Audit trail** | As described in Section 7 — a dedicated, access-controlled audit log distinct from operational logs, reviewable by the Auditor role |
| **Health checks** | Standard liveness/readiness endpoints for each service, used by the orchestrator (Kubernetes or a simple monitoring script under Docker Compose) to detect and restart unhealthy instances |

---

## 10. Scalability Considerations

The architecture is designed to start small and scale deliberately:

- **Horizontal scaling of stateless services:** The Core App Service, NLP/Extraction Service, and Graph Analytics Service are stateless (state lives in the databases/queue) and can be scaled horizontally by running additional container instances behind the load balancer/API gateway as load increases.
- **Database scaling path:** Start with a single well-resourced PostgreSQL instance (with read replicas added if read load grows); Neo4j can scale via its clustering options (Enterprise edition) if a single instance becomes a bottleneck at very large graph sizes.
- **Queue-based decoupling:** Because ingestion and extraction are asynchronous and queue-driven, spikes in document volume do not block the interactive application — worker instances for the NLP service can simply be scaled up to drain the queue faster.
- **Caching:** Introduce a caching layer (e.g., Redis, which is already present for the queue) for frequently requested, expensive computations (e.g., centrality results for a large, unchanged network) rather than recomputing on every request.
- **Deliberately deferred scaling investments:** Full microservices decomposition, a dedicated stream-processing platform (Kafka), multi-region deployment, and auto-scaling Kubernetes clusters are not recommended until the pilot deployment demonstrates a genuine need — introducing them prematurely would add operational burden without a corresponding benefit at MVP scale.

---

## 11. Recommended Technology Stack Summary

| Layer | Recommended Technology | Notes |
|---|---|---|
| Frontend | React + TypeScript, Cytoscape.js/Sigma.js for graph viz | SPA, browser-based, no native mobile app for MVP |
| API Gateway | NGINX or Kong (optional at MVP scale) | Can start with reverse proxy + auth middleware in the Core App Service |
| Backend (Core App) | Python (FastAPI) or Node.js (NestJS) | FastAPI recommended for shared Python ecosystem with NLP/ML services |
| NLP/Extraction | spaCy / Hugging Face Transformers, Tesseract OCR | Self-hosted, on-premise inference |
| Entity Resolution | Fuzzy matching (`rapidfuzz`) + attribute rules | Escalate to probabilistic record linkage later if needed |
| Graph Database | Neo4j (+ Graph Data Science library) | Core to relationship modeling and analytics |
| Relational Database | PostgreSQL | Users, cases, alerts, audit logs, configuration |
| Object Storage | MinIO (self-hosted, S3-compatible) | Raw documents and exported reports |
| Message Queue | Redis + Celery/BullMQ | Async ingestion, extraction, analytics jobs |
| Search (optional) | Elasticsearch/OpenSearch | Only if native DB search proves insufficient at scale |
| Identity/Auth | Keycloak (or agency's existing LDAP/AD via SAML/OIDC) | SSO, MFA, RBAC |
| Containerization | Docker | All services containerized |
| Orchestration | Docker Compose (MVP/pilot) → Kubernetes (scale-up) | Avoid premature Kubernetes complexity |
| CI/CD | GitLab CI / Jenkins / GitHub Actions | Manual approval gate for production |
| Monitoring | Prometheus + Grafana | Metrics and dashboards |
| Logging | ELK/OpenSearch stack or Loki | Centralized log aggregation |
| Secrets Management | HashiCorp Vault | Centralized credential/key management |
| Reporting | Puppeteer / WeasyPrint | Server-side PDF generation |

---

## 12. Architecture Decision Summary (Why Not Over-Engineered)

| Temptation | Decision Made | Reasoning |
|---|---|---|
| Full microservices architecture | Modular monolith (Core App) + 2–3 specialized services | Reduces operational overhead; specialized services only where workload characteristics genuinely differ (NLP, graph analytics) |
| Kafka for all async processing | Redis + Celery/BullMQ | Sufficient for MVP job volumes; Kafka deferred until real-time streaming (e.g., live surveillance) is actually needed |
| Kubernetes from day one | Docker Compose for pilot, Kubernetes as a scale-up path | Avoids unnecessary orchestration complexity before real scale is proven |
| GraphQL for flexible querying | REST + dedicated graph-query endpoints | Simpler to secure and audit; graph flexibility handled by purpose-built endpoints instead |
| Custom-built NER/ML models from scratch | Fine-tuned open-source NLP models (spaCy/Transformers) | Faster to deploy, well-supported, avoids reinventing well-solved NLP problems |
| Third-party cloud AI APIs for NLP | Self-hosted inference | Required for data sovereignty in a law-enforcement context |
| Building a custom graph algorithm engine | Neo4j + Graph Data Science library | Production-grade centrality/community algorithms available out of the box |
| Custom-built IAM/SSO system | Keycloak or existing agency LDAP/AD | Avoids reinventing authentication, MFA, and RBAC infrastructure |

---

## 13. Open Items for Architecture Finalization

- Confirm whether the agency has an existing identity provider (LDAP/AD) to integrate with, or whether Keycloak should be deployed as a new component.
- Confirm target deployment environment (fully air-gapped on-premise vs. government-approved private cloud) — this affects choices around managed vs. self-hosted services (e.g., managed PostgreSQL vs. self-hosted).
- Confirm expected initial data volumes (documents/month, CDR records/month) to size compute and storage appropriately.
- Confirm RPO/RTO targets with stakeholders for backup and disaster recovery planning.
- Determine licensing approach for Neo4j (Community edition may be sufficient for MVP; Enterprise features like clustering may be needed at larger scale).

---

*End of Document*
