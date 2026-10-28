# CPU-only deployment operations

**Temporary shutdown requested on 28 October:** read [shutdown status](shutdown.md) before using historical live URLs or operating cloud resources. The guarded restart procedure is in [rebuild.md](rebuild.md).

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

The helper verifies the project kubeconfig's API address before reading current Route metadata. It lists the ROSA console, OpenShift AI, GitOps, monitoring APIs, CLI downloads, cluster API, the recorded MaaS endpoint, authenticated chat/dashboard Routes, the Red Team Control path, the configured audience Route, and optional local forwarding commands. It reports when live discovery fails instead of inventing URLs. The recorded AWS account is labeled as context, not a fresh STS check. It does not start forwarding processes, change cluster resources, or make model requests. Use --offline for recorded context without cluster calls, or --json for structured output without credentials.

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

The functional deployment uses FMS complete JSON responses (app.upstreamStreaming=false) and model.chatTemplateKwargs.enable_thinking=false. Keep the small 128-token budget and zero retries for this phase. The app releases model answer content only after all upstream and local output checks pass. In the revised SSE UX, progress events can arrive earlier without model answer text; after validation, the checked answer is displayed progressively. This does not enable raw provider-token streaming. A live allowed audience request at `fa5f23f` showed progress before a validated event and then checked-content chunks; a blocked request released no answer content. These are functional checks, not a latency benchmark. The provider's exact checkpoint revision remains unknown; revalidate behavior after provider changes.

Chat and dashboard are exposed through HTTPS Routes named lemonade-chat and lemonade-dashboard in lemonade-demo. Current operator links:

- Chat: https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com
- Dashboard: https://lemonade-dashboard-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com

 Run scripts/show-credentials.sh locally, or python3 scripts/show_access.py without passwords, for their current URLs. Both use OpenShift sign-in and check that the authenticated user can get pods in lemonade-demo; cluster-admin satisfies this check. Ordinary authenticated cluster users without that project permission are denied. These are operator links, not anonymous event audience links.

The chart creates two small CPU OAuth proxies using the exact image from the installed OpenShift release. Each Route reencrypts traffic to a service-serving certificate; TLS verification remains enabled. The operator proxies accept ingress-router traffic on port 8443. With demoControl enabled, the separate audience gateway is the explicit additional ingress exception on port 9090; it cannot forward operator endpoints. Chat, dashboard, inference, and guardrails backend services retain the internal network policy. The dashboard proxy supports WebSockets. No extra nodes or public load balancers are required.

Before the first GitOps sync, run python3 scripts/operator_access_secrets.py to create missing cookie-signing Secrets directly in the verified cluster. Keys use URL-safe Base64 as required by the OpenShift OAuth proxy. It retains existing keys, does not print their values, and writes no secret file. OpenShift generates service TLS Secrets. Keep both kinds of Secret out of Git. Apply gitops/bootstrap/controller-access.yaml for the scoped ServiceAccount and Route permissions; this does not grant cluster-admin. Setting operatorAccess.enabled=false and pruning its resources removes the operator entry path. The manually created session Secrets can then be removed if no longer needed.

For optional troubleshooting, the original localhost forwarding remains available. From this repository, open separate terminals:

```sh
oc --kubeconfig local/kubeconfig -n lemonade-demo port-forward service/lemonade-stand 18080:8080 --address 127.0.0.1
```

```sh
oc --kubeconfig local/kubeconfig -n lemonade-demo port-forward service/shiny-dashboard 18081:3838 --address 127.0.0.1
```

Use http://127.0.0.1:18080 for chat and http://127.0.0.1:18081 for the dashboard. Stop each forwarding process with Ctrl-C. A pod rollout can end forwarding; restart it afterward. These addresses are only for the operator's machine and are not event audience links.

The TrustyAI operator generates guardrails Routes. The internal-only NetworkPolicy allows namespace-local callers, platform monitoring, and the AI application namespace, while excluding ingress-router pods. Supplemental Route IP allowlists were also set during bootstrap; the NetworkPolicy is the declarative control. Do not remove it to enable audience participation. The dedicated audience gateway described below admits bounded event sessions while raw application and guardrail services stay internal.

