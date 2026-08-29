# Software Requirements Specification (SRS)
## AI-Powered Criminal Network Analysis System

**Document Version:** 1.0
**Date:** August 23, 2026
**Status:** Draft for Review
**Conforms to:** IEEE 830 / ISO/IEC/IEEE 29148 style structure

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines the functional and non-functional requirements for the **AI-Powered Criminal Network Analysis System** (hereafter "the System"). It is intended for use by the development team, QA/testing team, project stakeholders, and law enforcement agency representatives to ensure a shared, unambiguous understanding of what the System must do. Every requirement in this document is written to be specific, measurable, and testable.

### 1.2 Scope
The System will:
- Ingest structured and unstructured crime-related data from multiple sources (FIRs, CDRs, financial transaction records, surveillance reports, social media intelligence, criminal history databases, intelligence reports).
- Extract entities (persons, locations, vehicles, phone numbers, organizations, events) using NLP/ML techniques.
- Construct and maintain a relationship graph linking extracted entities.
- Apply graph analytics to identify key/influential individuals within networks.
- Detect suspicious patterns and anomalies within the data.
- Provide investigators with visual and analytical tools to explore networks and generate reports.
- Enforce role-based access control, authentication, and audit logging appropriate for sensitive law-enforcement data.

The System is an **investigative support tool**. It does not make legal determinations, automate enforcement actions, or serve as sole evidence of guilt; all AI-generated outputs are advisory and subject to human review.

### 1.3 Intended Audience
- Software architects and developers
- QA/Test engineers
- Project managers
- Law enforcement agency stakeholders (investigators, analysts, IT administrators)
- Security and compliance auditors

### 1.4 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|---|---|
| FIR | First Information Report — the initial police report of a cognizable offense |
| CDR | Call Detail Record — metadata of telephone calls (numbers, duration, timestamps, cell tower) |
| NER | Named Entity Recognition — NLP technique to identify entities in text |
| NLP | Natural Language Processing |
| ML | Machine Learning |
| RBAC | Role-Based Access Control |
| SOCMINT | Social Media Intelligence |
| Entity | A discrete object of interest: person, location, vehicle, phone number, organization, or event |
| Entity Resolution | The process of determining whether two entity records refer to the same real-world entity |
| Node | A graph vertex representing an entity |
| Edge | A graph connection representing a relationship between two entities |
| Centrality | A graph metric quantifying the relative importance/influence of a node |
| Case | A logical container of records, entities, and relationships associated with a specific investigation |
| PII | Personally Identifiable Information |
| MFA | Multi-Factor Authentication |
| SLA | Service Level Agreement |

### 1.5 References
- Project PRD: "AI-Powered Criminal Network Analysis System" (v1.0, August 23, 2026)
- IEEE Std 830-1998, Recommended Practice for Software Requirements Specifications
- ISO/IEC/IEEE 29148:2018, Systems and software engineering — Life cycle processes — Requirements engineering
- Applicable national data protection and law enforcement data-handling regulations (to be confirmed with legal/compliance team)

### 1.6 Overview
Section 2 provides an overall description of the System. Section 3 details functional requirements organized by module. Section 4 defines user roles and permissions. Section 5 defines business rules. Section 6 covers data requirements and validations. Section 7 covers authentication and authorization. Section 8 covers error handling and edge cases. Section 9 covers security requirements. Section 10 covers performance requirements. Section 11 defines acceptance criteria. Section 12 lists assumptions and dependencies.

---

## 2. Overall Description

### 2.1 Product Perspective
The System is a new, standalone software platform intended to be deployed within a secure law enforcement/government network. It will interface with existing systems (CDR databases, financial record repositories, criminal history databases) via defined import mechanisms but is not a replacement for existing case management or records management systems.

