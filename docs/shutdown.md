# Weekend shutdown — 6 November 2026

**Completed:** ROSA and its foundation network have been destroyed. The final account-scoped audit found no active project compute, volumes, load balancers, network resources, project IAM/OIDC or cluster DNS resources. Both removed Terraform stages contain zero managed resources. Only the private Terraform state bucket and its four bootstrap resources remain. No automatic restart is scheduled.

Current scope: AWS account `058264461741`, region `eu-central-1`, cluster `lemonade-demo` (`2ts9ru3jvhafk5h0q1bvhlfqe1d9icqs`), VPC `vpc-055157230688f4ec8`. The `6abk` URLs are retired. No automatic restart is scheduled.

The new checkpoint is `local/backups/2026-11-06-weekend-final/`. All three database hashes, schemas, idle-state checks and SQLite integrity checks passed. An isolated restore reproduced their hashes. It contains eight campaigns, two saved profiles, six audience sessions, twelve audience events and 96 provider calls. No inference or new campaign was started during shutdown. The private archive has SHA-256 `8e27ad2a0d3af55ebe4b99e8908161edb36032c5815156cc360943e5394fa93b` and is 12,943 bytes. No application database archive was uploaded to S3; the existing Terraform backend continues to store infrastructure state.

Private pre-deletion infrastructure state and ownership evidence are in `local/backups/2026-11-06-weekend-infrastructure/`. The baseline identifies the current VPC, three worker instances and six owned EBS volumes. The final read-only audit used these inputs, never the old October identifiers:

```sh
python3 scripts/audit_shutdown.py \
  --infrastructure-backup local/backups/2026-11-06-weekend-infrastructure \
  --baseline-inventory local/backups/2026-11-06-weekend-infrastructure/baseline-inventory.json \
  --output local/shutdown-audit-2026-11-06.json
```

## Measured completion

- ROSA removed 32 managed resources; the cluster itself took 18 minutes 5 seconds to delete and is absent from ROSA inventory. Foundation removed 15 managed resources. Their current Terraform states are empty; bootstrap retains four state-bucket resources.
- All three workers are terminated and all six EBS volumes are gone. No project VPC, load balancer, active NAT gateway, Elastic IP, interface, endpoint, Auto Scaling group, Security Group, IAM role/policy, OIDC provider, cluster DNS zone or log group remains. AWS still lists the terminated instances and deleted NAT as historical entries.
- One unused cluster `vpce-private-router` Security Group remained after ROSA deletion. Its exact account/VPC/cluster tags, absence of attached interfaces and absence of references from other regional groups were verified before removing it.
- The final audit started at 14:47:23 UTC (15:47:23 Europe/Berlin) and completed with no failed queries. Private evidence is in `local/shutdown-audit-2026-11-06.json` and `local/shutdown-completion-2026-11-06.json`. This covers the selected demo services, not an account-wide billing audit; shared account roles and an unrelated DNS zone were preserved.
- The only retained project cloud resource is `lemonade-demo-tfstate-058264461741`: versioning enabled, AES256 encryption and all public-access blocks enabled. Its `checkpoints/` prefix is empty. Small S3 storage/request charges remain possible.

Retain the private, encrypted, versioned Terraform state bucket. Database checkpoints remain local-only. Rebuild only on an explicit owner request and restore the latest verified checkpoint above. Historical October evidence follows.

---

# Historical four-day shutdown — 28 October 2026

**Historical shutdown record:** the owner requested a rebuild on 4 November 2026. The CPU-only cluster rebuilt on that date passed data-restoration and bounded functional acceptance; it was subsequently removed on 6 November as recorded above. The completed shutdown inventory below describes 28 October, not current resource usage. Current details and URLs are in [build-journal.md](build-journal.md), [version-manifest.json](version-manifest.json) and [rebuild.md](rebuild.md). The original verified checkpoint remains local-only and unchanged.

The owner requested a cost-saving shutdown and reproducible rebuild while away for four days. No automatic restart is scheduled. The retained AWS account is `058264461741`, region `eu-central-1`, former ROSA HCP cluster `lemonade-demo` (`2tn4c1sto6l3cj13je431lqenalg0f38`). Never use the retired account or the portfolio project's Terraform state.

## Historical measured status — 28 October shutdown completed

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

The helper verifies account/region/backend and the exact current ROSA identity, requires a verified checkpoint from that same cluster, accepts only delete/no-op changes inside the expected Terraform modules, and saves diagnostic output privately. The foundation stage refuses to proceed until the ROSA state has no managed resources. Inspect the resource addresses from each plan before applying. The standard Terraform module owns the Lemonade-specific cluster/IAM/OIDC lifecycle. Shared account/organization ROSA roles remain outside this teardown.

Retain `bootstrap`: the private, encrypted, versioned S3 state bucket and its local Terraform state. Do not purge state versions. Retained storage has small ongoing charges; zero total cost is not claimed. After deletion, inspect remaining EC2 instances, NAT/EIPs, load balancers, ENIs, EBS volumes, logs and project IAM/OIDC resources. Remove only confirmed Lemonade leftovers, preserving the private state bucket. The measured completed inventory is recorded above. The current audit helper requires explicit pre-deletion state and baseline inputs that match the current project context. Use the invocation in the latest shutdown record above; it writes only under ignored `local/`. Do not use the historical October scope to classify a rebuilt cluster.

Do not delete data volumes independently before cluster removal unless backup verification is complete. The SQLite backup preserves the durable application evidence; the pinned 50-GiB detector-model cache may be downloaded again. A cloud snapshot is optional, not part of the current completed checkpoint.

## Rebuild

Follow [rebuild.md](rebuild.md). The infrastructure code, pinned operators, guardrails, model settings, application, dashboard and presentation are preserved. `scripts/rebuild.py` supplies guarded bootstrap steps and updates the new cluster URLs and QR assets. `scripts/checkpoint.py restore` restores the durable records with all public entry points and both database writers stopped. A deleted cluster is recreated rather than instantly powered on; rebuild duration has not been benchmarked.
