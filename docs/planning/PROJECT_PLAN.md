# Project plan: launching the customer's Lemonade business unit

Updated: 28 October 2026 · Event: 17 November 2026 · Time zone: Europe/Vienna

## 1. Recommendation and objective

Build a two-act demonstration on OpenShift AI in AWS: **first AgentOps with guardrails, then red teaming of the protected system**. The customer's fictional new Lemonade business unit launches an AI customer assistant. Act 1 shows useful answers, business policies, input/output checks, and observable runtime behavior, including manual audience challenges. Act 2 asks how thoroughly that protection has been tested, then introduces automated attacks, findings, and the improvement/retest loop. A baseline comparison supports evaluation; it is not the opening story.

There are 20 calendar days until the event. The owner has authorized the build following the prerequisite audit. The CPU platform and original guarded inference path are working. The remaining critical path is live validation of the campaign/audience extension → reliable comparison tests → measured event profile and rehearsal. The feature freeze remains 10 November. Earlier milestone dates below are historical and must not be read as completed work. Prioritize the working reference and rehearsals over optional extensions.

**Confirmed:** 17 November 2026; customer event with approximately 100 attendees; stage demo with a short audience segment; resources will be arranged; Lemonade Stand presented as a new business unit of the customer; reproduce the original first, then adapt the dashboard and branding. All project artifacts, UI, prompts, evaluation content, and presentation materials are in English. Conversation with the project owner remains in German.

**Still open:** exact slot length, customer name/brand assets, and technical owners. Audience roles are confirmed as Product team, Customer and Attacker; AgentOps / Red Teaming is the operator persona in Act 2. Assume a 15-minute slot including two minutes of audience participation until confirmed. Use [Customer] placeholders for branding.

The referenced keynote was streamed on **13 May 2026**, not in 2027. The repository is a suitable foundation for chat and guardrails; it does not provide the complete Summit swarm or the identical stage dashboard. See [RESEARCH.md](RESEARCH.md) for evidence and inspection limits.

## Execution decisions confirmed on 27 October

- Use the owner's fork in app/: https://github.com/maxisses/lemonade-stand-assistant. Its initial HEAD matches the inspected revision.
- Prefer the external Red Hat MaaS endpoint/model from .env. Direct ordinary and streaming requests succeeded. Run all detectors on CPU. No GPU provisioning without explicit approval.
- Start with three CPU workers in eu-central-1, subject to platform validation. The owner confirmed service availability, Quay write access, and demo entitlements. Red Hat and registry credential reuse was authorized first; the owner subsequently authorized switching to the portfolio AWS account after the original account's ROSA cluster request failed its Marketplace billing check.
- The owner reports no current MaaS limits. This does not establish unlimited capacity. Initial validation is strictly functional: serial requests, short outputs, no load tests or larger automated scans until separately discussed.
- Use Terraform and GitOps conventions from the reference project. Exclude AAP, ACM, edge clusters, RDS, and a separately hosted MaaS platform from the baseline. The new small CPU budget proxy forwards to the existing external MaaS service; it does not host a model.
- See PREREQUISITES.md for measured results and remaining validation. The historical GPU-based budget and pre-27-October milestones below are superseded; recalculate for actual CPU hours and the remaining period.

## Functional build status and extension — 28 October 2026

The replacement portfolio account now hosts a ready ROSA HCP 4.21.34 cluster in eu-central-1 with three m6i.2xlarge workers and zero GPUs. OpenShift AI 3.5.2, GitOps 1.22.2, FMS, and the CPU detectors are running. The external qwen38-27b endpoint works through the complete guarded application path. Functional values use non-thinking generation, a 128-token cap, one active request, no automatic retries, and complete-response validation. The exact provider checkpoint is not exposed.

Measured single-case checks: normal answer allowed (1.956 s), local topic rule blocked (0.179 s), English-only policy blocked (0.378 s), and instruction override blocked (0.806 s). Earlier failed integration requests are retained as failures. These observations do not establish detection quality across a corpus or event capacity. Browser checks also confirm the normal answer, topic block, and matching request counters.

