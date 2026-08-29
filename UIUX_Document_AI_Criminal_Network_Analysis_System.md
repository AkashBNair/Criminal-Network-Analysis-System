# UI/UX Design Document
## AI-Powered Criminal Network Analysis System

**Document Version:** 1.0
**Date:** August 23, 2026
**Status:** Draft for Review
**Related Documents:** PRD v1.0, SRS v1.0, System Architecture v1.0

---

## 1. Purpose

This document defines the user experience and interface design for the AI-Powered Criminal Network Analysis System. It covers user journeys, navigation, screen-by-screen specifications, flows, components, interaction states, forms, responsive behavior, accessibility, and the visual design system (typography, color, spacing). It is intended to be implementation-ready for frontend engineers and designers building the MVP defined in the PRD/SRS.

---

## 2. Design Principles

1. **Clarity over decoration.** Investigators work with sensitive, high-stakes information. Every screen should prioritize legibility and unambiguous meaning over visual flourish.
2. **Evidence, not accusation.** The UI must visually distinguish AI-generated/inferred data (entities, relationships, alerts) from human-confirmed data at all times, using consistent, unmissable visual cues (see Section 12). The system suggests; the investigator decides.
3. **Progressive disclosure.** Show a simple, focused view by default (e.g., a case summary or a filtered graph); let advanced detail (raw records, confidence scores, full audit history) be one click away, not on-screen by default.
4. **Consistency over novelty.** Reuse the same graph visualization, entity card, and alert patterns everywhere they appear. Investigators should never have to relearn an interaction pattern between screens.
5. **Designed for stress and fatigue.** Investigators may be reviewing dense information over long shifts. High contrast, generous spacing, and forgiving interactions (confirmations before destructive actions, undo where feasible) reduce error and cognitive load.
6. **No dead ends.** Every screen — including empty, loading, and error states — gives the user a clear next action.

---

## 3. Target Users (Recap for Design Context)

| Role | Primary Screens Used | Design Implication |
|---|---|---|
| Investigating Officer | Case dashboard, entity profile, graph view, alerts | Needs fast search, clear entity summaries, simple manual editing |
| Crime Analyst | Graph view, analytics panel, rule configuration, entity resolution queue | Needs power-user tools: filters, thresholds, bulk review |
| Senior Official | Cross-case dashboard, reports | Needs high-level summaries, minimal interaction depth |
| Data Entry Staff | Upload/ingestion screen | Needs a simple, error-tolerant upload flow |
| Auditor | Audit log viewer | Needs a read-only, searchable, tabular view |

---

## 4. Information Architecture & Navigation

### 4.1 Top-Level Navigation (Persistent Sidebar)

```
┌────────────────────┐
│ 🔍  Search           │
│ 🏠  Dashboard         │
│ 📁  Cases             │
│ 🕸️  Network Explorer  │
│ 🚨  Alerts            │
│ 📤  Ingestion         │
│ 📄  Reports           │
│ ⚙️  Admin (role-gated)│
│ 🧾  Audit Log (Auditor)│
└────────────────────┘
```

- Navigation is role-aware: items the user's role cannot access are hidden entirely (not shown-but-disabled), to avoid confusing users with inaccessible options.
- A persistent global search bar sits at the top of every screen (see Section 6.3).
- The currently selected **Case context** is shown as a persistent breadcrumb/chip near the top of the screen whenever the user is working within a specific case, so investigators always know which case's data they are viewing.

### 4.2 Site Map

```
Login / MFA
  └── Dashboard (role-specific landing)
        ├── Case List
        │     └── Case Detail
        │           ├── Case Overview
        │           ├── Entity List
        │           │     └── Entity Profile
        │           ├── Network Explorer (graph view, scoped to case)
        │           ├── Alerts (scoped to case)
        │           ├── Ingestion (scoped to case)
        │           └── Case Reports/Export
        ├── Global Network Explorer (cross-case, if authorized)
        ├── Global Alerts Queue
        ├── Global Search Results
        ├── Reports (all accessible reports)
        ├── Admin
        │     ├── User Management
        │     ├── Role/Permission Management
        │     └── Detection Rule Configuration
        └── Audit Log (Auditor role)
```

