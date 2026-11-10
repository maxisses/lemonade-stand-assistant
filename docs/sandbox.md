# Operator analysis in Agent Sandbox

This extension keeps the two-act demonstration: runtime controls first, systematic testing second. The customer chat remains a protected, single-turn text assistant. Only authenticated operators can generate and explicitly run a small analysis of synthetic Lemonade sales at `/sandbox`. Audience roles grant no execution rights.

## Workflow and evidence

1. Close audience admission and finish campaigns. Keep provider concurrency one.
2. Open Agent Sandbox from Red Team Control. Wait for a warm VM.
3. Generate one fixed analysis using the shared, budgeted external model (192 output tokens). Review the complete code; generation never executes it.
4. Run the reviewed code. The saved SHA-256 binds the approval to that exact candidate. A broker allocates a fresh claim and verifies its Pod owner and `kata-remote` runtime before execution.
5. Inspect stdout, outcome, runtime, code hash and cleanup. The fictional dataset is Monday 40, Tuesday 55 and Wednesday 65 cups at 250 ml per cup: the expected total is 160 cups / 40 litres. These are fixture values, not business KPIs.
6. In the release-validation chapter, run predefined internal-network, credential-mount and timeout checks individually. They use the same execution path without an attacker model. A boundary observation is not a proof against arbitrary escape or exfiltration.

Code generation has a separate tool-workflow policy; customer-chat FMS detectors do not validate Python. Execution security depends on authorization, explicit review, fixed templates, restricted identity/network, resource limits and VM isolation. The runner receives neither provider keys nor a service-account token. Output is untrusted text and displayed with textContent. No arbitrary target, uploaded dataset or free-form execution API is exposed to the audience.

The broker permits one claim. The warm pool retains one slot and replenishes after allocation: up to two t3.medium peer VMs on one selected worker, with a per-worker peer-pod limit and namespace quota. Each run has a five-second subprocess wall limit, bounded output, foreground cleanup and a 240-second claim deadline. Cleanup errors lock further dispatch. Unexpected interrupted executions are recorded and never replayed. Records reside in the existing private audience SQLite database and are included in local-only checkpoints.

## Versions and status

Pinned Agent Sandbox 0.9.0 and OpenShift Sandboxed Containers 1.13.1 run on ROSA HCP 4.21.34. AWS peer pods and this Agent Sandbox path are Technology Preview. This is not a production-support or kernel-escape assurance claim. Actual acceptance is recorded separately in the build journal.

The owner explicitly approved the scoped AWS/operator plan and, separately, the namespace/RBAC/internal-key/application integration. Temporary image-building IAM rights were removed after image readiness on 10 November. No GPU or load-test approval was added.

## Rebuild

Use the normal account-checked ROSA and platform rebuild first. Before the application phase, from the repository root:

```bash
python3 scripts/sandbox_platform.py discover
python3 scripts/sandbox_platform.py init
python3 scripts/sandbox_platform.py plan
# Inspect local/sandbox/plan.log and its exact account/cluster/resource changes.
python3 scripts/sandbox_platform.py apply
python3 scripts/sandbox_platform.py operators
python3 scripts/sandbox_platform.py approve
python3 scripts/sandbox_platform.py configure
python3 scripts/sandbox_platform.py status
# Wait for the VM image and kata-remote; do not repeat image construction blindly.
python3 scripts/sandbox_platform.py image-permissions-off
# Confirm only the temporary image policy is being removed.
python3 scripts/sandbox_platform.py apply
python3 scripts/sandbox_platform.py access
# Publish the reviewed GitOps revision, then use the normal application phase.
python3 scripts/rebuild.py application
```

`discover` refuses metadata from a different cluster. Archive the previous ignored `local/sandbox/` directory after completed teardown before discovery for a new cluster. Backend metadata remains account scoped. The platform configuration pins a dedicated image bucket/name and records image/snapshot IDs privately. The existing application image digest supplies the Python runner; the operator supplies the pinned VM image payload. Do not substitute latest images.

## Shutdown order

Follow the existing admission-close and local-checkpoint procedure first, then:

```bash
python3 scripts/sandbox_platform.py quiesce
# Wait until runner Pods and tagged peer VMs are gone.
python3 scripts/sandbox_platform.py image-permissions-on
# Review the temporary cleanup policy plan before applying it.
python3 scripts/sandbox_platform.py apply
python3 scripts/sandbox_platform.py remove-runtime
# Wait for KataConfig removal and operator image cleanup.
python3 scripts/sandbox_platform.py destroy-plan
# Review the delete-only plan.
python3 scripts/sandbox_platform.py destroy-apply
# Continue with the account-scoped ROSA and foundation shutdown scripts.
```

Image cleanup must remove the dedicated AMI, recorded snapshots, dedicated image bucket and newly created vmimport role before the scoped role is removed. The helper refuses to continue if these remain. Do not delete shared account resources to bypass a refusal. Normal ROSA teardown is blocked while the sandbox Terraform stage retains managed resources. Keep GitOps manual during quiescence so warm slots are not recreated.

AWS pricing observed during installation: Linux t3.medium in Frankfurt USD 0.048 per hour. Two continuously running slots therefore add USD 2.304 per day in instance cost, excluding storage, network and CPU credits. A warm pool incurs cost while idle. Removing application Pods alone does not remove image storage or platform IAM resources.

## Sources

- [Requested Agent Sandbox demonstration](https://developers.redhat.com/articles/2026/07/15/red-hat-build-agent-sandbox-isolated-workload-management-kubernetes)
- [Agent Sandbox 1.13 documentation](https://docs.redhat.com/en/documentation/openshift_sandboxed_containers/1.13/html/deploying_red_hat_build_of_agent_sandbox/discover-agent-sandbox_agent-sandbox)
- [ROSA HCP peer-pod deployment guide](https://cloud.redhat.com/experts/rosa/sandboxed-containers/)
- OSC source v1.13.1: `891eadc9fa270c38b1d7040d05675636990058b8`; Cloud API Adaptor submodule: `9a7ba8eefca59e9929111b276faf7448432a3f17`.
