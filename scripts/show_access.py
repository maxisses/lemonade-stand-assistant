#!/usr/bin/env python3
"""Show project URLs and login instructions without displaying credentials."""
import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from project_env import ROOT, terraform_environment, verify_backend

NAMESPACE = "lemonade-demo"
ROUTE_FIELDS = (
    r'{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}'
    r'{.spec.host}{"\t"}{.spec.path}{"\t"}{.spec.tls.termination}{"\n"}{end}'
)


class AccessError(RuntimeError):
    """An error whose message is safe to display."""


def command(args, *, env=None, input=None, strip=True):
    # Never echo command output on failure: it may include sensitive data.
    try:
        result = subprocess.run(args, env=env, input=input, capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        raise AccessError("A required local command failed or timed out; its output was withheld.") from None
    if result.returncode:
        raise AccessError("A required local command failed; its output was withheld.")
    return result.stdout.strip() if strip else result.stdout


def public_url(value):
    """Accept only plain HTTPS service URLs; never expose embedded credentials."""
    if not isinstance(value, str):
        raise AccessError("Project metadata contains an invalid service URL.")
    parts = urlsplit(value or "")
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or any(ord(c) < 33 for c in value)):
        raise AccessError("Project metadata contains an invalid or credential-bearing service URL.")
    return urlunsplit(parts)


def load_context():
    try:
        raw = json.loads((ROOT / "local/context.json").read_text())
        context = {key: raw.get(key) for key in (
            "aws_account_id", "region", "cluster_id", "cluster_api_url", "console_url"
        )}
        if not re.fullmatch(r"\d{12}", context["aws_account_id"] or ""):
            raise ValueError()
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", context["region"] or ""):
            raise ValueError()
        if not re.fullmatch(r"[a-zA-Z0-9-]+", context["cluster_id"] or ""):
            raise ValueError()
        context["cluster_api_url"] = public_url(context["cluster_api_url"])
        context["console_url"] = public_url(context["console_url"])
        return context
    except (OSError, ValueError, TypeError):
        raise AccessError("Project context is missing or incomplete. Run scripts/cluster_login.py after provisioning.") from None


def discover_routes(context):
    oc = ["oc", "--kubeconfig", str(ROOT / "local/kubeconfig"), "--request-timeout=8s"]
    server = command(oc + ["config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"])
    if server.rstrip("/") != context["cluster_api_url"].rstrip("/"):
        raise AccessError("Kubeconfig points at another cluster. Live discovery was refused.")
    # Select only public Route fields, never TLS private keys or Secret resources.
    text = command(oc + ["get", "routes", "-A", "-o", "jsonpath=" + ROUTE_FIELDS])
    routes = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 5:
            continue
        namespace, name, host, path, tls = fields
        if tls not in {"edge", "reencrypt", "passthrough"} or not re.fullmatch(r"[a-zA-Z0-9.-]+", host):
            continue
        routes[(namespace, name)] = public_url("https://" + host + path)
    return routes


def build_report(context, *, offline=False):
    routes = {}
    status = "Offline: recorded project context only; live routes were not checked."
    if not offline:
        try:
            routes = discover_routes(context)
            status = "Live Route metadata read from the verified project cluster; browser reachability was not tested."
        except AccessError as error:
            status = str(error) + " Showing recorded context and local access instructions only."
    services = [{"name": "ROSA console", "url": routes.get(("openshift-console", "console"), context["console_url"]),
                 "login": "OpenShift login; project administrator username: cluster-admin"}]
    selections = [
        ("Chat", [(NAMESPACE, "lemonade-chat")]),
        ("Red Team Control", [(NAMESPACE, "lemonade-chat")]),
        ("Audience role selection", [(NAMESPACE, "lemonade-audience")]),
        ("Dashboard", [(NAMESPACE, "lemonade-dashboard")]),
        ("OpenShift AI", [("openshift-ingress", "data-science-gateway"), ("redhat-ods-applications", "rhods-dashboard")]),
        ("GitOps / Argo CD", [("openshift-gitops", "openshift-gitops-server")]),
        ("Metrics API / Thanos", [("openshift-monitoring", "thanos-querier")]),
        ("Alertmanager API", [("openshift-monitoring", "alertmanager-main")]),
        ("OpenShift CLI downloads", [("openshift-console", "downloads")]),
    ]
    for name, keys in selections:
        url = next((routes[key] for key in keys if key in routes), None)
        login = ("API endpoint; use project OpenShift API authentication. The browser UI is in the ROSA console."
                 if "API" in name else "Use OpenShift sign-in where requested; no separate demo password is created.")
        if name == "Red Team Control":
            url = url.rstrip("/") + "/control" if url else None
            login = "OpenShift sign-in; viewing requires get pods, execution requires create jobs in lemonade-demo."
        if name == "Audience role selection":
            url = url.rstrip("/") + "/join" if url else None
            login = "Choose a persona; chat only works during an operator-opened event window."
        if name in {"Chat", "Dashboard"}:
            login = "OpenShift sign-in; requires permission to get pods in lemonade-demo. No port forwarding needed."
        services.append({"name": name, "url": url, "login": login})
    try:
        manifest = json.loads((ROOT / "docs/version-manifest.json").read_text())
        model_endpoint = public_url(manifest.get("provider_endpoint"))
    except (OSError, ValueError, AttributeError, AccessError):
        model_endpoint = None
    services.append({
        "name": "MaaS inference API (recorded configuration)", "url": model_endpoint,
        "login": "API key is held in the lemonade-model runtime Secret; no inference request was sent.",
    })
    forwards = []
    for name, service, local, remote in [("Chat", "lemonade-stand", 18080, 8080), ("Dashboard", "shiny-dashboard", 18081, 3838)]:
        forwards.append({
            "name": name, "url": f"http://127.0.0.1:{local}",
            "status": "Runs on ROSA; localhost access requires its forwarding process. Forwarding was not tested or started.",
            "command": shlex.join(["oc", "--kubeconfig", str(ROOT / "local/kubeconfig"), "-n", NAMESPACE,
                                    "port-forward", "service/" + service, f"{local}:{remote}", "--address", "127.0.0.1"]),
        })
    return {
        "project": NAMESPACE, "context": context, "discovery": status,
        "services": services, "local_access": forwards,
        "login_command": shlex.join(["python3", str(ROOT / "scripts/cluster_login.py")]),
        "kubeconfig": str(ROOT / "local/kubeconfig"),
        "credentials": {
            "console_username": "cluster-admin",
            "console_password": "Stored in private Terraform state; use --copy-admin-password locally when needed.",
            "model_key": "Runtime Secret lemonade-demo/lemonade-model; managed by scripts/runtime_secrets.py.",
            "local_configuration": str(ROOT.parent / ".env") + " (or LEMONADE_ENV_FILE); values are never displayed here.",
        },
        "notes": [
            "AWS account/region above are recorded context, not a live STS check. Select that account in your AWS browser session.",
            "The API URL is a CLI endpoint, not the web console.",
            "Chat, dashboard, and campaign controls use OpenShift sign-in. Audience chat needs an active event window.",
            "Operator-generated guardrails Routes are intentionally excluded: ingress is blocked by the demo network policy.",
            "Renew Red Hat authentication when required with: rosa login --use-device-code",
        ],
    }


