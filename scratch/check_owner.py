from eth_account import Account
import os
from dotenv import load_dotenv

load_dotenv()

pk = os.getenv("OWNER_PRIVATE_KEY")
addr = os.getenv("OWNER_EOA")

if pk:
    acct = Account.from_key(pk)
    print(f"Calculated Address: {acct.address}")
    print(f"Configured Address: {addr}")
    if acct.address.lower() == addr.lower():
        print("Match!")
    else:
        print("MISMATCH!")
else:
    print("No PK found")
