# Rebuild after the October break

The application, CPU infrastructure, operator versions, model revisions, routes, guardrails, presentation and limits are stored in this fork. Persistent reports/settings and credentials need the private backup described below. Rebuilding a deleted ROSA HCP cluster provisions a new cluster; it is not an instant power-on. The new cluster receives new hostnames, so refresh all links and QR assets before use. Rebuild duration has not been benchmarked.

Run commands from the `app/` checkout. Keep the AWS Open Environment account available while away. No automatic restart or scheduled model traffic is configured. Do not use `scripts/deploy.sh` or `scripts/undeploy.sh` for this environment: those are upstream variant helpers with different namespaces and unguarded contexts.

## Preserved inputs

- Git branch `codex/lemonade-cpu-maas`: `infra/`, `gitops/`, `chart/`, `deploy/functional-values.yaml`, `presentation/` and documented versions.
- Private `../.env`, `local/context.json`, account-specific Terraform backend metadata/state and `local/model-storage-credentials.json`. Keep these outside Git. The local credential-display Bash script is deliberately not in a fresh clone.
- Private shutdown backup under `local/backups/`: campaign, audience and provider SQLite databases plus checksums and context. Campaign data includes saved profile revisions, attempts, reviews and reports. Audience data contains session metadata; its sessions must not be reopened on restore. Provider data retains settings and budget history.
- The retained encrypted/versioned Terraform state bucket and local bootstrap state. Do not import the retired account's state or use the portfolio project's Terraform files.

The final shutdown record identifies what was actually retained. A manifest and checksum alone are not a backup: verify the database files exist and `PRAGMA integrity_check` passes. The verified local checkpoint is `local/backups/2026-10-28-ooo-final`; its isolated restore matched all three original database hashes. The existing private state bucket is retained for recovery. An additional encrypted S3 checkpoint archive awaits explicit upload approval; no archive has been uploaded. Check [shutdown.md](shutdown.md) for the latest status. Do not place the `.env` or registry credentials in Git.

## 1. Check access and recreate infrastructure

Verify that `../.env` contains current credentials for the account recorded in `local/context.json`, the selected external model, and its API key. Renew the Red Hat session when necessary:

```sh
rosa login --use-device-code
```

The guarded Terraform wrapper verifies STS account, region, stage-specific backend and saved-plan identity. Run the stages in order: `bootstrap` only if its retained resources need repair, then `foundation`, then `rosa`. Never reuse a pre-shutdown plan. Example for each required stage:

```sh
python3 scripts/tf.py foundation init
python3 scripts/tf.py foundation plan -out="$PWD/local/rebuild-foundation.tfplan"
python3 scripts/tf.py foundation show "$PWD/local/rebuild-foundation.tfplan"
python3 scripts/tf.py foundation apply "$PWD/local/rebuild-foundation.tfplan"
```

Repeat with `rosa` after the network has been applied. Keep OpenShift 4.21.34 and the pinned provider/module versions unless the service no longer offers them; review and record any required version change. The desired topology is three `m6i.2xlarge` CPU workers, no GPU resources and no cluster autoscaling. Saved plans/state contain sensitive material and stay under ignored `local/`.

Do not blindly apply a plan that replaces resources in a different account or includes unexpected resources. Keep the shared account/organization ROSA roles that were reused from the portfolio environment outside this teardown/rebuild lifecycle.

```sh
python3 scripts/cluster_login.py
python3 scripts/rebuild.py check
```

`cluster_login.py` updates the project context and private kubeconfig from the new Terraform outputs without printing the admin password. All subsequent cluster commands must explicitly use `local/kubeconfig`.

## 2. Bootstrap the pinned platform

```sh
python3 scripts/rebuild.py gitops-operator
oc --kubeconfig local/kubeconfig -n openshift-gitops-operator get installplans
```

Inspect the pending InstallPlan's `spec.clusterServiceVersionNames` and approve only the plan for `openshift-gitops-operator.v1.22.2`. Do not approve every pending upgrade. Use the actual inspected name in place of `INSTALLPLAN_NAME`:

```sh
oc --kubeconfig local/kubeconfig -n openshift-gitops-operator get installplan INSTALLPLAN_NAME -o jsonpath='{.spec.clusterServiceVersionNames}'
oc --kubeconfig local/kubeconfig -n openshift-gitops-operator patch installplan INSTALLPLAN_NAME --type=merge -p '{"spec":{"approved":true}}'
oc --kubeconfig local/kubeconfig -n openshift-gitops-operator get csv
python3 scripts/rebuild.py platform
```

The helper refuses the platform phase until the exact GitOps CSV has succeeded. It applies the scoped RBAC/AppProject and the platform GitOps Application. Inspect the OpenShift AI InstallPlan in `redhat-ods-operator`; approve only `rhods-operator.3.5.2` using the same procedure in that namespace. Wait for the CSV to succeed and `default-dsc` to become Ready. GitOps creates the configured KServe/TrustyAI components. Its controllers need time to install before the application CRDs exist.

```sh
oc --kubeconfig local/kubeconfig -n redhat-ods-operator get installplans,csv
oc --kubeconfig local/kubeconfig get datasciencecluster default-dsc
```

## 3. Refresh URLs, QR and secrets

