# CPU-only deployment operations

The initial build uses three m6i.2xlarge workers, a single-AZ ROSA HCP cluster, external MaaS inference, and CPU guardrail detectors. Single-AZ is a demo trade-off; this is not a production HA design. There is no GPU machine-pool resource.

## Configuration

Keep project configuration in ../.env or set LEMONADE_ENV_FILE. Credentials are never command-line arguments to Terraform. local/context.json records the expected AWS account and region; scripts/tf.py checks STS before each command, and AWS providers enforce allowed_account_ids.

The active account is now the portfolio AWS account, verified through STS and ROSA billing after the owner clarified that the original Open Environment was deleted. Original credentials, local bootstrap state, backend metadata, and plans are archived under ignored local/accounts/. Treat them as historical evidence, not active deployment inputs. Original-account cleanup was reported by the owner and not independently verified.

The wrapper isolates backend metadata under local/terraform/ACCOUNT/STAGE and bootstrap state under local/accounts/ACCOUNT/bootstrap.tfstate. It verifies backend account, region, and stage before use, and checks saved-plan account/region before apply. Initialization supplies the correct backend configuration automatically. Do not bypass the wrapper or copy state/plans between accounts. Plan files should use absolute paths under local/.

The default RHCS authentication path uses the current local ROSA refresh-token session. Renew it with rosa login --use-device-code, including before teardown. Alternatively set RHCS_AUTH=service-account and valid RHCS_CLIENT_ID/RHCS_CLIENT_SECRET in local configuration.

## Infrastructure order

For each stage, initialize, inspect the plan, and apply that saved plan: bootstrap, foundation, rosa. Use python3 scripts/tf.py STAGE init and the same wrapper for plan/apply. Saved plans must stay under local/ or use the ignored .tfplan extension. Bootstrap creates the private versioned encrypted state bucket; foundation creates the VPC/NAT/subnets; rosa creates the CPU-only cluster and roles. Validate current ROSA version availability before cluster creation.

Use a project kubeconfig under local/. Bootstrap OpenShift GitOps, then synchronize the declared platform and application configuration. Populate runtime secrets from local credentials without printing rendered secret manifests. The initial application Route is disabled; use authenticated operator access and port forwarding for functional testing.

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

The upstream default local-model installation is intentionally gated by allowGpu=false. A GPU approval is a prerequisite to changing that setting. The functional values select external inference and do not create model-key or storage-key Secrets; create those securely before deployment. Operator channels are proposed and manual approval is configured; record exact selected versions after cluster catalog inspection.

After the cluster Terraform apply completes, run python3 scripts/cluster_login.py to populate the isolated kubeconfig. Once the namespace exists, run python3 scripts/runtime_secrets.py for model/storage credentials. These helpers do not print secret values. All subsequent oc commands must explicitly select local/kubeconfig.

The OCM and user roles were restored/linked with the ROSA CLI using the existing ManagedOpenShift prefix. They are account/organization bootstrap resources outside the Terraform stages. During final teardown, check whether they are shared before removing them with the ROSA CLI.