---

## 5. User Journeys

### 5.1 Journey: Investigating Officer reviews a new FIR and explores connections
1. Logs in (MFA) → lands on personalized Dashboard.
2. Opens assigned Case → Case Overview screen.
3. Uploads a new FIR document via Ingestion screen.
4. Receives an in-app notification when extraction completes.
5. Reviews extracted entities in the "Pending Review" queue; confirms or edits them.
6. Navigates to Network Explorer to see the newly added entities in context.
7. Clicks a suspicious entity to view its full Entity Profile, including all relationships.
8. Adds a manual relationship based on investigative knowledge, with a required justification note.
9. Exports a summary report for the case file.

### 5.2 Journey: Crime Analyst investigates a cross-case pattern
1. Logs in → Dashboard shows a summary of new alerts.
2. Opens Alerts Queue, filters by "Cross-Case Match" type.
3. Opens an alert → sees the two cases and shared entity (e.g., a phone number) highlighted.
4. Opens Network Explorer in "combined view" to see both cases' networks merged around the shared entity.
5. Runs centrality analysis to identify key individuals in the combined network.
6. Updates the alert status to "Confirmed" with an investigative note.
7. Links the two cases formally so future views default to the combined network.

### 5.3 Journey: Senior Official reviews overall network activity
1. Logs in → lands on an oversight Dashboard (read-oriented, cross-case).
2. Views summary cards: active cases, high-priority alerts, top-ranked influential individuals across jurisdiction.
3. Drills into a specific case's Network Explorer (read-only) for a closer look.
4. Exports a jurisdiction-level summary report.

---

## 6. Screen Specifications

For each screen: purpose, key components, primary actions, and states.

### 6.1 Login / MFA Screen
- **Purpose:** Secure entry point.
- **Components:** Username/password fields, "Forgot password" link, MFA code entry step (shown after successful password validation), agency logo/branding, session security notice (e.g., "This system is for authorized use only").
- **States:** Default, validating, invalid credentials (inline error, no field-specific hints beyond "Invalid username or password" to avoid username enumeration), account locked (clear message with retry time), MFA required, MFA invalid.

### 6.2 Dashboard (Role-Specific Landing Page)
- **Purpose:** At-a-glance summary tailored to the user's role.
- **Components (Investigating Officer/Analyst view):**
  - "My Cases" card list (case name, status, unread alert count)
  - "Recent Alerts" panel (top 5, with severity tags)
  - "Pending Entity Reviews" count with quick link
  - Quick search bar
- **Components (Senior Official view):** Jurisdiction-wide summary cards (active cases, total alerts by severity, top influential individuals across cases), with drill-down links.
- **Empty state:** New users with no assigned cases see a friendly message: "You have no assigned cases yet. Contact your administrator." with no broken/empty widgets.

### 6.3 Global Search
- **Purpose:** Fast lookup of any entity by name, phone number, vehicle registration, or ID, across accessible cases.
- **Components:** Search input with autocomplete/fuzzy suggestions, filter chips (entity type, case), results list showing entity type icon, name, matched attribute, and case association.
- **States:**
  - *Loading:* Skeleton list rows while results load.
  - *No results:* "No matching entities found. Check the spelling or try a partial number/name." with a suggestion to broaden filters.
  - *Unauthorized results excluded silently* — the user never sees a "result exists but you can't view it" message, to avoid leaking the existence of restricted case data.

### 6.4 Case List
- **Purpose:** List all cases the user can access.
- **Components:** Table/card list with columns: Case ID, Name, Status (Active/Archived), Assigned Users, Last Updated, Alert Count. Filter/sort controls. "Create New Case" button (role-gated).
- **States:** Loading (skeleton rows), empty ("No cases found" with a "Create Case" call-to-action for authorized roles), error (retry banner if the list fails to load).

