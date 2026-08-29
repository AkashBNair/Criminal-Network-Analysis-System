# Development Plan
## AI-Powered Criminal Network Analysis System

**Document Version:** 1.0
**Date:** August 23, 2026
**Status:** Draft for Review
**Related Documents:** PRD v1.0, SRS v1.0, System Architecture v1.0, UI/UX Document v1.0

---

## 1. Purpose

This Development Plan converts the PRD, SRS, System Architecture, and UI/UX Document into a sequenced, actionable roadmap. It defines what gets built, in what order, by whom it depends on, and how the team will know each piece is actually done — so implementation can begin without ambiguity.

---

## 2. Planning Assumptions

- Team composition assumed for sequencing purposes: 1 tech lead/architect, 2–3 backend engineers, 1–2 frontend engineers, 1 ML/NLP engineer, 1 QA engineer, 1 DevOps engineer (part-time acceptable), 1 product owner/BA liaising with law enforcement stakeholders. Adjust timelines proportionally if team size differs.
- Timelines below are expressed in **sprints (2 weeks each)** rather than calendar dates, since actual start date and team availability are not yet fixed.
- MVP scope is exactly as defined in the PRD (Section 6) and SRS — this plan does not introduce new scope, only sequences the agreed scope.
- Infrastructure decisions (Docker Compose vs. Kubernetes, on-prem vs. private cloud) follow the System Architecture document's recommendations for MVP.

---

## 3. Guiding Priorities

1. **Foundations before features.** Auth, RBAC, case model, and core data storage must exist before any entity/graph/analytics feature can be meaningfully built or tested.
2. **Data pipeline before intelligence.** Ingestion and entity extraction must be reliable before relationship graphs, analytics, or pattern detection can produce trustworthy output.
3. **Thin vertical slices over broad shallow ones.** Get one complete flow working end-to-end early (upload → extract → graph → view) before expanding breadth (more entity types, more detection rules), to surface integration risks early.
4. **Security and audit are not a phase — they're a constraint on every phase.** RBAC enforcement, audit logging, and encryption are built alongside each module, not bolted on at the end.
5. **Testing happens continuously, not as a final phase.** Each module carries its own test suite; a dedicated hardening phase exists for integration/security/performance testing, not for first-time testing.

---

## 4. Roadmap Overview (Phase Summary)

| Phase | Focus | Approx. Duration |
|---|---|---|
| **Phase 0** | Project setup, environments, tooling | 1 sprint |
| **Phase 1** | Foundation: Auth, RBAC, Case management, core DB schema | 2 sprints |
| **Phase 2** | Data Ingestion (structured + unstructured) | 2 sprints |
| **Phase 3** | Entity Extraction (NLP) & Entity Resolution | 3 sprints |
| **Phase 4** | Relationship Graph construction & Graph DB integration | 2 sprints |
| **Phase 5** | Graph Analytics (centrality, communities, shortest path) | 2 sprints |
| **Phase 6** | Pattern & Anomaly Detection (rule engine + alerts) | 2 sprints |
| **Phase 7** | Frontend: Core screens (Dashboard, Case, Entity, Ingestion) | Parallel to Phases 2–4 |
| **Phase 8** | Frontend: Network Explorer & Analytics/Alerts UI | Parallel to Phases 5–6 |
| **Phase 9** | Reporting & Export | 1 sprint |
| **Phase 10** | Integration Testing, Security Hardening, Performance Testing | 2 sprints |
| **Phase 11** | UAT, Bug Fixing, Pilot Deployment Prep | 2 sprints |
| **Phase 12** | Production Deployment & Go-Live | 1 sprint |

**Estimated total MVP duration: ~20 sprints (~40 weeks / ~9–10 months)**, assuming the team composition in Section 2 and frontend work running in parallel with backend phases as indicated. This is a planning estimate, not a committed date — refine once team size/start date are confirmed.

---

## 5. Detailed Phase Breakdown

### Phase 0 — Project Setup & Tooling
**Goal:** A working, secured development environment before any feature code is written.

**Tasks:**
- Set up version control (repo structure, branching strategy — e.g., trunk-based with short-lived feature branches).
- Provision development, staging environments (per Architecture doc: Docker-based).
- Set up CI/CD pipeline skeleton (build, lint, test stages; deployment stages added later).
- Set up core infrastructure: PostgreSQL instance, Neo4j instance, Redis, object storage (MinIO), all in Docker Compose for local/dev use.
- Set up centralized logging and basic monitoring (Prometheus/Grafana) scaffolding.
- Set up secrets management (Vault or equivalent) even in dev, to establish the pattern early.
- Define coding standards, linting rules, PR review process.

