from bot.config import CREDENTIALS_FILE, AGENT_WALLET_FILE, OWNER_WALLET_FILE
import os

print(f"CREDENTIALS_FILE: {CREDENTIALS_FILE.absolute()}")
print(f"AGENT_WALLET_FILE: {AGENT_WALLET_FILE.absolute()}")
print(f"OWNER_WALLET_FILE: {OWNER_WALLET_FILE.absolute()}")

print(f"Exists? {CREDENTIALS_FILE.exists()}")

if CREDENTIALS_FILE.exists():
    with open(CREDENTIALS_FILE, 'r') as f:
        print("Content of CREDENTIALS_FILE:")
        print(f.read())