### 6.5 Case Overview
- **Purpose:** Landing page for a specific case.
- **Components:** Case metadata header (ID, name, status, assigned team), summary stats (entity count, relationship count, open alerts), tabbed navigation to Entities / Network Explorer / Alerts / Ingestion / Reports within the case, recent activity feed.

### 6.6 Entity List (within a case)
- **Purpose:** Browsable/filterable list of all entities in the case.
- **Components:** Filter bar (entity type, confidence threshold, review status), sortable table (Name, Type, Confidence, Last Seen, Relationship Count), bulk-select for batch review actions.
- **States:** Loading, empty ("No entities yet — upload data to begin extraction"), pending-review badge shown per row.

### 6.7 Entity Profile
- **Purpose:** Full detail view of a single entity.
- **Components:**
  - Header: entity name/identifier, type icon, confidence score badge, "AI-extracted" or "Human-confirmed" tag.
  - Attributes panel: all known attributes (aliases, phone numbers, addresses, etc.), each with source record links.
  - Relationships panel: list of connected entities with relationship type, weight/strength, and a "view in graph" shortcut.
  - Source records panel: list of original documents/records that mention this entity.
  - Action buttons: Edit, Merge with another entity, Add relationship, Flag for review.
- **States:** Loading skeleton, "entity has no confirmed relationships yet" empty state within the relationships panel.

### 6.8 Entity Resolution / Review Queue
- **Purpose:** Investigator/analyst reviews AI-suggested entity matches (potential duplicates) and low-confidence extractions.
- **Components:** Side-by-side comparison card (Entity A vs. Entity B, shared attributes highlighted), similarity score, "Merge" / "Not a Match" / "Skip" actions; separate tab for low-confidence single-entity reviews (confirm/edit/discard).
- **States:** Empty ("No items pending review — you're all caught up"), loading, and a confirmation dialog before any merge ("This will combine all records for these two entities. This action can be reversed by an administrator. Continue?").

### 6.9 Network Explorer (Graph View)
- **Purpose:** The core investigative tool — interactive visualization of entities and relationships.
- **Components:**
  - Central canvas: force-directed graph, nodes colored/shaped by entity type, edges styled by relationship type and weight (thicker = stronger).
  - Left panel: filters (entity type, relationship type, date range, minimum confidence/weight, case scope).
  - Right panel (contextual): details of the currently selected node or edge.
  - Top toolbar: search-within-graph, "Top Influencers" toggle (highlights top-N centrality nodes), "Find Path" tool (select two nodes to trace shortest path), zoom controls, export-view button.
  - Legend: persistent, collapsible legend explaining node/edge colors and shapes.
- **Interactions:**
  - Click a node → opens contextual detail panel (not a full navigation away from the graph, to preserve context).
  - Double-click a node → navigates to full Entity Profile.
  - Drag to reposition nodes (manual layout adjustment); "Reset Layout" button to restore auto-layout.
  - Hover over an edge → tooltip showing relationship type, weight, and first/last observed date.
- **States:**
  - *Loading:* Skeleton graph placeholder with a progress indicator, especially important since large graphs may take a few seconds to render.
  - *Empty:* "This case has no relationships yet. Upload data or add entities to begin building the network." with a shortcut to Ingestion.
  - *Large graph warning:* If node count exceeds a configured threshold (e.g., 1,000), display a non-blocking banner: "This network is large — showing the most connected 500 entities. Use filters to narrow the view." rather than silently truncating.

### 6.10 Alerts Queue
- **Purpose:** Central place to review pattern-detection alerts.
- **Components:** Filterable/sortable table (Alert Type, Entities Involved, Detected Date, Status, Severity), detail drawer on row click showing supporting evidence and a "View in Network Explorer" shortcut, status-update controls (New → Under Review → Confirmed/Dismissed) with mandatory note on Dismiss.
- **States:** Empty ("No active alerts"), loading, and a clear visual distinction between severity levels (see Section 12 color system).