**Dependencies:** None — this is the starting point.

**Definition of Done (DoD):**
- A developer can clone the repo, run one command (e.g., `docker-compose up`), and have all core services (DB, graph DB, queue, object store) running locally.
- CI pipeline runs lint + placeholder test on every PR.
- Environment variables/secrets are never committed to source control (verified via a pre-commit hook/secret scanner).

---

### Phase 1 — Foundation: Auth, RBAC, Case Management, Core Schema
**Goal:** The System can authenticate users, enforce roles, and manage cases — the skeleton everything else attaches to.

**Tasks:**
- Design and implement core PostgreSQL schema: Users, Roles, Permissions, Cases, Case Assignments, Audit Log.
- Integrate identity provider (Keycloak or agency LDAP/AD) for authentication + MFA (SRS FR-10.1–FR-10.4).
- Implement JWT-based session handling (access + refresh tokens).
- Implement RBAC enforcement middleware in the Core App Service, driven by the permission matrix (SRS Section 4.2).
- Implement Case CRUD APIs (create, assign users, archive) — SRS FR-8.1–FR-8.3.
- Implement audit logging middleware capturing all authenticated actions from this point forward.
- Build Admin: User & Role Management screens (frontend) — UI/UX Section 6.13.

**Dependencies:** Phase 0 complete.

**Definition of Done:**
- A user cannot access any API endpoint without a valid token (verified by automated test).
- A user assigned to Case A cannot retrieve Case B's data via direct API call (automated authorization test per SRS FR-10.5).
- MFA is enforced for all roles above Data Entry Staff (tested).
- Every login, permission denial, and case-assignment change appears correctly in the audit log within 5 seconds.
- Admin can create a user, assign a role, and assign them to a case entirely through the UI.

---

### Phase 2 — Data Ingestion
**Goal:** Structured and unstructured data can be reliably uploaded, validated, and stored.

**Tasks:**
- Build structured file ingestion (CSV/XLSX) for CDRs, financial records, criminal history — including schema validation (SRS FR-1.1, FR-1.3, DV-6).
- Build unstructured document ingestion (PDF/DOCX/TXT) with object storage integration (SRS FR-1.2).
- Implement duplicate-file detection via hashing (SRS FR-1.6).
- Implement batch ingestion support (SRS FR-1.4).
- Implement incremental/delta ingestion for structured sources (SRS FR-1.7).
- Implement ingestion job queuing (Redis/Celery) so uploads trigger async downstream processing.
- Build the Ingestion/Upload frontend screen with progress, validation errors, and batch summary (UI/UX Section 6.11).

**Dependencies:** Phase 1 (requires Case model, auth, and audit logging).

**Definition of Done:**
- Uploading a valid CDR CSV of 1,000 rows completes with a matching record count (SRS FR-1.1 acceptance test).
- Uploading a malformed file produces a specific, field-level error, not a generic failure.
- Uploading the same file twice triggers a duplicate warning.
- 100 files can be submitted as a single batch with a per-file success/failure report.
- All ingested records carry source, filename, timestamp, and uploader metadata (SRS FR-1.5).

---

### Phase 3 — Entity Extraction & Entity Resolution
**Goal:** Entities are automatically extracted from ingested data and deduplicated against existing records.

**Tasks:**
- Stand up the NLP/Extraction Service (self-hosted spaCy/Transformers model) as an independently deployable service consuming the ingestion queue.
- Train/fine-tune NER model on a representative, agency-approved document sample for target entity types (Person, Location, Phone, Vehicle, Organization, Event, Date).
- Implement OCR fallback (Tesseract) for scanned documents.
- Implement confidence scoring per extracted entity (SRS FR-2.2) and threshold-based routing to a "Pending Review" state (SRS FR-2.5).
- Implement structured-source entity extraction (direct field mapping from CDR/financial records — SRS FR-2.4).
- Implement entity resolution: similarity scoring (fuzzy match + attribute match), match review queue, and merge/split logic with full audit history (SRS FR-3.1–FR-3.3).
- Support manual entity creation (SRS FR-3.4).
- Build Entity List, Entity Profile, and Entity Resolution Review Queue frontend screens (UI/UX Sections 6.6–6.8).