Dashboard conversations equal allowed + blocked + errors + rejected + cancelled + pending. Detector hits are separate. The common application execution path assigns presenter, automation and audience_product/audience_customer/audience_attacker sources on the server. Malformed HTTP bodies or audience admission failures rejected before that path are outside these counters. The audience/automation panels compare the same current-process scope; they are not attack-success benchmarks. Counters reset on application restart and stale scrape values are hidden. Persistent campaign reports have a different lifetime. The presenter chat stop button only cancels that browser request; use the operator controls below to stop campaigns and close audience admission.

An additional single functional case is available as python3 scripts/functional_probe.py prompt-injection. Do not turn these helpers into a larger scan until its budget is agreed. R dashboard validation uses tests/test_dashboard.R with the deployed image's R runtime; it makes no model calls.


## Act 2 deployment status and configuration

The control UI, audience gateway and shared provider budget are deployed at GitOps revision fa5f23f (Synced/Healthy) as of 28 October. The following initial evidence belongs to the earlier e85b6f8 revision. Initial live checks completed a six-case Functional campaign, nine-attempt Adaptive campaign, same-policy selected-case retest and one audience request. Real OAuth access, missing-CSRF rejection and public gateway path restrictions were also checked. Restarting the application and provider preserved all three completed reports and the 24-request/17-generation ledger, with no active work and the audience still closed. These initial checks predate the direct-chat, suggestion-switch, SSE and editable-settings revision. The separate fa5f23f check passed a saved custom Functional profile (2 allowed, 1 blocked, 0 errors), immutable snapshot/idempotent start, direct chat with the same session quota despite legacy role fields, and settings lock while the audience was open. Allowed SSE produced status at 0.099 seconds, a validated event at 6.142 seconds, then checked-content chunks and done; a block produced status/error with no answer content. Only 3 new target generations ran, all at concurrency 1. The final state had no active campaign and audience admission closed. Controlled application/provider restart at fa5f23f preserved the saved profile, run snapshot, selected model and concurrency; audience admission remained closed. All 12 deployments were 1/1 ready and both GitOps applications were Synced/Healthy. Higher-concurrency live behavior, other-model inference and event capacity remain unvalidated; see red-teaming.md for limits.

The chart default is `demoControl.enabled=false`. Functional values enable it, require `operatorAccess.enabled=true`, and configure exact operator/audience HTTPS origins. Before syncing the extension, run `python3 scripts/demo_secrets.py` with the project context available. It verifies the selected cluster and creates only the missing `lemonade-control` Secret with private `session-secret` and `gateway-key` entries; it retains existing keys and prints no values. Existing model credentials remain in `lemonade-model`. Keep these Secrets out of Git.

The extension adds two small CPU services and two persistent claims, with no GPU or model-hosting change:

- `lemonade-provider-budget` serializes the configured FMS target/tokenization, attacker and judge calls before the existing external model. Its internal HTTPS service uses an OpenShift serving certificate and no public Route.
- `lemonade-audience-gateway` exposes only the audience chat page and allowlisted audience APIs. The `lemonade-audience` Route uses edge TLS with HTTP redirected to HTTPS; the gateway-to-application hop is internal HTTP. The operator Routes continue to use reencrypt TLS.
- `lemonade-campaign-data` stores campaign and audience SQLite databases; `lemonade-provider-data` stores the budget ledger. Each requests 1 GiB in functional values. The single-worker application and provider deployments use Recreate to avoid concurrent writers on their ReadWriteOnce claims.

Keep `demoControl.operatorUrl` and `demoControl.audienceUrl` aligned with actual Route origins. They participate in Origin checks. The QR must keep the audience `/join` URL, with no token. That URL opens chat directly; the compact role control is inside chat, so this UX change does not require a new QR target. If the origin changes, update the deck configuration and regenerate its QR, then copy the validated SVG to `chart/files/lemonade/audience-qr.svg` before syncing the application. The deck checks QR metadata; the operator page serves the deployed static SVG. Test both with a phone.

Extension entry points checked during initial live validation:

- Control: https://lemonade-chat-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com/control
- Audience: https://lemonade-audience-lemonade-demo.apps.rosa.lemonade-demo.28s8.p3.openshiftapps.com/join

Read actual Routes with the access helper before sharing them. Port-forwarding the raw service does not supply the OAuth access token required by Control. Use its authenticated Route for browser operation.

## Model, concurrency and profile controls

