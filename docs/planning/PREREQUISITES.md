# Build prerequisite audit

Checked: 27 October 2026. Event: 17 November 2026. No infrastructure was created, no application was deployed, and no adversarial tests were run during this audit. Two small benign inference requests were made, one ordinary and one streamed. Credentials and model response bodies were not printed or stored.

## Proposed build

Use the owner's fork, [maxisses/lemonade-stand-assistant](https://github.com/maxisses/lemonade-stand-assistant), as the application foundation. Its HEAD currently matches the researched revision `5c0f65f07e4773c9770dde866bb877fe727e3391`.

Start with ROSA HCP in eu-central-1, three CPU workers of approximately 8 vCPU / 32 GiB each, OpenShift GitOps, and the required OpenShift AI/TrustyAI components. Use the configured external Red Hat MaaS model for inference. HAP, prompt-injection, and language detectors run on CPU. Reuse the provider initially for attacker/judge experiments if its limits and model behavior permit; separate roles do not inherently require separate GPUs or keys.

The CPU size is a proposal, not measured capacity. The upstream application without its local Llama model requests at least 8.25 vCPU / 24.5 GiB, excluding several platform and service overheads. Validate allocatable capacity and scheduling before finalizing node count. No GPU pool, GPU autoscaling, or hosted target model is included. Any later GPU provisioning requires explicit owner approval.

Preserve the stage sequence: AgentOps with guardrails and observable runtime decisions, then automated red teaming of the protected application, then improvement and retesting. Using a different target model requires fresh behavioral evaluation; it does not reproduce the original Llama model's outcomes.

## Verified locally and through service APIs

| Area | Result | Limitation |
|---|---|---|
| Local configuration | .env contains AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, modelkey, modelendpoint, and model | No Red Hat service-account or registry variables in this project's file |
| Secret exclusion | .gitignore excludes .env; this workspace has no Git repository yet | Expand exclusions before implementation; inspect staged files before commits |
| AWS identity | STS accepts the project credentials; checked account ends in 0925 | No credentials from the reference project were used |
| AWS region | eu-central-1 inspected; no EC2 instances or VPCs found | Other regions/services were not exhaustively inventoried |
| DNS | A public sandbox Route53 zone exists | No additional domain purchase needed for the initial demo |
| CPU quota | Standard On-Demand EC2 quota is 1152 vCPU | Does not establish all HCP quotas, IAM permissions, or AZ capacity |
| ROSA roles | No IAM role names containing rosa, ocm, or hcp were found | Role creation and billing linkage remain to be completed or verified |
| ROSA session | Saved local session has expired | Needs a valid user login or suitably authorized service account |
| Git fork | Public fork of rh-ai-quickstart/lemonade-stand-assistant found; SSH ls-remote succeeded | Read access is verified; a write/push was not attempted |
| Podman | VM is running; approximately 12 GiB RAM and 8 CPUs | Current Quay login is a different robot, not the Lemonade robot |
| CLI tools | aws, rosa, oc, Helm, Terraform, Git, Ansible and Podman installed | GitHub CLI and openshift-install absent; neither blocks the ROSA/SSH path |
| External model | Configured qwen38-27b appears in authenticated /v1/models; chat completions returned HTTP 200 | Provider model revision, service lifetime, and usage quota not supplied |
| Streaming | Short SSE request returned content and [DONE], HTTP 200; about 2.12 seconds for this one probe | Not a latency benchmark or a concurrency test |
| CPU model access | Public config.json retrieval succeeds for IBM HAP and Protect AI injection detector | Full weight downloads, licenses, image pulls, and cluster egress still need validation |
| Existing cluster context | Current oc context references another demo | Use a separate project kubeconfig; do not deploy to the workstation default context |

The model's ordinary completion included a separate reasoning field. The application must handle provider-specific fields and token limits deliberately, expose only intended final content, and validate the full protected response. No rate-limit headers were present in the streamed probe, so provider limits cannot be inferred from this response.

## Owner answers received on 27 October

The owner authorized use of the existing Red Hat service-account and registry credentials, confirmed ROSA activation/linkage and demo entitlement, confirmed availability and Quay write access, and reported no current MaaS limits. These confirmations authorize the CPU-only build; service permissions still require validation. Exact Quay repository discovery remains an implementation check. The owner additionally requested functional testing only at first: short serial requests, with larger scans and load tests deferred until discussed.

## Prerequisite questions asked before the build

1. **Red Hat authentication.** Confirm whether the Red Hat service-account and registry credentials in AWS-RH-Portfolio-Demo may be used for this project, or supply dedicated credentials locally. Their variable names were inspected; their values had not been used at the time of the initial audit. A service account still needs appropriate organization/cluster permissions. If using the proven interactive route, renew the session with `rosa login --use-device-code`.
2. **ROSA activation and entitlement.** Confirm Marketplace activation, linkage of this AWS account to the intended Red Hat organization/billing account, and the OpenShift AI demo entitlement. These are distinct from having AWS API keys. Quay credentials do not substitute for access to registry.redhat.io. If activation/linkage is incomplete, follow the AWS/Red Hat console flow before cluster creation.
3. **Operating conditions.** Confirm eu-central-1 and the initial three-CPU-worker proposal; ensure AWS and MaaS availability through at least 18 November. Supply known MaaS request/token/concurrency limits and the Quay repository names to which the Lemonade robot can push. Unknown limits may be investigated during a bounded integration test, but are not evidence of event capacity.

