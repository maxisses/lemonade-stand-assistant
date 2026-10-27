# Manual steps and deployment gates

The initial steps below are complete in the active portfolio account as of 27 October 2026. No owner input is currently blocking the CPU-only functional baseline. Retain these gates for rebuilds and upgrades.

1. ROSA login was renewed by the owner and verified on 27 October. Renew it again when necessary with rosa login --use-device-code. The existing service account returned HTTP 401 on 27 October. The owner confirmed Marketplace activation, billing linkage and OpenShift AI entitlement; verify the actual organization/account association after login.
2. Check the available supported OpenShift version before applying infra/rosa. OpenShift 4.21.34 was verified available and is deployed; recheck availability and compatibility before a later rebuild.
3. Bootstrap OpenShift GitOps using the project kubeconfig. Inspect the proposed operator InstallPlan, record its exact CSV/image version in version-manifest.json, then approve the chosen version. Manual InstallPlan policy prevents unreviewed automatic upgrades; approval can be performed by the implementation automation and does not introduce a blanket owner-approval requirement.
4. Publish the validated implementation branch before configuring GitOps to consume it. Commit no secrets, state, plans, provider caches, or raw private results.
5. Apply the bootstrap controller access and platform Application, approve the inspected RHOAI InstallPlan, and verify TrustyAI/KServe CRDs and dependencies. Create runtime model/storage secrets before syncing the application. Secret bootstrap is intentionally outside committed manifests.
6. Keep public Routes disabled for initial functional tests. Use project-authenticated port forwarding. Validate actual service certificate trust, provider authentication, and detector errors through the whole request chain before calling it functional.
7. Record the successful functional run, then discuss a bounded next evaluation phase with the owner. No large scans or load generation during initial integration.
