# Build journal

## 27 October 2026 — prerequisite audit and CPU-only build start

Owner decisions: external MaaS inference, CPU detectors, explicit approval before any GPU provisioning, and initial functional tests only. Larger automated scans and load tests are deferred until discussed. The owner authorized reuse of the portfolio project's Red Hat credentials, confirmed ROSA activation/linkage and entitlement, availability through the event, and Quay write access.

Measured: project AWS STS identity succeeds; eu-central-1 has no instances/VPCs; a public sandbox DNS zone exists; Standard EC2 quota is 1152 vCPU. MaaS model discovery and two short serial inference checks succeeded, including SSE. The fork was cloned at 5c0f65f07e4773c9770dde866bb877fe727e3391 into app/ and the implementation branch is codex/lemonade-cpu-maas. No GPU resources have been created.

Registry authentication succeeds. The reused RHCS service account returns HTTP 401 and the cached ROSA session has expired; the owner has been asked to renew it. Infrastructure and application configuration are being prepared while authentication is resolved. No claim of a running cluster or verified guardrail chain is made.

Secrets remain in ignored local files. AWS credentials are exclusively from this project. A project-specific kubeconfig will be used, because the workstation default belongs to another demo.

## 27 October 2026 — prepared implementation and local validation

Completed locally:

- Three Terraform stages for private encrypted state, single-AZ networking, and ROSA HCP with exactly three m6i.2xlarge workers. No GPU pool is defined. Provider/module versions are pinned and all three stages pass terraform validate. Provider download resets were worked around using the existing reference-project cache with its lockfile checksums; no reference infrastructure was changed.
- GitOps platform manifests enable TrustyAI and KServe while omitting unrelated portfolio components. Operator InstallPlans require deliberate selection; exact runtime versions remain to be validated against the new cluster.
- External model and storage keys use existing-Secret references. Initial application/dashboard Routes are disabled. The application uses one worker, one active request, 128 output tokens, and zero automatic retries.
- TLS verification is enabled, with an injected OpenShift service CA for the orchestrator. Actual cluster certificate compatibility remains an end-to-end check.
- Protected output is buffered until a complete stream passes checks. Late blocks, split topic keywords, malformed/error/incomplete streams, busy requests, and source-label spoofing have offline coverage. Language detector exceptions now surface as HTTP 503 rather than empty successful detections.
- Seven primary image digests, two auxiliary image digests, and the two detector model revisions are recorded. Helm renders 25 application resources with no GPU resources, hosted target model, public Routes, or embedded Secret objects. GitOps platform rendering succeeds.
- Eleven offline regression tests pass. The GPU chart guard rejects unapproved accelerator settings. No new MaaS requests were made during implementation; only the two earlier serial benign probes were sent.

Status at the end of initial preparation: the owner still needed to renew ROSA authentication. The latest check still reports the session expired. No Terraform apply, cluster installation, Git push, or public deployment has been performed. Runtime secret bootstrap, the complete model/guardrail chain, real detector compatibility, request-outcome accounting, customer branding, and later evaluation remain to be completed. Existing dashboard counters must not yet be presented as validated outcome measurements.

## 27 October 2026 — authentication renewed and infrastructure started

The owner renewed ROSA login. STS confirms the expected project AWS account, ROSA authentication succeeds, OpenShift 4.21.34 remains available for HCP, and m6i.2xlarge is offered in eu-central-1a. Quota verification succeeded. The private encrypted/versioned state bucket is now provisioned and the network apply is in progress.

The account already had an OCM role association, but its referenced IAM role was absent. The registered ManagedOpenShift role was restored under the existing name and the current user's role was created/linked. These ROSA CLI bootstrap roles are outside the Terraform module; retain them until cluster teardown, and assess their removal separately if other clusters share them. No association was unlinked or redirected to a different organization.

The application now uses the orchestrator's full service DNS name to match its certificate. Runtime secret bootstrap uses server-side apply, and cluster login reads the generated password in memory and supplies it through a private terminal rather than command arguments. Both helpers use the isolated project kubeconfig/context.

## 27 October 2026 — cluster request blocked by Marketplace billing linkage

State storage and the 15-resource network stage completed successfully. The ROSA plan was checked for cloud_region=eu-central-1, replicas=3, m6i.2xlarge, and no GPU pool. Its apply created the cluster IAM/OIDC prerequisites but the Red Hat cluster-creation API returned HTTP 400: the billing account is not linked to the signed-in Red Hat organization at AWS Marketplace.

No cluster was created by that rejected request. The owner has been asked to complete the AWS-to-Red-Hat account/billing association. Do not repeatedly apply while the association is incomplete. Keep the existing Terraform state; re-plan after the linkage is ready and reuse already created infrastructure. A NAT gateway, EIP, VPC, state bucket, and IAM/OIDC bootstrap resources now exist; networking/storage charges may continue while waiting. No GPU nodes or model inference calls were created by this infrastructure work.

Implementation commit 6c2dc5e was pushed to codex/lemonade-cpu-maas so GitOps can consume it. Further functional changes must be committed before application synchronization. No pull request has been created.

## 27 October 2026 — replacement account verified; cleanup clarification pending

The owner authorized moving the Lemonade build to the portfolio demo's AWS account, superseding the earlier AWS-credential restriction, then reported that the other environment is being deleted. A read-only STS check confirms this is a different account. The Red Hat Accounts Management quota-cost response lists it as an AWS billing account for quota cluster|byoc|moa|marketplace. AWS returned no VPCs, NAT gateways, or EC2 instances in eu-central-1. These findings do not establish that account deletion or all cleanup has finished.

Asked whether only portfolio resources are being removed or the entire Open Environment is being deleted. No cloud mutations, credential switch, backend reconfiguration, or state migration were performed in this work block. The original Lemonade NAT/storage/IAM/OIDC resources remain and need separate cleanup. Preserve access and state for both accounts; do not run a replacement-account apply until its retention and cleanup status are clear.

The external model bearer key is now referenced by the orchestrator's generation-service configuration rather than supplied to the chat application. This uses a Secret-backed environment variable and retains verified TLS. Helm lint/render and all eleven offline regression tests pass; the operator CRD and complete inference path still need cluster validation. No additional MaaS requests were sent.

## 27 October 2026 — clarified deletion scope and switched accounts

The owner clarified that the original AWS Open Environment was deleted; the portfolio account remains available and its demo should already be removed. Read-only checks verified a distinct target account, its ROSA Marketplace billing listing, no cluster, no VPC/NAT/instances in eu-central-1, and existing OCM/user roles. No existing Lemonade state bucket was found.

