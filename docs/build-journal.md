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