def read_admin_password(context):
    """Read the project password after account/state checks; never print it here."""
    env = terraform_environment("rosa")
    verify_backend("rosa", env)
    if env["TF_VAR_expected_account_id"] != context["aws_account_id"] or env["TF_VAR_region"] != context["region"]:
        raise AccessError("Project account or region changed; no password was copied.")
    identity = json.loads(command(["aws", "sts", "get-caller-identity", "--output", "json"], env=env))
    if identity.get("Account") != context["aws_account_id"]:
        raise AccessError("AWS account mismatch; no Terraform output or password was read.")
    terraform = ["terraform", "-chdir=" + str(ROOT / "infra/rosa"), "output", "-raw"]
    server = command(terraform + ["api_url"], env=env)
    if server.rstrip("/") != context["cluster_api_url"].rstrip("/"):
        raise AccessError("Terraform state targets another cluster; no password was read.")
    password = command(terraform + ["admin_password"], env=env, strip=False)
    if not password:
        raise AccessError("The cluster admin password is unavailable; clipboard was unchanged.")
    return password


def copy_admin_password(context):
    """Copy one password only on an explicit local invocation, after account/state checks."""
    clipboard = shutil.which("pbcopy") if sys.platform == "darwin" else None
    if not clipboard:
        raise AccessError("Password copying requires macOS pbcopy. Use scripts/cluster_login.py for CLI login.")
    password = read_admin_password(context)
    # Password travels through stdin, never command arguments, reports, or files.
    command([clipboard], input=password)


def print_report(report):
    print("Lemonade demo access")
    context = report["context"]
    print(f"AWS account: {context['aws_account_id']} | Region: {context['region']}")
    print("Cluster ID: " + context["cluster_id"])
    print("Discovery: " + report["discovery"])
    print("\nCluster services")
    for service in report["services"]:
        print(f"  {service['name']}: {service['url'] or 'Not discovered (offline, absent, or unavailable to this login).'}")
        if service["url"]:
            print("    " + service["login"])
    print("  Cluster API: " + context["cluster_api_url"])
    print("\nOptional local forwarding for troubleshooting (not required for the HTTPS Routes)")
    for access in report["local_access"]:
        print(f"  {access['name']}: {access['url']}")
        print("    " + access["status"])
        print("    " + access["command"])
    print("\nCLI login: " + report["login_command"])
    print("Project kubeconfig: " + report["kubeconfig"])
    print("\nCredentials")
    for name, detail in report["credentials"].items():
        print("  " + name + ": " + detail)
    print("\nNotes")
    for note in report["notes"]:
        print("  - " + note)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Show recorded context and commands without contacting the cluster")
    parser.add_argument("--json", action="store_true", help="Emit a structured report with no credential values")
    parser.add_argument("--copy-admin-password", action="store_true", help="Explicitly copy the project cluster-admin password to the macOS clipboard")
    args = parser.parse_args()
    if args.copy_admin_password and (args.offline or args.json):
        parser.error("--copy-admin-password cannot be combined with --offline or --json")
    context = load_context()
    report = build_report(context, offline=args.offline)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    if args.copy_admin_password:
        copy_admin_password(context)
        print("\nCluster-admin password copied. Your clipboard now contains a secret; replace it after pasting.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AccessError as error:
        sys.exit(str(error))
    except (OSError, ValueError, KeyError, RuntimeError):
        sys.exit("Access information could not be read safely. Check the project configuration; details were withheld.")
