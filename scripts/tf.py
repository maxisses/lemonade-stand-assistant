#!/usr/bin/env python3
"""Run Terraform with project-only AWS credentials and an explicit account guard."""
import json, subprocess, sys
from project_env import ROOT, infrastructure_environment

def main():
    if len(sys.argv) < 3 or sys.argv[1] not in {"bootstrap", "foundation", "rosa"}:
        sys.exit("Usage: python3 scripts/tf.py bootstrap|foundation|rosa <terraform arguments>")
    stage, args = sys.argv[1], sys.argv[2:]
    env = infrastructure_environment()
    check = subprocess.run(["aws", "sts", "get-caller-identity", "--output", "json"], env=env, capture_output=True, text=True)
    if check.returncode:
        sys.exit("AWS identity verification failed; no Terraform command executed")
    account = json.loads(check.stdout)["Account"]
    if account != env["TF_VAR_expected_account_id"]:
        sys.exit("AWS account mismatch; no Terraform command executed")
    directory = ROOT / "infra" / stage
    if args[0] == "init" and stage != "bootstrap":
        args += ["-backend-config=bucket=lemonade-demo-tfstate-" + account]
    print("Verified project AWS account; Terraform stage: " + stage, flush=True)
    return subprocess.call(["terraform", *args], cwd=directory, env=env)

if __name__ == "__main__":
    sys.exit(main())
