"""Load project configuration as data without exposing credential values."""
from pathlib import Path
import json, os, re, shlex

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
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "RHCS_", "TF_"))}
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        if values.get(key):
            env[key] = values[key]
    region = values.get("AWS_REGION", "eu-central-1")
    env.update(AWS_REGION=region, AWS_DEFAULT_REGION=region, AWS_PAGER="", AWS_EC2_METADATA_DISABLED="true")
    context = json.loads((ROOT / "local/context.json").read_text())
    if not re.fullmatch(r"[0-9]{12}", context["aws_account_id"]):
        raise RuntimeError("Invalid expected AWS account")
    if context.get("region") != region:
        raise RuntimeError("Configured region differs from the project context")
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

def terraform_environment(stage):
    """Keep backend metadata and bootstrap state isolated by AWS account."""
    if stage not in {"bootstrap", "foundation", "rosa"}:
        raise RuntimeError("Unknown Terraform stage")
    env = infrastructure_environment()
    account = env["TF_VAR_expected_account_id"]
    directory = ROOT / "local/terraform" / account / stage
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    env["TF_DATA_DIR"] = str(directory)
    return env

def backend_configuration(stage, env):
    account = env["TF_VAR_expected_account_id"]
    if stage == "bootstrap":
        return {"path": str(ROOT / "local/accounts" / account / "bootstrap.tfstate")}
    return {
        "bucket": "lemonade-demo-tfstate-" + account,
        "key": stage + "/terraform.tfstate",
        "region": env["TF_VAR_region"],
    }

def verify_backend(stage, env):
    metadata = Path(env["TF_DATA_DIR"]) / "terraform.tfstate"
    if not metadata.is_file():
        raise RuntimeError("Initialize this account's Terraform stage first")
    backend = json.loads(metadata.read_text())["backend"]
    expected_type = "local" if stage == "bootstrap" else "s3"
    expected = backend_configuration(stage, env)
    if backend.get("type") != expected_type or any(backend.get("config", {}).get(k) != v for k, v in expected.items()):
        raise RuntimeError("Terraform backend does not match the selected account and stage")