### 2.2 Product Functions (Summary)
1. Multi-source data ingestion (structured and unstructured)
2. Entity extraction via NLP/ML
3. Entity resolution and deduplication
4. Relationship graph construction and management
5. Graph-based influence/centrality analysis
6. Suspicious pattern and anomaly detection
7. Interactive visualization and search
8. Reporting and export
9. User authentication, authorization, and audit logging

### 2.3 User Classes and Characteristics
See Section 4 for detailed roles and permissions.

### 2.4 Operating Environment
- Server-side deployment on agency-controlled or government-approved cloud/on-premise infrastructure.
- Web-based client interface accessible via standard modern browsers (Chrome, Edge, Firefox — latest two major versions).
- No public internet exposure; access restricted to agency network/VPN.

### 2.5 Design and Implementation Constraints
- Must comply with applicable national data protection and law enforcement data-handling regulations.
- Must support integration with legacy structured data formats (CSV, fixed-width, or database exports) as a baseline import mechanism.
- Must operate within an environment with restricted internet access (air-gapped or tightly firewalled deployments are a likely scenario and should be considered in architecture).

### 2.6 Assumptions and Dependencies
See Section 12.

---

## 3. Functional Requirements

Each requirement is uniquely identified (FR-x.y) and written to be independently testable.

### 3.1 Data Ingestion Module

**FR-1.1** The System shall allow authorized users to upload structured data files (CSV, XLSX) containing CDRs, financial transaction records, and criminal history records.
*Acceptance test:* Upload a valid CSV of 1,000 CDR rows; system confirms successful ingestion with a record count matching the input file.

**FR-1.2** The System shall allow authorized users to upload unstructured/semi-structured documents (PDF, DOCX, TXT) containing FIRs, surveillance reports, and intelligence reports.
*Acceptance test:* Upload a PDF FIR document; system confirms successful ingestion and queues it for entity extraction.

**FR-1.3** The System shall validate uploaded structured files against a predefined schema (required columns, data types) before ingestion and reject files that do not conform, returning a specific error listing the failed validation(s).
*Acceptance test:* Upload a CSV missing a required column; system rejects the file and displays the missing column name(s).

**FR-1.4** The System shall support batch ingestion of multiple files (minimum 100 files per batch) without requiring individual manual submission.
*Acceptance test:* Submit a batch of 100 files; system processes all files and reports success/failure count per file.

**FR-1.5** The System shall record, for every ingested record, its source type, source file name, upload timestamp, and uploading user ID.
*Acceptance test:* After ingestion, query the record's metadata and confirm all four fields are populated correctly.

**FR-1.6** The System shall detect and flag duplicate file uploads (identical file hash) and prompt the user to confirm whether to proceed with re-ingestion.
*Acceptance test:* Upload the same file twice; system displays a duplicate-file warning on the second attempt.

**FR-1.7** The System shall support incremental/delta ingestion of structured data sources (e.g., new CDR records added since the last import) without duplicating previously ingested records.
*Acceptance test:* Ingest a CDR file, then ingest an updated file with 10 new rows and all prior rows unchanged; system ingests only the 10 new rows.

### 3.2 Entity Extraction Module

**FR-2.1** The System shall extract the following entity types from ingested unstructured documents: Person, Location, Phone Number, Vehicle (registration number/description), Organization, Event, Date/Time.
*Acceptance test:* Run extraction on a validated test document set; each entity type present in the ground truth is identified with an F1 score ≥ 0.85.

**FR-2.2** The System shall assign a confidence score (0–100%) to each extracted entity.
*Acceptance test:* Every extracted entity record includes a non-null confidence score field.

**FR-2.3** The System shall allow investigators to manually review, edit, confirm, or reject extracted entities for any document.
*Acceptance test:* Open a document's extraction results, edit an entity's name, save; the updated value persists and is reflected in the relationship graph.

**FR-2.4** The System shall extract entities from structured data sources (CDRs, financial records) directly from designated fields without requiring NLP (e.g., phone numbers from a CDR "caller" column).
*Acceptance test:* Ingest a CDR file; confirm phone number entities are created matching the "caller" and "callee" column values.

