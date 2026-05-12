from web3 import Web3

RPC_URL = "https://mainnet.crosstoken.io:22001"
OWNER = "0x447346Dcc57CC459A8B7121559dC029bF77bd533"
FACTORY = "0x378De49F47817D3dF10393851A587e5C2C58EF7C"
FACTORY_LEGACY = "0x0713665E4D19fD16e1F09AD77526CC343c6F0223"

ABI = [
    {
        "name": "getWallets",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "address[]"}],
    }
]

def check():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    print(f"Checking Factory: {FACTORY}")
    f1 = w3.eth.contract(address=Web3.to_checksum_address(FACTORY), abi=ABI)
    w1 = f1.functions.getWallets(Web3.to_checksum_address(OWNER)).call()
    print(f"  Wallets: {w1}")
    
    print(f"Checking Legacy Factory: {FACTORY_LEGACY}")
    f2 = w3.eth.contract(address=Web3.to_checksum_address(FACTORY_LEGACY), abi=ABI)
    w2 = f2.functions.getWallets(Web3.to_checksum_address(OWNER)).call()
    print(f"  Wallets: {w2}")

if __name__ == "__main__":
    check()
