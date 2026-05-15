import os
import json
import stat
from pathlib import Path
from typing import Optional, Any
from eth_account import Account
from bot.utils.logger import get_logger

log = get_logger(__name__)

# Base directory for all agent data
DEFAULT_DATA_DIR = Path("dev-agent")

def _get_path(filename: str, data_dir: Optional[str] = None) -> Path:
    """Get absolute path for a file within a specific data directory."""
    target_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename


def _write_secure(path: Path, data: dict):
    """Write JSON data to path with restricted permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        if os.name != 'nt':
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except:
        pass


def is_first_run(data_dir: Optional[str] = None) -> bool:
    """Check if credentials.json exists in data_dir."""
    return not _get_path("credentials.json", data_dir).exists()


def save_credentials(creds: dict, data_dir: Optional[str] = None):
    """Save credentials to JSON."""
    _write_secure(_get_path("credentials.json", data_dir), creds)


def load_credentials(data_dir: Optional[str] = None) -> dict | None:
    """Load credentials from JSON."""
    path = _get_path("credentials.json", data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def save_owner_intake(intake: dict, data_dir: Optional[str] = None):
    """Save owner intake configuration."""
    _write_secure(_get_path("owner-intake.json", data_dir), intake)


def load_owner_intake(data_dir: Optional[str] = None) -> dict | None:
    """Load owner intake configuration."""
    path = _get_path("owner-intake.json", data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def save_agent_wallet(address: str, private_key: str, data_dir: Optional[str] = None):
    """Save agent wallet EOA."""
    _write_secure(_get_path("agent-wallet.json", data_dir), {
        "address": address,
        "privateKey": private_key
    })


def load_agent_wallet(data_dir: Optional[str] = None) -> dict | None:
    """Load agent wallet EOA."""
    path = _get_path("agent-wallet.json", data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def save_owner_wallet(address: str, private_key: str, data_dir: Optional[str] = None):
    """Save owner wallet EOA (advanced mode only)."""
    _write_secure(_get_path("owner-wallet.json", data_dir), {
        "address": address,
        "privateKey": private_key
    })


def load_owner_wallet(data_dir: Optional[str] = None) -> dict | None:
    """Load owner wallet EOA."""
    path = _get_path("owner-wallet.json", data_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def get_api_key(data_dir: Optional[str] = None) -> str:
    """Get API key from credentials or env."""
    creds = load_credentials(data_dir)
    if creds and creds.get("api_key"):
        return creds["api_key"]
    
    suffix = ""
    if data_dir and "-" in str(data_dir):
        parts = str(data_dir).split("-")
        if parts[-1].isdigit():
            suffix = f"_{parts[-1]}"
    return os.getenv(f"API_KEY{suffix}", os.getenv("API_KEY", ""))


def get_agent_private_key(data_dir: Optional[str] = None) -> str:
    """Get Agent private key from wallet file or env."""
    wallet = load_agent_wallet(data_dir)
    if wallet and wallet.get("privateKey"):
        return wallet["privateKey"]
    
    suffix = ""
    if data_dir and "-" in str(data_dir):
        parts = str(data_dir).split("-")
        if parts[-1].isdigit():
            suffix = f"_{parts[-1]}"
    return os.getenv(f"AGENT_PRIVATE_KEY{suffix}", os.getenv("AGENT_PRIVATE_KEY", ""))


def get_owner_private_key(data_dir: Optional[str] = None) -> str:
    """Get Owner private key from wallet file or env."""
    wallet = load_owner_wallet(data_dir)
    if wallet and wallet.get("privateKey"):
        return wallet["privateKey"]
    
    suffix = ""
    if data_dir and "-" in str(data_dir):
        parts = str(data_dir).split("-")
        if parts[-1].isdigit():
            suffix = f"_{parts[-1]}"
    return os.getenv(f"OWNER_PRIVATE_KEY{suffix}", os.getenv("OWNER_PRIVATE_KEY", ""))


def update_env_file(key: str, value: str):
    """Local helper to update .env file for development."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    try:
        lines = env_path.read_text().splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            new_lines.append(f"{key}={value}")
        
        env_path.write_text("\n".join(new_lines) + "\n")
    except:
        pass

def generate_agent_wallet():
    """Create a new Ethereum EOA for the agent."""
    acct = Account.create()
    return acct.address, acct.key.hex()

def generate_owner_wallet():
    """Create a new Ethereum EOA for the owner."""
    acct = Account.create()
    return acct.address, acct.key.hex()
