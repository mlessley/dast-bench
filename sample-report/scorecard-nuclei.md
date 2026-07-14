# Nuclei Scorecard

Status: evaluated

| Criterion | Category | Weight | Score | Evidence | Confidence |
|---|---|---|---|---|---|
| API/SPA Coverage | Coverage | 5 | 3.5 | 11,000+ community templates with strong dedicated GraphQL coverage (introspection, query-depth, batch-abuse); fundamentally a template-matcher against target URLs, not a headless-browser crawler -- weaker JS-rendered SPA content discovery than ZAP's AJAX Spider. Source: github.com/projectdiscovery/nuclei-templates | paper |
| Shadow/Zombie API Discovery | Coverage | 4 | 3 | Exposure/technology-fingerprint templates do heuristic path-guessing, similar depth to ZAP; no deprecated/versioned-endpoint-aware discovery engine. | paper |
| Authentication & Session Handling | Coverage | 6 | 4 | v3.2 added real static + dynamic authentication (API keys, OAuth-style flows, session cookie/header maintenance) -- documented and real, though newer/less battle-tested than ZAP's scripting approach. Source: projectdiscovery.io/blog/nuclei-3-2 | paper |
| Detection Accuracy | Detection Quality | 7 | 2 | Aggregate hands-on: 4/15 (27%) known vulnerabilities detected across Juice Shop (2/10) and VAmPI (2/5). Confirms the low-confidence paper score's concern (2.5) -- Nuclei's signature-matching strength (known CVEs/exposures) doesn't align well with this ground truth's misconfiguration-heavy composition. | hands-on |
| Noise / False-Positive Rate | Detection Quality | 4 | 2 | Aggregate hands-on: 17 false positives against 4 real detections. Coarse metric (counts legitimate info-level fingerprinting as FP too, not just wrong findings), but still a real ratio worth reflecting, refining the earlier paper score (4.5, now 2) downward significantly. | hands-on |
| Safe Production Scanning | Production Safety & Operability | 6 | 3.5 | Rate-limiting flags exist and most templates are non-destructive by nature (matching, not exploiting), but no dedicated safe-mode branding/formal guarantee like ZAP's. | paper |
| CI/CD-Native Fit | Production Safety & Operability | 5 | 3.5 | Strong JSON/JSONL/SARIF output and widespread CI adoption -- but Nuclei always returns exit code 0 regardless of findings; must parse JSON output yourself to fail a build. Falls short of clear exit codes. Source: github.com/orgs/projectdiscovery/discussions/3218 | paper |
| Triage & Remediation Guidance | Developer Experience | 4 | 3 | Templates include name/description/references, but quality is inconsistent across 11,000+ community-contributed templates. | paper |
| Auto-Remediation / Auto-PR | Developer Experience | 2 | 1 | No auto-remediation/auto-PR capability. | paper |
| Setup & Onboarding Friction | Developer Experience | 3 | 5 | Single static Go binary, go install or docker, -update-templates auto-fetches the library -- genuinely lower friction than ZAP's Java/docker footprint. | paper |
| Reporting Quality / Exportability | Reporting & Extensibility | 2 | 4.5 | JSON/JSONL/SARIF output -- SARIF integrates natively with GitHub's code-scanning security tab, a stronger integration story than ZAP's plugin-based approach. | paper |
| Extensibility / Custom Rules | Reporting & Extensibility | 1 | 5 | The entire tool is custom rules -- a simple YAML DSL explicitly designed for community/user-authored templates, no vendor involvement needed. | paper |
| Business Logic & Workflow Vulnerability Detection | Coverage | 4 | 2 | Signature/template matching by design; no session-state-aware or multi-step business-logic testing engine, even in ProjectDiscovery's cloud platform. | paper |
| Legacy Application & Protocol Support | Coverage | 2 | 2.5 | Can technically probe legacy endpoints, but the template library's coverage skews heavily toward modern CVEs/misconfigurations/exposed panels rather than legacy-framework-specific vulnerability classes. | paper |
| Third-Party/Partner API Risk Assessment | Coverage | 1 | 2 | Cloud platform's attack-surface-management angle is about discovering your own exposed assets, not partner/third-party-integration risk assessment specifically. | paper |
| Asset Discovery & Inventory Tracking | Coverage | 1 | 5 | ProjectDiscovery's cloud platform is a genuine attack-surface-management product (subdomain/IP/ASN/CNAME/tech-fingerprint discovery, screenshots) -- an RSAC 2025 Innovation Sandbox finalist specifically for this capability. Source: RSAC 2025 Innovation Sandbox coverage, projectdiscovery.io | paper |
| Compliance & Standards Mapping | Detection Quality | 4 | 3.5 | Normalized CWE metadata and CVE/CVSS classification across templates (recent improvement); no financial-services-specific (GLBA/SOX/FFIEC/NYDFS) mapping out of the box. | paper |
| Finding Validation / Proof-of-Exploit | Detection Quality | 2 | 3.5 | A template match is itself a precise, specific assertion about the condition tested -- arguably inherently more confirmed than a generic payload-based finding -- though not universally accompanied by attached response evidence. | paper |
| Sensitive Financial Data Exposure Detection | Detection Quality | 2 | 2 | Possible via community-contributed templates if they exist, but no documented, dedicated financial-data-pattern detection capability. | paper |
| Scan Performance & Scalability | Production Safety & Operability | 2 | 4.5 | OSS tool is fast/concurrent by design; ProjectDiscovery's cloud platform explicitly markets continuous scanning 'at scale' across many assets. | paper |
| Incremental / Differential Scanning | Production Safety & Operability | 1 | 3 | Cloud platform does continuous asset/change monitoring (new hosts/endpoints detected automatically) -- incremental at the asset-discovery level, not confirmed at the application-code level. | paper |
| IDE / Local Developer Tooling | Developer Experience | 1 | 2 | Still CLI-only; no IDE plugin or pre-commit integration found. | paper |
| Ticketing & Collaboration Integration | Reporting & Extensibility | 2 | 4.5 | Native, documented integrations to Jira/GitHub/GitLab with built-in deduplication preventing duplicate tickets -- more official than ZAP's community-maintained add-ons. | paper |
| SIEM/SOAR Integration | Reporting & Extensibility | 1 | 4.5 | Native, documented integrations to Splunk and Elasticsearch. | paper |
| Historical Risk Trend Dashboards | Reporting & Extensibility | 2 | 3 | Cloud platform likely has some dashboard view given its continuous-monitoring nature, but an explicit remediation-velocity/risk-reduction trend view isn't confirmed. | paper |
| Vulnerability Status Management | Reporting & Extensibility | 4 | 2 | No exception-management, risk-acceptance, or audit-trail workflow found -- platform appears discovery-focused rather than governance-workflow-focused. | paper |
| Deployment Model & Data Residency | Deployment & Data Governance | 5 | 4.5 | Self-hosted OSS available, plus a SOC 2 compliant SaaS platform with EU and US hosting choice, plus TunnelX for internal/on-prem-adjacent scanning; fully air-gapped operation not confirmed. Source: projectdiscovery.io platform docs | paper |
| Multi-Tenancy & Access Control | Deployment & Data Governance | 3 | 3 | Cloud platform supports team members (up to 10 free), but fine-grained RBAC and an audit log are not confirmed. | paper |
| Vendor Security Posture | Deployment & Data Governance | 3 | 4 | Cloud platform is explicitly described as SOC 2 compliant; ISO 27001 certification or a published third-party pentest summary not confirmed. | paper |
| Traditional Stateful Web Crawling | Coverage | 3 | 2 | No native crawling; pairing with katana (ProjectDiscovery's separate crawler) adds endpoint discovery but not deep stateful multi-step form/wizard completion -- fundamentally a template-matcher against known/discovered URLs. | paper |
| Automated Triage / FP-Reduction Engine | Detection Quality | 3 | 1.5 | OSS core is a deterministic template matcher with no historical-learning or PoC-generation capability; suppression is manual (excluding templates), not adaptive. | paper |
| ASPM Integration | Reporting & Extensibility | 2 | 2.5 | Nuclei JSON output can be ingested by ASPM platforms with generic scanner-import support (e.g. DefectDojo's generic findings importer), but no documented native/first-party ASPM connector. | paper |
| Predictability of Licensing Model | Deployment & Data Governance | 3 | 3.5 | Core engine is free/MIT -- maximally predictable at zero cost. ProjectDiscovery's cloud ASM platform (where advanced features live) uses enterprise/contact-sales pricing without public per-asset rate transparency. | paper |

## Category Breakdown

| Category | Weight | Weighted Score |
|---|---|---|
| Coverage | 26 | 3.06 |
| Detection Quality | 22 | 2.34 |
| Production Safety & Operability | 14 | 3.61 |
| Developer Experience | 10 | 3.10 |
| Reporting & Extensibility | 14 | 3.32 |
| Deployment & Data Governance | 14 | 3.86 |

**Weighted score: 3.13 / 5.00**