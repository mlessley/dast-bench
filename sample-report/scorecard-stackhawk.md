# StackHawk Scorecard

> 🚧 Draft/sample output demonstrating what dast-bench produces — not a final vendor recommendation. Scores, weights, and evidence below are illustrative of a real evaluation in progress.

Status: rejected

| Criterion | Category | Weight | Score | Evidence | Confidence |
|---|---|---|---|---|---|
| API/SPA Coverage | Coverage | 5 | 4 | Native REST/GraphQL/SOAP/gRPC, introspection-driven GraphQL test generation. API coverage excellent; JS-rendered SPA-UI crawling not emphasized in their docs (spec-driven, not crawl-driven). Source: [stackhawk.com/blog/graphql-security](https://stackhawk.com/blog/graphql-security) | paper |
| Shadow/Zombie API Discovery | Coverage | 4 | 2.5 | INFERRED, LOW CONFIDENCE. No documented shadow/undocumented-endpoint discovery capability found; model is spec-driven (OpenAPI/GraphQL) rather than traffic-analysis-based discovery. Absence of evidence, not confirmed weakness. | paper |
| Authentication & Session Handling | Coverage | 6 | 4.5 | JWT, OAuth flows, most 3rd-party providers directly configurable in the stackhawk YAML config without custom scripts -- strong, low-friction, well-documented. | paper |
| Detection Accuracy | Detection Quality | 7 | 4 | VENDOR CLAIM, not independently verified. HawkScan runs real attacks against the live app; dedicated Intelligent Business Logic Testing feature specifically targets authorization/logic flaws -- notable vs ZAP/Nuclei. All from StackHawk's own marketing. | paper |
| Noise / False-Positive Rate | Detection Quality | 4 | 4 | VENDOR CLAIM. Runtime testing against live app (not code patterns) reduces FPs per their own materials -- directionally credible but unverified independently. | paper |
| Safe Production Scanning | Production Safety & Operability | 6 | 2.5 | INFERRED, LOW CONFIDENCE. No passive-mode/rate-limiting documentation found; framing emphasizes catching issues before production (pre-prod/CI-gate positioning), suggesting less emphasis on safe live-production scanning. | paper |
| CI/CD-Native Fit | Production Safety & Operability | 5 | 5 | Core value prop -- YAML config-as-code, deliberately CI-native exit-code design: exit 42 for findings-threshold-reached vs exit 1 for scan failure, cleanly distinguishable. | paper |
| Triage & Remediation Guidance | Developer Experience | 4 | 4.5 | Remediation guidance written in the target language with code-level context, not generic jargon. | paper |
| Auto-Remediation / Auto-PR | Developer Experience | 2 | 2.5 | Delivers findings into PR comments and auto-generates a reproduction cURL command -- doesn't generate a fix diff or open a PR automatically. | paper |
| Setup & Onboarding Friction | Developer Experience | 3 | 4 | Three-line YAML minimum config, onboarding wizard -- fast, but requires SaaS signup/API key, a qualitatively different friction than a docker pull. | paper |
| Reporting Quality / Exportability | Reporting & Extensibility | 2 | 5 | Direct, first-party Jira/Slack/PR-comment integrations -- stronger than ZAP's plugin-based story, comparable to Nuclei's SARIF. | paper |
| Extensibility / Custom Rules | Reporting & Extensibility | 1 | 2 | INFERRED. No evidence of a custom-rule-authoring engine akin to ZAP's Zest or Nuclei's YAML DSL; appears to be a closed, managed platform rather than community-extensible. | paper |
| Business Logic & Workflow Vulnerability Detection | Coverage | 4 | 4.5 | 'Intelligent Business Logic Testing' -- explicit, purpose-built multi-profile/multi-user-perspective testing for authorization flaws (BOLA-style), StackHawk's own marketed differentiator. Source: [stackhawk.com/blog/business-logic-testing](https://stackhawk.com/blog/business-logic-testing), [docs.stackhawk.com/hawkscan/business-logic-testing](https://docs.stackhawk.com/hawkscan/business-logic-testing) | paper |
| Legacy Application & Protocol Support | Coverage | 2 | 3 | Explicit SOAP support alongside REST/GraphQL/gRPC (SOAP is often legacy-adjacent); no legacy-framework-specific (older Microsoft web forms, JSP) testing confirmed. | paper |
| Third-Party/Partner API Risk Assessment | Coverage | 1 | 2 | No dedicated vendor-risk-assessment output shaping found for partner-facing APIs specifically. | paper |
| Asset Discovery & Inventory Tracking | Coverage | 1 | 2.5 | Auto-maps GitHub/GitLab/Bitbucket/Azure Repos to applications and can generate OpenAPI specs from source -- real discovery, but source-driven (finds apps in your own VCS), not scanning for unknown/rogue external assets like a network-based ASM tool. Source: [docs.stackhawk.com](https://docs.stackhawk.com) | paper |
| Compliance & Standards Mapping | Detection Quality | 4 | 4.5 | Explicit, well-documented pre-built compliance reports for PCI-DSS, HIPAA, and SOC 2, including a dedicated PCI DSS v4.0.1 mapping blog post -- best-documented of the three candidates on this point. Source: [stackhawk.com/blog/pci-dss-appsec-compliance](https://stackhawk.com/blog/pci-dss-appsec-compliance) | paper |
| Finding Validation / Proof-of-Exploit | Detection Quality | 2 | 4 | HawkScan runs real dynamic tests against the live running application by design (not static pattern matching), inherently closer to proof-of-exploit validation than a signature-only tool. | paper |
| Sensitive Financial Data Exposure Detection | Detection Quality | 2 | 2.5 | OWASP API Top 10 coverage includes generic excessive-data-exposure testing; no dedicated financial-data-pattern (account/routing number) detection confirmed. | paper |
| Scan Performance & Scalability | Production Safety & Operability | 2 | 4 | Cloud-backed execution built for per-PR CI/CD gating implies genuine scale across many apps, not limited by a single self-hosted instance. | paper |
| Incremental / Differential Scanning | Production Safety & Operability | 1 | 2 | No code-diff-aware/incremental scanning mode confirmed. | paper |
| IDE / Local Developer Tooling | Developer Experience | 1 | 2.5 | Local CLI (HawkScan) exists for developers to run themselves; no IDE plugin confirmed. | paper |
| Ticketing & Collaboration Integration | Reporting & Extensibility | 2 | 4.5 | Native Jira/Slack/Teams integration with a real finding-status workflow (Assigned/Risk Accepted/False Positive, linked to Jira tickets). Source: [docs.stackhawk.com/integrations/workflows/jira](https://docs.stackhawk.com/integrations/workflows/jira) | paper |
| SIEM/SOAR Integration | Reporting & Extensibility | 1 | 2 | No documented native SIEM/SOAR integration found. | paper |
| Historical Risk Trend Dashboards | Reporting & Extensibility | 2 | 3.5 | Markets itself as an 'AppSec Intelligence Platform,' implying dashboard/trend views, though an explicit remediation-velocity trend view isn't independently confirmed. | paper |
| Vulnerability Status Management | Reporting & Extensibility | 4 | 4 | Real, documented finding-lifecycle workflow (mark as Assigned/Risk Accepted/False Positive, tied to Jira) -- best-documented of the three candidates here. | paper |
| Deployment Model & Data Residency | Deployment & Data Governance | 5 | 2 | Cloud-only execution (config-as-code + cloud backend, Tier 2 per dast-onboard-tool's tiering); no on-prem or configurable data-residency option found. | paper |
| Multi-Tenancy & Access Control | Deployment & Data Governance | 3 | 3 | 'Activity history and audit logging' mentioned as an enterprise feature; fine-grained RBAC not explicitly confirmed. | paper |
| Vendor Security Posture | Deployment & Data Governance | 3 | 2.5 | Extensive marketing about helping CUSTOMERS comply with SOC2/PCI-DSS/HIPAA, which is different from StackHawk's own certification status -- that isn't independently confirmed either way. | paper |
| Traditional Stateful Web Crawling | Coverage | 3 | 3.5 | Built on ZAP's underlying scan engine (inherits baseline capability), but StackHawk's product positioning/workflow (HawkScan configs driven by OpenAPI/GraphQL specs) is API-first -- multi-page traditional crawling isn't a marketed strength. | paper |
| Automated Triage / FP-Reduction Engine | Detection Quality | 3 | 3 | Real finding-lifecycle workflow (Assigned/Risk Accepted/False Positive) persists manual triage decisions across scans -- but no documented automated PoC-generation or ML-driven historical learning. | paper |
| ASPM Integration | Reporting & Extensibility | 2 | 2.5 | No clearly documented native ASPM-platform connector found in public materials; limited public information to confirm a first-party connector specifically. | paper |
| Predictability of Licensing Model | Deployment & Data Governance | 3 | 3.5 | Publicly documented per-application/target-based tiered SaaS pricing at smaller tiers (transparent, footprint-aligned), but enterprise-scale tiers move to custom/contact-sales pricing -- less transparent at the scale a Fortune 500 buyer would operate at. | paper |

## Category Breakdown

| Category | Weight | Weighted Score |
|---|---|---|
| Coverage | 26 | 3.69 |
| Detection Quality | 22 | 3.82 |
| Production Safety & Operability | 14 | 3.57 |
| Developer Experience | 10 | 3.75 |
| Reporting & Extensibility | 14 | 3.64 |
| Deployment & Data Governance | 14 | 2.64 |

**Weighted score: 3.55 / 5.00**