This extension is deployed at fa5f23f. The saved custom Functional profile, immutable snapshot, idempotent start and settings lock during an open audience window passed a bounded live check. Only qwen38-27b at concurrency 1 has live inference evidence; the available controls do not establish another model or higher-concurrency capacity.

Before applying global settings, close audience admission, finish or stop active campaigns, and let outstanding work settle. The backend accepts changes only while the system is idle and the audience window is closed. Choose a model ID from the configured MaaS provider's advertised catalogue and a shared concurrency value from 1 through 4 (default 1). The model choice applies to target, attacker and judge together; it does not change the provider endpoint or expose credentials. Do not assume every discovered model works with FMS tokenization, current generation parameters, guardrails or the judging rubric. The exact provider checkpoint is still unavailable.

Read-only provider discovery on 28 October returned HTTP 200 from `/v1/models` and advertised only `qwen38-27b`. This catalogue observation made no generation request and does not establish another model's compatibility or quality. The selector must reflect the advertised catalogue rather than inventing extra choices.

Named custom profiles define a Functional selection of fixed attack cases with two mandatory benign controls, or an Adaptive selection of 1–3 strategies and 1–3 rounds each (maximum 9 attempts). Set a duration of 30–180 seconds. Original profile defaults remain 120 seconds for Functional and 180 seconds for Adaptive. Save the profile, inspect the effective settings, then start a bounded run. Each run retains an immutable profile snapshot and its model/settings context; later edits to the saved profile must not rewrite old reports or an active run.

The adaptive scheduler runs independent strategies concurrently, bounded by the shared provider limit, while each strategy waits for its own measured result before its next round. At default concurrency 1, provider calls remain serialized. Even at a higher concurrency setting, the shared 12 generation starts/minute and hourly ceilings of 240 provider requests, 120 generations and 240,000 tokens remain unchanged. Queue, request, token and time limits can end a run before all attempts finish.

Keep new live checks at concurrency 1. A higher-concurrency live run, a load ramp, or a combined audience/automation rehearsal requires a further operational discussion and bounded scope; the request for editable controls does not itself authorize those tests. Treat another advertised model as unvalidated until its own agreed serial functional check passes, and record the changed model/configuration fingerprint rather than attributing differences to policy alone.

## Run a bounded campaign

1. Sign into the operator chat Route, open **Red Team Control**, and confirm the model, policy fingerprint, provider state and audience window. Viewing requires `get pods` in `lemonade-demo`; changing state additionally requires `create jobs` in API group `batch` there. The controller checks these permissions through the Kubernetes API; audience role selection grants neither.
2. Keep audience admission closed for initial functional validation. Select the original **Functional** default, enter a meaningful name and start once. This default dispatches at most six predefined cases, including two benign controls, within 120 seconds. Custom-profile controls can select fewer fixed attack cases while retaining both benign controls; the three-case saved profile passed the fa5f23f live check. It makes no attacker/judge model calls and does not automatically retry failures.
3. Inspect request outcomes separately from attack verdicts. Target attempts include input-blocked calls; they are not a count of actual provider generations. Unknown semantic results remain inconclusive. Review and export the run after completion.
4. **Pause** prevents new campaign dispatch while the current call settles. **Resume** retains the original deadline; it does not renew the budget. **Stop campaign** cancels waiting work and requests cancellation of in-flight work. Provider computation may continue until its timeout.
5. For a later bounded Adaptive check, the original default uses three strategies, at most nine target attempts and 27 role-call reservations within 180 seconds. It is serial at concurrency 1. Custom profiles allow 1–3 strategies and 1–3 rounds, with independently scheduled strategies but sequential feedback within each strategy. Live checks have not exercised concurrency above 1. Judge findings require human review before confirmed attack success includes them. Do not present this profile as a load test or as validated event capacity.
6. To retest, select up to nine completed allowed/blocked cases. The engine preserves exact prompts and adds two benign controls, removing duplicate controls. A real policy change is a separate reviewed configuration/deployment step. A changed fingerprint during a run pauses it; stop that run and create a new one. A same-policy retest is a repeatability check, not evidence of improvement.

A refreshed browser attaches to durable run state. Duplicate starts with the same idempotency key return the existing run; conflicting settings are rejected. Only one campaign can be active. Run reports contain potentially sensitive prompt/response evidence, so save exports under ignored `local/` storage and review them before sharing.

