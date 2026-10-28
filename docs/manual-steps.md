# Manual steps and deployment gates

The initial steps below are complete in the active portfolio account as of 27 October 2026. No owner input is currently blocking the CPU-only functional baseline. Retain these gates for rebuilds and upgrades.

1. ROSA login was renewed by the owner and verified on 27 October. Renew it again when necessary with rosa login --use-device-code. The existing service account returned HTTP 401 on 27 October. The owner confirmed Marketplace activation, billing linkage and OpenShift AI entitlement; verify the actual organization/account association after login.
2. Check the available supported OpenShift version before applying infra/rosa. OpenShift 4.21.34 was verified available and is deployed; recheck availability and compatibility before a later rebuild.
3. Bootstrap OpenShift GitOps using the project kubeconfig. Inspect the proposed operator InstallPlan, record its exact CSV/image version in version-manifest.json, then approve the chosen version. Manual InstallPlan policy prevents unreviewed automatic upgrades; approval can be performed by the implementation automation and does not introduce a blanket owner-approval requirement.
4. Publish the validated implementation branch before configuring GitOps to consume it. Commit no secrets, state, plans, provider caches, or raw private results.
5. Apply the bootstrap controller access and platform Application, approve the inspected RHOAI InstallPlan, and verify TrustyAI/KServe CRDs and dependencies. Create runtime model/storage secrets before syncing the application. Secret bootstrap is intentionally outside committed manifests.
6. Keep public Routes disabled for initial functional tests. Use project-authenticated port forwarding. Validate actual service certificate trust, provider authentication, and detector errors through the whole request chain before calling it functional.
7. Record the successful functional run, then discuss a bounded next evaluation phase with the owner. No large scans or load generation during initial integration.


## Act 2 extension — deployed, remaining acceptance checks

The owner requested the campaign controls, persona audience interface and first HTML deck. The implementation does not authorize a large scan or capacity ramp. Use [operations](operations.md) and [red-teaming](red-teaming.md) for the current limits.

1. Keep the explicit project kubeconfig and current account checks. Verify the existing CPU cluster; no additional GPU resource is needed.
2. Create missing control/session keys with `python3 scripts/demo_secrets.py`; retain the existing model and OAuth Secrets. Do not render or print their values.
3. Verify the configured operator/audience origins and the QR target before syncing `demoControl`. Confirm the two data claims bind and the shared provider service is ready before beginning a functional campaign.
4. Check viewer versus executor permissions, audience gateway path restrictions, a closed audience window, and the fact that raw app/guardrail endpoints remain internal.
5. Start only the bounded Functional profile for initial live validation. Record actual outcomes, provider failures, durable export and stop/restart behavior. Keep larger scans, adaptive validation scope and audience/automation capacity rehearsal distinct.
6. Test the real QR and session expiry on a phone, then rehearse the persona order with the HTML deck. Leave audience admission closed outside the scheduled segment. Preserve a labeled backup run before the feature freeze.

Initial live checks now cover OAuth access, missing-CSRF rejection, bounded Functional/Adaptive/retest campaigns and one audience session/request. A restart of application and provider preserved the three completed reports and usage ledger, with no active work and audience access closed. A full capacity rehearsal is outstanding. Treat the list above as rebuild/acceptance guidance, not a claim that every item has passed. The build journal remains the source for measured outcomes.