### 6.11 Ingestion / Upload Screen
- **Purpose:** Upload structured and unstructured data sources.
- **Components:** Drag-and-drop upload zone (with a visible "Browse files" fallback button for accessibility), file-type/size guidance text, upload queue list showing per-file progress and status, batch summary after completion (X succeeded, Y failed, with reasons).
- **States:**
  - *Uploading:* Per-file progress bar.
  - *Validation error:* Inline error per rejected file (e.g., "Missing required column: phone_number") with a link to a template/format guide.
  - *Duplicate detected:* Modal prompt — "This file appears to have been uploaded before on [date]. Upload again?" with Cancel/Proceed options.
  - *Success:* Confirmation summary with a link to the entity review queue if extraction is triggered.

### 6.12 Reports / Export Screen
- **Purpose:** Generate and download PDF summaries of a case, network, or entity.
- **Components:** Report type selector (Case Summary, Network Snapshot, Entity Profile), scope/filter options matching what's currently in view, "Generate Report" button, list of previously generated reports with download links and export metadata (who exported, when).
- **States:** Generating (progress indicator, since PDF rendering may take several seconds for large graphs), ready (download link appears), error (retry option).

### 6.13 Admin: User & Role Management
- **Purpose:** Manage users, roles, and case assignments (System Administrator only).
- **Components:** User table (name, role(s), status, last login), "Add User" form, role-assignment multi-select, case-assignment matrix for assigning users to specific cases.
- **States:** Standard CRUD states (loading, empty, validation errors on form fields, success confirmation toast).

### 6.14 Admin: Detection Rule Configuration
- **Purpose:** Configure pattern-detection thresholds and enable/disable rules (Crime Analyst / Admin).
- **Components:** List of rules (Communication Burst, Circular Transaction, Cross-Case Match, etc.) each with an enable/disable toggle and editable threshold fields; inline validation (e.g., threshold must be a positive integer); "Save Changes" with a confirmation summary of what changed.

### 6.15 Audit Log Viewer (Auditor role)
- **Purpose:** Read-only, searchable view of all system activity.
- **Components:** Filterable table (User, Action Type, Resource, Timestamp, IP Address), date-range filter, export-to-CSV option.
- **States:** Loading, empty (only if filters return nothing — the log itself is never truly empty), no edit actions available anywhere on this screen by design.

---

## 7. Key User Flows (Step-by-Step)

### 7.1 Flow: Upload a Document → Review Extracted Entities
```
Ingestion Screen
   → Select/drag file
   → Client-side file type/size check
   → Upload (progress shown)
   → Server validation
        ├── Fail → Inline error, file remains editable/re-uploadable
        └── Pass → Queued for extraction → Confirmation toast
   → [Async] Extraction completes → In-app notification badge
   → User opens Entity Review Queue
   → For each extracted entity: Confirm / Edit / Discard
   → Confirmed entities appear in Entity List and Network Explorer
```

### 7.2 Flow: Merge Two Duplicate Entities
```
Entity Resolution Queue (or Entity Profile "Merge" action)
   → Select candidate match
   → Side-by-side comparison shown
   → User selects "Merge"
   → Confirmation dialog (explains consequences, notes reversibility)
   → Confirm
   → Merge executes → Success toast → Audit log entry created
   → (If needed later) Admin can "Split" from the entity's history panel
```

### 7.3 Flow: Investigate an Alert
```
Alerts Queue → Filter by type/severity
   → Select an alert → Detail drawer opens
   → Review supporting evidence
   → "View in Network Explorer" → graph opens pre-filtered to relevant entities
   → Return to alert → Update status (Under Review / Confirmed / Dismissed)
   → If Dismissed → mandatory reason field → Save
```

### 7.4 Flow: Trace Relationship Path Between Two Suspects
```
Network Explorer → "Find Path" tool activated
   → Click first entity (Entity A)
   → Click second entity (Entity B)
   → System highlights shortest path with all intermediate entities/edges
   → Path details shown in right panel (hop count, relationship types)
   → Option to export this path view as a report
```

