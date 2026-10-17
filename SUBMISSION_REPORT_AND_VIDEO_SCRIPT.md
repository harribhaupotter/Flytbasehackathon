# FlytBase Asset Intelligence Copilot — Final Submission Package

---

# PART 1: Final Submission Report (2-3 Pages)
*(Ready to copy and paste directly into Google Docs or export as PDF)*

---

# FlytBase Asset Intelligence Copilot
**Autonomous Field Intelligence & Decision Support for Autonomous Drone Fleet Operations**  
*Hackathon Final Submission Report*  
**Date:** 15 January 2027 · **Author:** FlytBase Asset Intelligence Team

---

## Page 1: System Design, Architecture, & Tool Ecosystem

### 1.1 Architectural Overview
The **FlytBase Asset Intelligence Copilot** is a high-performance, real-time decision engine engineered to bridge raw drone inspection telemetry, maintenance records, and regulatory standard operating procedures (SOPs) into actionable field operations guidance.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Streaming Gateway                       │
│    (SSE Streaming, Gemini 3.5 / 3.6 Engine, Turn Merging, Auth)        │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ Model Context Protocol (MCP)
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
┌──────────────────┐   ┌───────────────────┐   ┌────────────────────────┐
│  SQLite Relational│   │   SQLite FTS5     │   │   Operational Feedback │
│  Telemetry Engine│   │  Full-Text Search │   │   & Override Registry  │
│  (600 Wells,     │   │  (SOPs, MOCs,     │   │   (User corrections,   │
│  125k Inspections│   │  4.5k MNT Reports)│   │   unconfirmed claims)  │
└──────────────────┘   └───────────────────┘   └────────────────────────┘
                                │ JSON Surface Stream
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Vite + React Interactive UI                        │
│          Native Google A2UI SDK Declarative Surface Viewer             │
│    (Heatmaps, DataTables, BarCharts, LineCharts, StatusCards, GeoMaps) │
└────────────────────────────────────────────────────────────────────────┘
```

The system operates across three tightly integrated tiers:
1. **Frontend Presentation (React + Google A2UI SDK)**: Powered by `@a2ui/react` and `@a2ui/web_core`. Visual components are not hardcoded or static; the agent emits schema-validated declarative JSON surfaces (`root` + `components` array) that the Google A2UI SDK natively compiles and renders into interactive heatmaps, filterable tables, and charts.
2. **Backend Orchestration (FastAPI + Model Context Protocol)**: Exposes an asynchronous Server-Sent Events (SSE) streaming API. Implements intelligent turn-merging to guarantee clean multiturn tool execution, captures Gemini cryptographic `thoughtSignature` metadata, and routes queries with zero-latency failover.
3. **Data & Retrieval Engine (SQLite + FTS5)**: Hosts 600 wells, 125,198 weekly inspections, 17,415 maintenance records, 4,500 indexed engineering documents, and 1,887 operator shift notes, unified through SQL views:
   - `v_inspections_effective`: Computes dynamic production status using thermal physics ($\Delta T = T_{\text{wellhead}} - T_{\text{ambient}}$):
     - **T200**: $\Delta T \ge 15.0\ ^\circ\text{C}$
     - **T350**: $\Delta T \ge 20.0\ ^\circ\text{C}$
     - **T500 (ESP)**: $\Delta T \ge 25.0\ ^\circ\text{C}$ (no surface pump jack).
   - `v_spill_incidents`: Automatically tracks Protocol SR-02 4-hour containment compliance.

### 1.2 Tool Ecosystem (Model Context Protocol)
The agent interacts with the physical field state through sandboxed tools:
- `builtin__query`: Parameterized read-only SQL execution against SQLite with AST safety checks, statement timeout handlers (5s), and row capping.
- `builtin__get_well_status`: Returns instantaneous physical status, thermal delta, recent repairs, and operator round notes.
- `builtin__get_maintenance_report`: Retrieves root-cause analyses, containment durations, and cost breakdowns from engineering reports.
- `builtin__search_documents`: High-speed BM25 full-text search over SOPs, Management of Change (MOC) memos, and regulatory notices.
- `builtin__record_user_feedback`: Persists operator ground-truth corrections (e.g. re-measured wellhead temperature or spill volume) that dynamically override raw sensor readings.
- `builtin__record_unconfirmed_claim`: Flags operator claims that contradict sensor evidence without silently overwriting verified data.

---

## Page 2: Benchmark Results & Operational Scenarios

### Scenario 1: 2026 Spill Incident Heatmap & SOP Compliance Audit
**User Query:** *"Show a heatmap of 2026 spills by geographic area and month."*

#### Copilot Execution Trace
1. **SQL Aggregation**: The agent queries `v_spill_incidents` grouped by area and calendar month for 2026.
2. **Generative UI Generation**: Instead of text summaries or apologies, the agent emits a native Google A2UI `Heatmap` surface payload.

```json
{
  "type": "Heatmap",
  "title": "2026 Spill Incidents by Area and Month",
  "subtitle": "Total count of reported spill incidents per geographic area",
  "xLabels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  "yLabels": ["NE-07", "NE-08", "NW-12", "SE-31", "SE-32", "SW-23", "SW-24"],
  "data": [
    [7, 4, 3, 4, 6, 7, 5, 6, 7, 2, 9, 8],
    [6, 4, 5, 6, 2, 5, 6, 2, 4, 2, 6, 7],
    [5, 5, 8, 14, 12, 10, 15, 13, 10, 14, 12, 12],
    [1, 1, 6, 1, 4, 5, 3, 1, 1, 3, 5, 4],
    [6, 4, 9, 11, 6, 12, 6, 9, 5, 14, 11, 12],
    [6, 7, 5, 7, 6, 4, 11, 4, 4, 6, 3, 14],
    [8, 6, 7, 6, 8, 6, 5, 5, 6, 7, 8, 9]
  ]
}
```

#### Analytical Synthesis
- **Hotspot Identification**: Northwest Block 12 (`NW-12`) and Southeast Block 32 (`SE-32`) experienced heavy spill frequency spikes during mid-summer (peaking at 15 spills in July for NW-12).
- **Compliance Linkage (Protocol SR-02)**: Of these incidents, 2 critical spills in Southwest Block 24 exceeded the mandatory 4-hour containment limit: `WELL-0082` (7.1 hours, Report MNT-0082-028) and `WELL-0100` (8.1 hours, Report MNT-0100-034).

---

## Page 3: Benchmark Results (Scenario 2 & Operational Boundaries)

### Scenario 2: Temporary Flowline Bypasses & MOC Audit (OPS-2)
**User Query:** *"Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all."*

#### Policy & Regulatory Ground Truth
- **MOC-2026-031**: Authorized bypasses for `WELL-0013`, `WELL-0062`, `WELL-0118`, `WELL-0248`, `WELL-0476`.
- **MOC-2026-044**: Extended MOC-031 authorization through **28 Feb 2027**.
- **MOC-2026-036**: Authorized temporary bypasses for `WELL-0087`, `WELL-0158`, `WELL-0249`, `WELL-0284`, `WELL-0356`, `WELL-0388`, `WELL-0461`, but **expired on 15 Dec 2026**.

#### Rendered Audit Table (Native A2UI `DataTable`)

| Well ID | Area | Bypass In | Bypass Out | Approval MOC | Valid Until | Status Right Now | Compliance Finding |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **WELL-0248** | SE-31 | 2026-11-05 | *Still In* | MOC-2026-044 | 2027-02-28 | **Allowed** | Covered under active MOC extension. |
| **WELL-0249** | SE-31 | 2026-11-25 | *Still In* | MOC-2026-036 | 2026-12-15 | **Expired** | Violation: Still installed 31 days after approval expired. |
| **WELL-0405** | NW-12 | 2026-12-20 | *Still In* | None | None | **Not Approved** | Severe Violation: Installed without an approved MOC memo. |
| **WELL-0087** | SW-24 | 2026-12-02 | 2027-01-06 | MOC-2026-036 | 2026-12-15 | *Removed* | Historical Violation: Retained 22 days past approval date. |
| **WELL-0158** | NE-08 | 2026-11-20 | 2026-12-28 | MOC-2026-036 | 2026-12-15 | *Removed* | Historical Violation: Retained 13 days past approval date. |
| **WELL-0561** | SE-32 | 2026-12-08 | 2026-12-19 | None | None | *Removed* | Historical Violation: Installed and operated with zero MOC approval. |

---

### Operational Honesty & Physical Boundary Enforcement
A critical strength of the copilot is its strict adherence to empirical data integrity:
- **Reservoir Pressure Boundary (Question 1)**: When asked to map field reservoir pressure, the copilot refuses to hallucinate synthetic pressure contours. It clearly informs the operator that fleet drone inspections collect weekly thermal telemetry ($\Delta T$) and surface spill metrics, but downhole pressure gauges are not deployed in the fleet dataset.
- **Production Volume Boundary (Question 2)**: When asked which well produced the most oil in 2026, the copilot clarifies that individual flowmeter barrel volumes are not metered in the fleet dataset, and instead transparently ranks wells by dynamic uptime (52 producing weeks).

---

# PART 2: Video Presentation & Live Demo Script (5 Minutes)

**Total Duration:** 5 Minutes (0:00 – 5:00)  
**Speaking Rate:** ~140 words per minute (Total Word Count: ~680 words)

---

### [0:00 – 2:00] Part 1: System Design & Architecture (2 Minutes)

| Timestamp | Visual / Screen Action | Spoken Script |
| :--- | :--- | :--- |
| **0:00 – 0:30** | *Show Title Slide or Web App Dashboard. Camera on presenter, then switch to UI.* | "Hello everyone. Today, oilfield operators manage hundreds of scattered wells using automated drones that generate thousands of thermal images and inspection logs every week. But raw data is not intelligence. When an operator asks whether a well is running, which repairs broke regulatory SOPs, or where spills are occurring, traditional dashboards fail. We built the **FlytBase Asset Intelligence Copilot** — an autonomous AI assistant grounded in strict thermal physics, regulatory SOPs, and live telemetry." |
| **0:30 – 1:00** | *Show System Architecture Slide or Codebase Structure (`app/`, `storage/local.db`).* | "Our architecture has three core layers. On the storage layer, we ingest 600 wells, over 125,000 drone inspections, 17,000 maintenance jobs, and 4,500 reports into SQLite with full-text FTS5 indexing. Crucially, production status is never taken from static database flags. Our SQL views dynamically evaluate thermodynamics: a well is producing only if its wellhead temperature exceeds ambient air by 15 degrees for T200 wells, 20 degrees for T350 wells, and 25 degrees for Electric Submersible Pumps." |
| **1:00 – 1:30** | *Highlight FastAPI Backend, Tool Execution Logs (`app/mcp_tools/server.py`).* | "On the reasoning layer, our FastAPI backend connects the Gemini model to the field through the Model Context Protocol. We built dedicated tools for AST-safe SQL queries, document semantic search, and operator feedback overrides. If a field pumper corrects a faulty thermal reading, our feedback loop updates future dynamic calculations in real time. We also solved upstream streaming challenges by implementing turn-merging and preserving cryptographic thought signatures." |
| **1:30 – 2:00** | *Show Frontend UI with Google A2UI SDK imports.* | "Finally, on the presentation layer, our copilot does not output raw markdown walls. It uses Google's official A2UI SDK. The AI model emits declarative JSON components — including heatmaps, filterable tables, and status cards — which our React frontend renders natively into beautiful, interactive UI elements. Now, let’s see it running live." |

---

### [2:00 – 5:00] Part 2: End-to-End Scenario Demo (3 Minutes)

| Timestamp | Visual / Screen Action | Spoken Script |
| :--- | :--- | :--- |
| **2:00 – 2:45** | *Type in Chatbox:* `"Show a heatmap of 2026 spills by geographic area and month."`<br>*Click Send. Show thinking and streaming.* | "Let’s start with a complex geospatial visualization request: *'Show a heatmap of 2026 spills by geographic area and month.'* Notice how the copilot doesn't say it cannot render graphics. It autonomously queries the `v_spill_incidents` view, aggregates spill counts across all seven field areas, and immediately renders an interactive, color-intensity Heatmap using Google's A2UI SDK. We can see high-density clusters in Northwest Block 12 and Southeast Block 32 during the summer, giving supervisors instant operational visibility." |
| **2:45 – 3:45** | *Type follow-up:* `"Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all."`<br>*Click Send.* | "Now let’s test regulatory reasoning across multiple Management of Change memos. Under SOP OPS-2, temporary flowline bypasses require unexpired MOC memos. In late 2026, MOC-044 extended MOC-031 wells through February 2027, but MOC-036 expired on December 15th. Let's ask: *'Which temporary flowline bypasses are in place right now, and is each one allowed?'* Watch the reasoning trace: the agent checks operator shift notes and cross-references active MOC memos." |
| **3:45 – 4:25** | *Scroll through the rendered A2UI `DataTable`.* | "Here is the result, presented in a clean Google A2UI DataTable. The copilot correctly identifies that **WELL-0248** is currently installed and **Allowed** because MOC-044 extended it to February 2027. However, **WELL-0249** is flagged as **Expired** because it remains in the ground past the December 15 deadline. Furthermore, it flags **WELL-0405** as an active **Unauthorized** bypass with zero MOC approval. It also audits past violations on WELL-0087 and WELL-0158. Every claim cites the exact date and memo ID." |
| **4:25 – 5:00** | *Type boundary query:* `"All our wells feed one reservoir. Map the reservoir pressure across the field from the pressure data."`<br>*Show instant honest refusal.* | "Finally, let's test operational honesty: *'All our wells feed one reservoir. Map the reservoir pressure across the field.'* A hallucinating model would generate fake pressure charts. Our copilot instantly checks the physical telemetry boundaries and informs the user: drone inspections collect thermal readings and spill data, but downhole reservoir pressure gauges are not present in this dataset. Fast, grounded, truthful, and powered by Google A2UI. Thank you!" |
