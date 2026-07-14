# DAST Tool Comparison Matrix

> 🚧 Draft/sample output demonstrating what dast-bench produces — not a final vendor recommendation. Scores, weights, and evidence below are illustrative of a real evaluation in progress.

## Scoring Legend

### Coverage

**API/SPA Coverage**
- 1: Only scans traditional server-rendered HTML forms; no JS-rendered SPA crawling, no OpenAPI/GraphQL-aware scanning, no WebSocket/HTTP2/gRPC support.
- 3: Crawls JS-rendered SPA content with a headless browser and supports REST via OpenAPI import, but GraphQL support is absent or minimal, and no coverage of WebSocket/gRPC traffic.
- 5: Full support for JS-rendered SPAs (headless browser crawling), REST (OpenAPI/Swagger import), GraphQL (schema-aware introspection and query fuzzing, including inferring schema when introspection is disabled), and modern protocols (WebSockets, HTTP/2, gRPC) where applicable.

**Shadow/Zombie API Discovery**
- 1: Only tests endpoints explicitly provided; no discovery of undocumented endpoints.
- 3: Some heuristic discovery but misses deprecated/versioned endpoints.
- 5: Actively discovers undocumented, deprecated, and versioned endpoints via traffic analysis, JS bundle parsing, and pattern-based enumeration.

**Authentication & Session Handling**
- 1: No support for authenticated scanning; every scan is effectively unauthenticated.
- 3: Supports basic scripted login (form-based or token-based) but session handling breaks on complex flows (MFA, SSO, refresh tokens), and custom scripting is required for anything beyond a simple form.
- 5: Robust support for complex auth flows (SSO/OIDC/SAML validated against real enterprise IDPs like Okta/Ping/Azure AD, MFA bypass hooks, token refresh, token-chaining across sequential API calls), automated session recovery on mid-scan drops, multi-role/matrix scanning to catch privilege escalation and BOLA, and scriptless visual macro recording instead of fragile custom scripts.

**Business Logic & Workflow Vulnerability Detection**
- 1: Only tests individual endpoints/parameters in isolation; no multi-step or business-logic-aware testing.
- 3: Some multi-step workflow testing (e.g. basic BOLA checks via a second test account) but limited to common patterns.
- 5: Purpose-built business-logic testing -- multi-step workflow sequences, authorization-state tracking across roles, and sequence-dependent attack chains -- beyond generic parameter fuzzing.

**Legacy Application & Protocol Support**
- 1: Assumes a modern stack; no meaningful support for older frameworks (ASP.NET WebForms, JSP, SOAP-heavy legacy services) or mainframe-fronting web gateways.
- 3: Can crawl and passively scan legacy tech but active-scan coverage and accuracy drop noticeably compared to modern stacks.
- 5: Full active and passive scanning parity across legacy and modern stacks alike, including SOAP-heavy internal services.

**Third-Party/Partner API Risk Assessment**
- 1: No concept of scanning or flagging partner/third-party-facing integration points differently from internal endpoints.
- 3: Can scan partner-facing APIs the same as any other endpoint, but findings aren't organized in a vendor-risk-assessment-friendly way.
- 5: Explicitly supports scanning open-banking/partner-integration endpoints and can produce output organized for a third-party risk management program.

**Asset Discovery & Inventory Tracking**
- 1: No capability to discover apps/assets beyond a manually-provided target list.
- 3: Can discover some additional assets via basic domain/subdomain enumeration.
- 5: Actively scans public IP ranges/domains to surface rogue or unmapped internet-facing company applications, feeding a live asset inventory.

**Traditional Stateful Web Crawling**
- 1: Crawler treats each page/form independently; loses session/cookie continuity across multi-step flows, can't follow wizard-style navigation or dependent form fields.
- 3: Maintains session state across a multi-step flow and can complete simple multi-page forms, but struggles with deeply nested wizards or fields whose valid values depend on earlier steps.
- 5: Robust stateful crawling engine that reliably completes complex multi-step, multi-page workflows (shopping-cart-style flows, wizards with conditional branching, dependent field values) end to end, maintaining session continuity throughout.

### Detection Quality

**Detection Accuracy**
- 1: Detects only a small fraction of known vulnerabilities, well below OWASP Top 10 baseline coverage.
- 3: Detects most common vulnerability classes reliably but misses nuanced/logic-based vulnerabilities.
- 5: High detection rate across both common and nuanced vulnerability classes, validated against known ground truth.