**FR-2.5** The System shall flag any extracted entity with a confidence score below a configurable threshold (default: 60%) for mandatory human review before it is used in relationship graph construction.
*Acceptance test:* An entity extracted at 45% confidence appears in a "Pending Review" queue and is not auto-linked in the graph until reviewed.

### 3.3 Entity Resolution Module

**FR-3.1** The System shall compare newly extracted entities against existing entities in the database and identify likely matches (duplicates) based on name similarity, shared attributes (phone number, address, ID number), and configurable matching rules.
*Acceptance test:* Ingest a document referencing "Raj Kumar, 9876543210" when an existing entity "R. Kumar, 9876543210" exists; system flags a potential match with a similarity score.

**FR-3.2** The System shall present potential duplicate matches to an authorized user for confirmation or rejection; no automatic merge shall occur without either (a) a match confidence score above a configurable auto-merge threshold (default: 95%) or (b) explicit human confirmation.
*Acceptance test:* A match at 80% confidence appears in a review queue and remains unmerged until a user acts on it.

**FR-3.3** The System shall maintain a full history of entity merge/split actions, including which user performed the action and when.
*Acceptance test:* After merging two entities, the audit log shows the merge event with user ID and timestamp; the merge can be reversed (split) by an authorized user.

**FR-3.4** The System shall support manual creation of new entities directly by investigators (not solely via extraction).
*Acceptance test:* A user manually creates a "Person" entity with name and phone number; the entity appears in search results and is available for relationship linking.

### 3.4 Relationship Graph Module

**FR-4.1** The System shall automatically generate a relationship (edge) between two entities when they co-occur in the same source record (e.g., both mentioned in the same FIR, both parties on the same call, both parties in the same financial transaction).
*Acceptance test:* Ingest a CDR row linking Phone A to Phone B; an edge of type "Communication" is created between the two corresponding entities.

**FR-4.2** The System shall support relationship types including, at minimum: Communication, Financial Transaction, Family, Co-accused, Associate, Employment, Ownership (e.g., vehicle owner), and Location Presence.
*Acceptance test:* Create relationships of each listed type between test entities; each is correctly labeled and displayed in the graph.

**FR-4.3** The System shall assign a weight to each relationship based on frequency/strength of co-occurrence (e.g., number of calls between two phone numbers).
*Acceptance test:* Two entities with 50 shared call records show a higher edge weight than two entities with 2 shared call records.

**FR-4.4** The System shall allow authorized users to manually add, edit, or delete relationships between entities, with a mandatory reason/note field for manual additions.
*Acceptance test:* A user adds a manual relationship without entering a note; system rejects the save action and prompts for a note.

**FR-4.5** The System shall maintain a timestamped history of all relationship changes (creation, edit, deletion) including the responsible user.
*Acceptance test:* Query relationship history for a given edge; all changes and responsible users are listed chronologically.

**FR-4.6** The System shall support filtering the relationship graph by entity type, relationship type, date range, and minimum confidence/weight threshold.
*Acceptance test:* Apply a filter for "Financial Transaction" relationships only, within the last 6 months; only matching edges are displayed.

### 3.5 Influence / Network Analysis Module

**FR-5.1** The System shall compute degree centrality for every entity within a selected network/case.
*Acceptance test:* For a test graph with known degree values, computed values match expected values exactly.

**FR-5.2** The System shall compute betweenness centrality for every entity within a selected network/case.
*Acceptance test:* For a test graph with known betweenness values (validated against a reference graph library), computed values match within an acceptable numerical tolerance (±0.01).

**FR-5.3** The System shall rank and visually highlight the top N (configurable, default 10) entities by centrality score within a selected network.
*Acceptance test:* For a test network, the top-10 list matches the expected ranking derived independently.

**FR-5.4** The System shall support community/cluster detection to identify sub-groups within a larger network.
*Acceptance test:* For a test graph with two known disconnected clusters plus one bridge node, the system correctly identifies the two communities.