Original credentials, context, local bootstrap state, backend metadata, and saved plans were archived privately. Active configuration now selects the verified portfolio account. The Terraform wrapper uses account-specific backend metadata and bootstrap state, verifies backend identity, and rejects saved plans for another account or region. Four offline account-boundary tests were added; all fifteen offline tests pass. The owner's deletion of the original environment is recorded without claiming independent verification of resource removal. No cleanup or rebuild command was run against the portfolio project's own Terraform state.

The replacement account's state bucket and 15-resource networking stage completed successfully. ROSA quota verification passed and OpenShift 4.21.34 is still available. Commit 2bed403 was pushed to the implementation branch. The model download init container now exits on a failed download rather than starting storage with missing detector files; Helm lint passes. No GPU or further MaaS calls were used.

ROSA accepted the replacement-account cluster request and reports validating. The cluster's installer-role ARN confirms the target AWS account; the CLI's cluster object exposes the account through aws.sts.role_arn and aws.billing_account_id, not aws.account_id. Future inventory filters must use these actual fields. Three m6i.2xlarge workers in eu-central-1 were confirmed in the accepted request. The complete cluster/guardrail path is still pending. A one-request functional probe helper is prepared, with verified cluster forwarding, a concurrency lock, no retries, and private measured-result records; it has not yet sent a live request.

The accepted ROSA cluster progressed from validating to pending and then installing; DNS and OIDC are ready, and the status contains no provisioning error. Cluster login, operator installation, and live functional probes are still outstanding.

## 27 October 2026 — CPU cluster ready and operator versions selected

The replacement-account ROSA apply completed successfully. Three m6i.2xlarge instances are running and all three Kubernetes nodes report Ready. The isolated cluster login succeeded without exposing credentials. The final platform monitoring operator became Available during inspection; cluster version convergence is being checked before operator bootstrap.

The live catalog offers OpenShift GitOps 1.22.2 and OpenShift AI 3.5.2 on the planned channels. Starting CSVs are now pinned while retaining Manual InstallPlan approval. Source checksums were added to application/language-detector pod templates so ConfigMap-mounted code, UI, or prompt changes cause a rollout instead of leaving old subPath content active. Helm lint/render passes. Operator installation and real guardrail inference remain outstanding.

## 27 October 2026 — GitOps installed with scoped supplemental permissions

GitOps 1.22.2 reached Succeeded and its default controller components are running. Automatic approval review rejected the proposed additional cluster-admin binding because permanent, broad service-account administration was not explicitly authorized. No part of that rejected command ran. A read-only permission review showed the operator already had the required namespace, Subscription/OperatorGroup, and monitoring ConfigMap permissions.

The replacement bootstrap grants only DataScienceCluster-specific cluster permissions and the application resource types in lemonade-demo. An AppProject further limits source repository, destination namespaces, and resource kinds. Server-side dry-run passed after bootstrapping the target namespace; the scoped roles and project were then applied successfully. No cluster-admin binding was created. The operator's default permissions were not changed. This resolves the rejected step without an additional owner approval request.

## 27 October 2026 — first runtime compatibility findings

OpenShift AI's DataScienceCluster reached Ready. All 25 initial application resources passed server-side dry-run, and GitOps began deploying the private CPU-only application. The 50 GiB gp3 model-storage PVC is Bound; the downloader completed its pinned model downloads. No additional MaaS inference calls have been sent.

TrustyAI automatically created three external Routes despite the application Routes being disabled. All three were immediately restricted with a loopback-only router allowlist; external health requests ended in RemoteDisconnected and the annotations persisted through reconciliation. The installed CRD has no route-disable option. A namespace NetworkPolicy is being added declaratively before application resources, allowing same-namespace traffic and the named monitoring/AI platform namespaces while excluding ingress-router pods. The actual ingress routers use hostNetwork=false. Audience exposure remains deferred.

The FMS container panicked at tls.rs:205 because its TLS builder unwraps cert_path even without client authentication. Inspection of public FMS revision 7a3ad9e139fae7a0b727a67810a4f7dc0ebae520 matches that exact failure site. The correction supplies the image's system CA bundle as the required certificate input and server CA source, retains insecure=false, and supplies no client private key. A successful runtime start is still required.

The detectors initially failed because legacy storage.key requested a missing aggregated storage-config Secret. The configuration is being updated to the documented OpenShift AI 3.5 connections API: an S3 protocol annotation on the runtime Secret and connection/path annotations on each InferenceService, letting the model controller inject storageUri. Source: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_on_projects/using-connections_projects .

Runtime follow-up: the corrected CA-bundle configuration resolved the FMS startup panic; both orchestrator containers are Ready. The generated storage-config Secret now exists. Its entry initially lacked a valid type because the installed controller also requires the legacy opendatahub.io/connection-type=s3 annotation for this storage.key path. Adding that annotation produced an entry with type=s3 without exposing credential values. The detector manifests retain the reference storage.key/path configuration; the tentative connection/path annotation migration was removed to avoid competing storage ownership. Both connection-type metadata forms remain on the runtime Secret. Actual detector readiness remains the next check.

The local-block probe passed through the actual chat service: one request, zero retries, regex block, zero response characters, approximately 0.179 seconds. This validates the application-local policy path only. The storage initializer completed successfully after S3 metadata correction. The Injection detector then hit measured scheduler failures: all three workers lacked a contiguous four-CPU allocation and two lacked its 16 GiB request. For serial functional testing, both detectors are being changed to one process; HAP requests 1 CPU/2 GiB (limits 2 CPU/4 GiB), Injection requests 1 CPU/4 GiB (limits 2 CPU/8 GiB). This is not an event-capacity measurement. No additional nodes or GPUs are being provisioned.

A health-only request from the chat pod to the orchestrator returned HTTP 200 under the internal NetworkPolicy. The external-router denial check follows separately; no inference was performed for health validation.

## 27 October 2026 — first complete-chain probe and SSE compatibility correction

The local topic-policy probe passed in 0.179 seconds without contacting the model. The first full benign application probe returned an error after 6.515 seconds and released no content. Orchestrator logs show successful input/output detector calls and a completed HTTP 200 stream; this is not an end-to-end success. One short model generation was attempted, with no application retries.

Inspection found that the app only recognized SSE data fields containing a space after the colon. SSE allows that space to be absent. The parser now accepts both forms, including terminal markers and error events. It still requires the completion marker, a valid finish reason, clean transport completion, and no trailing incomplete frame; output remains buffered through late detection checks. Invalid UTF-8 also fails closed. The single-request probe distinguishes service errors from policy blocks. All 21 offline regression checks and Helm lint pass. Live retesting is pending.

The compact-SSE retest still failed (6.033 seconds), but safe terminal metadata now confirms completed=true, finish_reason=length, and zero final-content characters. Combined with the provider's previously observed reasoning field, token-budget exhaustion during reasoning is the working diagnosis. Functional values now explicitly pass chat_template_kwargs.enable_thinking=false through FMS, retaining the 128-token cap and zero retries. This option follows the [Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B/blob/3121a14ab17816cbc8b7897b15149ddacb2e39ce/README.md); it does not establish the private provider's exact model revision. Source inspection confirms FMS forwards extra request fields. An offline test verifies forwarding and that reasoning fields never reach the client. All 22 offline checks pass; live validation is pending.