**Noise / False-Positive Rate**
- 1: High false-positive rate requiring extensive manual triage.
- 3: Moderate false-positive rate; manageable triage.
- 5: Low false-positive rate; findings consistently actionable with minimal triage.

**Compliance & Standards Mapping**
- 1: Findings have no mapping to any standard taxonomy.
- 3: Maps findings to OWASP Top 10 only.
- 5: Maps findings to OWASP Top 10, OWASP API Security Top 10, CWE, and CVE where applicable, plus regulatory-relevant frameworks for financial services (PCI-DSS, GLBA, SOX IT general controls, FFIEC guidance, NYDFS 23 NYCRR 500) out of the box.

**Finding Validation / Proof-of-Exploit**
- 1: Every finding is a raw pattern match with no confirmation of actual exploitability.
- 3: Some findings include ad hoc confirmation (e.g. a reflected payload echoed back) but not systematic.
- 5: Systematically validates/confirms exploitability with non-destructive proof (e.g. actual response payload) for most finding classes, meaningfully reducing manual triage.

**Sensitive Financial Data Exposure Detection**
- 1: No pattern-specific detection for financial data types; only generic PII disclosure, if any.
- 3: Detects some financial data patterns (e.g. SSNs) but not comprehensively (misses account/routing numbers or card PANs).
- 5: Dedicated, accurate pattern detection for account numbers, routing numbers, card PANs, and SSNs in responses, distinct from generic PII disclosure.

**Automated Triage / FP-Reduction Engine**
- 1: No triage automation; every scan's findings must be manually re-triaged from scratch with no memory of prior decisions.
- 3: Some automation exists (e.g. suppressing previously-dismissed findings on re-scan) but no active proof-of-exploit generation or cross-scan learning to reduce net-new noise.
- 5: Active automated-triage engine -- generates/replays proof-of-concept payloads to auto-confirm exploitability and/or learns from historical triage decisions across scans to measurably reduce false positives over time without manual re-review.

### Production Safety & Operability

**Safe Production Scanning**
- 1: No passive-only mode; active scans risk disrupting a live system.
- 3: Offers a passive/safe mode but with limited configurability.
- 5: Robust passive/non-destructive scanning mode with configurable rate limiting suitable for a real production system.

**CI/CD-Native Fit**
- 1: GUI-only; no meaningful CLI/API to drive scans headlessly.
- 3: CLI/API exists but requires significant scripting/glue code to integrate into a pipeline (inconsistent output formats, unclear exit codes, no native pass/fail build gating).
- 5: First-class CLI/API designed for CI/CD use -- clear exit codes that distinguish findings-over-threshold from a failed run, native pass/fail policy gates by severity, containerized/Kubernetes-native scan runners, consistent machine-readable output, and full API parity with anything available in the UI.

**Scan Performance & Scalability**
- 1: Scans are slow and can't run concurrently across multiple apps/targets.
- 3: Reasonable single-scan performance but limited concurrency/parallelism across many apps.
- 5: Fast scans with genuine horizontal scalability across many apps/targets simultaneously.

**Incremental / Differential Scanning**
- 1: Every scan is a full rescan of the entire app regardless of what changed.
- 3: Some support for manually scoping a scan to specific paths/endpoints.
- 5: Automatically detects and scans only what changed since the last scan.

### Developer Experience

**Triage & Remediation Guidance**
- 1: Findings list vulnerability names only, with no guidance on how to fix them.
- 3: Findings include general remediation advice but not tailored to the specific instance/tech stack.
- 5: Findings include specific, actionable remediation guidance tailored to the detected instance and tech stack, including code-snippet-level fixes and links to CWE/OWASP documentation.

**Auto-Remediation / Auto-PR**
- 1: No auto-remediation capability.
- 3: Can suggest a fix diff but can't open a PR automatically.
- 5: Can automatically open a pull request with a proposed fix for at least some finding classes.

**Setup & Onboarding Friction**
- 1: Significant setup complexity — hours/tickets needed.
- 3: Moderate setup; first scan achievable within an hour with docs.
- 5: Minimal setup; first useful scan achievable within minutes, sensible defaults.

**IDE / Local Developer Tooling**
- 1: No local/IDE integration; only runs centrally (CI or SaaS).
- 3: A CLI tool developers can run locally, but no IDE plugin.
- 5: Native IDE plugin or pre-commit/pre-push local feedback loop.

