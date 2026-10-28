#!/usr/bin/env python3
"""Create missing operator-session secrets in the verified cluster, without outputting values."""
import base64
import json
import secrets
import subprocess
import sys

from project_env import ROOT
from show_access import AccessError, command, load_context


def main():
    context = load_context()
    oc = ["oc", "--kubeconfig", str(ROOT / "local/kubeconfig"), "--request-timeout=15s"]
    server = command(oc + ["config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"])
    if server.rstrip("/") != context["cluster_api_url"].rstrip("/"):
        raise AccessError("Kubeconfig mismatch; no session secrets were created.")
    for target in ("lemonade-chat", "lemonade-dashboard"):
        name = target + "-proxy-session"
        exists = command(oc + ["-n", "lemonade-demo", "get", "secret", name, "--ignore-not-found", "-o", "name"])
        if exists:
            print("Retained existing session secret: " + name)
            continue
        manifest = {
            "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
            "metadata": {"name": name, "namespace": "lemonade-demo"},
            "stringData": {"cookie-secret": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()},
        }
        result = subprocess.run(oc + ["create", "-f", "-"], input=json.dumps(manifest), capture_output=True, text=True, timeout=25)
        if result.returncode:
            raise AccessError("Session secret creation failed; response withheld.")
        print("Created session secret: " + name)


if __name__ == "__main__":
    try:
        main()
    except AccessError as error:
        sys.exit(str(error))
    except Exception:
        sys.exit("Operator session bootstrap failed; details were withheld.")
