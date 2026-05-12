import requests
import json

AGENT = "0x520019A584830F2a7A559066a9be12Fa3d3dB41e"
RPC_URL = "https://rpc.crossonline.io"

def check():
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [AGENT, "latest"],
        "id": 1
    }
    try:
        # Use a timeout and handle potential issues
        response = requests.post(RPC_URL, json=payload, timeout=10)
        result = response.json()
        balance_hex = result.get('result', '0x0')
        balance_wei = int(balance_hex, 16)
        print(f"Agent Balance: {balance_wei / 10**18} CROSS")
    except Exception as e:
        print(f"Error checking balance: {e}")

if __name__ == "__main__":
    check()