### Reporting & Extensibility

**Reporting Quality / Exportability**
- 1: Reports are hard to read/export; no integration with common tools.
- 3: Clear reports with basic export (PDF/CSV) but no direct integrations.
- 5: Clear, exportable reports with direct integrations into common tools (Jira, Slack, CI dashboards), including custom white-label branding for external auditors or clients.

**Extensibility / Custom Rules**
- 1: No way to add custom detection rules.
- 3: Some support but limited/awkward.
- 5: Well-documented, straightforward way to add custom detection rules/policies without vendor involvement.

**Ticketing & Collaboration Integration**
- 1: No direct integration; findings must be manually copied elsewhere.
- 3: One-way export/webhook to a ticketing tool.
- 5: Direct, bidirectional integration with common ticketing tools (Jira, ServiceNow) and chat (Slack/Teams), including automatically closing a ticket when a re-scan confirms the fix.

**SIEM/SOAR Integration**
- 1: No structured export suitable for a SIEM/SOAR pipeline.
- 3: Exports in a common format (CEF/syslog) but needs custom parsing.
- 5: Native, documented integration with common SIEM/SOAR platforms.

**Historical Risk Trend Dashboards**
- 1: No historical view; each scan's results stand alone.
- 3: Some trend data available but not presented as an executive-level view.
- 5: Executive-level dashboards showing remediation velocity, risk-reduction curves, and SLA tracking across quarters.

**Vulnerability Status Management**
- 1: No workflow for managing a finding's lifecycle; findings are just a static list.
- 3: Basic status marking (open/closed) but no formal exception or risk-acceptance workflow.
- 5: Native workflows for exception management, risk-acceptance tracking, false-positive tagging, and a full audit trail of who did what.

**ASPM Integration**
- 1: No API/webhook surface suitable for ASPM ingestion; findings can only be manually exported.
- 3: Findings can be exported in a format an ASPM platform can ingest (e.g. SARIF, generic JSON) via manual/scripted integration, but no native/documented ASPM connector.
- 5: Native, documented integration with at least one major ASPM platform (e.g. ArmorCode, DefectDojo, Snyk AppRisk) -- findings flow automatically with metadata (asset, owner, risk score) preserved for cross-scanner prioritization.

### Deployment & Data Governance

**Deployment Model & Data Residency**
- 1: Single fixed deployment model with no visibility into where scan data/traffic is processed or stored.
- 3: Offers more than one deployment model (e.g. SaaS + on-prem) but data residency isn't configurable.
- 5: Flexible deployment (on-prem, SaaS, hybrid with on-prem/VPC scan agents behind the firewall, or fully air-gapped) with clear, configurable control over where scan data lives, plus static IP ranges/proxy tunneling for safely traversing perimeter defenses.

**Multi-Tenancy & Access Control**
- 1: No role-based access control; every user has the same permissions.
- 3: Basic roles (admin/user) but no fine-grained permissions or audit log.
- 5: Fine-grained RBAC segregating Global Admins, Security Engineers, and Developers, plus an audit log of who did what, with support for business-unit/asset-portfolio isolation.

**Vendor Security Posture**
- 1: No visibility into the vendor's own security posture.
- 3: Vendor claims certifications but doesn't make reports available for review.
- 5: Vendor publishes a current SOC 2 Type II report, ISO 27001 certification, and a recent third-party penetration test summary.

**Predictability of Licensing Model**
- 1: Licensing model is opaque or scales unpredictably (e.g. hidden usage tiers, frequent renegotiation required, cost scales in a way disconnected from actual usage), making multi-year budgeting difficult.
- 3: Licensing model is documented and scales along one clear axis (e.g. per-seat or per-target), but with some friction points (step-function pricing jumps, ambiguous asset-counting rules) that complicate precise forecasting.
- 5: Licensing model is transparent, documented, and scales smoothly and predictably with actual technical footprint (clear per-user/per-target/flat-rate terms, no hidden tiers), enabling confident multi-year budget forecasting.