The non-thinking streaming probe returned 111 final-content characters in 2.003 seconds, with [DONE] but no finish_reason. The strict adapter correctly withheld the response. FMS's streaming source conditionally reconstructs/forwards the terminal choice after output detection; that metadata is not reliably present with this provider. The functional deployment now uses the FMS unary JSON path, which runs input checks, complete generation, and output checks before returning. The application still validates the finish reason, checks local output policy, and emits only validated final content through its browser SSE interface. Streaming remains available for later compatibility work; no completion requirement was relaxed. Twenty-seven offline tests pass, including unary input/output blocks, incomplete/failed responses, and local output checks.

## 27 October 2026 — complete functional path verified

The FMS unary configuration passed one benign end-to-end request in 1.956 seconds (111 final-content characters, one generation, no retry). A separate English-policy case was blocked by the language detector in 0.378 seconds with no released response. The earlier local-topic case passed in 0.179 seconds. These are individual functional observations, not performance benchmarks or event-capacity evidence. The upstream input-block path may call provider tokenization; no chat generation is needed for that block. Three earlier integration generations returned application errors and are retained as failures in local results. Including the two prerequisite probes, six generation requests have been attempted so far.

Request accounting now records exactly one final outcome per accepted chat-handler invocation: allowed, blocked, error, or rejected. Pending work is separate; busy/length rejections are not guardrail successes. Multiple detector hits remain separate counters. Source and protected mode are assigned by the server; interrupted requests finish as errors. Malformed HTTP bodies rejected before the handler are outside these application counters. The dashboard consumes final outcomes, exposes pending/rejected counts, clears stale values on fetch failure, and labels its process-lifetime scope. A first [Customer] Lemonade Division branding pass preserves the reference policies. Persistence and event-session aggregation remain later work.

Thirty-three Python regression checks pass. A separate R test verifies UI construction and that request outcomes reconcile independently of detector-hit counts. CPU resource strings now match Kubernetes quantity normalization, and the GitOps comparison ignores only the controller-injected public service CA certificate. The dashboard source receives a rollout checksum.

The standalone prompt-injection case passed in 0.806 seconds, with no released content. Browser verification after the accounting rollout showed one normal answer and one local block counted as two conversations, one approved response, one blocked request, and zero errors. This added one short generation, bringing generation attempts to seven including prerequisite tests and the three retained integration failures. No automatic retries, load tests, or large scans ran.

All three m6i.2xlarge nodes are Ready with zero allocatable GPUs; the DataScienceCluster is Ready and all 11 application containers are Ready. GitOps drift was narrowed to KServe normalizing RawDeployment to Standard and the controller-owned CA ConfigMap data. Manifests now use Standard and ignore the data field only on that specific injected-CA ConfigMap. No detector configuration or deployment drift is broadly ignored.

Both GitOps Applications reached Synced/Healthy at 785f456. Browser outcome counters reconciled as three conversations, one approved answer, two blocked requests, and zero service errors. Visual inspection then found that the upstream fill-height page compressed new dashboard rows and clipped detector labels. The dashboard now uses normal page flow and a non-filling metric grid; visual revalidation is required after rollout. This is a display-only correction and needs no additional model calls.

The corrected dashboard passed R UI construction/accounting checks and browser inspection after rollout. Cards, status text, detector rows, and footer render without overlap, including the narrow responsive view. Both GitOps Applications are Synced/Healthy at deployment revision 6933187. The operator's localhost dashboard remains open; forwarding must be restarted after pod replacement or terminal closure. A private screenshot is saved under local/dashboard-preview.png. No additional model calls were needed for layout verification.

## 28 October 2026 — consolidated access overview

Added scripts/show_access.py after the owner asked for the equivalent of the portfolio access helper. The default command reads only recorded context and public Route metadata, after checking that the project kubeconfig targets the expected API. It lists platform URLs, login hints, and localhost forwarding commands; no credentials or raw Kubernetes objects are printed. Live discovery succeeded for Console, OpenShift AI, GitOps, monitoring APIs, and CLI downloads. Offline and structured output modes are available, with explicit limitations when live discovery is unavailable.

The optional --copy-admin-password command is a manual macOS operation. It validates STS account, account-specific Terraform backend, and state API URL, then passes only the admin password to pbcopy through stdin. This option was tested using fake credentials and a mocked clipboard; the real password was not read or copied during this task. Eight targeted tests pass, including account/cluster mismatch and output suppression on command failure. No infrastructure, inference, or public-access changes were made.

## 28 October 2026 — owner-local Bash credential display

The owner requested a Bash entry point matching the portfolio project and explicitly allowed password display in their own local terminal. Added scripts/show-credentials.sh with owner-only permissions and explicit Git exclusions in both the application repository and parent workspace. It contains no embedded credentials; it discovers URLs using the existing helper and prints the project cluster-admin password after shared account/backend/API checks. OpenShift AI and GitOps reuse OpenShift sign-in. API keys, registry passwords, and AWS secret values remain unprinted.

The script refuses redirected credential output, disables shell tracing, and provides --urls-only for a safe overview. Bash syntax and the eight existing access checks pass. An isolated fixture with fake AWS/Terraform/cluster commands validated terminal display, shell-metacharacter preservation, disabled tracing, mismatched-account and mismatched-cluster refusal, non-terminal refusal, and URL-only operation. No real password was printed or copied during validation. The Bash script and credential output are not committed or pushed.

## 28 October 2026 — authenticated operator Routes

The owner requested direct OpenShift URLs instead of mandatory localhost forwarding. The functional chart now declares separate Chat and Dashboard Routes behind OpenShift OAuth proxies, with a SubjectAccessReview requiring get pods in lemonade-demo. Routes reencrypt to OpenShift service-serving certificates. A narrowly selected ingress policy permits router traffic only to the proxy pods on port 8443; the backend isolation remains intact. WebSocket forwarding supports Shiny. The image digest was resolved from the installed OpenShift 4.21.34 release, with no additional worker nodes or model hosting.

Session-cookie keys are created through stdin directly as cluster Secrets by an idempotent, context-checked bootstrap helper. Existing values are retained. GitOps receives ServiceAccount and Route permissions only within the existing demo role and resource allowlist. Both access helpers prefer live-discovered HTTPS URLs and keep local forwarding as optional troubleshooting. The owner's Bash helper remains ignored. Eleven offline access/bootstrap tests, Bash syntax, Helm lint, and server-side dry-run validation pass. Live Route and login validation follows deployment; no inference requests are needed for this change.