---

## 8. Forms — Design Standards

- **Labels:** Always visible above the field (never placeholder-only labels, which disappear on input and harm usability/accessibility).
- **Required fields:** Marked with a red asterisk (*) and enforced with inline validation on blur, not only on submit.
- **Validation messages:** Specific and actionable (e.g., "Phone number must be 10 digits" rather than "Invalid input"), shown directly below the relevant field.
- **Destructive actions:** Always require a confirmation dialog with explicit consequences stated in plain language (e.g., relationship deletion, entity merge, alert dismissal).
- **Justification/note fields:** Wherever a business rule requires a note (manual relationship creation, alert dismissal), the field is visually marked as required and the Save/Submit button remains disabled until it is populated.
- **Multi-step forms** (e.g., case creation with team assignment): Use a simple stepper component with clear step labels and the ability to go back without losing entered data.

---

## 9. Loading, Error, and Empty States (System-Wide Standards)

| State | Standard Treatment |
|---|---|
| **Loading (short, <1s expected)** | Inline spinner on the triggering element (e.g., button) |
| **Loading (longer, e.g., graph render, report generation)** | Skeleton screens matching the eventual layout, plus a progress indicator or estimated time where feasible |
| **Empty (no data exists yet)** | Friendly, specific message explaining *why* it's empty and *what to do next* (never a blank screen with no explanation) |
| **Empty (filtered to zero results)** | Distinguish from true emptiness: "No results match your filters" with a "Clear filters" action |
| **Error (recoverable, e.g., failed API call)** | Inline banner with a plain-language explanation and a "Retry" button; technical details are not shown to the user (per SRS EH-1) but are logged |
| **Error (blocking, e.g., session expired)** | Modal interrupt explaining the issue with a single clear action (e.g., "Log in again") |
| **Partial success (e.g., batch upload)** | Summary state clearly separating succeeded vs. failed items, with failed items individually actionable (retry/view reason) |

---

## 10. Responsive Behavior

The System is designed **desktop-first**, reflecting its primary use in an office/investigative-desk context, with graceful adaptation down to tablet width. A dedicated mobile-optimized experience is out of scope for MVP (per PRD), but the interface must remain usable on tablet devices for field use.

| Breakpoint | Target Devices | Layout Behavior |
|---|---|---|
| **≥1280px (Desktop)** | Standard investigator workstations | Full three-panel layouts (e.g., Network Explorer: filter panel + graph canvas + detail panel) all visible simultaneously |
| **768–1279px (Tablet / small laptop)** | Tablets, small laptops | Side panels collapse into slide-over drawers triggered by icon buttons; graph canvas takes priority as the main view |
| **<768px (Mobile)** | Phones (not a primary target) | Core screens (Dashboard, Alerts, Case List) remain functionally usable in a single-column layout; Network Explorer displays a simplified message recommending a larger screen for full graph interaction, rather than attempting a degraded graph experience that could mislead investigators |

**Note:** Given the analytical density of graph visualization, forcing full graph interactivity onto a small phone screen would risk investigators misreading a cramped, hard-to-navigate network — the explicit recommendation to switch devices is a deliberate safety choice, not a limitation to hide.

---

## 11. Accessibility

The System targets **WCAG 2.1 Level AA** compliance, appropriate for a government system.

