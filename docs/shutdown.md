# Four-day shutdown checkpoint — 28 October 2026

The owner requested a cost-saving shutdown and reproducible rebuild while away for four days. No automatic restart is scheduled. The live account is `058264461741`, region `eu-central-1`, ROSA HCP cluster `lemonade-demo` (`2tn4c1sto6l3cj13je431lqenalg0f38`). Never use the retired account or the portfolio project's Terraform state.

## Current measured status

- Audience admission is closed; no campaign was active when shutdown began.
- All three entry deployments (`lemonade-chat-proxy`, `lemonade-dashboard-proxy`, `lemonade-audience-gateway`) are at zero replicas and their pods are gone. The demo URLs are unavailable.
- The ROSA cluster and its AWS resources have **not yet been deleted**. Terraform's read-only destroy plan and ROSA CLI both rejected the expired Red Hat login. The owner has been asked to run `rosa login --use-device-code`.
- Three CPU workers, one NAT gateway, one application load balancer and six EBS volumes were present before shutdown. Closing entry points does not stop their charges.
- Optional private S3 checkpoint upload awaits explicit owner approval after automatic approval review rejected that transmission. **No checkpoint archive has been uploaded.** The existing versioned Terraform state remains in its original private bucket.

## Saved evidence and recovery inputs

The final local checkpoint is `local/backups/2026-10-28-ooo-final/`. Its three databases passed checksum, schema, idle-state and SQLite integrity checks. Restoring them into isolated local files reproduced all three original hashes. The compressed private archive is `local/backups/2026-10-28-ooo-final.tar.gz` (10,204 bytes), SHA-256 `015b46a1ebc9f519d064d103dabbb4eb8e21f8d562c1d447b6ef2601310d546a`.

It contains six campaign reports, one saved profile, five audience session records, eight audience event records, and 54 provider call records. These include activity after the earlier functional check. Counts are storage records, not a fresh evaluation or load test. No model inference was requested during shutdown. Campaign records retain raw synthetic prompts/responses and reviews; the backup must remain private.

Additional private Terraform state copies are in `local/backups/2026-10-28-infrastructure/` for bootstrap, foundation and ROSA. The source is in the owner's Git fork; `.env`, model/storage credentials, kubeconfig, state, raw reports and backup archives remain excluded from Git. Keep the local project directory intact. The detector models are a reproducible cache downloaded from pinned revisions; no GPU or locally hosted target model is needed.

## Finish the authorized teardown

Full HCP hibernation is not a supported assumption for this cluster. The [current Red Hat hibernation notice](https://access.redhat.com/articles/7012966) distinguishes the abandoned Classic preview from HCP's evolving scale-to-zero functionality. Use normal ROSA deletion, then remove its network. Do not stop managed EC2 instances or alter their Auto Scaling group directly.

After renewing the existing Red Hat login, run from `app/`:

```sh
python3 scripts/checkpoint.py verify local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py rosa plan --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py rosa apply --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py foundation plan --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py foundation apply --checkpoint local/backups/2026-10-28-ooo-final
```

The helper verifies account/region/backend, requires a verified checkpoint, accepts only delete/no-op changes inside the expected Terraform modules, and saves diagnostic output privately. The foundation stage refuses to proceed until the ROSA state has no managed resources. Inspect the resource addresses from each plan before applying. The standard Terraform module owns the Lemonade-specific cluster/IAM/OIDC lifecycle. Shared account/organization ROSA roles remain outside this teardown.

Retain `bootstrap`: the private, encrypted, versioned S3 state bucket and its local Terraform state. Do not purge state versions. Retained storage has small ongoing charges; zero total cost is not claimed. After deletion, inspect remaining EC2 instances, NAT/EIPs, load balancers, ENIs, EBS volumes, logs and project IAM/OIDC resources. Remove only confirmed Lemonade leftovers, preserving the private state bucket and any separately approved backup. Record the final inventory here before declaring shutdown complete.

Do not delete data volumes independently before cluster removal unless backup verification is complete. The SQLite backup preserves the durable application evidence; the pinned 50-GiB detector-model cache may be downloaded again. A cloud snapshot is optional, not part of the current completed checkpoint.

## Rebuild

Follow [rebuild.md](rebuild.md). The infrastructure code, pinned operators, guardrails, model settings, application, dashboard and presentation are preserved. `scripts/rebuild.py` supplies guarded bootstrap steps and updates the new cluster URLs and QR assets. `scripts/checkpoint.py restore` restores the durable records with all public entry points and both database writers stopped. A deleted cluster is recreated rather than instantly powered on; rebuild duration has not been benchmarked.