**FR-5.5** The System shall provide a "shortest path" function that returns the shortest relationship path(s) between any two selected entities, including all intermediate entities and relationship types.
*Acceptance test:* For a test graph with a known 3-hop path between Entity A and Entity D, the system returns that exact path.

### 3.6 Pattern & Anomaly Detection Module

**FR-6.1** The System shall flag when a phone number, address, vehicle registration, or bank account appears across two or more distinct cases.
*Acceptance test:* Ingest the same phone number into two separate case files; system generates a cross-case alert referencing both case IDs.

**FR-6.2** The System shall flag communication bursts, defined as a configurable threshold (default: ≥10 calls within 24 hours) between two entities with no prior recorded communication history.
*Acceptance test:* Ingest CDR data showing 12 calls in 24 hours between two previously unconnected numbers; system generates a "Communication Burst" alert.

**FR-6.3** The System shall flag circular or structured financial transaction patterns (e.g., funds routed through 3+ intermediate accounts back to a related account) based on configurable rule definitions.
*Acceptance test:* Ingest a test transaction set representing a known circular flow (A→B→C→A); system generates a "Circular Transaction" alert identifying all involved accounts.

**FR-6.4** The System shall allow authorized users to configure detection thresholds and enable/disable specific detection rules.
*Acceptance test:* A user changes the communication-burst threshold from 10 to 20 calls/24 hours; subsequent processing uses the new threshold.

**FR-6.5** Every generated alert shall include: alert type, entities involved, supporting evidence/records, timestamp of detection, and a status field (New, Under Review, Confirmed, Dismissed).
*Acceptance test:* Generate a test alert; confirm all listed fields are present and populated.

**FR-6.6** The System shall allow authorized users to update an alert's status and add investigative notes.
*Acceptance test:* A user changes an alert status from "New" to "Confirmed" and adds a note; the change is saved and reflected in the alert history.

### 3.7 Visualization & Search Module

**FR-7.1** The System shall render an interactive graph visualization for any selected case/network, supporting zoom, pan, and node/edge selection.
*Acceptance test:* Load a test network of 200 nodes; user can zoom in/out and select an individual node to view details without page reload.

**FR-7.2** The System shall provide an entity profile view displaying all known attributes, associated records, and relationships for a selected entity.
*Acceptance test:* Select an entity; profile view displays name, all extracted attributes, linked records, and a relationship list.

**FR-7.3** The System shall provide a search function allowing lookup of entities by name, phone number, vehicle registration, or other unique identifiers, with partial-match/fuzzy-search support.
*Acceptance test:* Search "98765" returns all phone number entities containing that substring.

**FR-7.4** The System shall allow filtering of the graph visualization by entity type, relationship type, date range, and case.
*Acceptance test:* Apply a date filter for the last 30 days; only entities/relationships with activity in that window are displayed.

**FR-7.5** The System shall support exporting the current graph view and an entity/network summary as a PDF report.
*Acceptance test:* Export a network view; generated PDF contains the graph image and a textual summary of top entities and relationships.

### 3.8 User & Case Management Module

**FR-8.1** The System shall support creation of "Cases" as logical containers for related records, entities, and relationships.
*Acceptance test:* A user creates a new case with a name and case ID; the case appears in the case list and can have records assigned to it.

**FR-8.2** The System shall allow assignment of specific users to specific cases, restricting data visibility to assigned users (plus higher-privilege roles as defined in Section 4).
*Acceptance test:* A user not assigned to Case X cannot view Case X's entities or graph (verified via direct URL/API access attempt returning an authorization error).

**FR-8.3** The System shall allow linking of two or more cases when a cross-case entity match is confirmed, enabling a combined network view.
*Acceptance test:* Confirm a cross-case match between Case A and Case B; a combined graph view becomes available showing entities from both cases.

---

## 4. User Roles and Permissions

### 4.1 Defined Roles

