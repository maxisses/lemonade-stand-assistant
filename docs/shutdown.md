# Four-day shutdown checkpoint — 28 October 2026

The owner requested a cost-saving shutdown and reproducible rebuild while away for four days. No automatic restart is scheduled. The retained AWS account is `058264461741`, region `eu-central-1`, former ROSA HCP cluster `lemonade-demo` (`2tn4c1sto6l3cj13je431lqenalg0f38`). Never use the retired account or the portfolio project's Terraform state.

## Current measured status — shutdown completed

- ROSA cluster deletion completed, and the cluster is absent from the account's ROSA inventory. The cluster resource took 18 minutes 6 seconds to delete; this is a shutdown measurement, not a rebuild estimate.
- Terraform removed 32 managed resources in the ROSA stage and 15 in the foundation stage. Both states contain zero managed resources. The retained bootstrap has four managed resources for the state bucket and its safeguards.
- All three worker instances are terminated. All six EBS volumes, the load balancer, NAT gateway, Elastic IP, VPC, subnets, endpoints and network interfaces are removed. AWS may temporarily list terminated instances and the NAT gateway with state `deleted`; these are not active resources.
- Project IAM roles, OIDC provider and the three cluster DNS zones are removed. One unused, tagged cluster Security Group was left by ROSA; ownership and zero dependencies were checked before deleting it. The final inventory has no remaining project Security Groups. Shared account/organization resources were preserved.
- The final read-only audit at 20:38:53 UTC (21:38:53 Europe/Vienna) returned no incomplete queries. It covers the demo's regional services and global IAM/S3/Route53, not an account-wide billing audit. Private detail: `local/shutdown-audit.json`.
- The only retained project cloud resource is `lemonade-demo-tfstate-058264461741`: versioning enabled, AES256 default encryption, all public-access blocks enabled. Small S3 storage/request charges remain possible; zero total account cost is not claimed.
- The owner explicitly chose local-only database checkpoints. No application backup archive has been uploaded, and the bucket's `checkpoints/` prefix is empty. No automatic restart is scheduled.

## Saved evidence and recovery inputs

The final local checkpoint is `local/backups/2026-10-28-ooo-final/`. Its three databases passed checksum, schema, idle-state and SQLite integrity checks. Restoring them into isolated local files reproduced all three original hashes. The compressed private archive is `local/backups/2026-10-28-ooo-final.tar.gz` (10,204 bytes), SHA-256 `015b46a1ebc9f519d064d103dabbb4eb8e21f8d562c1d447b6ef2601310d546a`.

It contains six campaign reports, one saved profile, five audience session records, eight audience event records, and 54 provider call records. These include activity after the earlier functional check. Counts are storage records, not a fresh evaluation or load test. No model inference was requested during shutdown. Campaign records retain raw synthetic prompts/responses and reviews; the backup must remain private.

Additional private Terraform state copies are in `local/backups/2026-10-28-infrastructure/` for bootstrap, foundation and ROSA. The source is in the owner's Git fork; `.env`, model/storage credentials, kubeconfig, state, raw reports and backup archives remain excluded from Git. Keep the local project directory intact. The detector models are a reproducible cache downloaded from pinned revisions; no GPU or locally hosted target model is needed.

## Reproducible teardown procedure (completed for this shutdown)

Full HCP hibernation is not a supported assumption for this cluster. The [current Red Hat hibernation notice](https://access.redhat.com/articles/7012966) distinguishes the abandoned Classic preview from HCP's evolving scale-to-zero functionality. Use normal ROSA deletion, then remove its network. Do not stop managed EC2 instances or alter their Auto Scaling group directly.

The following guarded procedure was used after the owner renewed the Red Hat login. For a later shutdown, create and verify a new checkpoint first. Run from `app/`:

```sh
python3 scripts/checkpoint.py verify local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py rosa plan --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py rosa apply --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py foundation plan --checkpoint local/backups/2026-10-28-ooo-final
python3 scripts/shutdown.py foundation apply --checkpoint local/backups/2026-10-28-ooo-final
```

The helper verifies account/region/backend, requires a verified checkpoint, accepts only delete/no-op changes inside the expected Terraform modules, and saves diagnostic output privately. The foundation stage refuses to proceed until the ROSA state has no managed resources. Inspect the resource addresses from each plan before applying. The standard Terraform module owns the Lemonade-specific cluster/IAM/OIDC lifecycle. Shared account/organization ROSA roles remain outside this teardown.

Retain `bootstrap`: the private, encrypted, versioned S3 state bucket and its local Terraform state. Do not purge state versions. Retained storage has small ongoing charges; zero total cost is not claimed. After deletion, inspect remaining EC2 instances, NAT/EIPs, load balancers, ENIs, EBS volumes, logs and project IAM/OIDC resources. Remove only confirmed Lemonade leftovers, preserving the private state bucket. The measured completed inventory is recorded above. Use `python3 scripts/audit_shutdown.py` to repeat the read-only audit for this recorded shutdown; it writes only under ignored `local/`.

Do not delete data volumes independently before cluster removal unless backup verification is complete. The SQLite backup preserves the durable application evidence; the pinned 50-GiB detector-model cache may be downloaded again. A cloud snapshot is optional, not part of the current completed checkpoint.

## Rebuild

Follow [rebuild.md](rebuild.md). The infrastructure code, pinned operators, guardrails, model settings, application, dashboard and presentation are preserved. `scripts/rebuild.py` supplies guarded bootstrap steps and updates the new cluster URLs and QR assets. `scripts/checkpoint.py restore` restores the durable records with all public entry points and both database writers stopped. A deleted cluster is recreated rather than instantly powered on; rebuild duration has not been benchmarked.
