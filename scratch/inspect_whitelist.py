from web3 import Web3

RPC_URL = "https://mainnet.crosstoken.io:22001"
OWNER = "0x447346Dcc57CC459A8B7121559dC029bF77bd533"
AGENT = "0x520019A584830F2a7A559066a9be12Fa3d3dB41e"
WALLET = "0x13c654D050272F8DE378d4c69212CBFD15908925"

ABI = [
    {
        "name": "getWhitelists",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address[]"}],
    },
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
    }
]

def check():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=Web3.to_checksum_address(WALLET), abi=ABI)
    
    print(f"Checking Wallet: {WALLET}")
    
    wl = contract.functions.getWhitelists().call()
    print(f"Whitelists: {wl}")
    if AGENT.lower() in [a.lower() for a in wl]:
        print("✅ AGENT IS WHITELISTED!")
    else:
        print("❌ AGENT IS NOT WHITELISTED.")
        
    reqs = contract.functions.getRequestedAddWhitelists().call()
    print(f"Pending Requests: {reqs}")

if __name__ == "__main__":
    check()
