"""Load project configuration as data without exposing credential values."""
from pathlib import Path
import json, os, shlex

ROOT = Path(__file__).resolve().parents[1]

def configuration():
    path = Path(os.environ.get("LEMONADE_ENV_FILE", str(ROOT.parent / ".env")))
    if not path.is_file():
        raise RuntimeError("Project .env is missing; set LEMONADE_ENV_FILE to its path")
    result = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, sep, value = line.partition("=")
        if not sep or not key.strip().isidentifier():
            raise RuntimeError("Invalid configuration assignment; shell commands are not supported")
        parts = shlex.split(value, comments=True)
        if len(parts) > 1:
            raise RuntimeError("Configuration values containing spaces must be quoted")
        result[key.strip()] = parts[0] if parts else ""
    return result

def infrastructure_environment():
    values = configuration()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "RHCS_", "TF_VAR_"))}
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        if values.get(key):
            env[key] = values[key]
    region = values.get("AWS_REGION", "eu-central-1")
    env.update(AWS_REGION=region, AWS_DEFAULT_REGION=region, AWS_PAGER="", AWS_EC2_METADATA_DISABLED="true")
    context = json.loads((ROOT / "local/context.json").read_text())
    env.update(TF_VAR_expected_account_id=context["aws_account_id"], TF_VAR_region=region)
    if values.get("RHCS_AUTH", "rosa") == "service-account":
        for key in ("RHCS_CLIENT_ID", "RHCS_CLIENT_SECRET"):
            if values.get(key): env[key] = values[key]
    else:
        candidates = [Path.home() / "Library/Application Support/ocm/ocm.json", Path.home() / ".config/ocm/ocm.json"]
        for path in candidates:
            if path.is_file():
                auth = json.loads(path.read_text())
                if auth.get("refresh_token"):
                    env["RHCS_TOKEN"] = auth["refresh_token"]
                    env["RHCS_CLIENT_ID"] = auth.get("client_id", "cloud-services")
                    break
    return env