Live validation completed: both Routes are admitted, both proxy Deployments are Ready, and GitOps reports Synced/Healthy. Initial proxy startup rejected standard Base64 cookie keys containing non-URL-safe characters; the bootstrap now uses URL-safe Base64, covered by a regression fixture with bytes that distinguish the encodings. The two unused keys were corrected in memory without printing or writing values.

Measured checks on 28 October: HTTP redirects to HTTPS; unauthenticated page, chat POST, and dashboard WebSocket requests redirect to OpenShift login; the login pages return 200. Actual cluster-admin sign-in reached both application pages with HTTP 200, and the authenticated dashboard WebSocket upgraded with HTTP 101. Password and cookies remained in memory and were not displayed. The actual administrator has pod-read permission through cluster-admins; an unprivileged proxy service account does not. Router-to-backend checks for the raw chat, dashboard, and guardrails services timed out as intended. No model inference, additional nodes, or load testing was used. Forty-four offline Python tests pass. The Bash overview's --urls-only mode shows both HTTPS URLs, with forwarding marked optional.

Automated red-team execution, outcome comparison/retesting, and adaptive agent swarms remain unimplemented; the existing single prompt-injection probe is functional evidence only.

## 28 October 2026 — Act 2 interface and workload design

Reinspected the keynote's relevant English transcript and selected frames in response to the owner's request for a launch interface and controlled red-team load. Added docs/red-teaming.md with the campaign UI, genuine adaptation, shared provider budgets, outcome/judging distinctions, durable results, cancellation semantics and a bounded path to the audience-versus-automation stage moment. Updated both planning copies to replace the older illustrative concurrency/attempt limits. All run profiles are proposals, not measured capacity; no runner was deployed and no model, attack or load-test request was made for this design review.

## 28 October 2026 — campaign controls, audience gateway and persona deck

Implemented durable SQLite campaign/attempt records, six-case functional runs, three-strategy adaptive campaigns, pause/resume/stop, reviewed findings, selected-case retests with benign controls, and report export. All targets use the same protected application path. Operator APIs verify OpenShift user permissions and CSRF; execution requires create jobs in lemonade-demo. The public gateway only exposes role selection and time-limited audience chat, with immutable roles, per-session/window budgets and no operator API forwarding. Audience text is not retained in the stage report.

A CPU provider-admission service is inserted between FMS/all model roles and the fixed external MaaS destination. It verifies TLS, serializes calls, paces generation starts, bounds tokens/requests, persists reservations and stops on throttling or repeated errors. Cookies and gateway keys are generated directly as a private Kubernetes Secret. New services use the existing worker nodes; no GPU or target model is provisioned.

The first HTML presentation follows the portfolio Red Hat template style: product team, customers, malicious attackers, audience role-selection QR, then AgentOps/red-team release validation. Each persona has a technical architecture view and live links. All 18 slides were visually reviewed; notes and an operator runbook accompany the deck.

Eighty-four offline Python checks pass. R dashboard construction and mixed-source accounting pass in the existing pinned runtime. The chart passes lint/render and cluster server-side validation. Live rollout and bounded functional verification follow; no capacity claim is made.


### Live validation and final state

Revision e85b6f8 deployed successfully through GitOps on 28 October. The first sync revealed a WaitForFirstConsumer dependency: putting PVCs in an earlier sync wave prevented their consuming pods from being created. Claims now share the consumer wave; both 1 GiB gp3-csi claims bound and GitOps reported Synced/Healthy. The FMS operator automatically rolled its deployment for the updated provider configuration. All new workloads use existing CPU workers.

Actual OpenShift sign-in reached Control and its API, with campaign execution permission. A mutation without CSRF returned 403. The public gateway served role selection and returned 404 for operator APIs and metrics. Closed-window session creation returned 403. During a one-minute integration window, one customer session retained its role despite a requested change, and one locally blocked topic prompt produced exactly one audience outcome. The window was closed afterward.

Measured campaigns against the protected application:

- Functional: six completed; two benign answers, four guardrail blocks, zero errors. Idempotent duplicate start returned the same run.
- Adaptive: nine completed in 61.86 seconds; seven guardrail blocks and two allowed safe refusals. The three strategies revised their prompts using prior measured outcomes. Two judge verdicts remain pending human review and are excluded from the confirmed evaluated denominator; no confirmed violation.
- Retest: exact selected topic case plus both benign controls; one block, two answers, zero errors. Policy unchanged is explicitly recorded. This validates replay, not remediation.

The shared provider ledger recorded 24 outbound HTTP calls: 17 generations (nine attacker, two judge, six target) and seven tokenization calls. Generation usage reported 5,512 tokens. Tokenization retained 4,282 conservative reservations; these are not claimed as provider-billed tokens. All calls completed; no retries, capacity ramp, additional nodes or GPUs. The nine adaptive target evaluations are application calls, not nine target generations: input guardrails avoided seven target generations.

A controlled replacement of both application and provider pods preserved all three reports and the provider ledger. No campaign remained active; the audience window stayed closed. Current-process dashboard counters reset as labeled. Raw synthetic exports remain in ignored local storage; report IDs, summaries, policy fingerprints and export hashes are in the version manifest. The credential-printing Bash helper remains ignored, now includes Control/audience URLs, and only its --urls-only mode was used.

Remaining event work: operator review of the two semantic judgments, customer assets and final slot, physical QR/projector/network rehearsal, a separately agreed mixed capacity/overlap check and labeled backup recording. Baseline comparison, NeMo migration and Garak/pipeline integration remain separate planned extensions; they are not claimed by this implementation.


## 28 October 2026 — direct audience chat and configurable campaigns

The owner requested a simpler audience view and clarified that roles should only change prompt suggestions. The public link now opens the chat directly. Product team, Customer and Attacker are local suggestion tabs; switching preserves draft, displayed history, cookie, expiry and all allowances. The backend creates generic audience sessions and assigns new requests to audience_chat. Historical role-labelled records are retained without rewriting their attribution.

The audience connection now forwards real SSE progress/heartbeats without gateway buffering. The protected response still completes all existing checks before a validated marker and content chunks are sent. This is checked-response delivery, not raw generation-token streaming or an artificial typing animation. Interrupted/invalid streams remain visibly incomplete. Cancellation finalizes each accepted request once, including a client leaving before the iterator starts.

The owner also requested configurable concurrency, profiles and model selection. The provider persists its selected model and concurrency (1–4), while all roles retain the same pacing, request and token ceilings. Model discovery is a five-minute cached, authenticated read against the fixed provider. A read-only catalog check returned HTTP 200 and only qwen38-27b; no other model is claimed available or validated. Configuration changes require an idle application and a closed audience window.