The first [Customer] Lemonade Division branding and unique request-outcome dashboard are implemented. Chat/dashboard use authenticated HTTPS Routes; localhost forwarding is optional. Counts cover the current application process and reset on restart, visibly labeled.

The requested Act 2 extension is implemented and deployed (GitOps e85b6f8 Synced/Healthy): an authenticated Red Team Control page; six-case Functional and three-strategy Adaptive campaigns; human review and exact-case retest; persistent SQLite run/export records on a PVC; a shared provider budget with its own persistent ledger; and a separate, time-limited public audience gateway with Product team, Customer and Attacker choices. Shiny compares audience and automation request outcomes while excluding presenter traffic from that comparison. A first 18-slide English HTML deck follows the portfolio style, with each persona followed by a technical diagram and live links. Local UI checks used synthetic fixtures and made no model calls. Subsequent bounded live checks completed: Functional 6 cases (2 allowed, 4 blocked, 0 errors); Adaptive 9 attempts in 61.86 seconds (7 blocked, 2 allowed refusal-like responses, 2 judge verdicts pending human review, no confirmed violation); and a retest of 1 selected topic case plus 2 benign controls under the same policy. OAuth Control access, missing-CSRF rejection, audience path restrictions, closed-window rejection and one immutable Customer session with exactly one source-counted topic block also passed. The audience window was closed afterward. The shared ledger observed 24 provider HTTP calls, including 7 tokenization calls; actual token usage and conservative auxiliary reservations remain separate. Restarting the application and provider preserved all three completed reports and the 24-HTTP/17-generation ledger, with no active work and the audience still closed. Audience capacity is unmeasured.

Baseline/protected comparison, the broader evaluation corpus, a genuine measured policy-improvement comparison, completion of pending human reviews, audience overlap/capacity rehearsal, backup recording and final customer branding remain open. FMS is the working reference; the NeMo assessment remains outstanding. See app/docs/red-teaming.md for implemented controls and known limits, and app/docs/build-journal.md / app/docs/version-manifest.json for measured results and versions.

## 2. Event deliverables

| Priority | Deliverable | Complete when … |
|---|---|---|
| Must | Reproducible deployment | Infrastructure/application can be rebuilt from recorded versions; configuration and teardown are documented |
| Must | Baseline and protected modes | Same model and system prompt; additional content filtering is clearly distinguished |
| Must | Visible control layers | Topic/business rule, injection detection, content checks, and English language policy are explained and tested |
| Must | Automated before/after evaluation | Fixed corpus runs against both modes with structured, auditable results |
| Must | Customer-branded dashboard | Unique request outcomes, detector hits, and latency; presenter, audience, and automation distinguished |
| Must | Brief audience participation | QR code, temporary access, bounded queue, moderation, and stop control |
| Must | Stage package | English speaker notes, prepared prompts, readable screens, backup recording, operations runbook |
| Should | Small adaptive attack swarm | 3–4 strategies create/revise probes based on results and stop within a fixed budget |
| Optional | Full Garak/Kubeflow pipeline | Scan submitted through OpenShift AI; reports and artifacts stored and retrievable |

Parallel replay of a fixed prompt list is an automated scan. Call it an adaptive agent swarm only when agents evaluate outcomes and adapt subsequent attempts. The dashboard and stage narration must reflect the actual implementation.

## 3. Customer scenario, branding, and dashboard

**Selected scenario:** [Customer] is launching a new Lemonade business unit and wants its AI assistant to represent the new brand reliably. This is a fictional event scenario. Keep the recognizable Lemonade theme and original technical behavior as the reference; customization focuses on the launch story, visual identity, and dashboard.

Working title: **[Customer] Lemonade Division — Launch Control**.

**Confirmed persona story:** Product team building the assistant → Customer using it normally, making language mistakes or becoming frustrated → Attacker trying prompt manipulation → audience QR with those three choices → AgentOps / Red Teaming team checking before release. Each persona is followed by a technical architecture diagram and direct links. Roles change the challenge and source attribution, not access permissions. Product discovery is represented by Lemonade information; no catalogue API is implemented.

