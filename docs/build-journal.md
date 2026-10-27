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