**Dependencies:** Phase 2 (needs ingested data to extract from); Phase 1 (needs case/user context).

**Definition of Done:**
- NER extraction achieves ≥0.85 F1 score on the agreed validation document set (SRS FR-2.1 acceptance criterion).
- Every extracted entity has a non-null confidence score.
- Entities below the confidence threshold appear in the review queue and are excluded from auto-linking until reviewed.
- A test case with a known duplicate ("Raj Kumar" vs. "R. Kumar," same phone number) is correctly flagged as a potential match.
- Merging two entities is reversible (split) and both actions are logged with user and timestamp.
- Investigators can fully review, confirm, edit, and reject extracted entities via the UI without needing direct database access.

---

### Phase 4 — Relationship Graph Construction
**Goal:** Confirmed entities and their relationships are represented in a queryable graph.

**Tasks:**
- Stand up Neo4j and integrate it with the Core App Service / extraction pipeline.
- Implement automatic relationship (edge) generation from co-occurrence in source records (SRS FR-4.1).
- Implement relationship types and weighting logic (SRS FR-4.2, FR-4.3).
- Implement manual relationship add/edit/delete with mandatory justification notes (SRS FR-4.4, BR-2).
- Implement relationship change history/audit trail (SRS FR-4.5).
- Implement graph filtering API (by entity type, relationship type, date range, confidence/weight — SRS FR-4.6).

**Dependencies:** Phase 3 (requires confirmed entities to build relationships between).

**Definition of Done:**
- Ingesting a CDR record linking two phone numbers automatically creates a correctly typed and weighted edge in Neo4j.
- A manual relationship cannot be saved without a justification note (enforced server-side, not just in the UI).
- Relationship history for any edge shows all changes with responsible user and timestamp.
- Filtering the graph via API by relationship type and date range returns the correct subset (verified against a known test graph).

---

### Phase 5 — Graph Analytics
**Goal:** Investigators can identify key individuals and trace connections using graph algorithms.

**Tasks:**
- Integrate Neo4j Graph Data Science (GDS) library.
- Implement degree and betweenness centrality computation, exposed via API (SRS FR-5.1, FR-5.2).
- Implement top-N influencer ranking and highlighting (SRS FR-5.3).
- Implement community/cluster detection (SRS FR-5.4).
- Implement shortest-path query between two entities (SRS FR-5.5).
- Add caching for expensive/unchanged network computations (per Architecture Section 10).

**Dependencies:** Phase 4 (requires a populated relationship graph to analyze).

**Definition of Done:**
- Centrality scores computed on a test graph with known expected values match exactly (degree) or within ±0.01 tolerance (betweenness).
- Top-10 influencer ranking on a test network matches an independently derived expected ranking.
- Community detection correctly separates two known disconnected clusters joined by one bridge node in a test graph.
- Shortest-path query returns the correct, expected path (including intermediate nodes) for a test graph with a known 3-hop path.
- Analytics for a 10,000-node test network complete within 60 seconds (SRS PERF-6).

---

### Phase 6 — Pattern & Anomaly Detection
**Goal:** The system automatically surfaces suspicious patterns as reviewable alerts.

**Tasks:**
- Build the rule-engine service with configurable thresholds stored in PostgreSQL.
- Implement cross-case entity match detection (SRS FR-6.1).
- Implement communication-burst detection (SRS FR-6.2).
- Implement circular/structured financial transaction detection (SRS FR-6.3).
- Implement rule configuration UI/API (enable/disable, threshold editing — SRS FR-6.4) with role gating (Crime Analyst/Admin only).
- Implement alert lifecycle (status transitions, mandatory dismissal reason — SRS FR-6.5, FR-6.6, BR-3).
- Build Alerts Queue and Detection Rule Configuration frontend screens (UI/UX Sections 6.10, 6.14).

**Dependencies:** Phase 4 (relationship graph) and Phase 2 (structured data ingestion, for financial/CDR pattern rules).

**Definition of Done:**
- A phone number ingested into two separate test cases triggers a cross-case alert referencing both case IDs.
- A test CDR dataset with 12 calls in 24 hours between two previously unconnected numbers triggers a communication-burst alert.
- A known circular transaction test dataset (A→B→C→A) triggers a circular-transaction alert identifying all involved accounts.
- Changing a detection threshold via the UI affects subsequent rule evaluations without a code deployment.
- Alerts cannot be deleted — only dismissed with a mandatory reason (verified: delete action is not exposed/possible, per BR-3).