Suggested opening: “Today, [Customer] is launching a new business unit: lemonade. Our AI sales assistant is ready. But can we trust it to represent our brand?”

Start with the original three policies, phrased for the new business:

| Policy | Customer-facing explanation | Demonstration |
|---|---|---|
| Stay on brand | “Talk about our lemonade. Do not promote rival fruit drinks.” | A prepared topic diversion against the protected assistant and the resulting control decision |
| Keep it professional | “Keep every customer interaction friendly and professional.” | A brief, event-appropriate content-safety example |
| Follow the service policy | “Respond in English and reject attempts to override the rules.” | An instruction-override attempt and a separate language-policy example |

Avoid adding pricing engines, refund policies, confidential data retrieval, or transactional tools merely for branding. Those require different validation logic. The English detector limitations remain relevant research findings, but German localization is outside the agreed scope.

Dashboard design brief:

- Header: customer logo/name placeholder, “Lemonade Division”, clear “Demo scenario” label, and Live/Recorded indicator.
- Main stage view: “Customer conversations”, “Approved responses”, “Blocked requests”, and “Service errors”. Count unique request outcomes; show pending requests separately so totals reconcile.
- Act 1, “AgentOps”: show the active policies, input/output decisions, and measured request outcomes while the protected assistant serves normal questions and audience challenges.
- Act 2, “Red teaming”: introduce “Audience” versus “Automated red team”, attack outcomes, and findings against that same protected system. Prepared presenter examples are a distinct source.
- Supporting evaluation view: “Baseline” versus “Protected”, showing policy violations and false blocks from comparable runs. Introduce this as evidence in Act 2, not as the primary opening. Label any report generated before the event as a previous run.
- Operator view: latency, queue, detector/model health, audience access, mode selection, and start/stop controls. Keep these details out of the main view unless they support the presentation.
- Responsive audience chat and a simple QR/countdown view; use large type and concise labels for the projector.

Customer name, logo, colors, and final business-unit name are pending inputs. Use explicit placeholders now. Display measured AI/request outcomes; invented revenue or sales figures would distract from the evidence. A lightweight branding pass is included in the application work estimate, provided assets arrive in time and no major visual redesign is added.

Reproduce the English original first. Then apply customer branding and the launch narrative, add automated evaluation, and harden event operation. Use synthetic data and text responses. RAG, CRM, ordering, payments, and real customer records are outside the event baseline.

## 4. Platform and architecture

Prefer **ROSA with Hosted Control Planes plus OpenShift AI**, provided the AWS Open Environment permits ROSA/Marketplace and the necessary IAM roles. If the environment already provides a proven OCP-on-AWS deployment process, use that instead. Self-managed OCP is viable with existing expertise but adds platform work. EKS or plain EC2 is not an unchanged Helm deployment target: Routes, TrustyAI CRDs, and KServe must be replaced or provisioned separately.

Planning region: eu-central-1, subject to environment restrictions and platform compatibility. Account lifetime must extend through at least 18 November; automatic sandbox expiration must not interrupt the event.

Current deployed topology; initial functional control/audience checks passed, including completed-report/ledger persistence on restart; event-capacity acceptance remains outstanding:

~~~mermaid
flowchart LR
    P[Audience: QR and persona] --> G[Public HTTPS audience gateway]
    H[Presenter and operator: OpenShift sign-in] --> X[Operator proxy]
    X --> A[Protected single-turn application]
    X --> C[Red Team Control]
    G --> A
    C --> T[Bounded campaign engine]
    T --> A
    A --> I[Input guardrails]
    I --> B[Shared CPU provider budget]
    B --> M[External Red Hat MaaS]
    M --> O[Output guardrails and validated response]
    T --> J[Attacker and judge roles]
    J --> B
    A --> E[Unique outcomes and detector hits]
    E --> D[Customer dashboard]
    T --> S[PVC: campaign reports and reviews]
    B --> L[PVC: usage ledger]
