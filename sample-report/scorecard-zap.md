# OWASP ZAP Scorecard

Status: evaluated

| Criterion | Category | Weight | Score | Evidence | Confidence |
|---|---|---|---|---|---|
| API/SPA Coverage | Coverage | 5 | 4 | REST/GraphQL/SOAP via Automation Framework + dedicated GraphQL add-on (introspection + query fuzzing), AJAX Spider for headless JS-SPA crawling. GraphQL deep testing sometimes needs custom scripts, not fully automatic. Source: zaproxy.org/docs/desktop/addons/graphql-support | paper |
| Shadow/Zombie API Discovery | Coverage | 4 | 3 | AJAX Spider + traditional spider do JS-bundle/common-path heuristic discovery; no dedicated deprecated/versioned-endpoint detection engine. | paper |
| Authentication & Session Handling | Coverage | 6 | 3.5 | Form/script-based auth and HTTP session management are solid; SSO/OAuth/MFA flows handleable via custom Zest scripts but require manual scripting, not native support. | paper |
| Detection Accuracy | Detection Quality | 7 | 3.5 | Aggregate hands-on: 11/15 (73%) known vulnerabilities detected across Juice Shop (8/10) and VAmPI (3/5), against ground truth rebuilt from real observed output. Solid coverage of misconfiguration/header-level issues; refines the earlier paper score (3.5, unchanged) with real evidence. | hands-on |
| Noise / False-Positive Rate | Detection Quality | 4 | 3.5 | Aggregate hands-on: 5 false positives against 11 real detections across both targets -- a manageable ratio, refining the earlier paper score (3, now 3.5) with real evidence. | hands-on |
| Safe Production Scanning | Production Safety & Operability | 6 | 4.5 | Passive-only proxying explicitly documented as safe for production; dedicated safe/protected modes; configurable rate limiting (Network > Rate Limit). Source: zaproxy.org/faq/is-there-any-danger-when-scanning-with-zap | paper |
| CI/CD-Native Fit | Production Safety & Operability | 5 | 5 | First-class docker CLI scripts (zap-full-scan.py etc.), YAML Automation Framework, clear exit codes, machine-readable JSON/XML output -- this project's own CI pipeline uses it directly. | paper |
| Triage & Remediation Guidance | Developer Experience | 4 | 3 | Every alert includes a description, solution text, and references -- generic per-vulnerability-class advice, not tailored to the specific instance/tech stack. | paper |
| Auto-Remediation / Auto-PR | Developer Experience | 2 | 1 | No auto-remediation or auto-PR capability -- it's a scanner, not a code-fixing tool. | paper |
| Setup & Onboarding Friction | Developer Experience | 3 | 4.5 | Free, official docker images, first useful scan achievable in minutes with sensible defaults -- confirmed by this project's own live-verification run. | paper |
| Reporting Quality / Exportability | Reporting & Extensibility | 2 | 4 | HTML/XML/JSON/Markdown report generation; community plugins for Jira/Slack exist but aren't first-party/polished. | paper |
| Extensibility / Custom Rules | Reporting & Extensibility | 1 | 5 | Highly extensible -- custom active/passive scan rules via Zest/Python/JS/Groovy scripting, large add-on marketplace. | paper |
| Business Logic & Workflow Vulnerability Detection | Coverage | 4 | 2.5 | Context-based multi-user/multi-role testing possible via manual session-management scripting per Context, but no purpose-built sequence-aware business-logic testing engine. | paper |
| Legacy Application & Protocol Support | Coverage | 2 | 4 | Protocol-agnostic HTTP(S) proxy/scanner since 2010; traditional server-rendered/legacy web tech was its original design target before SPA-crawling was added. | paper |
| Third-Party/Partner API Risk Assessment | Coverage | 1 | 2 | Can scan partner-facing APIs the same as any other target given a spec; no dedicated vendor-risk-assessment output shaping. | paper |
| Asset Discovery & Inventory Tracking | Coverage | 1 | 1 | Not an attack-surface-management tool; requires a manually-provided target. | paper |
| Compliance & Standards Mapping | Detection Quality | 4 | 3.5 | Real cweid/wascid mapping per plugin and OWASP Top 10 tagging used for compliance reporting (SOC2/PCI-DSS), but mapping coverage is incomplete across all plugins per ZAP's own developers; no financial-services-specific (GLBA/SOX/FFIEC/NYDFS) tagging out of the box. Source: zaproxy.org/docs/alerts, ZAP developer mailing list discussion on OWASP Top 10 mapping completeness. | paper |
| Finding Validation / Proof-of-Exploit | Detection Quality | 2 | 3 | Active scan rules attach real evidence (matched payload/response snippet) for many findings, but not a formalized/systematic proof-of-exploit engine across all rule types. | paper |
| Sensitive Financial Data Exposure Detection | Detection Quality | 2 | 3 | Generic PII Disclosure passive rule likely catches common patterns (SSN, card-like numbers), but no dedicated account/routing-number-specific detection. | paper |
| Scan Performance & Scalability | Production Safety & Operability | 2 | 2.5 | Single-scan performance is workable (confirmed by this project's own ~10min full scans) but scaling across many apps requires DIY orchestration (e.g. our own CI dispatch pattern), not a built-in fleet feature. | paper |
| Incremental / Differential Scanning | Production Safety & Operability | 1 | 1 | Always a full spider+scan of the whole target; no incremental/differential mode. | paper |
| IDE / Local Developer Tooling | Developer Experience | 1 | 2 | Runnable locally via CLI/desktop app, but no native IDE plugin or pre-commit hook integration. | paper |
| Ticketing & Collaboration Integration | Reporting & Extensibility | 2 | 2.5 | Community-built JIRA add-on (exports alerts as issues) and a Jenkins plugin bridging to Jira exist, but are unofficial/community-maintained, one-way, no auto-close-on-fix. | paper |
| SIEM/SOAR Integration | Reporting & Extensibility | 1 | 2 | Possible via third-party bridging tools (e.g. Flame, forwarding ZAP output to Splunk) -- not a native ZAP capability. | paper |
| Historical Risk Trend Dashboards | Reporting & Extensibility | 2 | 1 | Produces per-scan reports only; no cross-scan executive trend dashboard. | paper |
| Vulnerability Status Management | Reporting & Extensibility | 4 | 1 | No exception/risk-acceptance workflow or audit trail for finding lifecycle -- a scan-and-report tool, not a vulnerability management platform. | paper |
| Deployment Model & Data Residency | Deployment & Data Governance | 5 | 5 | Fully self-hostable by nature (docker/desktop/CLI) -- all scan data and traffic stay wherever you run it, inherently on-prem/air-gap-capable since it isn't a SaaS product at all. | paper |
| Multi-Tenancy & Access Control | Deployment & Data Governance | 3 | 1 | No built-in RBAC or audit logging; single-user tool by design, relies on OS/CI-level access control. | paper |
| Vendor Security Posture | Deployment & Data Governance | 3 | 3 | Backed corporately by Checkmarx since Sept 2024 (all core devs hired); Checkmarx conducts annual SOC 2 Type II audits per their Trust Center, but reports are request-gated, not fully public, and no ISO 27001 confirmation found. Source: checkmarx.com/trust | paper |
| Traditional Stateful Web Crawling | Coverage | 3 | 4.5 | ZAP's traditional Spider is one of its oldest, most mature features -- built specifically for multi-page, session-stateful crawling before SPAs existed, with well-documented forms/session handling. | paper |
| Automated Triage / FP-Reduction Engine | Detection Quality | 3 | 3 | Alert Filters let you globally suppress a specific rule/pattern once flagged, persisting across future scans -- static rule-based suppression, not adaptive learning or PoC-based auto-confirmation. | paper |
| ASPM Integration | Reporting & Extensibility | 2 | 4 | DefectDojo (a named example ASPM platform) ships a native, documented ZAP-report parser/importer -- a real first-party connector on the ASPM side, not just generic export. | paper |
| Predictability of Licensing Model | Deployment & Data Governance | 3 | 5 | Fully open-source (Apache 2.0); zero cost regardless of usage scale -- the most predictable possible model. | paper |

## Category Breakdown

| Category | Weight | Weighted Score |
|---|---|---|
| Coverage | 26 | 3.37 |
| Detection Quality | 22 | 3.34 |
| Production Safety & Operability | 14 | 4.14 |
| Developer Experience | 10 | 2.95 |
| Reporting & Extensibility | 14 | 2.43 |
| Deployment & Data Governance | 14 | 3.71 |

**Weighted score: 3.34 / 5.00**