| Criterion | Weight | Invicti | Nuclei | StackHawk | Veracode Dynamic Analysis | OWASP ZAP |
|---|---|---|---|---|---|---|
| API/SPA Coverage | 5 | 4.5 | 3.5 | 4 | 3.5 | 4 |
| Shadow/Zombie API Discovery | 4 | 4 | 3 | 2.5 | 2 | 3 |
| Authentication & Session Handling | 6 | 4 | 4 | 4.5 | 3.5 | 3.5 |
| Detection Accuracy | 7 | 4 | 2 | 4 | 3 | 3.5 |
| Noise / False-Positive Rate | 4 | 4.5 | 2 | 4 | 4.5 | 3.5 |
| Safe Production Scanning | 6 | 3 | 3.5 | 2.5 | 3 | 4.5 |
| CI/CD-Native Fit | 5 | 5 | 3.5 | 5 | 4 | 5 |
| Triage & Remediation Guidance | 4 | 4.5 | 3 | 4.5 | 4 | 3 |
| Auto-Remediation / Auto-PR | 2 | 3.5 | 1 | 2.5 | 2 | 1 |
| Setup & Onboarding Friction | 3 | 3 | 5 | 4 | 2.5 | 4.5 |
| Reporting Quality / Exportability | 2 | 4.5 | 4.5 | 5 | 4 | 4 |
| Extensibility / Custom Rules | 1 | 2 | 5 | 2 | 2.5 | 5 |
| Business Logic & Workflow Vulnerability Detection | 4 | 2 | 2 | 4.5 | 3 | 2.5 |
| Legacy Application & Protocol Support | 2 | 3 | 2.5 | 3 | 2.5 | 4 |
| Third-Party/Partner API Risk Assessment | 1 | 2 | 2 | 2 | 2 | 2 |
| Asset Discovery & Inventory Tracking | 1 | 3.5 | 5 | 2.5 | 2 | 1 |
| Compliance & Standards Mapping | 4 | 4.5 | 3.5 | 4.5 | 4.5 | 3.5 |
| Finding Validation / Proof-of-Exploit | 2 | 5 | 3.5 | 4 | 3 | 3 |
| Sensitive Financial Data Exposure Detection | 2 | 2 | 2 | 2.5 | 2 | 3 |
| Scan Performance & Scalability | 2 | 3 | 4.5 | 4 | 4 | 2.5 |
| Incremental / Differential Scanning | 1 | 2 | 3 | 2 | 2 | 1 |
| IDE / Local Developer Tooling | 1 | 2 | 2 | 2.5 | 3 | 2 |
| Ticketing & Collaboration Integration | 2 | 5 | 4.5 | 4.5 | 4.5 | 2.5 |
| SIEM/SOAR Integration | 1 | 3.5 | 4.5 | 2 | 2 | 2 |
| Historical Risk Trend Dashboards | 2 | 4.5 | 3 | 3.5 | 2.5 | 1 |
| Vulnerability Status Management | 4 | 4.5 | 2 | 4 | 4 | 1 |
| Deployment Model & Data Residency | 5 | 4.5 | 4.5 | 2 | 3 | 5 |
| Multi-Tenancy & Access Control | 3 | 4 | 3 | 3 | 2.5 | 1 |
| Vendor Security Posture | 3 | 4.5 | 4 | 2.5 | 5 | 3 |
| Traditional Stateful Web Crawling | 3 | 4 | 2 | 3.5 | 4 | 4.5 |
| Automated Triage / FP-Reduction Engine | 3 | 5 | 1.5 | 3 | 2.5 | 3 |
| ASPM Integration | 2 | 5 | 2.5 | 2.5 | 2.5 | 4 |
| Predictability of Licensing Model | 3 | 3.5 | 3.5 | 3.5 | 3 | 5 |

## Category Breakdown

| Category | Weight | Invicti | Nuclei | StackHawk | Veracode Dynamic Analysis | OWASP ZAP |
|---|---|---|---|---|---|---|
| Coverage | 26 | 3.62 | 3.06 | 3.69 | 3.06 | 3.37 |
| Detection Quality | 22 | 4.23 | 2.34 | 3.82 | 3.39 | 3.34 |
| Production Safety & Operability | 14 | 3.64 | 3.61 | 3.57 | 3.43 | 4.14 |
| Developer Experience | 10 | 3.60 | 3.10 | 3.75 | 3.05 | 2.95 |
| Reporting & Extensibility | 14 | 4.39 | 3.32 | 3.64 | 3.39 | 2.43 |
| Deployment & Data Governance | 14 | 4.18 | 3.86 | 2.64 | 3.32 | 3.71 |
| **Weighted Total** | 100 | 3.94 | 3.13 | 3.55 | 3.26 | 3.34 |