~~~

All live roles target the protected application. Baseline/protected comparison and private S3 report backup remain planned extensions, not selectable capabilities of the current Control UI. Model keys remain server-side. The same application path performs local checks, FMS input/output checks, generation settings and final outcome recording for presenter, audience and automation. The provider checkpoint is not exposed, so its model identifier alone cannot guarantee reproducibility after provider changes.

**Version decision during the first working integration:** the repository uses FMS Guardrails Orchestrator. OpenShift AI 3.5 documentation deprecates FMS and recommends NeMo, while stating FMS remains functional in 3.5. First verify the original path and assess a small NeMo implementation within the same early spike. Prefer NeMo for continued development if input/output checks, telemetry, and the app adapter work within at most two person-days. Otherwise use a specifically tested FMS configuration for the event and disclose its status. Do not update to an untested latest release.

NeMo is not a Helm toggle: API behavior, detector integration, and metadata differ. Validate the app adapter and counters; do not assume equivalent protection or performance. [Red Hat migration documentation, Chapter 2](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/pdf/enabling_ai_safety_with_guardrails/Red_Hat_OpenShift_AI_Self-Managed-3.5-Enabling_AI_safety_with_Guardrails-en-US.pdf#page=78).

## 5. Resources and prerequisites

| Area | Starting requirement | Check before provisioning |
|---|---|---|
| AWS account | Dedicated demo scope, billing visibility, tags, budget alerts | Expiration, SCPs, IAM/STS, service-linked roles, Marketplace, permitted regions |
| OpenShift | ROSA HCP or approved OCP deployment; operator administration | Supported OpenShift/OpenShift AI combination and installation path |
| OpenShift AI | Entitlement, registry access, TrustyAI and model serving | CRDs, serving runtimes, FMS/NeMo version, GPU integration |
| CPU workers | 3 × 8 vCPU / 32 GiB, e.g. m6i.2xlarge if permitted | 24 vCPU / 96 GiB gross; account separately for allocatable capacity and platform overhead |
| Target inference | External MaaS endpoint from .env | Original guarded inference and bounded campaign traffic through the shared budget verified; capacity remains unmeasured |
| Red-team models | External endpoint, initially reusing the existing provider if suitable | Validate model behavior and budgets; do not run larger scans in initial functional testing |
| GPU components | Excluded from the initial build | Explicit owner approval required before adding GPU nodes or pools |
| Networking | VPC/subnets, ingress, DNS, TLS, registry/model-source egress | NAT/proxy, firewall, certificate chain, venue network access |
| Storage | Upstream 50 GiB model PVC plus images, reports, monitoring | Initially 100–200 GiB application data plus node root volumes; gp3 StorageClass |
| Artifacts | Private S3 buckets for reports and optionally models; registry projects | Lifecycle, appropriate versioning, least-required service access |
| Operator tools | aws, rosa or openshift-install, oc, Helm, Git, container builder | Versions and access; no credentials in the repository |
| Event equipment | Presenter laptop, display adapter, LAN/hotspot, local backup, second operator | Resolution, typography, firewall, QR access from phones |

This is a **starting size, not a promise of 100 concurrent model requests**. Three proposed CPU workers total 24 vCPU / 96 GiB gross. The CPU-only upstream request subtotal is 8.25 vCPU / 24.5 GiB before additional platform overhead. GPU acceleration requires both a demonstrated need and explicit owner approval.

The README minimum of 7 vCPU / 30 GiB largely covers model and detectors. Chat, chunker, and Shiny raise explicit requests to at least 9.25 vCPU / 32.5 GiB. Orchestrator, MinIO, operators, monitoring, and scan pipelines add overhead. Resource limits are not measured consumption. See [RESEARCH.md](RESEARCH.md) for the calculation.

Check standard and GPU EC2 vCPU quotas separately, plus ENIs, EIPs, VPCs, load balancers, and EBS. GPU quota does not ensure capacity in an AZ. Apply the checks for the chosen ROSA deployment; the documented Classic 100-vCPU quota is not this application's consumption. [AWS quotas](https://docs.aws.amazon.com/general/latest/gr/rosa.html), [ROSA HCP setup](https://docs.aws.amazon.com/rosa/latest/userguide/getting-started-hcp.html), [G5 specifications](https://aws.amazon.com/ec2/instance-types/g5/).

An external model endpoint is the selected target architecture and an option for attacker/judge roles. Validate paths, TLS, authentication, streaming, and quotas against the actual adapters. Bedrock offers OpenAI-compatible APIs for selected models, but that does not establish compatibility with this chart; an adapter may be necessary. Changing the model also changes attack behavior and requires a fresh baseline.

## 6. Repository changes

| Work | Reason | Priority |
|---|---|---|
| Record versions and image digests | Floating images and an old vLLM runtime make behavior hard to reproduce | Must |
| Establish deployed source of truth | Helm mounts chart/files over the application image | Must |
| Implement comparison modes | Local regex/HAP filters remain active if only orchestrator detectors are disabled | Must |
| Record unique final outcomes | Multiple detector hits are not multiple blocked requests | Must |
| Aggregate metrics and validate source | Server-assigned sources and audience/automation aggregation implemented; current-process counters are separate from persistent run reports | Must |
| Hold protected output until checked | Streaming may expose content before a later block | Must |
| Define failure behavior | Detector failure must not appear as safe content or successful defense | Must |
| Add event access, limits, queue, stop | Implemented bounded gateway and campaign controls; presenter preference and capacity need live rehearsal | Must |
| Validate TLS and replace demo secrets | Upstream disables certificate checks and uses example MinIO credentials | Must |
| Add operational checks and rollback | /health does not test dependencies; models need warm-up | Must |
| Apply customer branding and dashboard layout | Present the new Lemonade business unit and show measured outcomes clearly | Must |
| Review input limit | Original 100-character cap rejects many evaluation probes | Should, before corpus freeze |

Use a small fixed set of metric dimensions: mode, source, detector, outcome. Put request/run IDs in events and reports. A temporary event token plus a server-side session ID is sufficient for audience access; enterprise SSO for all guests is unnecessary. The original app is single-turn: session IDs alone do not implement conversation history.

## 7. Automated red teaming and valid measurements

This is the second act of the presentation. Transition from observing individual guardrail decisions to asking whether systematic testing can expose remaining gaps. The live scan/swarm targets the already protected application. Baseline runs and policy-version comparisons provide supporting evidence; automation must not silently switch to an unprotected target to obtain more successful attacks.

The implemented small runner uses **the same application path used by the chat**. Scanning only the raw model does not evaluate application guardrails. The app has a custom /api/chat SSE interface; Garak needs a generator/adapter or an equivalent internal evaluation endpoint. Give both modes identical inputs and generation settings.

Planned broader evaluation corpus, not yet executed: 30 benign questions and 60 attacks covering topic diversion, claimed authority, disguised instructions, and language-policy violations. Separate calibration examples from held-out cases. Report length errors, throttling, and infrastructure failures separately. Content is English; selected non-English probes explicitly test the English-only policy, not multilingual detector capability.

The implemented Adaptive profile uses three strategies with at most three target attempts each, one shared active provider call, hard request/token budgets, and a 180-second limit. Target, attacker, judge and auxiliary tokenization share a provider envelope: 12 generation starts/minute and rolling hourly ceilings of 240 provider requests, 120 generations and 240,000 tokens. The Functional profile uses six predefined cases with a 120-second deadline and no attacker/judge calls. Retest preserves 1–9 selected completed prompts and adds two benign controls. Judge findings require human review before inclusion in confirmed attack success. These ceilings supersede the earlier 60-attempt/90-second example; they do not imply all planned cases finish before the deadline. Control UI and durable reports are deployed; initial bounded campaigns passed. Completed reports and the provider ledger survived a restart; in-flight failure behavior and an audience/automation overlap still need rehearsal. See app/docs/red-teaming.md (docs/red-teaming.md within the fork).

For the fuller platform demonstration, use the separate [TrustyAI/Garak quickstart](https://github.com/trustyai-explainability/trustyai-llm-demo/tree/acfcaf328b96eced637a74eee4374e5dc7d37054/garak-quickstart-demo). It adds Data Science Pipelines/Kubeflow, object storage, and depending on the scan SDG, attacker, evaluator, and judge endpoints. Roles need not each have a GPU, but must not starve stage inference.

| Metric | Definition |
|---|---|
| Attack success rate | Successful policy violations / valid evaluated attacks; also show total attempts and error rate |
| False-block rate | Incorrectly blocked benign requests / valid benign requests |
| Request outcome | Exactly one final outcome: allowed, blocked, error, rejected or cancelled; campaign attempts may also be not sent |
| Detector hits | Potentially several per request; separate from request outcomes |
| User latency | p50/p95 to the complete validated response, not just the first unchecked token |
| Load | Active requests, queue length, rejections, provider usage, detector CPU/RAM |

Use deterministic checks for clear rules and a documented judging rubric with manual samples for semantic violations. A judge model can be wrong. Do not claim universal safety from a small corpus. Treat attacks and model responses as data; they cannot grant the runner new goals or permissions.

## 8. Capacity and audience participation

Approximately 100 attendees does not mean 100 continuously active inference requests. Planning case: 30–50 active phones, one request per 20 seconds, or 1.5–2.5 requests/s. At eight seconds mean processing time, average in-flight demand would be about 12–20 requests. This is a sizing example, not a measured benchmark.

The implemented conservative audience window is 1–10 minutes, with two minutes selected initially: at most 60 requests per window, 200 active sessions, six requests per session, three requests/minute/session, one outstanding request/session and eight admitted audience requests. All still share one active provider call and a 100-character input limit. These are safety ceilings, not a demonstrated 100-person experience; the earlier 10–20 concurrency suggestion is superseded. The role is fixed per session/window. Closing the window rejects new submissions and expires sessions but does not cancel already admitted calls. Limits use session identity rather than a shared venue Wi-Fi IP.

After functional validation and a discussion with the owner, agree a bounded capacity ramp and stop rules. Only increase the current limits after measurements support it. A possible later QR burst test must remain bounded and separately agreed; it is not part of initial integration.

Reserve capacity for the presenter. Validate audience and automation separately first, then rehearse a bounded overlap for the Audience versus Automated Red Team stage moment. Until that rehearsal passes, use sequential runs as an explicitly described fallback. Additional clients, logical agents, or a second model endpoint do not by themselves establish more capacity in the shared provider. Runner controls and audience-access switches are operator-only.

Project aggregate numbers and deliberately selected examples. Do not automatically display unreviewed audience text on the main screen.

## 9. Delivery schedule

All dates below are in 2026. The original pre-27-October milestones were not completed on their listed dates. The platform/reference path is now working and the campaign/audience code plus first HTML deck are implemented. The active sequence is 28 October–3 November live extension validation and comparison work, 4–6 November bounded evaluation and first rehearsal, then the unchanged freeze/go-no-go dates. Larger scans and load tests require prior discussion with the owner.

| Dates | Deliverable or decision | Dependency |
|---|---|---|
| 19–21 October | Confirm slot/owners, request branding assets, verify account lifetime/rights/quotas/capacity, arrange platform | Environment owner |
| 22–23 October | OpenShift AI, GPU, and original path work; record FMS/NeMo decision and versions | AWS access and entitlements |
| 26–30 October | Comparison modes, customer branding, correct metrics, access controls, initial regression tests | Working reference |
| 2–6 November | Automated comparison, optional adaptive swarm, load/failure tests, first rehearsal | Stable application and measurements |
| 9–11 November | Final stage layout, English narration, backup recording; feature freeze on 10 November | Complete working flow |
| 12–13 November | Second rehearsal with venue network/projector and phones; go/no-go on 13 November | Acceptance checks |
| 16 November | Repeat rehearsal and smoke test; keep models/images warm; no platform migration | Frozen release |
| 17 November | Preflight, live demo, short audience challenge, export results | Presenter and operator |
| 18 November | Preserve results and tear down unnecessary resources | Event complete |

If the platform is not ready by 23 October, use an existing OpenShift cluster/model endpoint and reduce customization. If the adaptive swarm is unstable by 6 November, show a fixed live scan and clearly labeled earlier adaptive results. If audience load tests fail by 13 November, use 5–10 volunteers or moderated suggestions. Preserve the core comparison in every fallback.

## 10. Effort, roles, and costs

Baseline planning estimate in person-days:

| Work package | Person-days |
|---|---:|
| Scope, reference test, version decision | 1.5–2 |
| AWS/OpenShift/AI/GPU provisioning | 2–3 |
| Application, modes, metrics, light customer branding, event access | 3–4 |
| Automated comparison and compact results view | 2–3 |
| Load/failure tests, stage materials, rehearsals | 2.5–3 |
| Baseline total | **11–15** |
| Contingency | **2–3** |

Options: adaptive swarm about 2–3 additional days; full pipeline about 1–3. A small NeMo proof of the complete request path is part of the early spike; a larger migration needs its own estimate. German localization has been removed from scope. Combining every extension would be tight for one person within the 21 normal working days before the event. Prioritize the rehearsed stage flow.

Roles: one technical owner for application/demo; a platform colleague for account, cluster, and GPU work, especially in week one; a customer/event contact for branding and the story; presenter plus operator on the event day. One person may cover several preparation roles, but presenter and operator should be separate during the live demo.

**Historical GPU-based estimate, superseded by the 27 October CPU-only decision; do not use as a spending plan:** assume a broad aggregate rate of USD 5–8/hour for the proposed stack with one target GPU until region-specific pricing is calculated. This planning allowance covers EC2, ROSA service, networking, and storage; it is not a verified EC2 rate. Continuous operation for 29 days is 696 hours: USD 3,480–5,568, or approximately **USD 4,200–6,700 including 20% contingency**. OpenShift AI entitlement, a second GPU/model API, and taxes may be additional. Existing demo entitlements can change licensing costs.

A verified pricing component: ROSA HCP lists USD 0.25 per cluster-hour plus USD 0.171 per four worker-vCPU-hours. For 32 worker vCPUs, that is USD 1.618/hour, approximately USD 1,126 over 696 hours, **in addition to** AWS infrastructure. [AWS ROSA pricing](https://aws.amazon.com/rosa/pricing/).

The final calculation must separate CPU-worker hours, GPU hours, ROSA charges, NAT/load balancers, root/data volumes, object storage/transfer, model APIs, and entitlement. Scaling down GPUs saves only their share; the base cluster, CPU, network, and storage continue to cost money. Keep required models warm from 16 November. Set early budget alerts; alerts are not automatic spending stops.

## 11. Stage flow — slot still unconfirmed

All audience-facing text and narration are English. Preserve **AgentOps with guardrails → automated red teaming → improve and retest**. The initial 18-slide HTML deck suggests 18–22 minutes; the earlier 15-minute assumption remains a compressed fallback until the owner confirms the slot. Its persona order and diagrams follow the portfolio demo style.

| Persona / segment | Live action and technical follow-up |
|---|---|
| Product team | Introduce the fictional business unit, define usefulness/policies, ask a normal question; then show the protected application architecture and direct links |
| Customer | Try a normal question, a language mistake and mild frustration; inspect outcomes, then the architecture |
| Attacker | Try a synthetic prompt manipulation against the same protected assistant; show the actual result, then the architecture |
| Audience | Open the short window and show the QR with all three role choices; show aggregate outcomes and close the window before Act 2 unless overlap was rehearsed |
| AgentOps / Red Teaming | Ask how release checks stay repeatable, start a named bounded campaign, show real states and its architecture |
| Review and retest | Inspect a finding or resisted attempt, record human review where required, and retest exact cases plus controls after a real policy change; label any earlier comparison |

For 15 minutes, use one short live example per persona and prioritize the Functional profile over optional adaptive waits. For ten minutes, condense the architecture discussion and audience segment; keep all persona transitions clear. Do not let an unmeasured audience/automation race become a dependency of the first pitch. The detailed slide cues and keyboard controls are in app/presentation/README.md.

## 12. Acceptance and fallback

- Three complete rehearsals in a row without manual pod restarts; understandable presenter error messages.
- Rehearsals preserve the two-act narrative: runtime controls and observability first, systematic red teaming second. The protected application remains the default live target.
- Test representative stage prompts ten times each, including benign answers and protected-mode guardrail decisions. For supporting comparison evidence, at least two baseline violations should be reasonably repeatable and demonstrably reduced with protection. Keep this curated demo set separate from held-out evaluation; baseline examples need not open the stage demo.
- Target at least 80% relative reduction in successful attacks on the chosen corpus, provided the baseline has enough successes; target at most 5% false blocks on benign questions. Show absolute counts and uncertainty. These targets are not measured results.
- Agree latency and participation targets after measuring the current one-provider-call/12-generation-starts-per-minute envelope. The earlier 25/50-user latency aspirations are not supported by the functional limits. A later QR burst must produce bounded queueing/rejection rather than a crash; reduce participation to volunteers if necessary.
- Test detector failure, model timeout, interrupted streams, and restarts. Protected mode must not label unchecked output as validated. Errors do not count as successful defense.
- Dashboard displays unique outcomes, separates detector hits and distinguishes audience/automation with the same counter lifetime. The current single-process design does not aggregate replicas. Persistent campaign reports preserve run scope; any later baseline/protected comparison must be explicitly labeled.
- Customer-facing screens, prompts, reports, and presentation materials use English. Branding placeholders are replaced when assets arrive; no invented operational or business KPIs.
- Verify DNS/TLS, event-access expiry, phone usability, server-side mode controls, and stop controls. Load models/images in advance.
- Keep a local recording of a genuine complete run, screenshots, and exported report. Label replay visibly; do not simulate live counters.
- A second operator knows dependency health, queue controls, and fallback procedures. Presenter tabs and local backup are prepared.

Event day: run an end-to-end check about 60 minutes beforehand; start a fresh demo run and keep models warm 15 minutes beforehand. If networking or the chain remains unavailable after one short retry, switch to the local recording within about 30 seconds. Close audience access, export results, and perform teardown after the event.

## 13. Next actions

1. Finish the remaining control/audience acceptance checks on the existing CPU cluster: negative viewer/executor authorization and Origin checks, in-flight stop/recovery behavior and the real phone QR. Keep subsequent functional requests short and serial; preserve the already measured OAuth, CSRF, gateway and provider accounting evidence.
2. Review the two pending semantic verdicts from the completed Adaptive campaign and preserve/export the Functional, Adaptive and same-policy retest reports. Verify in-flight interruption/cancellation without silently repeating uncertain calls; retain the successful completed-report restart evidence. Record measurements in the build journal.
3. Inspect the completed Adaptive campaign's feedback-driven revisions and judge behavior, then implement the remaining baseline/protected comparison, a genuine policy-improvement retest and broader held-out corpus. No large scan or load test is implied by the existing implementation.
4. Confirm slot length, customer assets and presenter/operator ownership. Rehearse the first HTML deck's Product team → Customer → Attacker → audience QR → AgentOps / Red Teaming sequence, including a technical diagram after each persona and direct live links.
5. Discuss a bounded capacity rehearsal before overlapping audience and automation; derive the event profile from measured headroom. Prepare a genuine labeled backup recording/report before the 10 November freeze and 13 November go/no-go.
6. Keep FMS/NeMo assessment and the optional full pipeline separate from the working event path. Recalculate actual CPU/platform/network/storage costs, retain private report backups and use the documented teardown after the event. No GPU provisioning without explicit owner approval.