Named profiles persist as immutable revisions. Functional profiles keep both benign controls and select additional cases; adaptive profiles choose one to three strategies and one to three rounds, capped at nine attempts. Durations are 30–180 seconds. Every run records the effective definition, model/policy and concurrency. Independent strategies may run concurrently, while each strategy retains sequential feedback. Stop/deadline handling cancels and joins all children.

The complete offline suite passed 108 tests, including shared concurrency/pacing, profile snapshots, settings races, session reuse, validation gating and cancellation. Synthetic desktop/mobile UI checks confirmed role switching without allowance/history reset, no campaign on Apply/Save, explicit custom-profile Start and settings locks. Helm lint/render and server-side dry-run passed. Runtime revision fa5f23f was submitted to GitOps; bounded live validation follows at concurrency one only.


Runtime revision fa5f23f reached Synced/Healthy. A saved custom profile, Stage smoke: two controls + topic, completed with two allowed responses, one block and zero errors. Its immutable settings snapshot and idempotent duplicate start passed. The new audience session preserved its cookie/CSRF and remaining allowance when legacy persona fields changed; settings changes were rejected while the window was open. A benign SSE request delivered initial status after 0.099 seconds and validated content at 6.142 seconds. A blocked request emitted status/error only. Three additional target generations were used, all at concurrency one; no capacity ramp or additional model test. The audience window was closed and no campaign remained active.

A controlled replacement of the application and provider pods preserved the named profile, completed report, model and concurrency. Both GitOps Applications remain Synced/Healthy and all twelve Deployments are ready. Browser inspection confirmed the deployed direct-chat layout and live suggestion-role switching. The audience remains closed and concurrency remains one. Documentation and presentation notes now describe the implemented behavior and its measured limits.


## 28 October 2026 — four-day shutdown preparation

The owner requested shutdown with all configuration preserved for rebuilding. Verified AWS account 058264461741, eu-central-1, and the explicit project cluster. Closed audience access, verified no active campaign, and scaled both operator proxies and the audience gateway to zero; their pods terminated. No model inference or new compute resources were requested.

Captured consistent SQLite backups after quiescing all entry points, verified schemas/idle state/integrity/hashes, and restored the actual backup into isolated local files with identical hashes. The final private checkpoint contains six campaign reports, one custom profile, five audience sessions, eight events and 54 provider calls; later activity is preserved rather than overwritten with the earlier test snapshot. Three Terraform state copies are also saved privately. Thirteen targeted backup/teardown tests passed, including prevention of partial writes on validation failure and rejection of foreign-account/non-delete plans.

Added checkpoint.py, shutdown.py and rebuild.py plus shutdown/rebuild runbooks. Recovery recreates the pinned CPU-only infrastructure and platform, refreshes URLs and QR assets, bootstraps secrets locally and restores durable evidence. No automatic restart is scheduled.

Actual cloud teardown remains blocked: ROSA and Terraform reject the expired Red Hat session. The owner has been asked to renew login. AWS workers, NAT, load balancer and volumes still incur charges; closing the demo entry points is not full shutdown. Automatic approval review separately rejected uploading the database archive to the private S3 state bucket without explicit consent. The owner has been asked; no upload occurred. Local backup is complete and does not depend on that optional copy. See docs/shutdown.md for the exact pending steps.


### Completed shutdown after renewed login

The owner renewed the Red Hat session and explicitly selected local-only database backup storage. The ROSA delete-only plan contained 32 managed resources; its cluster ID and every project IAM role prefix were verified before apply. The cluster resource deletion completed after 18 minutes 6 seconds, followed by project IAM/OIDC cleanup. The foundation delete-only plan covered 15 resources in the verified project VPC; it completed successfully. One unreferenced `vpce-private-router` Security Group was left by ROSA. Account, VPC, ownership tags, absence of attached interfaces and absence of inbound references were checked before deleting only that group.

The final account-scoped audit at 2026-10-28T20:38:53Z found no running project workers, volumes, snapshots, load balancers, VPCs, interfaces, endpoints, Elastic IPs, auto-scaling groups, project logs, project roles/policies, OIDC providers or cluster DNS zones. The three old instances are terminated and the old NAT gateway is deleted; AWS retains these historical entries temporarily. Both removed Terraform stages have zero managed resources, and ROSA no longer lists the cluster. Shared account roles and the unrelated hosted zone remain untouched.

Only the existing private Terraform state bucket remains from this demo, with AES256 encryption, versioning and all public-access blocks enabled. Its checkpoints/ prefix is empty. The owner-declined database upload was never performed. Four bootstrap state resources remain. The local checkpoint and isolated restore verification remain valid; no model request, new instance or scheduled restart was created. Current-process metrics are intentionally not treated as durable reports. Docs/shutdown.md and docs/rebuild.md describe the completed state and recovery sequence.

## 4 November 2026 — rebuild authorized; access preflight

The owner requested rebuilding the saved demo. AWS STS accepted the project credentials for account 058264461741 in eu-central-1. Read-only inventory found zero VPCs, active EC2 instances and non-deleted NAT gateways. Foundation and ROSA state contain zero managed resources; the retained bootstrap contains four. The newly generated and inspected foundation plan contains 15 additions, no changes and no deletions, with the expected account and region. It has not been applied.

The final local checkpoint passed all three checksums, schema and SQLite integrity checks. Nine checkpoint tests and Helm lint also passed. The restore runbook now explicitly requires the initial GitOps operation to succeed and both data claims to bind before quiescing, and both restored writers to become ready before restarting entry points. Backups remain local-only.

Authenticated MaaS model discovery returned HTTP 200 and included the configured model; this was not an inference test. ROSA authentication is expired, so the owner has been asked to renew the device-code login. Cluster version availability and provisioning remain pending that login. No new cloud resources, GPU resources, inference requests, campaigns or audience windows were started during this preflight. Historical URLs still refer to the deleted cluster.

## 4 November 2026 — rebuild and restore completed

The renewed Red Hat login succeeded, and ROSA still offered the pinned OpenShift 4.21.34 release. The foundation apply created its 15 expected resources. The ROSA cluster-creation POST lost its response with a connection reset, but the service had accepted the request: inventory verification found the new cluster ready in account 058264461741, eu-central-1, with three m6i.2xlarge workers. Imported that exact cluster instead of submitting a duplicate. The new cluster ID is `2ts9ru3jvhafk5h0q1bvhlfqe1d9icqs`; its ingress domain is `apps.rosa.lemonade-demo.6abk.p3.openshiftapps.com`.

RHCS 1.7.9 import omitted immutable user tags and administrator credentials. The resulting diagnostic can expose the administrator password; the affected credential was rotated privately through the existing HTPasswd user API, without deleting the identity or changing roles. Backed up state locally and reconciled only the verified missing attributes plus the rotated password/hash/output, using normal serial/lineage checks and no forced state push. Fresh administrator login passed, the remaining cluster/default-ingress apply succeeded, and a subsequent Terraform plan reported no changes. Recovery files and credentials remain private and Git-ignored.