| Role | Description |
|---|---|
| **System Administrator** | Manages users, roles, system configuration, and infrastructure; does not necessarily have case data access by default |
| **Senior Official (Reviewer)** | Cross-case, read-oriented access for oversight; can view dashboards, summaries, and all cases within their jurisdiction |
| **Crime Analyst** | Can access assigned cases, perform entity resolution, configure detection rules, and run network analysis |
| **Investigating Officer (IO)** | Can access assigned cases, upload data, view/edit entities and relationships, manage alerts |
| **Data Entry / Support Staff** | Can upload/ingest data into assigned cases but cannot edit relationships, run analytics, or resolve alerts |
| **Auditor** | Read-only access to audit logs and system activity; no access to case content unless separately authorized |

### 4.2 Permission Matrix

| Action | System Admin | Senior Official | Crime Analyst | Investigating Officer | Data Entry Staff | Auditor |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Manage users/roles | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View all cases (jurisdiction-wide) | ❌* | ✅ | ❌ | ❌ | ❌ | ❌ |
| View assigned case(s) | ❌* | ✅ | ✅ | ✅ | ✅ | ❌ |
| Upload/ingest data | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Edit/merge entities | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Add/edit relationships | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Run network/influence analysis | ❌ | ✅ (view only) | ✅ | ✅ | ❌ | ❌ |
| Configure detection rules/thresholds | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Update alert status | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Export reports | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Link/merge cases | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| View audit logs | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| System configuration | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

*System Admins do not have case-data access by default per least-privilege principle; access requires explicit, logged elevation with justification (see FR-9.x, Security).

**FR-9.1 (Roles)** The System shall enforce all permissions in the matrix above at the API/backend level, not solely in the user interface.
*Acceptance test:* A Data Entry Staff user attempting to call the "merge entity" API directly (bypassing the UI) receives a 403 Forbidden response.

**FR-9.2 (Roles)** The System shall support assignment of multiple roles to a single user where applicable (e.g., a user who is both Crime Analyst and Investigating Officer), with effective permissions being the union of assigned roles.
*Acceptance test:* A user assigned both Crime Analyst and IO roles can perform actions permitted to either role.

**FR-9.3 (Roles)** Any change to a user's role or permissions shall take effect within 60 seconds and be logged in the audit trail.
*Acceptance test:* Revoke a user's Crime Analyst role; within 60 seconds, that user can no longer access analyst-only functions.

---

## 5. Business Rules

**BR-1** No entity merge shall be finalized without either (a) an auto-merge confidence score ≥ 95%, or (b) explicit confirmation by a user holding Crime Analyst or Investigating Officer role.

**BR-2** All manually created relationships must include a note/justification field; the field cannot be empty.

**BR-3** An alert generated by the pattern detection module cannot be deleted, only marked as "Dismissed" with a mandatory reason, preserving a permanent audit trail.

**BR-4** A case cannot be permanently deleted from the System; cases may only be archived (soft-deleted), preserving all records and audit history, in line with evidentiary retention requirements.

**BR-5** Cross-case entity matches with a similarity score ≥ 90% must be surfaced to both assigned case teams within 24 hours of detection.

**BR-6** Users may only view entities and relationships belonging to cases to which they are explicitly assigned, except for Senior Official and Auditor roles as defined in the permission matrix.

**BR-7** All AI/ML-generated outputs (extracted entities, inferred relationships, alerts, centrality rankings) must be visually distinguished in the UI from human-verified/confirmed data, and must display a confidence score where applicable.

**BR-8** Data retention periods for ingested records and derived entities/relationships shall follow the agency's official records retention policy; the System shall not auto-delete data absent an explicit retention/archival policy configuration approved by an authorized administrator.

**BR-9** Any bulk export of case data (reports, graph exports) must be logged with the exporting user's ID, timestamp, and the scope of exported data.

---

## 6. Data Requirements and Validations

### 6.1 Core Data Entities

