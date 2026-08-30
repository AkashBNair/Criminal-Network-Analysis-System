# 🔍 CRIMENET — AI-Powered Criminal Network Analysis System

An intelligent criminal network analysis platform for law enforcement agencies. It ingests case files (FIRs, suspect dossiers, CDR/location reports), extracts entities and relationships, builds a criminal network graph, and provides actionable intelligence — including suspicious pattern detection, threat assessment, and serial pattern recognition.

## Features

### Core Analysis
- **Entity Extraction** — NLP-powered extraction of suspects, phones, vehicles, locations, and organizations from case documents
- **Relationship Mapping** — Builds criminal network graphs from shared cases, calls, locations, and financial links
- **Entity Resolution** — Deduplicates and merges aliases of the same person across multiple cases
- **Threat Assessment** — AI-scored threat levels (Critical / High / Medium / Low) based on network centrality and role severity

### Pattern Detection
- **Suspicious Patterns** — Automated detection of communication bursts, circular financial transactions, cross-case matches, shared phones, and shared addresses
- **Serial Pattern Recognition** — LLM-powered behavioral analysis to identify serial offending patterns across cases (signature behavior, MO, victimology)
- **Actionable Intelligence** — AI-generated investigative briefs for critical and high-threat suspects

### Visualization
- **People Graph** — Interactive network visualization of suspects with centrality-based sizing and coloring
- **Common Links Report** — Identifies people appearing across multiple cases with exportable PDF reports

### Case Management
- **Officer Login & Access Control** — Role-based authentication (Admin, Crime Analyst, Investigating Officer)
- **Case-Scoped Access** — Each officer only sees cases assigned to them
- **Case Status Management** — Open/closed case lifecycle with archive support
- **Auto Case Registration** — Upload case files and auto-extract case details

### Tamper-Evident Audit Trail (Blockchain)
- **SHA-256 Hash Chaining** — Every audit log entry is cryptographically chained to the previous entry
- **Immutable Chain** — Any modification to a historical record breaks the chain and is instantly detectable
- **On-Demand Verification** — Admin panel verifies full chain integrity in <1ms
- **Tamper Localization** — Reports the exact block index and record where tampering occurred

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Vite |
| Backend | Python + FastAPI + SQLAlchemy |
| Database | SQLite |
| NLP | spaCy (entity extraction) |
| LLM | Groq API (Llama 3.3 70B) + Gemini fallback |
| Visualization | D3.js + React |
| Graph Analytics | NetworkX |
| Audit Integrity | SHA-256 Hash Chain (custom) |

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Groq API key (free at https://console.groq.com)

### Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/sih.git
   cd sih
   ```

2. **Backend setup**
   ```bash
   cd backend
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env and add your GROQ_API_KEY
   ```

3. **Frontend setup**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Run the app**
   ```bash
   # Terminal 1 — Backend
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

   # Terminal 2 — Frontend
   cd frontend
   npm run dev
   ```

5. **Open** http://localhost:5173

### Default Login

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | System Administrator |
| akash | admin123 | Crime Analyst |
| analyst | admin123 | Crime Analyst |
| officer | admin123 | Investigating Officer |

> ⚠️ Change these credentials before any production use.

## Project Structure

```
sih/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── auth.py              # JWT authentication & role permissions
│   │   ├── models/              # SQLAlchemy models
│   │   ├── routers/             # API routes (cases, graph, reports, alerts, etc.)
│   │   └── services/            # Core analysis logic
│   │       ├── entity_extraction.py      # NLP entity extraction
│   │       ├── entity_resolution.py      # Deduplication & alias resolution
│   │       ├── resolved_graph.py         # Graph construction
│   │       ├── graph_analytics.py        # Centrality, community detection
│   │       ├── threat_scoring.py         # Threat assessment
│   │       ├── pattern_detection.py      # Suspicious pattern detection
│   │       ├── pattern_detection_v2.py   # V2 with LLM event verification
│   │       ├── serial_pattern_detection.py # Serial offending detection
│   │       ├── llm_entity_validator.py   # LLM entity validation
│   │       ├── llm_justification_severity.py # LLM severity assessment
│   │       ├── llm_linkage_analysis.py   # LLM case-pair analysis
│   │       └── blockchain.py            # SHA-256 hash chain for audit integrity
│   ├── data/                    # Runtime caches (gitignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard, People Graph, Threat Assessment, etc.
│   │   ├── components/          # Layout, sidebar
│   │   └── api.ts               # API client
│   └── package.json
└── docs/                        # Project documents (PRD, SRS, Architecture)
```

## LLM Integration

The system uses LLM reasoning (via Groq API) in three critical places to avoid false positives from naive keyword matching:

1. **Entity Validation** — Validates whether an extracted entity is a genuine named entity or a false-positive NER error
2. **Justification Severity** — Context-aware assessment of how strongly evidence text implicates a person (avoids scoring "cleared of murder" same as "confessed to murder")
3. **Serial Pattern Linkage** — LLM judges genuine behavioral similarity between cases, rejecting surface-level word overlap

Results are cached to minimize API calls. First analysis burns calls; subsequent runs use the cache.

## Blockchain Audit Trail

The system uses a **SHA-256 hash chain** to ensure audit log integrity — the same cryptographic primitive used in Bitcoin and other blockchains, deployed in a lightweight single-node configuration appropriate for institutional audit logs.

### How It Works

```
Block 0 (Genesis)     Block 1              Block 2
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ action:     │     │ action:     │     │ action:     │
│ login       │     │ create_case │     │ update_ent  │
│             │     │             │     │             │
│ details_hash│     │ details_hash│     │ details_hash│
│     │       │     │     │       │     │     │       │
│ prev: 000.. │     │ prev: hash │     │ prev: hash │
│     │       │     │  of Block 0│     │  of Block 1│
│ block_hash ─┼────▶│ block_hash ─┼────▶│ block_hash │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Every `log_audit()` call** (which is invoked by every API router after any data mutation) automatically:
1. Creates a new block with the action details
2. Computes SHA-256 of the details JSON → `details_hash`
3. Sets `previous_hash` to the most recent block's `block_hash`
4. Computes `block_hash` = SHA-256(all block fields)
5. Stores everything in the `audit_logs` table

**Verification** walks the chain from Block 0, recomputing each hash and checking linkage. Any tampering breaks the chain at the exact point of modification.

### Why Not a Full Blockchain Library?
- This is a **single-institution** system — no multi-party consensus needed
- The police department is the trusted writer; no distributed trust problem
- Zero external dependencies, zero infrastructure cost
- Verification is instant (0.2ms for 7 blocks)
- The core crypto (SHA-256 chaining) is identical to what real blockchains use

## License

For educational and hackathon use (Smart India Hackathon).