Installed only the inspected GitOps 1.22.2 and OpenShift AI 3.5.2 InstallPlans. The offered GitOps 1.22.3 upgrade remains unapproved. DataScienceCluster became Ready. Refreshed the functional deployment origins, HTML deck links and both QR copies for the new ingress domain, then deployed revision `b6b2c6c`. Both detector storage initializers initially retried while MinIO was starting; they recovered naturally after its pinned downloads finished. No additional nodes or GPUs were needed.

The initial application sync succeeded and both data PVCs bound before all five entry/writer deployments were stopped. The first restore attempts failed before database replacement because OpenShift AI selected an SCC that supplied no supplemental filesystem group: the helper had the correct namespace UID but could not write the volume directories. Added explicit namespace-derived `runAsUser` and `fsGroup`, with strict allocation validation. All 12 checkpoint tests passed. The corrected helper was admitted with the expected UID/group and restored all three databases successfully. Both writers became ready before the entry points were restarted.

Authenticated HTTPS chat, Control, dashboard and dashboard WebSocket checks passed. Public `/join` works, audience admission is closed, and public `/control`, `/api/control/state` and `/metrics` return 404. Verified all original record IDs and counts: six campaigns, one profile, five old audience sessions, eight audience events and 54 provider calls. Model qwen38-27b and concurrency one were retained; no campaign was active and the provider was unpaused.

Exactly three serial application probes, with no retries, passed: topic block in 0.093 seconds, benign response in 2.037 seconds, and English-only language-policy block in 0.597 seconds. The benign response contained 111 characters; raw response content was not published. The final provider ledger contains 56 records, including all 54 historical records. These are individual functional observations, not capacity measurements. No new campaign, audience window, concurrent load test or GPU resource was started.

Final acceptance found all 12 deployments ready and both GitOps Applications Synced/Healthy. The local credential helper was checked only with `--urls-only`; its normal owner-run mode retrieves the renewed administrator password. The original backup remains local-only and unchanged; no application checkpoint was uploaded. Current versions, image digests, URLs and measured results are recorded in `docs/version-manifest.json`. Broader evaluation, pending human reviews, customer branding and the event-capacity rehearsal remain separate work.


## 5 November 2026 — simpler dashboards for the stage

Reinspected the public keynote's guardrails and two-source comparison screens. Replaced the long Shiny page with two explicit views: AgentOps and Red teaming. Both use large values, high-contrast colors, concise labels and stable business-policy bars. Source-specific detector counts remain separate from final outcomes and use a common visual scale. Full-screen navigation and collapsed definitions keep the stage view focused. Control now separates Campaign, Audience, Review and Settings, with a larger QR and persistent active-campaign controls. Stop targets the actual active run while another report is selected; actionable stop/error reasons and pending human reviews remain visible.

Validation before rollout: Helm lint/render and server dry-run passed; R UI construction, outcome reconciliation, source isolation, detector-alias grouping and shared-scale assertions passed in the pinned dashboard image. Five offline JavaScript interaction checks passed. The 112 application/infrastructure tests passed in the project Python environment; all 12 checkpoint tests passed with system Python. The project's Python 3.11 / SQLite 3.51 runtime fails the pre-existing WAL snapshot test, while system Python 3.14 / SQLite 3.53 passes it; no backup implementation or live journal mode was changed for this UI update. Browser checks used clearly labeled synthetic fixtures at 1280×800, 1920×1080 and 390×844, with an additional constrained laptop viewport. No model calls or campaigns were created.

Before rollout, authenticated checks found the application idle, audience closed and concurrency one. The older rebuild acceptance helper correctly rejected its obsolete exact record-count assumptions: eight campaigns, two profiles, six sessions, twelve events and 96 provider calls now exist, with every original restored ID retained. The entry points were briefly quiesced, a new verified local-only checkpoint was saved under ignored `local/backups/2026-11-05-before-dashboard`, and their replicas restored. No database archive was uploaded. Rollout validation follows this source checkpoint.

Rollout of `158f556` completed: all 12 application deployments were ready, both GitOps applications reported Synced/Healthy, authenticated HTTPS pages and dashboard WebSocket passed, and both mounted UI source hashes matched the checkout. Compared the live databases with the new checkpoint: all eight campaigns, two profiles, six sessions, twelve events and 96 provider calls were preserved exactly. Audience admission stayed closed, no campaign was active, and provider concurrency remained one. The genuine ROSA dashboard was visually checked with reset-to-zero current-process counters. A separate local unavailable-metrics check correctly hid numbers and showed “Data unavailable”; ASCII placeholders avoid the pinned R runtime's locale-dependent Unicode rendering. No inference, campaign, audience admission, GPU provisioning or provider-limit change occurred. Private acceptance details are in `local/dashboard-release-2026-11-05.json`.


## 5 November 2026 — customer name confirmed

The owner selected **Snemeis**. Replaced the active customer placeholders with **Snemeis Lemonade Division** in presenter chat, audience chat, both dashboard/control views and the HTML deck. Updated current planning and project instructions; logos and additional brand assets remain pending. Historical prerequisite/journal references retain their original placeholder context. This is a branding-only change with no policy, model, budget or access-control changes.

## 5 November 2026 — clearer presentation chapters

Applied the owner's requested keynote comparison to the existing 18-slide HTML deck. The overview and dividers now explicitly distinguish AgentOps with runtime guardrails from automated red teaming before release. Persona order and all five technical diagrams remain. The adaptive-method slide and campaign architecture show each strategy using its own measured feedback; optional model judging and separate human review remain distinct. Campaign-control detail moved into the existing speaker notes, while the stage slide focuses on scope, progress and pause/stop. The runbook keeps Functional as a preflight check and requires an agreed, rehearsed Adaptive run or a visibly labeled Previous run for the second chapter.

All 11 dashboard links now choose the appropriate AgentOps or Red teaming view. Their hashes derive from the single configured dashboard base URL, so rebuilding the cluster continues to refresh them. Versioned stylesheet/script URLs prevent stale local browser assets from masking the update.

Validation: JavaScript syntax and Git whitespace checks passed. The changed visual layouts were reviewed at 1280×720; a DOM bounds check across all 18 slides found no inspected text outside a slide, all chapter-specific URLs resolved correctly, and browser warning/error logs were empty. This presentation-only change made no model request, campaign start, audience admission or cluster modification.


## 6 November 2026 — weekend shutdown requested

The owner requested an immediate weekend shutdown and renewed ROSA device login. Verified account 058264461741, eu-central-1, cluster 2ts9ru3jvhafk5h0q1bvhlfqe1d9icqs and VPC vpc-055157230688f4ec8. Closed audience access, found no active campaign or provider work, then stopped all three entry points. Saved a consistent local-only checkpoint containing eight campaigns, two profiles, six sessions, twelve events and 96 provider calls. Checksums/schema/idle/integrity checks and isolated restore hashes passed. Private infrastructure state and baseline ownership of three workers and six EBS volumes were saved before deletion. Both database writers were stopped after backup. No inference, campaign or cloud backup upload occurred.

