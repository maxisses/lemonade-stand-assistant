#!/usr/bin/env python3
"""Run Terraform with project-only AWS credentials and an explicit account guard."""
import json, subprocess, sys
from pathlib import Path
from project_env import ROOT, backend_configuration, terraform_environment, verify_backend

def verify_plan(plan, env, directory):
    result = subprocess.run(["terraform", "show", "-json", str(plan)], cwd=directory, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Saved plan could not be inspected; no apply executed")
    variables = json.loads(result.stdout).get("variables", {})
    for name in ("expected_account_id", "region"):
        if variables.get(name, {}).get("value") != env["TF_VAR_" + name]:
            raise RuntimeError("Saved plan targets another account or region; no apply executed")

def main():
    if len(sys.argv) < 3 or sys.argv[1] not in {"bootstrap", "foundation", "rosa"}:
        sys.exit("Usage: python3 scripts/tf.py bootstrap|foundation|rosa <terraform arguments>")
    stage, args = sys.argv[1], sys.argv[2:]
    env = terraform_environment(stage)
    check = subprocess.run(["aws", "sts", "get-caller-identity", "--output", "json"], env=env, capture_output=True, text=True)
    if check.returncode:
        sys.exit("AWS identity verification failed; no Terraform command executed")
    account = json.loads(check.stdout)["Account"]
    if account != env["TF_VAR_expected_account_id"]:
        sys.exit("AWS account mismatch; no Terraform command executed")
    directory = ROOT / "infra" / stage
    if args[0] == "init":
        if any(a.startswith(("-backend-config", "-migrate-state", "-force-copy", "-backend=false")) for a in args):
            sys.exit("Backend selection is managed by the project wrapper")
        if stage == "bootstrap":
            path = Path(backend_configuration(stage, env)["path"])
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.parent.chmod(0o700)
        args += ["-reconfigure", *["-backend-config=" + k + "=" + v for k, v in backend_configuration(stage, env).items()]]
    else:
        verify_backend(stage, env)
    if args[0] == "apply":
        plan = Path(args[-1]).expanduser().resolve()
        if len(args) < 2 or args[-1].startswith("-") or not plan.is_file():
            sys.exit("Apply requires an inspected saved plan; run plan -out=... first")
        verify_plan(plan, env, directory)
        args[-1] = str(plan)
    print("Verified project AWS account; Terraform stage: " + stage, flush=True)
    return subprocess.call(["terraform", *args], cwd=directory, env=env)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        sys.exit(str(error))