| Entity | Key Attributes |
|---|---|
| **Person** | Full name, aliases, date of birth (if known), national ID/identifier, gender, address(es), phone number(s), photograph (if available), source record references |
| **Location** | Address, coordinates (if available), location type (residence, business, meeting point), associated jurisdiction |
| **Phone Number** | Number, associated carrier (if known), associated person(s), first/last seen dates |
| **Vehicle** | Registration number, make/model, color, owner (linked Person entity) |
| **Organization** | Name, type (business, gang, front company), registered address, associated persons |
| **Event** | Type, date/time, location, involved entities |
| **Case** | Case ID, name, jurisdiction, assigned users, status, creation date |
| **Relationship (Edge)** | Source entity, target entity, relationship type, weight, first/last observed date, supporting record references |
| **Alert** | Type, involved entities, supporting evidence, detection timestamp, status |

### 6.2 Data Validation Rules

**DV-1** Phone numbers shall be validated against a configurable numbering-plan format (e.g., 10-digit national format); numbers failing validation shall be flagged as "Unverified Format" but not rejected outright, since OCR/extraction errors are possible.

**DV-2** Vehicle registration numbers shall be validated against the applicable regional registration format; non-conforming entries are flagged for manual review.

**DV-3** Dates extracted from unstructured documents shall be validated to ensure they fall within a plausible range (not before 1900, not more than 1 day in the future); invalid dates are flagged for manual correction.

**DV-4** All mandatory fields for manually created entities (at minimum: entity type and one identifying attribute) must be completed before the record can be saved.

**DV-5** Duplicate file uploads (identical SHA-256 hash) shall be detected at ingestion time (see FR-1.6).

**DV-6** Structured data imports shall be validated against a defined schema (column names, data types, required fields) prior to ingestion; non-conforming files are rejected with a specific error report (see FR-1.3).

**DV-7** Free-text fields (notes, justifications) shall be limited to 5,000 characters and sanitized to prevent script injection (see Section 9, Security).

**DV-8** Entity confidence scores and relationship weights shall be constrained to a numeric range of 0–100 (or 0.0–1.0 as implemented), with input validation preventing out-of-range values in manual overrides.

### 6.3 Data Retention and Archival

**DR-1** All source documents and derived data shall be retained according to the agency's configured retention policy (default retention period to be defined by legal/compliance stakeholders; not hardcoded in the application).

**DR-2** Archived cases shall remain searchable by Senior Officials and Auditors but shall not appear in default active-case views for standard users.

---

## 7. Authentication and Authorization

**FR-10.1 (Authentication)** The System shall require username/password authentication for all users, with passwords meeting a configurable complexity policy (minimum 12 characters, mix of uppercase, lowercase, numeric, and special characters by default).
*Acceptance test:* Attempt to set a password of "password1"; system rejects it citing complexity requirements.

**FR-10.2 (Authentication)** The System shall support Multi-Factor Authentication (MFA) and shall make MFA mandatory for all users with roles above Data Entry Staff.
*Acceptance test:* A Crime Analyst attempting login without completing the MFA step is denied access.

**FR-10.3 (Authentication)** The System shall lock a user account for a configurable duration (default: 30 minutes) after 5 consecutive failed login attempts.
*Acceptance test:* Enter incorrect credentials 5 times; the 6th attempt (even with correct credentials) is rejected with an "account locked" message.

**FR-10.4 (Authentication)** The System shall enforce session timeout after a configurable period of inactivity (default: 15 minutes), requiring re-authentication.
*Acceptance test:* Leave a session idle for 16 minutes; the next action requires re-login.

**FR-10.5 (Authorization)** The System shall check user permissions on every API request against the permission matrix (Section 4.2) and the user's case assignments before returning data or performing an action.
*Acceptance test:* An IO not assigned to Case Y receives a 403 Forbidden response when attempting to access Case Y's data via any interface (UI or API).

