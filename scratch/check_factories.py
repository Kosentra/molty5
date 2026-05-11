from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

# Constants from config.py
WALLET_FACTORY = "0x378De49F47817D3dF10393851A587e5C2C58EF7C"
WALLET_FACTORY_LEGACY = "0x0713665E4D19fD16e1F09AD77526CC343c6F0223"
CROSS_RPC = "https://mainnet.crosstoken.io:22001"

w3 = Web3(Web3.HTTPProvider(CROSS_RPC))
owner_eoa = os.getenv("OWNER_EOA")

ABI = [
    {
        "name": "getWallets",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "address[]"}],
    }
]

def check_factory(name, address):
    print(f"Checking {name} at {address}...")
    try:
        factory = w3.eth.contract(address=Web3.to_checksum_address(address), abi=ABI)
        wallets = factory.functions.getWallets(Web3.to_checksum_address(owner_eoa)).call()
        print(f"  Wallets: {wallets}")
        return wallets
    except Exception as e:
        print(f"  Error: {e}")
        return []

if owner_eoa:
    print(f"Owner EOA: {owner_eoa}")
    w1 = check_factory("Current Factory", WALLET_FACTORY)
    w2 = check_factory("Legacy Factory", WALLET_FACTORY_LEGACY)
    
    if w1 and w2:
        print("\nWARNING: Found wallets in BOTH factories!")
    elif w2 and not w1:
        print("\nIMPORTANT: Wallet found ONLY in legacy factory. Bot might be looking at the wrong one.")
else:
    print("OWNER_EOA not found in .env")
