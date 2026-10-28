# CPU-only deployment operations

The initial build uses three m6i.2xlarge workers, a single-AZ ROSA HCP cluster, external MaaS inference, and CPU guardrail detectors. Single-AZ is a demo trade-off; this is not a production HA design. There is no GPU machine-pool resource.

## Configuration

The owner's preferred local entry point is the Git-ignored Bash script:

```sh
./scripts/show-credentials.sh
```

It prints the service URLs, cluster-admin username and password directly in the owner's terminal, with OpenShift sign-in instructions for AI and GitOps. It reuses the account/backend/cluster validation below before reading the password. It contains no embedded passwords and writes no credential report to disk. The script has owner-only executable permissions and stays local, so a fresh Git clone does not include it. From the parent workspace use ./app/scripts/show-credentials.sh.

Credential output requires a terminal and disables shell tracing. Use ./scripts/show-credentials.sh --urls-only for output without passwords. Do not run its real credential-display mode through assistant tools or paste that output into chat. The owner explicitly authorized local password display on 28 October 2026. API keys, registry passwords and AWS secret values are not printed by this helper.

For a consolidated URL and login overview, run from this repository:

```sh
python3 scripts/show_access.py
```

The helper verifies the project kubeconfig's API address before reading current Route metadata. It lists the ROSA console, OpenShift AI, GitOps, monitoring APIs, CLI downloads, cluster API, the recorded MaaS endpoint, authenticated chat/dashboard Routes, and optional local forwarding commands. It reports when live discovery fails instead of inventing URLs. The recorded AWS account is labeled as context, not a fresh STS check. It does not start forwarding processes, change cluster resources, or make model requests. Use --offline for recorded context without cluster calls, or --json for structured output without credentials.

The console administrator username is cluster-admin. To copy its password explicitly on your own Mac:

```sh
python3 scripts/show_access.py --copy-admin-password
```

This option checks the live AWS account, selected Terraform backend, and state API address before reading the single admin_password output. It sends the password to pbcopy through stdin, never command arguments, terminal output, or a new file. The option changes your clipboard; replace its contents after pasting. It cannot be combined with --offline or --json. No password is read by the default overview. API keys, registry passwords, and AWS credential values are never displayed. This is an optional manual operation; automated validation covers it with fake credentials and does not touch the user's clipboard.

From the parent project folder, use python3 app/scripts/show_access.py instead.

Keep project configuration in ../.env or set LEMONADE_ENV_FILE. Credentials are never command-line arguments to Terraform. local/context.json records the expected AWS account and region; scripts/tf.py checks STS before each command, and AWS providers enforce allowed_account_ids.

The active account is now the portfolio AWS account, verified through STS and ROSA billing after the owner clarified that the original Open Environment was deleted. Original credentials, local bootstrap state, backend metadata, and plans are archived under ignored local/accounts/. Treat them as historical evidence, not active deployment inputs. Original-account cleanup was reported by the owner and not independently verified.

The wrapper isolates backend metadata under local/terraform/ACCOUNT/STAGE and bootstrap state under local/accounts/ACCOUNT/bootstrap.tfstate. It verifies backend account, region, and stage before use, and checks saved-plan account/region before apply. Initialization supplies the correct backend configuration automatically. Do not bypass the wrapper or copy state/plans between accounts. Plan files should use absolute paths under local/.

The default RHCS authentication path uses the current local ROSA refresh-token session. Renew it with rosa login --use-device-code, including before teardown. Alternatively set RHCS_AUTH=service-account and valid RHCS_CLIENT_ID/RHCS_CLIENT_SECRET in local configuration.

## Infrastructure order

For each stage, initialize, inspect the plan, and apply that saved plan: bootstrap, foundation, rosa. Use python3 scripts/tf.py STAGE init and the same wrapper for plan/apply. Saved plans must stay under local/ or use the ignored .tfplan extension. Bootstrap creates the private versioned encrypted state bucket; foundation creates the VPC/NAT/subnets; rosa creates the CPU-only cluster and roles. Validate current ROSA version availability before cluster creation.

Use a project kubeconfig under local/. Bootstrap OpenShift GitOps, then synchronize the declared platform and application configuration. The GitOps bootstrap extends the operator's existing permissions with a DataScienceCluster-specific ClusterRole and a Role limited to application resources in lemonade-demo. It does not bind cluster-admin. An AppProject restricts this fork to the Lemonade namespace, the AI operator namespace, and the platform monitoring namespace, with explicit resource-kind allowlists. Kubernetes RBAC cannot restrict create by resource name; later DataScienceCluster updates/deletion are limited to default-dsc. The operator's pre-existing default permissions remain unchanged. Populate runtime secrets from local credentials without printing rendered secret manifests. Direct application Routes stay disabled. The functional values enable separate authenticated operator Routes through the proxies described below.

## Functional testing

Only one request at a time. Start with one normal Lemonade question, one prepared local policy block, and one detector-mediated example after confirming the first two results. Use short output limits and no automatic retries. Record service errors separately from policy blocks. Do not run load tests, audience bursts, or larger red-team scans until discussed with the owner.

After cluster login and application readiness, run python3 scripts/functional_probe.py benign, inspect the result, then run local-block and language-policy individually. The helper verifies the project kubeconfig, opens its own localhost-only forwarding connection to the chat service, and sends exactly one request with no retries. A local file lock prevents concurrent probe processes. Results under ignored local/functional-results/ record actual outcomes, timing, and a response hash; they do not store model response text. A successful local block does not establish that the orchestrator or model worked. The language case tests the English-only policy, not multilingual safety quality.

