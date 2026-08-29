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
│   │       └── llm_linkage_analysis.py   # LLM case-pair analysis
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

## License

For educational and hackathon use (Smart India Hackathon).