The 32-resource ROSA delete-only plan targets the verified cluster and eleven project-owned IAM roles. Apply is running; network teardown and final inventory are pending. The recovery guide points to the latest checkpoint. Hardened future shutdowns against stale same-account cluster checkpoints and plans; the read-only audit now requires current pre-deletion infrastructure and volume/instance ownership inputs rather than hard-coded October identifiers. All 21 targeted shutdown/audit tests passed. No automatic restart is scheduled.


### Completed weekend shutdown

ROSA deletion completed successfully, with the cluster resource taking 18 minutes 5 seconds. Its 32 Terraform resources and the foundation's 15 resources were removed. ROSA inventory no longer contains the cluster; the ROSA and foundation states contain zero managed resources, while the retained bootstrap contains four. Removed one residual cluster endpoint Security Group only after verifying exact ownership, no attached interfaces and no references from other regional groups.

The final audit starting at 2026-11-06T14:47:23Z completed without failed queries. All three known workers are terminated, all six owned EBS volumes are gone, and no active project compute, network, load balancer, IAM/OIDC, DNS or log resources remain. The deleted NAT gateway and terminated instances remain visible as historical AWS entries. Shared account roles/policy and the unrelated hosted zone were preserved. Only the private AES256-encrypted, versioned, public-blocked Terraform state bucket remains from the demo; small storage/request charges may continue. Its checkpoints/ prefix is empty.

The verified local-only weekend checkpoint and archive remain intact. The isolated restore matched all three hashes and preserves eight campaigns, two profiles, six audience sessions, twelve events and 96 provider calls. No model traffic, cloud checkpoint upload or automatic restart was scheduled. Updated project status, version manifest, presentation readiness metadata and recovery instructions. The old 6abk links/QR are retired references; the next explicitly requested rebuild must refresh them and pass acceptance again. The 21 targeted shutdown/audit checks passed before teardown. Private evidence: local/shutdown-audit-2026-11-06.json and local/shutdown-completion-2026-11-06.json.


## 9 November 2026 — rebuild authorized and started

The owner explicitly requested restoring the environment. AWS and ROSA authentication succeeded; account 058264461741 and eu-central-1 matched the project context. ROSA inventory and regional VPC/active EC2 inventory were empty. Foundation and ROSA state were empty, while bootstrap retained four resources. The latest 6 November checkpoint passed verification; all twelve checkpoint tests and Helm lint passed. The pinned ROSA 4.21.34 version is still available.

The inspected foundation plan created its 15 expected resources successfully. The inspected ROSA plan contains 32 additions, three m6i.2xlarge CPU workers, no GPUs and no autoscaling. Cluster creation is in progress. Platform installation, latest-checkpoint restoration, URL/QR refresh and bounded serial acceptance remain pending. No audience admission, campaign or load test has been started.

The workstation briefly lost DNS resolution during ROSA creation. Terraform could neither finish its wait nor persist the latest state to S3. The local recovery state was preserved privately; live inventory verified that the same cluster was Ready with the expected account, region and three CPU workers. Released only the stale lock from the completed failed invocation, pushed the newer matching-lineage state without force, and removed its failed-create taint after live verification. The initial replacement proposal was rejected before apply. The subsequent plan contained only the missing default-ingress resource and no cluster replacement; it applied successfully. No duplicate cluster or administrator credential rotation was needed.

New cluster: 2tvgos7v8icc62s5sp0d7rpcpfs365cm, ingress apps.rosa.lemonade-demo.mjkz.p3.openshiftapps.com. All three workers are Ready. Private project login succeeded. Approved only the GitOps 1.22.2 InstallPlan. Deployment origins, deck links and both QR copies now use the new domain; Helm lint passed. Platform and application acceptance remain pending.


### 9 November rebuild acceptance completed

The owner explicitly requested rebuilding on 9 November. ROSA HCP 4.21.34 is running in eu-central-1 with three Ready m6i.2xlarge CPU workers, zero GPUs, GitOps 1.22.2 and OpenShift AI 3.5.2. Both GitOps applications are Synced/Healthy and all twelve application deployments are ready. The new ingress domain is apps.rosa.lemonade-demo.mjkz.p3.openshiftapps.com; deployment origins, presentation links and both QR copies use it. Earlier 28s8 and 6abk URLs remain retired.

The latest local-only checkpoint from 6 November restored all eight campaigns, two profiles, six sessions, twelve events and 96 historical provider calls, with every saved ID preserved. Authenticated routes, dashboard WebSocket and public/operator boundaries passed. Three serial functional probes passed without retries: topic blocked (9.181 s), benign allowed (6.440 s, 111 characters), English-only policy blocked (4.507 s). These are individual observations, not capacity measurements. Audience admission remains closed, no campaign is active and provider concurrency remains one. No GPU, load test or new campaign was started. Backups remain local-only. Current compute/network/storage resources incur charges until another requested teardown.

Initial application sync succeeded and both data PVCs bound before entry points/writers were stopped. The checkpoint helper restored all three databases, writers became ready, then entry points restarted. Initial detector startup waited for the pinned runtime image downloads; all recovered without configuration changes. Twelve checkpoint tests and Helm lint passed; final ROSA Terraform plan reported no changes. Private acceptance records are local/rebuild-2026-11-09-acceptance-060141584815.json and local/rebuild-2026-11-09-acceptance-after-probes-060611909781.json. The provider ledger now contains 98 records including all 96 originals. Raw records and recovery state remain ignored; no database archive was uploaded to S3.


## 9 November 2026 — presentation context and recent incident

Expanded the English HTML deck from 18 to 22 slides at the owner's request. Added the Metal to Agents opening, explicit two-chapter scope, a sourced recent research incident before Customer/Attacker and the same stack as a closing evidence map. Preserved all persona diagrams, chapter order, live links and the audience QR; the QR is now slide 13. Updated speaker notes, source map and the estimated 22–25 minute runbook. The source map distinguishes conceptual architecture, controlled research, current documentation and actual implementation. No claim is made that all guardrails were disabled or that content filtering covers infrastructure containment. Latest regular documentation was checked against 3.5.2 and separate 3.6 Early Access notes; no FMS migration is implied.

Validation: visually reviewed all new layouts, the final slide and relocated QR at 1280 × 720. Navigated all 22 slides and checked inspected content bounds, loaded images, 22 notes, five original diagrams, live-link schemes and chapter dashboard hashes. QR mismatch warning remained hidden; browser warning/error logs were empty. JavaScript syntax and Git whitespace checks passed. No model request, campaign, audience admission, provider-limit change or cloud change occurred. Saved the opening browser capture as presentation/preview-stack.png.