## Audience and provider operation

Open the audience window only when ready to invite participation. Visitors land directly in chat and may switch Product team, Customer or Attacker with its compact role control. The switch changes prompt suggestions only; it must preserve session identity, remaining allowance, rate counters, window expiry and the displayed transcript. All three use the same protected, single-turn assistant. Prior visible messages are not sent as model conversation context. The fa5f23f live check confirmed direct chat entry and quota retention in the same session while legacy role fields were ignored; the earlier fixed-role check remains historical. The window defaults to two minutes and permits one to ten minutes. It closes automatically; reopening expires previous sessions.

The revised SSE transport shows request progress during the wait and then progressively displays the fully validated answer. No answer content may precede complete upstream/local output validation; progress is not an unchecked token stream. Check blocks, failures, disconnects and a role change during an outstanding request without duplicate dispatch or retroactive outcome attribution before using this revision on stage.

Current audience ceilings: 60 requests per window, 200 active sessions, six requests per session, three requests/minute/session, one outstanding request/session, eight admitted audience requests and 100 characters per prompt. The provider budget can reject earlier. These are configured ceilings, not proof that 100 attendees can submit concurrently. Session identity is independent of venue Wi-Fi IP. Raw audience text is not automatically projected or stored in the audience database.

The shared provider service defaults to one active request; the deployed settings extension permits a global concurrency value of 1–4 only while idle with audience closed. Live validation has stayed at concurrency 1. It retains at most eight active/waiting requests, a generation start no more often than every five seconds, and rolling hourly ceilings of 240 provider requests, 120 generations and 240,000 tokens. Auxiliary tokenization counts as provider traffic. Requests reserve a conservative token estimate before dispatch and use returned provider usage when available. Estimates remain labeled when usage is missing. These limits apply across target, attacker and judge paths, with zero retries and 60-second provider timeouts. Budget code is in `chart/files/lemonade/provider_budget.py`; it is not a browser throttle or a claim about the provider's actual quota.

A provider 429, repeated provider errors or exhausted hourly budget pauses admission. Inspect the reason before using **Resume provider requests**; clearing a pause does not clear rolling usage. Campaign **Resume** checks the unchanged policy and unexpired deadline but deliberately does not clear the provider pause. Only **Resume provider requests** clears that pause; neither control clears rolling usage. Avoid repeated resume attempts against an exhausted budget or unavailable dependency. Presenter preference is best effort and cannot preempt already accepted provider work.

To quiet the event, **Close audience access**, **Stop campaign**, then let already admitted requests settle. Closing audience access invalidates sessions and rejects new submissions but does not cancel accepted requests. Keep the audience/automation sequence separate until a specifically discussed overlap rehearsal passes. If the shared budget is unavailable, show the controlled error or a labeled recorded run; do not bypass it by pointing FMS directly at the provider.

## Persistent evidence, restart and teardown

Campaign and provider state lives on the two PVCs. Normal pod replacement preserves it. On application startup, unfinished campaigns become interrupted, pending audience events become errors and the audience window closes. No uncertain operation is silently reissued. Provider startup marks pending calls interrupted and keeps conservative reservations and pause state. Dashboard counters still reset on application restart.

Export required campaign reports before a rollout or teardown. There is no automatic S3 report backup, retention cleanup or multi-replica coordination. Deleting the PVCs or namespace can destroy the remaining local evidence; do not treat pod-level persistence as a backup. Audience storage contains session hashes, persona, outcome and timing, without raw chat messages. Campaign exports do contain raw synthetic prompts/responses and reviews.

Before removing the extension, close audience admission and stop the active campaign, export the desired evidence, then remove its entry points and workloads. Disabling `demoControl` with pruning can remove the PVC manifests along with the services; inspect the rendered/pruned resource list first and preserve data explicitly. Check residual EBS volumes and the StorageClass reclaim policy during teardown. The manually created `lemonade-control` Secret has a separate lifecycle and may be removed after the extension is retired. Keep existing operator proxy Secrets if operator access is still needed.

The remaining acceptance checks are recorded in [red-teaming.md](red-teaming.md). The initial persona deck and its speaker cues are in [presentation/README.md](../presentation/README.md). Neither a green Helm render nor a deck preview establishes live campaign correctness or venue capacity.