---

### Phase 7 — Frontend: Core Screens (Runs in Parallel with Phases 2–4)
**Goal:** Investigators have a usable interface for the foundational workflows as backend modules become available.

**Tasks:**
- Build Login/MFA screen (Phase 1 dependency).
- Build role-specific Dashboard (Phase 1 dependency for cases; iterate as alerts/entities become available).
- Build Case List and Case Overview screens (Phase 1 dependency).
- Build Ingestion/Upload screen (Phase 2 dependency).
- Build Entity List, Entity Profile, Entity Resolution Review Queue (Phase 3 dependency).
- Implement global Search (can begin against Phase 1/3 data as it becomes available).
- Establish the shared component library (design tokens, buttons, tables, cards, dialogs) per UI/UX Section 12–13 — this should start in Phase 0/1 so later screens reuse it rather than duplicating patterns.

**Dependencies:** Tracks the corresponding backend phase for each screen; shared component library depends only on Phase 0/1.

**Definition of Done:**
- Each screen matches its specification in the UI/UX Document (Section 6), including all defined loading/empty/error states.
- All screens are keyboard-navigable and pass an automated accessibility audit (axe-core or equivalent) with no critical violations.
- Role-based navigation visibility is enforced (SRS-aligned): a user without access to a screen cannot reach it via direct URL.

---

### Phase 8 — Frontend: Network Explorer & Analytics/Alerts UI (Runs in Parallel with Phases 5–6)
**Goal:** The core investigative visualization tool and alert-handling interface are complete.

**Tasks:**
- Build the shared Graph Visualization component (Cytoscape.js/Sigma.js) supporting both full Network Explorer and mini-graph embed modes (per UI/UX Section 15).
- Implement Network Explorer: filters, legend, node/edge interactions, "Find Path" tool, "Top Influencers" toggle (UI/UX Section 6.9).
- Implement large-graph handling (node-count threshold warning/truncation per UI/UX Section 6.9).
- Implement accessible data-table fallback view for the graph (accessibility requirement, UI/UX Section 11).
- Build Alerts Queue detail drawer and status-update flow (UI/UX Section 6.10).

**Dependencies:** Phase 5 (analytics APIs), Phase 6 (alerts APIs), Phase 7 (shared component library must exist first).

**Definition of Done:**
- A 1,000-node test network renders within 5 seconds (SRS PERF-3).
- "Find Path" correctly highlights the shortest path returned by the backend for a known test case.
- The graph's accessible data-table alternative view contains equivalent information to the visual graph (manually verified).
- Alert status changes made in the UI are reflected in the backend and audit log within expected latency.

---

### Phase 9 — Reporting & Export
**Goal:** Investigators can generate and download PDF reports of cases, networks, and entities.

**Tasks:**
- Implement server-side PDF rendering (Puppeteer/WeasyPrint) for Case Summary, Network Snapshot, and Entity Profile report types.
- Implement export audit logging (exporting user, timestamp, scope — BR-9).
- Build the Reports/Export frontend screen (UI/UX Section 6.12).

**Dependencies:** Phases 4, 5, 6 (report content draws from graph, analytics, and alert data); Phase 7/8 for UI.

**Definition of Done:**
- Exporting a network view produces a PDF containing both the graph image and a textual summary of top entities/relationships (per PRD acceptance criteria).
- Every export action is logged with user, timestamp, and scope.
- Report generation for a typical case completes within an agreed time bound (to be set during performance testing, Phase 10).

---

### Phase 10 — Integration Testing, Security Hardening, Performance Testing
**Goal:** Validate the system holistically, not just module-by-module.