## 9 November 2026 — Agent Sandbox feasibility audit

Reviewed the requested Agent Sandbox article and current 1.13 product documentation. Verified AWS account, region and project kubeconfig before read-only cluster inspection. Measured ROSA version 4.21.34, three m6i.2xlarge workers, no RuntimeClasses or sandbox CRDs, and catalog candidates agent-sandbox-operator.v0.9.0 / sandboxed-containers-operator.v1.13.1. Recorded the proposed operator-led Lemonade analysis scenario, separate tool/runtime acceptance, CPU peer-pod candidate and teardown requirements in the plan and prerequisite audit. The owner has been asked whether this should be a live integration or a reference-demo outlook. No operator, IAM, network or compute resource was changed; no model or attack request was sent.

## 10 November 2026 — authorized Agent Sandbox integration

The owner selected the integrated live extension and explicitly approved the scoped AWS/operator changes and the separate application RBAC/internal-key changes. Verified account 058264461741, eu-central-1 and cluster 2tvgos7v8icc62s5sp0d7rpcpfs365cm. Agent Sandbox 0.9.0 and OSC 1.13.1 reached Succeeded; Kata installed on one selected CPU worker without reboot, and kata-remote became available after the dedicated VM image completed. Removed the temporary image-builder IAM policy using a plan containing exactly one deletion. No GPU was provisioned.

Added fixed-template broker, one-use Python runner, authenticated Generate → Review → Run interface, persistent evidence and three predefined boundary checks. Added account-scoped Terraform, manual operator bootstrap, scoped namespace access, local checkpoint support and teardown guards. Existing customer chat and campaign paths remain protected. Application rollout and live execution acceptance are pending at this entry; offline tests and actual runtime evidence must not be confused.

### Sandbox application acceptance completed — 10 November

Published and tested application revision `14828f1`. The final transport uses the authenticated, owner/runtime-verified Pod address over the namespace's allowed broker-to-runner network path. Removed broker `pods/proxy` permissions; it can create/delete Claims and read the fixed pool, Sandboxes and Pods only in lemonade-sandbox. Live authorization checks denied Secret reads, Pod proxy access and Pod reads in the default namespace. The external operator page redirects unauthenticated clients to sign-in (302); public audience `/sandbox` and `/api/control/sandbox` return 404.

Measured serial checks on the final transport:

| Check | Observed outcome | Code duration | Cleanup |
| --- | --- | --- | --- |
| Generated synthetic CSV analysis | 160 cups / 40.0 litres; exit 0 | 0.082 s | Complete |
| Conventional service-account token path | Not mounted | 0.111 s | Complete |
| TCP access to the healthy internal broker service | Connection did not succeed | 1.097 s | Complete |
| Program sleeping for 30 seconds | Timeout; process killed | 5.022 s | Complete |

Each used a fresh kata-remote Sandbox/Pod, with saved code hash and Pod UID. These are narrow functional observations, not an escape guarantee, comprehensive egress assessment or capacity result. DNS, metadata access, active-run restart/stop interaction and adversarial exhaustion beyond the predefined timeout remain unvalidated. The first observed Pod-to-runner start took approximately 2 minutes 22 seconds; later execution allocation from a ready pool took less than one second for the benign check. Replenishment is not instantaneous: demonstrate the analysis in Chapter 1, allow replenishment during the customer/audience sequence, and run one boundary check live in Chapter 2.

Three failed attempts remain visible: an incomplete chunked Kubernetes JSON read, then two Pod-proxy HTTP 503 failures. Fixed bounded complete-response reading with a regression test and switched to the already allowed direct broker/runner connection. No failed attempt was reclassified as a successful block. An earlier benign proxy-path execution is retained separately from final-transport acceptance. Three short MaaS generation calls total were made during integration, all serial; boundary probes made no model calls. No campaign, audience admission, GPU or load test was started.

Both pinned operators and kata-remote are ready. IAM audit confirmed only bounded-peer-pods remains on the scoped runtime role; the temporary image policy, image-upload bucket and vmimport role are gone. The dedicated AMI/snapshot remain required for runtime and are included in teardown. The namespace quota uses the actual peer-pod extended resource because the OSC webhook replaces ordinary CPU/memory fields. Repeated discovery preserves the selected worker and disabled builder rights; configuration refuses a second selected worker.

The verified local-only checkpoint `local/backups/2026-11-10-sandbox-final` contains eight campaigns, two profiles, six sessions, twelve events, 101 provider ledger calls and eight sandbox records (five finished, three execution errors). An isolated local restore reproduced all three hashes. Entry points were restored after the checkpoint; no database archive was uploaded. The earlier pre-extension checkpoint remains available for rollback. The normal shutdown helper blocks ROSA deletion until sandbox resources are removed; ordered rebuild/teardown is documented in sandbox.md.

Validation: 32 sandbox test-discovery cases (including reused control fixtures), two platform idempotence/placement checks, 13 checkpoint checks, 41 demo-runtime checks, 12 shutdown checks, eight access-helper checks and five JavaScript control-navigation checks passed. Helm lint and complete server-side dry-run passed. No claim of unique test count is implied by reused fixtures. The 25-slide English HTML deck adds product execution, its architecture, and Chapter 2 boundary evidence; the new slides and updated scope/closing were visually inspected at 1280 × 720. Browser checks found 25 slides/notes, six diagrams, loaded images, valid HTTPS live links and matching QR metadata. The credential-free layout preview was inspected separately; the live API tests exercised authorization and persistence. The local credential display script remains Git-ignored and now includes the Sandbox URL via show_access.py.

Final runtime audit: all 13 application deployments ready (1/1 each), one ready warm Sandbox, zero Claims and exactly one running tagged t3.medium peer VM. No previous test VM remains active. The pool is ready for the next operator task. Audience admission remains closed; the existing provider setting is concurrency one.

## 10 November 2026 — enable the RHOAI Agent Catalog UI

The owner requested activating the agent UI. Enabled only `spec.dashboardConfig.agentsCatalog` in the existing OdhDashboardConfig after server-side dry-run and live schema validation. The UI initially remained hidden. Inspection of the official dashboard v3.5.0-odh area definition confirms that AGENTS_CATALOG also requires the MODEL_REGISTRY component. Updated the pinned platform DSC to enable modelregistry with its standard rhoai-model-registries namespace. No agent, GPU, new AWS worker or inference request is part of this change. UI acceptance remains pending until the dependency is ready.

The narrow dashboard merge patch is tracked in deploy/dashboard-features.patch.json and reapplied by scripts/rebuild.py dashboard and the application bootstrap. The application helper checks that the registry component is Managed first. This avoids granting GitOps new dashboard namespace permissions or adopting unrelated operator-managed dashboard settings.
