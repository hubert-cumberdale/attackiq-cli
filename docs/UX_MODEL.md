# aiq-cli TUI — UX Model (Authoritative)

## Status
**Active — v0.x Read-Only Phase**

This document defines the **authoritative UX and interaction model** for the
`aiq-cli` Textual-based TUI. It is a **design contract**, not an implementation
guide.

All TUI work MUST conform to the rules and constraints defined here.

---

## 1. Purpose

The aiq-cli TUI provides a **read-optimized, operator-focused interface**
for understanding and inspecting AttackIQ BAS content and results.

The TUI is:
- An **abstraction over the CLI**
- A **workflow surface**, not a command wrapper
- Optimized for **security engineers / BAS operators**
- Explicitly **safe by default**

---

## 2. Primary Persona

**Security Engineer / BAS Operator**

Characteristics:
- Familiar with AttackIQ concepts (scenarios, assessments, tests, assets)
- Operates in terminal-centric workflows
- Values clarity, density, and confidence over visual polish
- Expects production-grade safety guarantees

The TUI is not designed for:
- Casual users
- Non-technical stakeholders
- Training or onboarding use cases

---

## 3. Interaction Philosophy

### 3.1 Read-First, Safe-by-Default

In v0.x:
- The TUI is **read-only**
- No actions may mutate remote state
- No scheduling, execution, or destructive operations are permitted

Future write capabilities MUST be:
- Explicit
- Deliberate
- Separately documented

---

### 3.2 Abstraction Boundary

The TUI:
- Consumes abstractions exposed by the CLI
- Does NOT directly expose raw OpenAPI structures
- Does NOT invent new semantics

If the OpenAPI spec changes:
- The CLI adapts first
- The TUI adapts second

---

## 4. Global Layout Model

The TUI uses a **persistent split-pane layout** across all workflow tabs.

### 4.1 Canonical Layout

```txt
┌──────────────────────────────────────────────────────────────┐
│ Header: Auth Status | Env | Workspace │
├──────────────────────────────────────────────────────────────┤
│ Banner: Error/command messages │
├───────────────┬──────────────────────────────────────────────┤
│ List Pane │ Detail Pane │
│ (filterable) │ - Metadata │
│ │ - Relationships │
│ │ - Last Run / Results │
│ │ - Logs / Artifacts (read-only) │
│ │ - Export Actions │
└───────────────┴──────────────────────────────────────────────┘
```

This layout is **non-negotiable** for core workflow tabs.

---

## 5. Navigation Model

### 5.1 Landing / Status Page

The landing page exists to provide **immediate system orientation**.

It MUST display:
- Authentication status (authenticated / unauthenticated)
- Active API environment
- High-level navigation entry points

It MUST NOT:
- Display content lists
- Perform implicit data loading if unauthenticated

---

### 5.2 Workflow Tabs

The TUI exposes the following primary tabs:

- **Scenarios**
- **Assessments**
- **Tests**
- **Assets**
- **Results**
- **Settings**

Each tab is a **workflow hub**, not a simple list view.
In v0.x, **Scenarios**, **Assessments**, **Tests**, **Assets**, **Results**, and **Settings**
are all active read-only workflows.

---

## 6. List Pane Behavior

### 6.1 Inline Filter Bar

All list panes MUST include an **inline, always-visible filter bar**.

Filter characteristics:
- Stateful (visible, persistent)
- Supports search and structured filters
- Debounced updates are used in API-backed list workflows (default 0.4s)
- Enter triggers filter submission; application timing follows the active tab workflow

Filters MUST:
- Scale to large datasets (1–2k items)
- Favor density over whitespace

---

### 6.2 Selection Semantics

- Selecting an item updates the Detail Pane
- No modal navigation for inspection
- Keyboard-first navigation is required

---

## 7. Detail Pane Behavior

The Detail Pane is the **primary inspection surface**.

It MAY include:
- Object metadata
- Tags and classifications
- Relationships to other objects
- Last run / associated assessment
- Logs and artifacts (read-only)
- Export controls

The Detail Pane MUST:
- Avoid raw API payload dumps by default
- Present parsed, operator-meaningful information
- Support dense layouts (“scroll less, parse more”)

---

## 8. Results Model

Results are **first-class objects**.

### 8.1 Results Tab

The Results tab:
- Lists completed assessment runs
- Allows selection and inspection
- Provides access to logs (artifacts are not surfaced in the TUI yet)

### 8.2 Cross-Linking

- Scenarios and Assessments MAY display:
  - Last run timestamp
  - Associated assessment or scenario
- Results are NOT embedded inline as primary content

---

## 9. Export Behavior

Export functionality is:
- Explicit
- Visible
- Non-destructive

In v0.x, export actions are implemented as read-only data extraction helpers (JSON/CSV)
for the current view.

---

## 10. Authentication Model

Authentication credentials are treated as **production secrets**.

### 10.1 Auth Rules

- Data loading is blocked when unauthenticated
- API-backed content lists do not populate unless authenticated
- The TUI does not collect or modify credentials; auth is resolved from CLI config/env at launch
- Changing auth requires updating config/env and relaunching the TUI

### 10.2 Error Handling

- Auth failures during data load/export appear as **banner notifications**; unauthenticated state is
  shown inline in list/detail/status placeholders
- No modal error dialogs
- Auth failures are persistent until resolved

---

## 11. Error Handling (Global)

All errors (auth or otherwise):
- API/load/export errors appear as **banners**; inline list/detail status text is used for non-fatal
  state (paging limits, empty results, unauthenticated notices)
- Preserve current context
- Do not interrupt navigation flow

Severity levels MAY be visually distinguished, but:
- Errors MUST remain readable
- No error may silently fail

---

## 12. Visual Density & Information Design

The TUI favors:
- High information density
- Minimal decorative spacing
- Operator-first readability

Design principle:
> Scroll less, parse more.

---

## 13. Non-Goals (Explicit)

The following are explicitly out of scope for v0.x:
- Scenario execution
- Assessment scheduling
- State mutation
- Visual analytics (charts, heatmaps)
- End-user onboarding flows

---

## 14. Change Control

Any change to this UX model requires:
- Explicit documentation update
- Justification in PR description
- Review for safety and consistency

## 15. Header Requirements
- Env: display host only; include label if known (prod/staging/dev), else label as custom.
- Workspace: local project root / active working tree (repo root if available; else CWD).
- Workspace display: show basename only; full path is available via help/copy affordances later.

This document is a **guardrail**.
