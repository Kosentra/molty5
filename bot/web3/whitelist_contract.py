"""
WalletFactory + MoltyRoyaleWallet on-chain calls for whitelist approval.
Checks if already whitelisted FIRST, then gas BEFORE executing any transaction.
Never crashes — returns None on failure.
"""
from web3 import Web3
from eth_account import Account
from bot.config import WALLET_FACTORY, CROSS_CHAIN_ID
from bot.web3.contracts import WALLET_FACTORY_ABI, MOLTY_WALLET_ABI
from bot.web3.provider import get_w3
from bot.web3.gas_checker import require_gas_or_wait_async
from bot.utils.logger import get_logger

log = get_logger(__name__)



async def get_molty_wallet_address(owner_eoa: str) -> str | None:
    """Resolve MoltyRoyaleWallet address from WalletFactory.getWallets(). Returns None on failure."""
    try:
        w3 = get_w3()
        # Check current factory first
        factory = w3.eth.contract(
            address=Web3.to_checksum_address(WALLET_FACTORY),
            abi=WALLET_FACTORY_ABI,
        )
        wallets = factory.functions.getWallets(
            Web3.to_checksum_address(owner_eoa)
        ).call()

        if wallets:
            wallet_addr = wallets[0]
            log.info("Resolved MoltyRoyaleWallet: %s", wallet_addr)
            return wallet_addr

        # Fallback to legacy factory
        from bot.config import WALLET_FACTORY_LEGACY
        log.info("No wallet in current factory, checking legacy factory...")
        legacy_factory = w3.eth.contract(
            address=Web3.to_checksum_address(WALLET_FACTORY_LEGACY),
            abi=WALLET_FACTORY_ABI,
        )
        legacy_wallets = legacy_factory.functions.getWallets(
            Web3.to_checksum_address(owner_eoa)
        ).call()

        if legacy_wallets:
            wallet_addr = legacy_wallets[0]
            log.info("Resolved MoltyRoyaleWallet (LEGACY): %s", wallet_addr)
            return wallet_addr

        log.info("No MoltyRoyaleWallet found for owner=%s in any factory", owner_eoa)
        return None
    except Exception as e:
        log.warning("Failed to resolve MoltyRoyaleWallet: %s", e)
        return None


async def verify_whitelist(owner_eoa: str, agent_eoa: str) -> bool:
    """Verify agent EOA appears in current whitelist on-chain."""
    try:
        wallet_addr = await get_molty_wallet_address(owner_eoa)
        if not wallet_addr:
            return False
        w3 = get_w3()
        wallet_contract = w3.eth.contract(
            address=Web3.to_checksum_address(wallet_addr),
            abi=MOLTY_WALLET_ABI,
        )
        whitelist = wallet_contract.functions.getWhitelists().call()
        agent_lower = agent_eoa.lower()
        is_wl = any(addr.lower() == agent_lower for addr in whitelist)
        if is_wl:
            log.info("✅ Agent %s is already in on-chain whitelist", agent_eoa[:12] + "...")
        return is_wl
    except Exception as e:
        log.warning("Whitelist verification error: %s", e)
        return False


async def request_whitelist_onchain(agent_private_key: str, wallet_addr: str) -> bool:
    """Call requestAddWhitelist() on the SC wallet from the Agent EOA."""
    try:
        w3 = get_w3()
        acct = Account.from_key(agent_private_key)
        wallet_contract = w3.eth.contract(
            address=Web3.to_checksum_address(wallet_addr),
            abi=MOLTY_WALLET_ABI,
        )
        
        log.info("Sending on-chain requestAddWhitelist from agent %s...", acct.address[:12])
        tx = wallet_contract.functions.requestAddWhitelist().build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 150000,
            "chainId": CROSS_CHAIN_ID,
        })
        signed = w3.eth.account.sign_transaction(tx, agent_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        
        if receipt.status == 1:
            log.info("✅ On-chain requestAddWhitelist successful: %s", tx_hash.hex())
            return True
        else:
            log.error("On-chain requestAddWhitelist failed: %s", tx_hash.hex())
            return False
    except Exception as e:
        log.error("Failed to send on-chain whitelist request: %s", e)
        return False


async def approve_whitelist_onchain(
    owner_private_key: str,
    agent_eoa: str,
    owner_eoa: str,
) -> str | None:
    """
    Auto-approve whitelist on-chain (advanced mode).
    1. Check if already whitelisted → return "ALREADY_APPROVED"
    2. Check gas
    3. Find pending request → approve
    Returns tx hash, "ALREADY_APPROVED", or None (no crash).
    """
    # Step 0: Check if already whitelisted — skip everything
    already_wl = await verify_whitelist(owner_eoa, agent_eoa)
    if already_wl:
        log.info("Agent already whitelisted on-chain — nothing to do")
        return "ALREADY_APPROVED"

    acct = Account.from_key(owner_private_key)

    # Gas check FIRST — wait and retry every 2 min until gas is available
    has_gas = await require_gas_or_wait_async(acct.address, "Whitelist approveAddWhitelist()")
    if not has_gas:
        return None  # Should never reach here (async version loops forever)

    try:
        w3 = get_w3()

        # Resolve MoltyRoyaleWallet
        wallet_addr = await get_molty_wallet_address(owner_eoa)
        if not wallet_addr:
            log.error("Cannot approve whitelist — no MoltyRoyaleWallet found")
            return None

        # Fetch pending whitelist requests
        wallet_contract = w3.eth.contract(
            address=Web3.to_checksum_address(wallet_addr),
            abi=MOLTY_WALLET_ABI,
        )
        pending = wallet_contract.functions.getRequestedAddWhitelists().call()

        # Find our agent's request
        agent_eoa_lower = agent_eoa.lower()
        target = None
        for req in pending:
            if req[0].lower() == agent_eoa_lower:
                target = req
                break

        if target is None:
            # No pending request for OUR agent — try to trigger it on-chain
            log.info("No pending request for agent %s on-chain. Attempting to trigger it...", agent_eoa_short)
            
            from bot.credentials import get_agent_private_key
            agent_pk = get_agent_private_key()
            if not agent_pk:
                log.error("Cannot trigger whitelist request — no Agent private key available")
                return None
                
            ok = await request_whitelist_onchain(agent_pk, wallet_addr)
            if not ok:
                return None
                
            # Retry fetching pending
            log.info("Retrying fetch pending whitelist requests...")
            pending = wallet_contract.functions.getRequestedAddWhitelists().call()
            for req in pending:
                if req[0].lower() == agent_eoa_lower:
                    target = req
                    break
            
            if target is None:
                log.warning("Agent %s still not found in pending requests after on-chain call.", agent_eoa_short)
                return None

        requestor = target[0]
        agent_id = target[1]
        log.info("Found pending whitelist: requestor=%s agentId=%d", requestor, agent_id)

        # Approve on-chain
        tx = wallet_contract.functions.approveAddWhitelist(
            Web3.to_checksum_address(requestor),
            agent_id,
        ).build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 200000,
            "chainId": CROSS_CHAIN_ID,
        })

        signed = w3.eth.account.sign_transaction(tx, owner_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            log.error("approveAddWhitelist TX failed: %s", tx_hash.hex())
            return None

        log.info("✅ Whitelist approved on-chain: tx=%s", tx_hash.hex())
        return tx_hash.hex()

    except Exception as e:
        log.error("Whitelist approval error: %s", e)
        return None