**FR-10.6 (Authorization)** The System shall log every authentication attempt (successful and failed) and every authorization denial, including user ID, timestamp, IP address, and requested resource.
*Acceptance test:* Attempt an unauthorized action; confirm a corresponding entry appears in the audit log within 5 seconds.

**FR-10.7 (Authentication)** The System shall support secure password reset via a time-limited (default: 1 hour), single-use reset token sent through an agency-approved secure channel (not open email, unless explicitly approved by the deployment's security policy).
*Acceptance test:* Request a password reset; confirm the reset link expires after 1 hour and cannot be reused after a successful reset.

---

## 8. Error Handling and Edge Cases

### 8.1 General Error Handling Principles

**EH-1** All user-facing errors shall include a human-readable message and a unique error code for support/troubleshooting purposes; internal system details (stack traces, database errors) shall never be exposed to end users.

**EH-2** All system errors (5xx-class) shall be logged with full technical detail (stack trace, request context) to a centralized logging system accessible only to authorized technical staff.

**EH-3** The System shall gracefully handle and report partial failures during batch operations (e.g., 95 of 100 files ingested successfully) rather than failing the entire batch silently.

### 8.2 Specific Edge Cases

| Edge Case | Expected Behavior |
|---|---|
| Uploaded document is corrupted or unreadable | System rejects the file, logs the failure, and displays a clear "file could not be processed" message; other files in the batch continue processing |
| Extracted entity has no identifiable attributes (e.g., NER identifies "a person" with no name) | Entity is created as "Unidentified Person" with a placeholder ID and flagged for manual review; not silently discarded |
| Two entities are merged, but later found to be distinct | Authorized user can "split" the merged entity, restoring original records with full audit trail (FR-3.3) |
| Relationship graph exceeds a very large size (e.g., >50,000 nodes) for a single case | System paginates/clusters the visualization and warns the user, rather than attempting to render all nodes simultaneously and crashing the browser |
| Two simultaneous users edit the same relationship at the same time | System applies optimistic locking; the second user's save attempt is rejected with a "record was modified by another user" message and prompts a refresh |
| CDR file contains malformed phone numbers (e.g., text instead of numbers) | Row is flagged as invalid, excluded from entity extraction, and reported in an ingestion error summary; valid rows in the same file are still processed |
| A user's session expires mid-edit | Unsaved changes are cached client-side where feasible and the user is prompted to re-authenticate before resuming; if not feasible, the user is warned before the session times out |
| Duplicate case IDs are submitted | System rejects creation of a new case with a duplicate ID and prompts for a unique identifier |
| Detection rule threshold is set to an invalid value (e.g., negative number) | System rejects the configuration change with a validation error before it can be saved |
| A cross-case match is later proven incorrect | Authorized user can unlink the cases; both cases revert to independent visibility, with the action logged |
| Network connectivity loss during file upload | Upload is retried automatically (configurable retry count, default 3) before failing with a clear error; partial uploads are not left in an inconsistent ingested state |

---

## 9. Security Requirements

**SEC-1** All data in transit between client and server shall be encrypted using TLS 1.2 or higher.

**SEC-2** All sensitive data at rest (PII, case data, credentials) shall be encrypted using industry-standard encryption (e.g., AES-256).

**SEC-3** Passwords shall never be stored in plaintext; the System shall use a strong, salted hashing algorithm (e.g., bcrypt or Argon2) for password storage.

**SEC-4** The System shall implement RBAC as defined in Section 4 at both the UI and API layers, with no client-side-only enforcement.

**SEC-5** The System shall log all data access, modification, export, and administrative actions in an immutable (append-only or write-once) audit log, retained per the agency's audit retention policy.

**SEC-6** The System shall sanitize all user inputs to prevent injection attacks (SQL injection, script injection, command injection).

**SEC-7** The System shall undergo periodic security assessments/penetration testing (recommended: at least annually, and after major releases) prior to production deployment and at defined intervals thereafter.

**SEC-8** The System shall not transmit case data to any third-party or external service (including cloud-based AI APIs) without explicit configuration and approval reflecting the deployment's data sovereignty and classification requirements. On-premise or agency-approved private model hosting shall be supported for NLP/ML components where required.

**SEC-9** The System shall support IP allow-listing and/or VPN-only access as configurable deployment options.

**SEC-10** The System shall enforce the principle of least privilege by default for all new user accounts, requiring explicit role assignment before any case data becomes accessible.

**SEC-11** Exported reports containing sensitive data shall support optional watermarking (exporting user, timestamp) to trace unauthorized distribution.

---

## 10. Performance Requirements

**PERF-1** The System shall support a minimum of [50] concurrent active users without response time degradation beyond the thresholds defined below. *(Exact concurrency target to be confirmed with deployment stakeholders based on agency scale.)*

**PERF-2** Standard page loads (dashboard, case list, entity search results) shall complete within 2 seconds under normal load (defined as up to the concurrency target in PERF-1).

**PERF-3** Graph visualization rendering for networks up to 1,000 nodes shall complete within 5 seconds.

**PERF-4** Entity extraction processing shall complete for a standard-length document (up to 5 pages) within 30 seconds per document.

**PERF-5** Bulk structured data ingestion shall process at a minimum rate of 10,000 records per minute.

**PERF-6** Centrality and community-detection computations for a network of up to 10,000 nodes shall complete within 60 seconds.

**PERF-7** The System shall maintain 99% uptime during defined operational hours, measured monthly, excluding scheduled maintenance windows communicated at least 48 hours in advance.

**PERF-8** The System's database and storage architecture shall be designed to scale to at least 10 million entities and 50 million relationships without requiring architectural redesign, though initial deployment sizing may be smaller.

---

## 11. Acceptance Criteria (System-Level)

The System will be considered ready for User Acceptance Testing (UAT) sign-off when:

1. All Functional Requirements in Section 3 pass their defined acceptance tests in a staging environment with representative test data.
2. The permission matrix in Section 4.2 is fully enforced and verified via both UI-based and direct API-based test attempts for each role.
3. All Business Rules in Section 5 are demonstrably enforced (i.e., attempts to violate each rule are correctly blocked or flagged).
4. Data validation rules in Section 6.2 correctly accept valid data and reject/flag invalid data per the defined behavior.
5. Authentication and authorization requirements in Section 7 pass security testing, including account lockout, MFA enforcement, and session timeout behavior.
6. All edge cases listed in Section 8.2 are tested and produce the documented expected behavior (no unhandled crashes or silent data loss).
7. Security requirements in Section 9 are validated via an independent security review/penetration test with no unresolved critical or high-severity findings.
8. Performance requirements in Section 10 are validated via load testing at the target concurrency and data volume, meeting or exceeding all stated thresholds.
9. Entity extraction accuracy on an agreed validation document set achieves an F1 score ≥ 0.85 (per FR-2.1).
10. A full end-to-end scenario — data ingestion → entity extraction → entity resolution → relationship graph construction → influence analysis → alert generation → investigator review and export — is successfully demonstrated using a realistic test case dataset.
11. All audit logging requirements produce complete, accurate, and tamper-evident records for a full test scenario, independently verified.

---

## 12. Assumptions and Dependencies

- Source systems (CDR databases, financial institutions' record systems, criminal history databases) will provide data extracts in agreed formats; direct real-time API integration with these external systems is out of scope for the initial release unless separately contracted.
- The deployment environment (network, servers, identity provider) will be provisioned and secured by the agency's IT/security team in line with Section 9 requirements.
- Legal and compliance review of data handling, retention, and cross-case linking practices will be completed and approved prior to production go-live.
- NLP/ML models will be trained/validated on a representative, agency-approved dataset for the target language(s) and document types prior to deployment.
- Final concurrency, data volume, and retention targets (marked as configurable/TBD in this document) will be confirmed with stakeholders during the design phase.

---

*End of Document*