**Tasks:**
- End-to-end scenario testing: full flow from ingestion → extraction → resolution → graph → analytics → alerts → reporting, using a realistic test dataset (SRS Acceptance Criterion #10).
- RBAC/permission matrix verification across all roles, via both UI and direct API testing (SRS Acceptance Criterion #2).
- Security testing: penetration test or independent security review (SRS Section 9 / SEC requirements) — no unresolved critical/high findings permitted before proceeding to Phase 11.
- Performance/load testing against SRS Section 10 targets (concurrency, ingestion throughput, analytics computation time, graph rendering time).
- Accessibility audit (WCAG 2.1 AA) across all screens.
- Audit log completeness/tamper-evidence verification.

**Dependencies:** All functional phases (1–9) substantially complete.

**Definition of Done:**
- All items in SRS Section 11 (System-Level Acceptance Criteria) pass.
- No unresolved critical or high-severity security findings.
- Performance targets in SRS Section 10 are met under simulated target load.
- A documented end-to-end test run (with realistic data) is signed off by QA and the product owner.

---

### Phase 11 — UAT, Bug Fixing, Pilot Deployment Prep
**Goal:** Real investigators validate the system against real (or realistic, sanitized) workflows before go-live.

**Tasks:**
- Conduct UAT sessions with representative Investigating Officers, Crime Analysts, and a Senior Official, using the journeys defined in the UI/UX Document (Section 5).
- Triage and fix UAT-identified bugs, prioritized by severity (see Section 8 below).
- Finalize deployment runbooks, backup/restore procedures, and monitoring dashboards for the pilot environment.
- Conduct user training sessions and prepare basic user documentation/quick-reference guides.
- Confirm data retention, RPO/RTO, and legal/compliance sign-off (per Architecture Section 13 open items).

**Dependencies:** Phase 10 complete.

**Definition of Done:**
- UAT sign-off obtained from designated representatives of each primary user role.
- All Critical and High severity bugs identified during UAT are resolved and verified.
- Backup/restore procedure has been tested at least once in the staging/pilot environment.
- Training materials exist and at least one training session has been delivered.

---

### Phase 12 — Production Deployment & Go-Live
**Goal:** The system is live in the agency's production environment with monitoring and support in place.

**Tasks:**
- Execute production deployment per the runbook (Docker Compose or Kubernetes, per Architecture doc decision).
- Verify TLS, encryption at rest, secrets management, and network isolation are correctly configured in production (not just staging).
- Enable production monitoring/alerting (Prometheus/Grafana, log aggregation).
- Conduct a go-live smoke test covering the core end-to-end flow.
- Establish a post-launch support/bug-triage process and point of contact.

**Dependencies:** Phase 11 sign-off.

**Definition of Done:**
- Production smoke test (login → upload → extraction → graph view → alert → export) passes.
- Monitoring dashboards are live and alerting is confirmed functional (e.g., a test alert successfully notifies the on-call contact).
- A rollback procedure exists and has been documented/tested.
- Go-live is formally signed off by the product owner and agency stakeholder.

---

## 6. Dependency Graph (Simplified)

```
Phase 0 (Setup)
   └─▶ Phase 1 (Auth/RBAC/Cases)
          ├─▶ Phase 2 (Ingestion)
          │      └─▶ Phase 3 (Extraction/Resolution)
          │             └─▶ Phase 4 (Relationship Graph)
          │                    ├─▶ Phase 5 (Graph Analytics)
          │                    └─▶ Phase 6 (Pattern Detection) ◀── (also needs Phase 2)
          └─▶ Phase 7 (Core Frontend) ── parallel to Phases 2–4
                 └─▶ Phase 8 (Network Explorer/Alerts UI) ── parallel to Phases 5–6
                        └─▶ Phase 9 (Reporting) ◀── needs Phases 4,5,6
                               └─▶ Phase 10 (Integration/Security/Perf Testing)
                                      └─▶ Phase 11 (UAT & Bug Fixing)
                                             └─▶ Phase 12 (Deployment & Go-Live)
```

**Critical path:** Phase 0 → 1 → 2 → 3 → 4 → 5/6 → 9 → 10 → 11 → 12. Frontend phases (7, 8) can run in parallel with their corresponding backend phases but cannot get *ahead* of them for screens requiring live APIs (though frontend teams can build against mocked/contract-defined APIs to avoid idle time — see Section 9).

---

## 7. Milestones

| Milestone | Marks Completion Of | Significance |
|---|---|---|
| **M1: Foundation Ready** | Phase 1 | Auth, RBAC, and case management are functional — all other work can proceed without blocking on core infrastructure |
| **M2: First Data In** | Phase 2 | Real data (CDRs, FIRs) can be ingested into the system for the first time |
| **M3: First Entities Extracted** | Phase 3 | The system produces its first automatically extracted, human-reviewable entities — proves the core AI value proposition |
| **M4: First Network Visible** | Phase 4 + Phase 8 (initial) | An investigator can, for the first time, see a real relationship graph in the UI — the "wow moment" and a key internal demo milestone |
| **M5: Intelligence Layer Complete** | Phases 5 & 6 | Centrality analysis and pattern-detection alerts are functional — the system now generates actionable intelligence, not just visualization |
| **M6: Feature-Complete Build** | Phase 9 | All MVP features (per PRD Section 6.1) are implemented end-to-end |
| **M7: Hardened & Tested** | Phase 10 | System has passed integration, security, and performance testing |
| **M8: UAT Signed Off** | Phase 11 | Real users have validated the system and critical/high bugs are resolved |
| **M9: Go-Live** | Phase 12 | System is live in production for the pilot agency/unit |

---

## 8. Bug Severity Definitions & SLA (for Phases 10–12 and beyond)

| Severity | Definition | Fix SLA (Pre-Launch) |
|---|---|---|
| **Critical** | Data loss/corruption, security/authorization bypass, or complete inability to perform a core workflow (ingest, extract, view graph) | Immediate — blocks further testing/release |
| **High** | A core feature works incorrectly (e.g., wrong centrality score, incorrect RBAC restriction) but doesn't block all usage | Within current sprint |
| **Medium** | A non-core feature or UI issue that has a workaround | Within 2 sprints |
| **Low** | Cosmetic issue, minor copy/labeling issue | Backlog, addressed as capacity allows |

All Critical and High severity bugs must be resolved before Phase 11 sign-off (per DoD in Section 5, Phase 11); Medium/Low bugs may be deferred to a post-launch backlog with stakeholder agreement.

---

## 9. De-Risking Strategy: Avoiding Idle Time and Late Integration Surprises

- **API contracts first:** Before each backend phase begins implementation, the tech lead publishes the API contract (request/response schema) for that phase's endpoints, so the corresponding frontend work (Phase 7/8) can begin against a mocked API rather than waiting for the real backend.
- **Thin end-to-end slice early:** Prioritize getting *one* document through the entire pipeline (upload → extract → graph → view) as early as possible — even with only one entity type and no analytics — to surface architectural/integration issues (Phase 2–4 boundary) long before all features are built out.
- **NLP model risk isolated early:** Because NER model quality (F1 ≥ 0.85 target) is the single highest-uncertainty technical risk, begin model training/evaluation in parallel with Phase 1–2, using whatever sample documents are available, rather than waiting until Phase 3 formally starts.
- **Security and RBAC tested continuously:** Do not defer all authorization testing to Phase 10 — each phase's DoD includes verifying that its new endpoints respect RBAC, so Phase 10 focuses on holistic/edge-case security testing rather than first-time discovery of basic authorization bugs.

---

## 10. MVP Scope Recap (What Ships in This Plan)

Consistent with the PRD (Section 6.1) and SRS, this plan builds exactly:
- Structured + unstructured data ingestion (FIRs, CDRs, financial records, criminal history)
- NLP-based entity extraction (Person, Location, Phone, Vehicle, Organization, Event) with confidence scoring
- Entity resolution/deduplication with human review
- Automatically and manually constructed relationship graph
- Centrality-based influence ranking and community/cluster detection
- Rule-based pattern/anomaly detection (cross-case matches, communication bursts, circular transactions)
- Interactive graph visualization, entity profiles, search
- PDF reporting/export
- RBAC, authentication (with MFA), and full audit logging

**Explicitly not built in this plan** (per PRD Section 6.2 — deferred to future phases): live surveillance feed integration, SOCMINT scraping, ML-based (non-rule-based) anomaly detection, predictive/forecasting analytics, multi-language NLP beyond the initial target language, a native mobile app, and automated cross-agency data federation. Introducing any of these mid-plan would require a scope change request and re-sequencing, not an ad hoc addition to an existing phase.

---

## 11. Definition of Done — System-Wide Checklist

Beyond each phase's specific DoD (Section 5), every feature merged into the main branch must satisfy:

- [ ] Meets its corresponding functional requirement(s) from the SRS, verified by an automated test where feasible.
- [ ] Enforces RBAC per the permission matrix — verified by an automated authorization test, not just manual UI checking.
- [ ] Relevant actions are captured in the audit log.
- [ ] UI (if applicable) matches the UI/UX Document's screen specification, including loading/empty/error states.
- [ ] UI (if applicable) passes an automated accessibility check with no critical violations.
- [ ] Code is peer-reviewed and passes CI (lint, unit tests, build).
- [ ] No hardcoded secrets/credentials; sensitive data handled per Architecture Section 7 (Security).
- [ ] Documentation (API contract, README, or runbook as applicable) is updated alongside the code change.

---

*End of Document*
