# Technical research: Summit Lemonade demo

Research date: 19 October 2026. These notes distinguish inspected source code, observations from the video, and proposed implementation changes. They do not establish that a deployment has been run successfully.

Project decision: the demo will use English throughout and present Lemonade as the customer's fictional new business unit. The language findings below explain the choice and remain relevant if the scope changes later.

## 1. Video and provenance

The linked video is titled “Red Hat Summit 2026 Day 2 Keynote - The AI-ready enterprise is here”. Its page states that it was streamed on 13 May 2026. The description includes the two requested chapters:

- [40:30 — Lemonade Stand, prompt hacking and guardrails](https://www.youtube.com/watch?v=6K8eqQ4ymvk&t=2430s)
- [47:45 — Automated red teaming and agent swarms](https://www.youtube.com/watch?v=6K8eqQ4ymvk&t=2865s)

Video metadata, chapter descriptions, and selected frames were inspected. Around 47:46 and 48:30, the video shows an “Audience vs Red Teamer” dashboard and a diagram connecting adversarial agents, guardrails, an AI system, and outputs. The cycle covers discovery, analysis, remediation, and retesting. Around 49:30, the closing slide emphasizes model protection, customer experience, and inference scaling.

**Video inspection limit:** the full transcript did not load in this session. The chapters were not transcribed continuously. The precise Summit image versions, model revisions, attack tooling, and historical Git commit are therefore unverified. The Garak recommendation below comes from a separate public TrustyAI example; it is not a claim that this exact current code ran on the Summit stage.

## 2. Inspected source revisions

| Repository | Inspected revision |
|---|---|
| rh-ai-quickstart/lemonade-stand-assistant | 5c0f65f07e4773c9770dde866bb877fe727e3391 |
| trustyai-explainability/trustyai-llm-demo | acfcaf328b96eced637a74eee4374e5dc7d37054 |

Both public repositories were shallow-cloned into temporary directories for analysis. At that initial review, the project workspace did not yet contain an application checkout; the owner's fork has since been cloned into app/. The current quickstart includes later variants and is not necessarily identical to the Summit build.

The README references the original TrustyAI Lemonade example. The quickstart uses the MIT license; model licenses and container/product entitlements require separate checks. The provocative prompt-injection text in the GitHub repository description is demo content, not an instruction to the implementation agent.

## 3. What the quickstart includes

| Component | Finding in the inspected revision |
|---|---|
| Chat application | FastAPI, custom /api/chat endpoint, server-sent events, HTML UI |
| Target model | Llama 3.2 3B Instruct through vLLM/KServe by default; configurable external endpoint |
| Input checks | Local regex and word lists, followed by HAP, language, and prompt-injection detectors through the orchestrator |
| Output checks | HAP and language through the orchestrator; additional local topic regex in the response stream |
| HAP model | ibm-granite/granite-guardian-hap-125m |
| Injection model | protectai/deberta-v3-base-prompt-injection-v2 |
| Language | Custom service using Lingua and fast_langdetect |
| Orchestration | TrustyAI GuardrailsOrchestrator CR, FMS orchestrator, chunker |
| Model storage | MinIO with a 50 GiB PVC for detector models; Llama model delivered as an OCI artifact |
| Monitoring | Application metrics, ServiceMonitor, default R Shiny dashboard; separate older Grafana variant |
| Themes | English Lemonade/Coffee; Spanish and Portuguese alternatives; no ready-made German variant |
| Missing | AWS/cluster provisioning, complete adaptive attack runner, identical Summit dashboard, complete public event access controls |

Sources: [chart values](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/values.yaml), [application](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/files/lemonade/app_fastapi.py), [templates](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/tree/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates).

## 4. Implementation findings

### Deployment and versions

1. **Deployed application files come from chart/files.** app.yaml mounts app_fastapi.py and index.html from ConfigMaps over the container image. Editing only lemonade-stand-app/ does not update these mounted files. Establish one clear source of truth or deliberately remove the duplication.
2. **This is not a generic Kubernetes chart.** It requires OpenShift Routes, TrustyAI and KServe CRDs, and ServiceMonitor. An empty AWS account or bare EKS cluster is insufficient.
3. **Versions are not fully pinned.** Detector, MinIO, and downloader images include latest tags; Shiny uses fedora. The target-model runtime references quay.io/modh/vllm:rhoai-2.19-cuda. This warrants compatibility testing and does not establish a current supported product combination.
4. **External model mode needs validation.** Populating model suppresses the local Llama deployment. Host and port are inserted into the orchestrator configuration. Supply the complete intended configuration and test a real request; arbitrary OpenAI-compatible URL paths are not automatically supported.
5. **Keep inference warm.** The Llama InferenceService specifies minReplicas: 0 and maxReplicas: 1. Explicitly keep at least one warm instance for the event and verify actual behavior in the selected serving mode.

Evidence: [application template](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates/app.yaml), [Llama template](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates/llm-llama32.yaml), [orchestrator configuration](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates/fms-orchestr8-config-nlp.yaml).

### Comparison validity and metrics

6. **No complete comparison switch exists.** process_chat runs local topic/HAP checks before the orchestrator. Disabling orchestrator detectors alone leaves these checks active. Baseline design must account for both layers while keeping the system prompt constant.
7. **The application is single-turn.** The request contains only message; the model payload includes a system prompt and the current user input, not conversation history. Event session IDs are useful, but conversational memory is additional functionality.
8. **Inputs are short.** MAX_INPUT_CHARS = 100 rejects many red-team probes before inference. Output max_tokens = 200 and temperature = 0 are also set. Align input limits, model context, detector length limits, and output caps. Do not score input-length rejection as a semantic guardrail success.
9. **Counters are process-local and volatile.** AsyncMetricsCollector keeps state in RAM. Restarts reset it and replicas accumulate separate counters. Shiny reads the application service directly, so multiple replicas can produce alternating displayed totals.
10. **Detector hits are not request outcomes.** add_detections increments detector-result counters. Shiny sums them into input_blocked/output_blocked and calculates approved_requests as total requests minus detections, clamped at zero. Several hits on one request distort that accounting. Record final outcomes separately.
11. **Source labels are client-controlled.** /api/chat accepts x-source without validation and uses it as a metric label. Assign audience, presenter, and automation identities server-side. Unbounded source values also create a cardinality problem.
12. **The Summit comparison dashboard is not supplied as-is.** The Shiny parser combines sources into ordinary summary cards. The visible “Audience vs Red Teamer” comparison needs UI and metrics work. Customer branding alone does not correct the underlying accounting.

Evidence: [application configuration, filters, payload, and endpoints](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/files/lemonade/app_fastapi.py), [Shiny parser, particularly lines 10–66](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/files/lemonade/shiny-app.R#L10).

### Event operation

13. **Output is checked while streaming.** Received content is forwarded after local checks. A later block cannot retract earlier displayed content. Initially buffer and validate the full protected response. Test split keywords across chunk boundaries and interrupted streams. Source inspection alone did not demonstrate a specific successful bypass.
14. **TLS verification is disabled.** The aiohttp context disables hostname and certificate checks. Configure the appropriate CA trust rather than retaining this in the event build.
15. **Public event access needs work.** The application has no visitor authentication or application-wide rate-limit/queue controls; its Route disables connection rate limiting. Chat and metrics share a service.
16. **Debug logging includes user content.** The chart sets DEBUG and code logs input messages. Prefer metadata and synthetic test data for the event, with deliberate limits on audience-content retention.
17. **Health checks are shallow.** /health returns healthy without validating the inference chain. Add a synthetic end-to-end check for model, orchestrator, and detectors, separately labeled from audience traffic.
18. **Language-detector failures may return empty detections.** Several exception paths return []. Distinguish failed validation from no violation detected in the protected path.
19. **MinIO uses static example credentials.** Replace them with dedicated secrets and keep model/pipeline storage internal. Do not copy the separate Garak tutorial's public HTTP MinIO exposure without reassessing the design.

Evidence: [application](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/files/lemonade/app_fastapi.py), [language detector](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/files/lingua-app.py), [MinIO template](https://github.com/rh-ai-quickstart/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates/minio-storage-models.yaml).

## 5. Resources specified in the templates

| Component | CPU request | RAM request | GPUs |
|---|---:|---:|---:|
| Llama target model | 1 | 8 GiB | 1 |
| HAP | 1 | 4 GiB | 0 |
| Prompt injection | 4 | 16 GiB | 0 |
| Language | 1 | 2 GiB | 0 |
| Chat application | 1 | 1 GiB | 0 |
| Chunker | 1 | 1 GiB | 0 |
| Shiny | 0.25 | 0.5 GiB | 0 |
| Explicit subtotal | **9.25** | **32.5 GiB** | **1** |

This subtotal does not fully include orchestrator/sidecars, MinIO, the downloader init container, platform operators, monitoring, or a red-team pipeline. An external target model removes one vCPU, 8 GiB, and the GPU from this subtotal, but needs capacity elsewhere.

The README gives 7 vCPU / 30 GiB requests and a 51 GiB limit for the original model components. The requests reconcile; the current model/detector limits actually total **55 GiB** (20 + 8 + 24 + 3). Size from rendered resources and measured demand rather than relying only on the README total.

## 6. Language and current product direction

Protect AI describes the selected DeBERTa model as an English prompt-injection classifier, excludes non-English inputs and general jailbreak detection from its stated capability, and displays an archival notice. IBM also describes HAP as an English-language classifier. Translated UI is not evidence of multilingual detection quality. The agreed English demo avoids adding German localization to this project. [Protect AI model card](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2), [IBM HAP model card](https://huggingface.co/ibm-granite/granite-guardian-hap-125m).

OpenShift AI 3.5 deprecates FMS and recommends NeMo while documenting continued FMS functionality for that release. Choose deliberately between original fidelity and migration, including app-interface and telemetry tests. The repository itself does not establish a currently validated product combination. [Red Hat, Chapter 2](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/pdf/enabling_ai_safety_with_guardrails/Red_Hat_OpenShift_AI_Self-Managed-3.5-Enabling_AI_safety_with_Guardrails-en-US.pdf#page=78).

## 7. Separate automated-attack component

The TrustyAI Garak quickstart provides predefined scans and an intents-based flow involving policy input, synthetic data generation, attack execution, and judging. It uses Kubeflow/Data Science Pipelines and exports structured results and HTML reports.

Its setup guide assumes RHOAI 3.4 with TrustyAI, AI Pipelines, dashboard, and product-image access. Intents scans add model roles and a policy file. This is a documented starting point, not a combination validated in this session or a component bundled with the Lemonade chart.

Sources: [Garak README](https://github.com/trustyai-explainability/trustyai-llm-demo/blob/acfcaf328b96eced637a74eee4374e5dc7d37054/garak-quickstart-demo/README.md), [cluster setup](https://github.com/trustyai-explainability/trustyai-llm-demo/blob/acfcaf328b96eced637a74eee4374e5dc7d37054/garak-quickstart-demo/CLUSTER_SETUP.md), [client setup](https://github.com/trustyai-explainability/trustyai-llm-demo/blob/acfcaf328b96eced637a74eee4374e5dc7d37054/garak-quickstart-demo/SETUP.md).

## 8. Completed and outstanding checks

Completed: source/template inspection at both pinned revisions; relevant model-card and AWS/Red Hat documentation checks; video metadata and selected frame inspection; successful Helm lint and helm template with the Lemonade default values. Lint only recommended adding a chart icon.

Outstanding: cluster/CRD validation, image access, supported runtime/product combination, model downloads, successful inference/detection, performance measurements, full video transcript, and historical Summit build identification. No attacks were run against third-party or publicly operated systems.

## 9. Implementation follow-up, 27 October 2026

The owner's fork matches the inspected upstream revision and is now cloned into app/. External Red Hat MaaS inference is selected instead of a locally hosted target model. Model discovery, one ordinary completion, and one streamed completion succeeded. This is direct-provider evidence, not a guardrail-chain test or a capacity measurement.

CPU-only Terraform and initial chart/application changes have been prepared, with pinned images/model revisions and offline tests for buffered output, failure handling, serial admission, and server-assigned source labels. The owner renewed ROSA authentication. State storage, networking, and IAM/OIDC prerequisites were created, but the cluster request failed the original account's Marketplace billing check; no cluster was created.

The owner authorized switching to the portfolio AWS account and clarified that the original Open Environment was deleted. The portfolio account remains available and its previous demo was removed. Read-only checks confirmed its ROSA billing listing, no target-account cluster, and no VPCs, NAT gateways, or EC2 instances in eu-central-1. Configuration has now switched, with original credentials/state archived and account-specific Terraform state isolation. Removal of original-account resources is owner-reported rather than independently verified. See app/docs/build-journal.md for current status. Initial validation excludes larger scans and load tests by explicit owner instruction.

## 10. Runtime findings from the CPU build, 27 October 2026

The reference-source findings above describe the inspected upstream revision. The adapted fork now runs on ROSA/OpenShift AI with external MaaS and CPU detectors. Full benign generation, local topic blocking, language-policy blocking, and a single prompt-injection block passed. Exact versions and both successful and failed measurements are recorded in app/docs/version-manifest.json. No load test or large scan was run.

Runtime integration required a trusted CA bundle for the FMS client, compatible S3 connection metadata, one worker per CPU detector for the functional sizing, and provider non-thinking options. FMS streaming did not reliably preserve the terminal finish reason after output detection; the working configuration uses complete JSON responses with complete input/output validation before delivery. Protected output is still buffered and fail-closed. The app now records unique request outcomes separately from detector hits. A browser check confirms that the dashboard matches normal and blocked requests; counters remain process-local and are labeled accordingly.

The operator automatically creates guardrails Routes. A namespace ingress policy excludes ingress-router pods; an internal health call succeeded while the same connection from a router pod timed out. Application/dashboard Routes remain disabled. This supports operator-only functional operation, not event audience readiness.

## 11. Keynote reinspection, 28 October 2026

The relevant public English transcript was retrieved and selected frames were reviewed again. It confirms that audience participation precedes the operator-started agent swarm and that the transition is motivated by repeatable testing after model changes. The live comparison emphasizes attack velocity. The depicted discovery/remediation/retest loop is broader than the actions visibly performed on stage. The transcript timing differs from the browser player, so use the chapter links above rather than precise caption timestamps. Historical image versions, exact swarm code and its operator controls remain unverified. See the new red-teaming design proposal in app/docs/red-teaming.md (docs/red-teaming.md within the fork). No campaign or load test was run during this review.