## Teardown

Export any needed reports, remove demo applications and their external resources, then destroy rosa, foundation, and bootstrap in that order using the guarded wrapper. Keep a working Red Hat login until ROSA deletion finishes. The versioned state bucket intentionally has force_destroy=false; retain state until all resources are confirmed removed, then explicitly purge versions before deleting the bucket. Check residual load balancers, EIPs/NAT, volumes, log groups, state versions, and OIDC/IAM resources. Registry images and external MaaS usage have separate lifecycles.

## Local verification

Use Python 3.11 and the resolved tests/requirements.lock for the offline tests:

```sh
uv venv --python 3.11 .venv
uv pip sync --python .venv/bin/python tests/requirements.lock
.venv/bin/python -m unittest discover -s tests -v
helm lint chart -f deploy/functional-values.yaml
helm template lemonade-demo chart -f deploy/functional-values.yaml
oc kustomize gitops/platform
```

The upstream default local-model installation is intentionally gated by allowGpu=false. A GPU approval is a prerequisite to changing that setting. The functional values select external inference and do not create model-key or storage-key Secrets; create those securely before deployment. Selected operators are GitOps 1.22.2 and OpenShift AI 3.5.2; manual upgrade approval remains configured. Exact images are recorded in docs/version-manifest.json.

After the cluster Terraform apply completes, run python3 scripts/cluster_login.py to populate the isolated kubeconfig. Once the namespace exists, run python3 scripts/runtime_secrets.py for model/storage credentials. These helpers do not print secret values. All subsequent oc commands must explicitly select local/kubeconfig.

In the original, now retired account, OCM and user roles were restored/linked with the ROSA CLI. In the active portfolio account those roles already existed and were reused. They are account/organization resources outside this project's Terraform state; retain them by default during Lemonade teardown. The lemonade-account and lemonade-operator role families are managed by this project's ROSA stage.

## Current operator access and response mode

The functional deployment uses FMS complete JSON responses (app.upstreamStreaming=false) and model.chatTemplateKwargs.enable_thinking=false. Keep the small 128-token budget and zero retries for this phase. The app emits a browser response only after all upstream and local output checks pass. The provider's exact checkpoint revision remains unknown; revalidate behavior after provider changes.

Chat and dashboard are exposed through HTTPS Routes named lemonade-chat and lemonade-dashboard in lemonade-demo. Run scripts/show-credentials.sh locally, or python3 scripts/show_access.py without passwords, for their current URLs. Both use OpenShift sign-in and check that the authenticated user can get pods in lemonade-demo; cluster-admin satisfies this check. Ordinary authenticated cluster users without that project permission are denied. These are operator links, not anonymous event audience links.

The chart creates two small CPU OAuth proxies using the exact image from the installed OpenShift release. Each Route reencrypts traffic to a service-serving certificate; TLS verification remains enabled. Only the proxy pods on port 8443 accept ingress-router traffic. Chat, dashboard, inference, and guardrails backend services retain the internal network policy. The dashboard proxy supports WebSockets. No extra nodes or public load balancers are required.

Before the first GitOps sync, run python3 scripts/operator_access_secrets.py to create missing cookie-signing Secrets directly in the verified cluster. It retains existing keys, does not print their values, and writes no secret file. OpenShift generates service TLS Secrets. Keep both kinds of Secret out of Git. Apply gitops/bootstrap/controller-access.yaml for the scoped ServiceAccount and Route permissions; this does not grant cluster-admin. Setting operatorAccess.enabled=false and pruning its resources removes the operator entry path. The manually created session Secrets can then be removed if no longer needed.

For optional troubleshooting, the original localhost forwarding remains available. From this repository, open separate terminals:

```sh
oc --kubeconfig local/kubeconfig -n lemonade-demo port-forward service/lemonade-stand 18080:8080 --address 127.0.0.1
```

```sh
oc --kubeconfig local/kubeconfig -n lemonade-demo port-forward service/shiny-dashboard 18081:3838 --address 127.0.0.1
```

Use http://127.0.0.1:18080 for chat and http://127.0.0.1:18081 for the dashboard. Stop each forwarding process with Ctrl-C. A pod rollout can end forwarding; restart it afterward. These addresses are only for the operator's machine and are not event audience links.

The TrustyAI operator generates guardrails Routes. The internal-only NetworkPolicy allows namespace-local callers, platform monitoring, and the AI application namespace, while excluding ingress-router pods. Supplemental Route IP allowlists were also set during bootstrap; the NetworkPolicy is the declarative control. Do not remove it to enable audience participation; implement a deliberately authenticated audience entry path first.

Dashboard conversations equal allowed + blocked + errors + rejected + pending. Detector hits are a separate breakdown. Metrics include requests handled by /api/chat, not malformed HTTP bodies rejected before that handler. They are in-memory, single-process counters; restarting the app resets them. The dashboard labels this limitation and hides stale values when scraping fails. Preserve reports before rollouts when durable event evidence is needed. The UI stop button cancels only its browser request; it is not an event-wide stop control.

An additional single functional case is available as python3 scripts/functional_probe.py prompt-injection. Do not turn these helpers into a larger scan until its budget is agreed. R dashboard validation uses tests/test_dashboard.R with the deployed image's R runtime; it makes no model calls.