Keep all new secret values in local protected configuration, never in chat or Git. The supplied Quay login was not executed during the audit. For the build, use a dedicated registry auth file and password-stdin; do not overwrite an unrelated working registry login unnecessarily. If the robot credentials need to be supplied again, place QUAY_USERNAME and QUAY_PASSWORD in the local .env. Confirm pull access for cluster workloads if repositories are private.

No customer logo, final slot length, additional GPU quota, AAP installer, AAP subscription manifest, edge cluster, or standalone OpenShift installer is required to begin the agreed baseline. Branding can use [Customer] placeholders. A separate Hugging Face token is not presently indicated by the two public detector configuration checks.

## Reference-project conventions to reuse

Reviewed the local portfolio project's README.md, CLAUDE.md, docs/rebuild.md, scripts/tf.sh, Terraform ROSA definitions, and OpenShift AI manifests. Its documented three rebuilds are evidence recorded by that project, not deployments performed in this audit.

Reuse Terraform infrastructure, remote encrypted state, explicit account checks, GitOps configuration, pinned dependencies, a build journal, documented manual steps, and teardown instructions. Carry over the approach rather than all resources.

Specific differences that prevent copying the project unchanged:

- terraform/rosa/variables.tf currently defaults gpu_pool_enabled to true despite the approval-oriented description. Our default must be false, with no enabled GPU pool or autoscaling in the plan.
- The portfolio DataScienceCluster explicitly removes trustyai and aipipelines. Enable TrustyAI for this demo; enable pipelines only when needed for the later pipeline option.
- Its scripts default to a cached ROSA session, while the Terraform provider can alternatively use RHCS_CLIENT_ID/RHCS_CLIENT_SECRET. A credential file alone does not establish that the selected authentication path works.
- Do not copy old account identifiers, credentials, state buckets, domains, kubeconfigs, or GPU settings into the new environment.
- AAP, ACM, RDS, edge clusters, a MaaS gateway hosted by us, and the automation portal are unnecessary for the initial Lemonade story.

## Engineering prerequisites owned by the implementation

These are work items, not additional accounts the owner must acquire:

- Check the supported OpenShift/OpenShift AI combination and pin versions. Reassess FMS versus NeMo in the first integration, preserving the functional reference path. Do not introduce an unbounded migration before the event.
- Adapt external inference carefully. The chart accepts hostname/port; .env contains a full HTTPS completion URL. Validate verified TLS, the API path, bearer-key forwarding, streaming, timeout behavior, and error handling through the full orchestrator chain. A successful direct provider call does not validate the chart.
- Inject model and registry keys through Secrets/runtime references, not committed values, ConfigMaps, generated manifests, or logs.
- Check all required HCP quotas and IAM/SCP constraints, selected AZ instance availability, subnet sizing, registry/model egress, DNS/TLS, StorageClasses, and operator access before applying infrastructure. ROSA role and networking creation can be automated after the prerequisites are settled.
- Build linux/amd64 images for the proposed workers even though the local Mac is arm64. Build-only local Podman use is viable; the existing VM is not sized to run the whole upstream detector stack alongside development tools.
- Correct outcome accounting, buffer/validate protected output, add bounded audience access, and implement the application-level evaluation adapter.
- Establish provider budgets and presenter priority, then measure end-to-end latency, detector errors, benign false blocks, attack outcomes, and bounded audience load. Do not infer 100-user capacity from the successful test requests.

## Sources

- [AWS: ROSA setup and activation](https://docs.aws.amazon.com/rosa/latest/userguide/set-up.html)
- [AWS: ROSA HCP prerequisites and deployment](https://docs.aws.amazon.com/rosa/latest/userguide/getting-started-hcp.html)
- [Red Hat: OpenShift AI 3.5 requirements](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install)
- [Fork model configuration](https://github.com/maxisses/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/values.yaml)
- [Fork orchestrator configuration](https://github.com/maxisses/lemonade-stand-assistant/blob/5c0f65f07e4773c9770dde866bb877fe727e3391/chart/templates/fms-orchestr8-config-nlp.yaml)

## Build follow-up

The fork is cloned into app/, and registry access works. The owner renewed the cached ROSA login after the reused Red Hat service account returned HTTP 401. Infrastructure preparation and initial applies created state storage, networking, and IAM/OIDC prerequisites in the original account, but cluster creation failed the Marketplace billing check. No cluster was created.

The owner subsequently authorized switching to the portfolio AWS account and clarified that the original Open Environment was deleted. The portfolio account remains available and its demo was removed. A read-only check on 27 October confirmed ROSA Marketplace billing, no target-account clusters, and no VPCs, NAT gateways, or EC2 instances in eu-central-1. Active configuration now uses that account; old credentials, bootstrap state, backend metadata, and plans are archived privately. No independent proof of complete original-account resource deletion is claimed. See app/docs/build-journal.md for completed checks and remaining work.