- **Color contrast:** Minimum 4.5:1 contrast ratio for body text, 3:1 for large text and UI component boundaries.
- **Color is never the sole indicator:** Alert severity, entity confidence, and relationship type are always paired with icons, labels, or patterns in addition to color (critical given colorblindness prevalence and the high-stakes nature of misreading an alert's severity).
- **Keyboard navigation:** All interactive elements (including graph node selection, via a keyboard-accessible list fallback) must be reachable and operable via keyboard alone, with a visible focus indicator at all times.
- **Screen reader support:** Semantic HTML and ARIA labels on all custom components (graph canvas includes an accessible data-table alternative view for screen reader users, since raw SVG/canvas graphs are not reliably screen-reader-navigable).
- **Text resizing:** UI remains functional and legible at up to 200% browser zoom without loss of content or functionality.
- **Motion:** Any animated transitions (e.g., graph layout changes) respect the user's OS-level "reduce motion" setting.
- **Form accessibility:** All form fields have programmatically associated labels; error messages are announced to assistive technology (e.g., via `aria-live` regions).

---

## 12. Visual Design System

### 12.1 Design Philosophy
Simple, modern, and restrained — a "data-first" aesthetic similar to professional analytics/BI tools rather than a consumer app. The interface should feel authoritative, calm, and trustworthy, avoiding anything that reads as playful or ambiguous given the sensitivity of the subject matter.

### 12.2 Typography

| Use | Font | Weight | Size (Desktop) |
|---|---|---|---|
| Primary typeface | **Inter** (or system-ui fallback stack) | — | — |
| Page titles (H1) | Inter | Semibold (600) | 28px |
| Section headers (H2) | Inter | Semibold (600) | 20px |
| Card/subsection headers (H3) | Inter | Medium (500) | 16px |
| Body text | Inter | Regular (400) | 14px |
| Small/meta text (timestamps, IDs) | Inter | Regular (400) | 12px |
| Monospace (for IDs, phone numbers, registration numbers) | **JetBrains Mono** or system monospace | Regular (400) | 13px |

**Rationale:** Inter is a highly legible, neutral, widely available typeface well-suited to dense data interfaces; a monospace face for identifiers (phone numbers, case IDs, vehicle plates) improves scanability and reduces transcription errors — an important detail in an investigative tool.

### 12.3 Color System

**Base/Neutral Palette** (backgrounds, text, borders):

| Token | Hex | Usage |
|---|---|---|
| `neutral-900` | #111827 | Primary text |
| `neutral-600` | #4B5563 | Secondary text |
| `neutral-300` | #D1D5DB | Borders, dividers |
| `neutral-100` | #F3F4F6 | Backgrounds, cards |
| `neutral-0` | #FFFFFF | Base background |

**Primary/Action Color:**

| Token | Hex | Usage |
|---|---|---|
| `primary-600` | #1D4ED8 | Primary buttons, active nav items, links |
| `primary-100` | #DBEAFE | Selected/hover backgrounds |

**Semantic Colors** (used consistently across alerts, confidence, and status indicators):

| Token | Hex | Meaning |
|---|---|---|
| `success-600` | #15803D | Confirmed/verified data, successful actions |
| `warning-600` | #B45309 | Pending review, medium-severity alerts, low-to-medium confidence |
| `danger-600` | #B91C1C | High-severity alerts, destructive actions, critical warnings |
| `info-600` | #0369A1 | Informational banners, neutral notices |

**Entity Type Colors** (used for graph nodes, kept distinct and colorblind-considerate):

| Entity Type | Color |
|---|---|
| Person | `#2563EB` (blue) |
| Location | `#059669` (green) |
| Phone Number | `#7C3AED` (purple) |
| Vehicle | `#D97706` (amber) |
| Organization | `#DB2777` (pink) |
| Event | `#4B5563` (neutral gray) |

**AI-generated vs. human-confirmed indicator:** A consistent small badge/icon (not solely color) — e.g., a dashed node border + "AI" tag for unconfirmed/AI-only data, a solid border + checkmark for human-confirmed data — applied uniformly across entity cards, profiles, and graph nodes.

### 12.4 Spacing System

An 8px base spacing scale is used throughout for consistency and easy implementation with standard CSS/utility frameworks:

| Token | Value | Typical Use |
|---|---|---|
| `space-1` | 4px | Icon-to-text gaps |
| `space-2` | 8px | Compact element spacing |
| `space-3` | 12px | Form field spacing |
| `space-4` | 16px | Card padding, standard gaps |
| `space-6` | 24px | Section spacing |
| `space-8` | 32px | Page-level margins |
| `space-12` | 48px | Major section breaks |

### 12.5 Component Library Foundations
Recommended to build on an existing, accessible component library rather than a fully custom design system, to accelerate implementation and ensure accessibility defaults are handled:
- **Recommended base:** A headless/accessible component library such as **Radix UI** or **shadcn/ui**, styled with **Tailwind CSS**, for buttons, dialogs, dropdowns, tables, and form controls.
- **Graph rendering:** Cytoscape.js or Sigma.js (per Architecture doc), themed to match the color/typography system above via CSS variables.

### 12.6 Iconography
A single consistent icon set (e.g., **Lucide** or **Heroicons**) throughout, used at 16px (inline/text-adjacent) and 20px (standalone/nav) sizes, always paired with text labels in navigation (icons are never the sole label for a primary navigation item).

### 12.7 Elevation & Borders
- Flat design with subtle elevation: cards and modals use a light shadow (`0 1px 3px rgba(0,0,0,0.1)`) rather than heavy drop shadows, keeping the interface calm and data-focused.
- 1px borders (`neutral-300`) used to delineate panels (e.g., graph canvas vs. filter panel) rather than relying solely on shadow/elevation.

---

## 13. Component Inventory (Reusable UI Elements)

| Component | Used In | Key States |
|---|---|---|
| Entity Card | Search results, entity lists, review queue | Default, selected, AI-flagged, human-confirmed |
| Graph Node | Network Explorer | Default, selected, highlighted (top influencer/path), dimmed (filtered out) |
| Alert Row | Alerts Queue, Dashboard | New, Under Review, Confirmed, Dismissed (each with a distinct badge) |
| Confidence Badge | Entity Profile, Review Queue | Color-coded by score band (e.g., <60% warning, ≥60% neutral/success), always shows numeric value |
| File Upload Row | Ingestion Screen | Queued, Uploading, Validating, Success, Failed |
| Confirmation Dialog | Merge, Delete, Dismiss actions | Standard pattern: title, consequence explanation, Cancel/Confirm buttons |
| Toast Notification | Global | Success, Error, Info — auto-dismiss after 5s except errors, which persist until manually dismissed |
| Filter Panel | Network Explorer, Entity List, Alerts Queue | Collapsed, expanded, active-filter-count badge |
| Data Table | Case List, Entity List, Audit Log | Loading (skeleton), populated, empty, sortable column headers |

---

## 14. Notifications & Feedback Patterns

- **In-app notification badge:** Shown on the relevant nav item (e.g., a red dot on "Alerts" when new alerts exist) rather than intrusive pop-ups, respecting focused investigative work.
- **Toasts:** Used for confirmations of user-initiated actions (save, merge, export) — brief, non-blocking, bottom-right positioned.
- **Modals:** Reserved for decisions requiring explicit confirmation (destructive or high-consequence actions) — never used for simple informational messages.
- **Long-running job feedback (extraction, analytics, report generation):** Persistent, dismissible progress indicator in a "Jobs" tray accessible from the top bar, so users can navigate away and check back rather than being blocked by a spinner.

---

## 15. Implementation Notes for Engineering

- Build the graph visualization component once as a shared, configurable component (supporting both full Network Explorer mode and a smaller "mini-graph" mode used in Entity Profiles and Alert detail views) rather than duplicating graph-rendering logic.
- All confidence scores and AI/human-confirmed indicators should be driven by a shared design-token/component so that visual treatment stays consistent as the product evolves.
- Empty/loading/error states should be implemented as shared components per data-display pattern (table, card list, graph) rather than ad hoc per screen, to guarantee the consistency described in Sections 9–10.
- Respect the role-based navigation visibility rules (Section 4.1) at the routing level, not just by hiding nav links, so that direct URL access to an unauthorized screen is redirected/blocked with a clear message, consistent with the backend authorization enforcement described in the SRS.

---

*End of Document*
