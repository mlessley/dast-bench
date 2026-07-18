# OWASP ZAP Scorecard

> 🚧 Draft/sample output demonstrating what dast-bench produces — not a final vendor recommendation. Scores, weights, and evidence below are illustrative of a real evaluation in progress.

Status: rejected

| Criterion | Category | Weight | Score | Evidence | Confidence |
|---|---|---|---|---|---|
| API/SPA Coverage | Coverage | 5 | 4 | REST/GraphQL/SOAP via Automation Framework + dedicated GraphQL add-on (introspection + query fuzzing), AJAX Spider for headless JS-SPA crawling. GraphQL deep testing sometimes needs custom scripts, not fully automatic. Source: [zaproxy.org/docs/desktop/addons/graphql-support](https://zaproxy.org/docs/desktop/addons/graphql-support) | paper |
| Shadow/Zombie API Discovery | Coverage | 4 | 3 | AJAX Spider + traditional spider do JS-bundle/common-path heuristic discovery; no dedicated deprecated/versioned-endpoint detection engine. | paper |
| Authentication & Session Handling | Coverage | 6 | 3.5 | Form/script-based auth and HTTP session management are solid; SSO/OAuth/MFA flows handleable via custom Zest scripts but require manual scripting, not native support. | paper |
| Detection Accuracy | Detection Quality | 7 | 3.5 | Aggregate hands-on: 11/15 (73%) known vulnerabilities detected across Juice Shop (8/10) and VAmPI (3/5), against ground truth rebuilt from real observed output. Solid coverage of misconfiguration/header-level issues; refines the earlier paper score (3.5, unchanged) with real evidence. | hands-on |
| Noise / False-Positive Rate | Detection Quality | 4 | 3.5 | Aggregate hands-on: 5 false positives against 11 real detections across both targets -- a manageable ratio, refining the earlier paper score (3, now 3.5) with real evidence. | hands-on |
| Safe Production Scanning | Production Safety & Operability | 6 | 4.5 | Passive-only proxying explicitly documented as safe for production; dedicated safe/protected modes; configurable rate limiting (Network > Rate Limit). Source: [zaproxy.org/faq/is-there-any-danger-when-scanning-with-zap](https://zaproxy.org/faq/is-there-any-danger-when-scanning-with-zap) | paper |
| CI/CD-Native Fit | Production Safety & Operability | 5 | 5 | First-class docker CLI scripts (the zap-full-scan script, etc.), YAML Automation Framework, clear exit codes, machine-readable JSON/XML output -- this project's own CI pipeline uses it directly. | paper |
| Triage & Remediation Guidance | Developer Experience | 4 | 3 | Every alert includes a description, solution text, and references -- generic per-vulnerability-class advice, not tailored to the specific instance/tech stack. | paper |
| Auto-Remediation / Auto-PR | Developer Experience | 0 | 1 | No auto-remediation or auto-PR capability -- it's a scanner, not a code-fixing tool. | paper |
| Setup & Onboarding Friction | Developer Experience | 3 | 4.5 | Free, official docker images, first useful scan achievable in minutes with sensible defaults -- confirmed by this project's own live-verification run. | paper |
| Reporting Quality / Exportability | Reporting & Extensibility | 2 | 4 | HTML/XML/JSON/Markdown report generation; community plugins for Jira/Slack exist but aren't first-party/polished. | paper |
| Extensibility / Custom Rules | Reporting & Extensibility | 1 | 5 | Highly extensible -- custom active/passive scan rules via Zest/Python/JS/Groovy scripting, large add-on marketplace. | paper |
| Business Logic & Workflow Vulnerability Detection | Coverage | 4 | 3.5 | ZAP's 'Access Control Testing' add-on defines per-role Access Rules within a Context, then automatically attacks every discovered URL as each configured user to flag authorization violations -- genuine authorization-state tracking across roles. Does not do true multi-step/sequence-dependent workflow chains; ZAP is independently documented to struggle with business logic flaws generally. Source: [zaproxy.org/docs/desktop/addons/access-control-testing](https://zaproxy.org/docs/desktop/addons/access-control-testing) | paper |
| Legacy Application & Protocol Support | Coverage | 5 | 4 | Protocol-agnostic HTTP(S) proxy/scanner since 2010; traditional server-rendered/legacy web tech was its original design target before SPA-crawling was added. | paper |
| Third-Party/Partner API Risk Assessment | Coverage | 1 | 3 | ZAP's OpenAPI/Swagger add-on scans any documented API including partner/open-banking-facing ones exactly like any other endpoint. No vendor-risk-assessment-formatted output found -- matches rubric level 3 cleanly. Source: [zaproxy.org/docs/desktop/addons/openapi-support](https://zaproxy.org/docs/desktop/addons/openapi-support) | paper |
| Asset Discovery & Inventory Tracking | Coverage | 1 | 1 | Not an attack-surface-management tool; requires a manually-provided target. | paper |
| Compliance & Standards Mapping | Detection Quality | 4 | 3.5 | Real cweid/wascid mapping per plugin and OWASP Top 10 tagging used for compliance reporting (SOC2/PCI-DSS), but mapping coverage is incomplete across all plugins per ZAP's own developers; no financial-services-specific (GLBA/SOX/FFIEC/NYDFS) tagging out of the box. Source: [zaproxy.org/docs/alerts](https://zaproxy.org/docs/alerts), ZAP developer mailing list discussion on OWASP Top 10 mapping completeness. | paper |
| Finding Validation / Proof-of-Exploit | Detection Quality | 2 | 3 | Active scan rules attach real evidence (matched payload/response snippet) for many findings, but not a formalized/systematic proof-of-exploit engine across all rule types. | paper |
| Sensitive Financial Data Exposure Detection | Detection Quality | 2 | 3 | Generic PII Disclosure passive rule likely catches common patterns (SSN, card-like numbers), but no dedicated account/routing-number-specific detection. | paper |
| Scan Performance & Scalability | Production Safety & Operability | 2 | 3 | Real deployed horizontal-scaling evidence exists in ZAP's OSS ecosystem: an open-source Kubernetes operator (zap-operator) and a documented case study 'ZaaS: ZAP As A Service -- Continuous Security for 20K+ APIs'. This is ecosystem/architecture-pattern evidence rather than a built-in ZAP feature, hence a modest bump only. Source: [github.com/NCCloud/zap-operator](https://github.com/NCCloud/zap-operator), [nullcon.net/talk/zaas-owasp-zap-as-a-service-continous-security-for-20k-apis](https://nullcon.net/talk/zaas-owasp-zap-as-a-service-continous-security-for-20k-apis) | paper |
| Incremental / Differential Scanning | Production Safety & Operability | 0 | 3 | ZAP's 'Contexts' feature lets users explicitly include/exclude URL patterns to scope a scan to specific paths, directly matching rubric level 3. No automatic change-detection-since-last-scan capability found. Source: [zaproxy.org/docs/desktop/start/features/contexts](https://zaproxy.org/docs/desktop/start/features/contexts) | paper |
| IDE / Local Developer Tooling | Developer Experience | 1 | 3 | ZAP ships a genuine, well-documented local desktop app plus official CLI/Docker packages ([zap-baseline.py](https://zap-baseline.py), [zap-full-scan.py](https://zap-full-scan.py)) that developers can run pre-commit -- a solid rubric-3 match. No official IDE plugin exists for ZAP itself. Source: [zaproxy.org](https://zaproxy.org), [github.com/zaproxy/zaproxy](https://github.com/zaproxy/zaproxy) | paper |
| Ticketing & Collaboration Integration | Reporting & Extensibility | 2 | 3 | ZAP's own official zaproxy/action-full-scan GitHub Action confirmed to auto-create/update/close a GitHub Issue as alerts resolve -- real one-way-plus-auto-close integration, but scoped to GitHub Issues specifically rather than Jira/ServiceNow/Slack named in the rubric. Source: [github.com/zaproxy/action-full-scan](https://github.com/zaproxy/action-full-scan) | paper |
| SIEM/SOAR Integration | Reporting & Extensibility | 1 | 2 | Possible via third-party bridging tools (e.g. Flame, forwarding ZAP output to Splunk) -- not a native ZAP capability. | paper |
| Historical Risk Trend Dashboards | Reporting & Extensibility | 2 | 1 | Produces per-scan reports only; no cross-scan executive trend dashboard. | paper |
| Vulnerability Status Management | Reporting & Extensibility | 4 | 1 | No exception/risk-acceptance workflow or audit trail for finding lifecycle -- a scan-and-report tool, not a vulnerability management platform. | paper |
| Deployment Model & Data Residency | Deployment & Data Governance | 5 | 5 | Fully self-hostable by nature (docker/desktop/CLI) -- all scan data and traffic stay wherever you run it, inherently on-prem/air-gap-capable since it isn't a SaaS product at all. | paper |
| Multi-Tenancy & Access Control | Deployment & Data Governance | 3 | 1 | No built-in RBAC or audit logging; single-user tool by design, relies on OS/CI-level access control. | paper |
| Vendor Security Posture | Deployment & Data Governance | 3 | 3 | Backed corporately by Checkmarx since Sept 2024 (all core devs hired); Checkmarx conducts annual SOC 2 Type II audits per their Trust Center, but reports are request-gated, not fully public, and no ISO 27001 confirmation found. Source: [checkmarx.com/trust](https://checkmarx.com/trust) | paper |
| Traditional Stateful Web Crawling | Coverage | 3 | 4.5 | ZAP's traditional Spider is one of its oldest, most mature features -- built specifically for multi-page, session-stateful crawling before SPAs existed, with well-documented forms/session handling. | paper |
| Automated Triage / FP-Reduction Engine | Detection Quality | 3 | 3 | Alert Filters let you globally suppress a specific rule/pattern once flagged, persisting across future scans -- static rule-based suppression, not adaptive learning or PoC-based auto-confirmation. | paper |
| ASPM Integration | Reporting & Extensibility | 2 | 4 | DefectDojo (a named example ASPM platform) ships a native, documented ZAP-report parser/importer -- a real first-party connector on the ASPM side, not just generic export. | paper |
| Predictability of Licensing Model | Deployment & Data Governance | 3 | 5 | Fully open-source (Apache 2.0); zero cost regardless of usage scale -- the most predictable possible model. | paper |

## Category Breakdown

| Category | Weight | Weighted Score |
|---|---|---|
| Coverage | 29 | 3.60 |
| Detection Quality | 22 | 3.34 |
| Production Safety & Operability | 13 | 4.46 |
| Developer Experience | 8 | 3.56 |
| Reporting & Extensibility | 14 | 2.50 |
| Deployment & Data Governance | 14 | 3.71 |

**Weighted score: 3.52 / 5.00**