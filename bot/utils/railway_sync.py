"""
Railway Variables auto-sync.
After account creation, saves API_KEY + private keys back to Railway Variables
so credentials survive container restarts.

Uses variableCollectionUpsert to set ALL variables in ONE API call = ONE redeploy.
Only syncs ONCE (checks SETUP_COMPLETE flag to prevent infinite redeploy loop).

Requires: RAILWAY_API_TOKEN (create at https://railway.com/account/tokens)
Railway auto-provides: RAILWAY_PROJECT_ID, RAILWAY_ENVIRONMENT_ID, RAILWAY_SERVICE_ID
"""
import os
import httpx
from bot.utils.logger import get_logger

log = get_logger(__name__)

RAILWAY_API_URL = "https://backboard.railway.com/graphql/v2"


def is_railway() -> bool:
    """Check if running on Railway."""
    return bool(os.getenv("RAILWAY_PROJECT_ID"))


def is_setup_complete() -> bool:
    """Check if first-run sync was already done (prevents redeploy loop)."""
    return os.getenv("SETUP_COMPLETE", "").lower() == "true"


def _get_railway_config(suffix: str = "") -> dict | None:
    """Get Railway config from env vars with suffix support."""
    # Priority: Suffixed token (e.g. RAILWAY_API_TOKEN_2), then global
    token = os.getenv(f"RAILWAY_API_TOKEN{suffix}", os.getenv("RAILWAY_API_TOKEN", ""))
    
    project_id = os.getenv("RAILWAY_PROJECT_ID", "")
    env_id = os.getenv("RAILWAY_ENVIRONMENT_ID", "")
    service_id = os.getenv("RAILWAY_SERVICE_ID", "")

    if not all([token, project_id, env_id, service_id]):
        if is_railway() and not token:
            log.warning(
                "⚠️ RAILWAY_API_TOKEN%s not set. Cannot auto-save credentials.", suffix
            )
        return None

    return {
        "token": token,
        "project_id": project_id,
        "environment_id": env_id,
        "service_id": service_id,
    }


async def _collection_upsert(variables_dict: dict, suffix: str = "") -> bool:
    """
    Save ALL variables in ONE API call using variableCollectionUpsert.
    """
    config = _get_railway_config(suffix)
    if not config:
        return False

    # variableCollectionUpsert sets all variables in a single mutation
    mutation = """
    mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) {
        variableCollectionUpsert(input: $input)
    }
    """

    # Filter out empty values
    clean_vars = {k: v for k, v in variables_dict.items() if v}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RAILWAY_API_URL,
                json={
                    "query": mutation,
                    "variables": {
                        "input": {
                            "projectId": config["project_id"],
                            "environmentId": config["environment_id"],
                            "serviceId": config["service_id"],
                            "variables": clean_vars,
                        }
                    },
                },
                headers={
                    "Authorization": f"Bearer {config['token']}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            data = resp.json()
            if "errors" in data:
                log.warning("Railway collection upsert error: %s", data["errors"])
                return False
            log.info("Railway sync: %d variables saved in 1 API call", len(clean_vars))
            return True
    except Exception as e:
        log.warning("Railway collection upsert error: %s", e)
        return False


async def sync_all_to_railway(creds: dict, agent_pk: str, owner_pk: str = "", suffix: str = ""):
    """
    ONE-TIME sync of ALL variables to Railway after first-run.
    Combines config + credentials + private keys into a SINGLE API call.
    Uses variableCollectionUpsert = only 1 redeploy for all variables.
    Sets SETUP_COMPLETE=true in the same call to prevent redeploy loop.
    
    suffix: Optional string like '_2', '_3' to support multi-agent.
    """
    if not is_railway():
        return

    # Skip if already synced (prevents infinite redeploy loop)
    # For multi-agent, we check if the specific API_KEY_N is set
    setup_flag = f"SETUP_COMPLETE{suffix}"
    if os.getenv(setup_flag, "").lower() == "true":
        log.info("[%s] Railway sync already done. Skipping.", setup_flag)
        return

    config = _get_railway_config()
    if not config:
        return

    log.info("First-time Railway sync — saving ALL variables in one API call...")

    from bot.config import (
        ROOM_MODE, ADVANCED_MODE, AUTO_WHITELIST,
        AUTO_SC_WALLET, ENABLE_MEMORY, ENABLE_AGENT_TOKEN,
        AUTO_IDENTITY, LOG_LEVEL, SKILL_VERSION,
    )

    # Build complete variables map — ALL in one call = ONE redeploy
    all_vars = {
        # Config (only sync these for primary agent or if desired)
        "ROOM_MODE": ROOM_MODE,
        "LOG_LEVEL": LOG_LEVEL,
        "SKILL_VERSION": SKILL_VERSION,
        # Credentials with suffix support
        f"API_KEY{suffix}": creds.get("api_key", ""),
        f"AGENT_NAME{suffix}": creds.get("agent_name", ""),
        f"AGENT_WALLET_ADDRESS{suffix}": creds.get("agent_wallet_address", ""),
        f"OWNER_EOA{suffix}": creds.get("owner_eoa", ""),
        # Private keys with suffix support
        f"AGENT_PRIVATE_KEY{suffix}": agent_pk,
        f"OWNER_PRIVATE_KEY{suffix}": owner_pk,
        # Flag to prevent redeploy loop
        f"SETUP_COMPLETE{suffix}": "true",
    }

    ok = await _collection_upsert(all_vars, suffix=suffix)
    if ok:
        log.info("✅ All variables synced to Railway (1 API call = 1 redeploy). Credentials saved!")
    else:
        log.warning("Railway collection upsert failed — check RAILWAY_API_TOKEN permissions")
