"""
Account setup — initialization and credential management.
Supports multi-agent data isolation and Railway environment sync.
"""
import os
import sys
import json
import asyncio
import random
from bot.api_client import MoltyAPI, APIError
from bot.utils.logger import get_logger
from bot.credentials import (
    save_credentials, load_credentials, is_first_run,
    save_agent_wallet, save_owner_wallet, save_owner_intake,
    generate_agent_wallet, generate_owner_wallet
)
from bot.config import AGENT_NAME, OWNER_EOA, ADVANCED_MODE, AUTO_SC_WALLET, AUTO_WHITELIST, AUTO_IDENTITY

log = get_logger(__name__)

def _is_interactive():
    return sys.stdin.isatty() if hasattr(sys, 'stdin') else False

def _restore_from_env(data_dir: str = None) -> dict | None:
    """Try to restore credentials from env, avoiding Agent 1 duplicates."""
    suffix = ""
    if data_dir and "-" in data_dir:
        parts = data_dir.split("-")
        if parts[-1].isdigit(): suffix = f"_{parts[-1]}"
            
    api_key = os.getenv(f"API_KEY{suffix}")
    main_key = os.getenv("API_KEY", "")
    if suffix and suffix != "_1" and api_key == main_key and api_key != "": return None
    if not api_key and (not suffix or suffix == "_1"): api_key = main_key
    if not api_key: return None

    agent_name = os.getenv(f"AGENT_NAME{suffix}", os.getenv("AGENT_NAME", f"Agent{suffix or '-1'}"))
    agent_pk = os.getenv(f"AGENT_PRIVATE_KEY{suffix}", "")
    agent_addr = os.getenv(f"AGENT_WALLET_ADDRESS{suffix}", "")
    owner_pk = os.getenv(f"OWNER_PRIVATE_KEY{suffix}", "")
    owner_addr = os.getenv(f"OWNER_EOA{suffix}", "")

    if agent_pk and agent_addr: save_agent_wallet(agent_addr, agent_pk, data_dir)
    if owner_pk and owner_addr: save_owner_wallet(owner_addr, owner_pk, data_dir)
        
    creds = {
        "api_key": api_key, "agent_name": agent_name,
        "agent_wallet_address": agent_addr, "owner_eoa": owner_addr,
    }
    save_credentials(creds, data_dir)
    return creds

async def run_first_run_intake(data_dir: str = None) -> dict:
    """Run initialization flow, ensuring unique identity and UNIQUE NAME."""
    log.info("[%s] ═══ FIRST-RUN INTAKE ═══", data_dir or "default")
    suffix = ""
    idx = 1
    if data_dir and "-" in data_dir:
        parts = data_dir.split("-")
        if parts[-1].isdigit():
            idx = int(parts[-1])
            suffix = f"_{idx}"

    # Use existing name or env var
    agent_name = os.getenv(f"AGENT_NAME{suffix}", os.getenv("AGENT_NAME", f"Agent-{idx}"))
    
    main_pk = os.getenv("AGENT_PRIVATE_KEY", "")
    agent_pk = os.getenv(f"AGENT_PRIVATE_KEY{suffix}", "")
    agent_address = os.getenv(f"AGENT_WALLET_ADDRESS{suffix}", "")
    
    if idx > 1 and agent_pk == main_pk and agent_pk != "":
        agent_pk = ""
        agent_address = ""

    if not agent_pk or not agent_address:
        agent_address, agent_pk = generate_agent_wallet()
    
    save_agent_wallet(agent_address, agent_pk, data_dir)

    owner_address = os.getenv(f"OWNER_EOA{suffix}", os.getenv("OWNER_EOA", ""))
    owner_pk = os.getenv(f"OWNER_PRIVATE_KEY{suffix}", os.getenv("OWNER_PRIVATE_KEY", ""))
    if ADVANCED_MODE and (not owner_address or not owner_pk):
        owner_address, owner_pk = generate_owner_wallet()
        save_owner_wallet(owner_address, owner_pk, data_dir)

    log.info("[%s] Registering: name=%s wallet=%s", data_dir or "default", agent_name, agent_address[:10])
    api = MoltyAPI()
    try:
        result = await api.create_account(agent_name, agent_address)
        api_key = result.get("apiKey", "")
    except APIError as e:
        if e.code == "CONFLICT":
            log.warning("[%s] ⚠️ CONFLICT (Name or Wallet taken). Retrying with NEW identity...", data_dir or "default")
            await asyncio.sleep(2) # Small delay
            return await run_first_run_intake(data_dir)
        raise
    finally:
        await api.close()

    creds = {
        "api_key": api_key, "agent_name": agent_name,
        "agent_wallet_address": agent_address, "owner_eoa": owner_address,
    }
    save_credentials(creds, data_dir)
    
    from bot.utils.railway_sync import is_railway, sync_all_to_railway
    if is_railway():
        await sync_all_to_railway(creds, agent_pk, owner_pk, suffix=suffix)
    return creds

async def ensure_account_ready(data_dir: str = None) -> dict:
    creds = _restore_from_env(data_dir)
    if creds and creds.get("api_key"):
        # If API Key exists but Owner is missing in Advanced Mode, just fill it in
        if ADVANCED_MODE and not creds.get("owner_eoa"):
            log.info("[%s] API Key found but Owner EOA missing — generating missing pieces...", data_dir or "default")
            owner_address, owner_pk = generate_owner_wallet()
            save_owner_wallet(owner_address, owner_pk, data_dir)
            creds["owner_eoa"] = owner_address
            save_credentials(creds, data_dir)
        return creds
    if not is_first_run(data_dir):
        creds = load_credentials(data_dir)
        if creds and creds.get("api_key"): return creds
    return await run_first_run_intake(data_dir)
