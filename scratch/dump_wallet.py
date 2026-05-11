from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

CROSS_RPC = "https://mainnet.crosstoken.io:22001"
w3 = Web3(Web3.HTTPProvider(CROSS_RPC))

wallet_addr = "0x13c654D050272F8DE378d4c69212CBFD15908925"

ABI = [
    {
        "name": "getRequestedAddWhitelists",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {
                "name": "",
                "type": "tuple[]",
                "components": [
                    {"name": "eoa", "type": "address"},
                    {"name": "agentId", "type": "uint256"},
                ],
            }
        ],
    },
    {
        "name": "getWhitelists",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address[]"}],
    }
]

wallet = w3.eth.contract(address=Web3.to_checksum_address(wallet_addr), abi=ABI)

print(f"Wallet: {wallet_addr}")
try:
    whitelist = wallet.functions.getWhitelists().call()
    print(f"Current Whitelist: {whitelist}")
except Exception as e:
    print(f"Error getWhitelists: {e}")

try:
    pending = wallet.functions.getRequestedAddWhitelists().call()
    print(f"Pending Requests: {pending}")
except Exception as e:
    print(f"Error getRequestedAddWhitelists: {e}")
