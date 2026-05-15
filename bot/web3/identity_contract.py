"""
ERC-8004 Identity Registry on-chain calls.
register() from Owner EOA → returns tokenId → POST /api/identity.
Uses PoA-enabled Web3 provider.

v1.6.0: Gas is DELEGATED for all ERC-8004 operations (relayed by Tx delegator).
The agent MUST NOT ask the owner to fund CROSS gas for identity registration.
We still set gasLimit manually to prevent ethers from failing on estimation.
"""
from web3 import Web3
from eth_account import Account
from bot.config import IDENTITY_REGISTRY, CROSS_CHAIN_ID
from bot.web3.contracts import IDENTITY_ABI
from bot.web3.provider import get_w3
from bot.web3.gas_checker import require_gas_or_wait_async
from bot.utils.logger import get_logger

log = get_logger(__name__)


async def register_identity_onchain(owner_private_key: str) -> int | None:
    """
    Call register() on ERC-8004 Identity Registry from Owner EOA.
    Returns tokenId (= agentId) or None if failed (no crash).
    """
    acct = Account.from_key(owner_private_key)

    # v1.6.2: Identity gas is delegated/free. We skip the strict gas checker
    # to allow the transaction to proceed even with 0 balance.
    log.info("Proceeding with delegated identity registration...")

    try:
        w3 = get_w3()
        registry = w3.eth.contract(
            address=Web3.to_checksum_address(IDENTITY_REGISTRY),
            abi=IDENTITY_ABI,
        )

        tx = registry.functions.register().build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "gas": 200000,
            "chainId": CROSS_CHAIN_ID,
        })

        signed = w3.eth.account.sign_transaction(tx, owner_private_key)
        # Using getattr for broad compatibility with different web3.py versions
        tx_hash = w3.eth.send_raw_transaction(getattr(signed, 'raw_transaction', getattr(signed, 'rawTransaction', None)))
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            log.error("ERC-8004 register() TX failed: %s", tx_hash.hex())
            return None

        # Extract agentId from Transfer event logs (ERC-721 mint)
        for event_log in receipt.logs:
            if len(event_log.topics) >= 4:
                token_id = int(event_log.topics[3].hex(), 16)
                log.info("ERC-8004 registered: tokenId=%d tx=%s", token_id, tx_hash.hex())
                return token_id

        log.warning("Could not extract tokenId from logs")
        return None

    except Exception as e:
        log.error("ERC-8004 register() error: %s", e)
        return None