`rebuild.py links` reads the actual new cluster ingress domain and updates `deploy/functional-values.yaml`, `presentation/config.js`, the QR SVG/metadata and the chart's QR copy together. It changes public URL configuration only. It marks the new runtime as awaiting acceptance checks while retaining earlier results as historical evidence.

Use the existing Python environment that has `segno`, or create an isolated local QR environment:

```sh
uv venv --python 3.11 local/qr-venv
uv pip install --python local/qr-venv/bin/python 'segno==1.6.6'
local/qr-venv/bin/python scripts/rebuild.py links
helm lint chart -f deploy/functional-values.yaml
git diff -- deploy/functional-values.yaml presentation/config.js presentation/assets/audience-qr.json
```

Review and commit the public URL and QR changes, then push the declared branch. The application phase verifies that the working tree is clean and this exact commit is present in the configured fork. Old printed QR codes must be replaced if the hostname changed.

```sh
python3 scripts/rebuild.py secrets
```

This runs the existing idempotent secret helpers against the verified project kubeconfig. The model API key comes from the local configuration; storage credentials reuse the private local file. Fresh control/session and OAuth cookie keys are acceptable and invalidate old sessions. Do not restore expired Kubernetes service-account tokens, serving certificates or old OAuth cookies from a previous cluster.

## 4. Deploy and restore durable records

```sh
python3 scripts/rebuild.py application
python3 scripts/rebuild.py status
```

The application phase checks pinned OpenShift AI readiness, current URL origins and the published Git revision, then requests a non-pruning sync. It starts no inference, audience window or campaign. Initial model downloads use pinned artifacts and require external network/registry access; they are not MaaS inference.

Restore the validated private database backup before normal operation. The required files are `campaigns.sqlite` and `audience.sqlite` on `lemonade-campaign-data`, and `provider.sqlite` on `lemonade-provider-data`. The checkpoint helper uses SQLite's backup API, including committed WAL content. Its restore validates all checksums/integrity and the AWS account, requires all three public entry points and both writers to be stopped with their pods gone, and refuses to overwrite existing campaign/profile/request evidence. It mounts the two PVCs in a temporary pod with the pinned application image and restricted security context. The application GitOps definition uses manual sync, so do not request another sync during this restore.

After the initial application sync has created and bound the claims, close audience admission and do not send test requests. Run:

```sh
python3 scripts/checkpoint.py verify local/backups/2026-10-28-ooo-final
oc --kubeconfig local/kubeconfig -n lemonade-demo scale deployment/lemonade-audience-gateway deployment/lemonade-chat-proxy deployment/lemonade-dashboard-proxy deployment/lemonade-stand deployment/lemonade-provider-budget --replicas=0
oc --kubeconfig local/kubeconfig -n lemonade-demo get pods -l app=lemonade-stand
oc --kubeconfig local/kubeconfig -n lemonade-demo get pods -l app=lemonade-provider-budget
```

Also check `oc --kubeconfig local/kubeconfig -n lemonade-demo get pods -l 'app in (lemonade-audience-gateway,lemonade-chat-proxy,lemonade-dashboard-proxy)'`. Wait until all five pod selections are empty, then restore:

```sh
python3 scripts/checkpoint.py restore local/backups/2026-10-28-ooo-final
oc --kubeconfig local/kubeconfig -n lemonade-demo wait --for=delete pod/lemonade-checkpoint-restore --timeout=60s
oc --kubeconfig local/kubeconfig -n lemonade-demo scale deployment/lemonade-stand deployment/lemonade-provider-budget --replicas=1
oc --kubeconfig local/kubeconfig -n lemonade-demo rollout status deployment/lemonade-stand --timeout=180s
oc --kubeconfig local/kubeconfig -n lemonade-demo scale deployment/lemonade-audience-gateway deployment/lemonade-chat-proxy deployment/lemonade-dashboard-proxy --replicas=1
python3 scripts/rebuild.py status
```

The helper leaves writers stopped even after a successful restore; restart them only after it reports success. If it refuses existing evidence, preserve that new evidence separately and resolve the conflict instead of deleting databases to force the restore.

On startup, incomplete campaigns become interrupted, uncertain pending events become errors, and audience admission closes. Do not replay interrupted requests automatically. Check saved profile names/revisions, run/attempt counts, model and concurrency in Control after restore; keep concurrency at one. Historical reports and settings persist, while current-process dashboard counters start from zero as labeled.

## 5. Acceptance before inviting users

Check both GitOps Applications are Synced/Healthy, all desired application deployments are ready, the provider is not unexpectedly paused and audience admission is closed. Run `python3 scripts/show_access.py` for the new links. Sign in once and confirm Control, chat, dashboard and its WebSocket work. Verify the public audience route does not expose Control or metrics, and the QR resolves to the new `/join` URL.

A rebuild is not validated merely because the pods are ready. Perform the previously agreed small serial functional checks only when the owner resumes testing: one benign response, the local topic block and the language policy. Keep model discovery separate from inference validation, preserve the shared budgets, and do not start a capacity ramp, concurrent audience campaign or GPU resources. Record the new runtime versions and measurements in the build journal/version manifest. Complete the event rehearsal and pending human reviews separately.
