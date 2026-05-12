from eth_account import Account

PK = "0x692a6ba35b88dc2f3dd17aa7eb27f24c2c28d40a2c8459aa4ef66d6bc43ae4a1"
EXPECTED_ADDR = "0x98e9823EB4eA10bfDb846a15Ab72A362DC5d5666"

def verify():
    # Remove 0x prefix for Account.from_key if present
    pk_clean = PK[2:] if PK.startswith("0x") else PK
    acct = Account.from_key(pk_clean)
    print(f"Recovered Address: {acct.address}")
    if acct.address.lower() == EXPECTED_ADDR.lower():
        print("✅ MATCH! This is the correct Private Key.")
    else:
        print(f"❌ MISMATCH! Expected {EXPECTED_ADDR}, but got {acct.address}")

if __name__ == "__main__":
    verify()
