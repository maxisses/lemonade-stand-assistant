#!/usr/bin/env python3
"""Restartable cluster bootstrap steps; never provision GPUs or run inference."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from project_env import ROOT, infrastructure_environment


class RebuildError(RuntimeError):
    """Safe diagnostic that contains no command output or credentials."""


def run(args, *, env=None, payload=None):
    try:
        result = subprocess.run(args, cwd=ROOT, env=env, input=payload,
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise RebuildError("A required command failed or timed out; output withheld.") from None
    if result.returncode:
        raise RebuildError("A required command failed; output withheld. Check the named phase and project login.")
    return result.stdout.strip()


def context():
    value = json.loads((ROOT / "local/context.json").read_text())
    env = infrastructure_environment()
    identity = json.loads(run(["aws", "sts", "get-caller-identity", "--output", "json"], env=env))
    if identity.get("Account") != value.get("aws_account_id"):
        raise RebuildError("AWS account mismatch; no cluster operation attempted.")
    oc = ["oc", "--kubeconfig", str(ROOT / "local/kubeconfig"), "--request-timeout=30s"]
    server = run(oc + ["config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"])
    if not server.startswith("https://") or server.rstrip("/") != value.get("cluster_api_url", "").rstrip("/"):
        raise RebuildError("Kubeconfig does not match project context; run cluster_login.py after provisioning.")
    run(oc + ["whoami"])
    print(f"Verified project account {value['aws_account_id']}, region {value['region']} and cluster API.")
    return value, oc


def get(oc, resource, *args):
    return json.loads(run(oc + ["get", resource, *args, "-o", "json"]))


def apply(oc, path):
    run(oc + ["apply", "-f", str(ROOT / path)])
    print("Applied " + path)


def require_csv(oc, namespace, name):
    csv = get(oc, "csv", name, "-n", namespace)
    if csv.get("status", {}).get("phase") != "Succeeded":
        raise RebuildError("Pinned operator is not ready: " + name)


def refresh_links(oc):
    # Check the QR dependency before modifying any deployment/presentation files.
    if importlib.util.find_spec("segno") is None:
        raise RebuildError("Use the documented QR Python environment with segno installed.")
    domain = get(oc, "ingresses.config.openshift.io", "cluster")["spec"]["domain"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+", domain):
        raise RebuildError("Unexpected ingress domain; no files changed.")
    chat = "https://lemonade-chat-lemonade-demo." + domain
    audience = "https://lemonade-audience-lemonade-demo." + domain
    values_path = ROOT / "deploy/functional-values.yaml"
    values = values_path.read_text()
    for field, url in (("operatorUrl", chat), ("audienceUrl", audience)):
        values, count = re.subn(r"(?m)^(  " + field + r":)\s*\S+\s*$", r"\g<1> " + url, values)
        if count != 1:
            raise RebuildError("Expected exactly one demoControl URL setting; no files changed.")
    config_path = ROOT / "presentation/config.js"
    config = json.loads(config_path.read_text().split("window.LEMONADE_DECK =", 1)[1].strip().removesuffix(";"))
    config["links"].update(chat=chat, control=chat + "/control", audience=audience + "/join",
                           dashboard="https://lemonade-dashboard-lemonade-demo." + domain,
                           console="https://console-openshift-console." + domain,
                           ai="https://rh-ai." + domain)
    config["readiness"] = {name: "Rebuild URL configured; live acceptance checks pending."
                           for name in ("chat", "dashboard", "control", "audience")}
    config.setdefault("validation", {})["currentRebuild"] = "New cluster: runtime and QR acceptance checks pending; earlier results are historical."
    values_path.write_text(values)
    config_path.write_text("/* Public presentation links only. Never add credentials or access tokens. */\n"
                           + "window.LEMONADE_DECK = " + json.dumps(config, indent=2) + ";\n")
    run([sys.executable, str(ROOT / "presentation/generate-qr.py")])
    shutil.copyfile(ROOT / "presentation/assets/audience-qr.svg", ROOT / "chart/files/lemonade/audience-qr.svg")
    print("Updated deployment origins, presentation links and both QR copies for " + domain)
    print("Review and commit these public files, then push before the application phase.")


def published_revision():
    if run(["git", "status", "--porcelain"]):
        raise RebuildError("Commit the intended deployment and URL changes before application sync.")
    branch = run(["git", "branch", "--show-current"])
    if branch != "codex/lemonade-cpu-maas":
        raise RebuildError("This helper expects the declared GitOps branch codex/lemonade-cpu-maas.")
    revision = run(["git", "rev-parse", "HEAD"])
    published = run(["git", "ls-remote", "https://github.com/maxisses/lemonade-stand-assistant.git",
                     "refs/heads/" + branch]).split()
    if not published or published[0] != revision:
        raise RebuildError("Push this exact revision to the declared fork before application sync.")
    return revision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("check", "gitops-operator", "platform", "links", "secrets", "application", "status"))
    phase = parser.parse_args().phase
    _, oc = context()
    if phase == "gitops-operator":
        apply(oc, "gitops/bootstrap/operator.yaml")
        print("Approve only the pinned GitOps InstallPlan as described in docs/rebuild.md, then rerun platform.")
    elif phase == "platform":
        require_csv(oc, "openshift-gitops-operator", "openshift-gitops-operator.v1.22.2")
        apply(oc, "gitops/bootstrap/controller-access.yaml")
        apply(oc, "gitops/bootstrap/platform-app.yaml")
        print("Approve only the pinned OpenShift AI InstallPlan and wait for default-dsc Ready before application.")
    elif phase == "links":
        refresh_links(oc)
    elif phase == "secrets":
        for filename in ("runtime_secrets.py", "operator_access_secrets.py", "demo_secrets.py"):
            run([sys.executable, str(ROOT / "scripts" / filename)])
            print("Completed secret bootstrap: " + filename)
    elif phase == "application":
        require_csv(oc, "redhat-ods-operator", "rhods-operator.3.5.2")
        dsc = get(oc, "datasciencecluster", "default-dsc")
        if not any(c.get("type") == "Ready" and c.get("status") == "True"
                   for c in dsc.get("status", {}).get("conditions", [])):
            raise RebuildError("OpenShift AI default-dsc is not Ready.")
        domain = get(oc, "ingresses.config.openshift.io", "cluster")["spec"]["domain"]
        for expected in ("https://lemonade-chat-lemonade-demo." + domain,
                         "https://lemonade-audience-lemonade-demo." + domain):
            if expected not in (ROOT / "deploy/functional-values.yaml").read_text():
                raise RebuildError("Refresh, review and publish the new cluster URLs before application sync.")
        revision = published_revision()
        apply(oc, "gitops/bootstrap/lemonade-app.yaml")
        run(oc + ["patch", "application", "lemonade-demo", "-n", "openshift-gitops", "--type=merge", "-p",
                  json.dumps({"operation": {"sync": {"revision": revision, "prune": False}}})])
        print("Requested application sync for the published revision; no inference was started.")
    elif phase == "status":
        for item in get(oc, "applications", "-n", "openshift-gitops").get("items", []):
            status = item.get("status", {})
            print(item["metadata"]["name"], status.get("sync", {}).get("status"), status.get("health", {}).get("status"))
        for item in get(oc, "deployments", "-n", "lemonade-demo").get("items", []):
            print(item["metadata"]["name"], str(item.get("status", {}).get("readyReplicas", 0))
                  + "/" + str(item["spec"].get("replicas", 1)))
        print("Readiness is not inference validation. Keep audience closed; follow the bounded acceptance checks.")


if __name__ == "__main__":
    try:
        main()
    except (RebuildError, OSError, KeyError, ValueError) as error:
        message = str(error) if isinstance(error, RebuildError) else "Required project metadata is missing or invalid; details withheld."
        sys.exit(message)
