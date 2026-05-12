from web3 import Web3
import json

RPC_URL = "https://rpc.crossonline.io"
AGENT = "0x520019A584830F2a7A559066a9be12Fa3d3dB41e"

def check():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    bal = w3.eth.get_balance(AGENT)
    print(f"Agent Balance: {Web3.from_wei(bal, 'ether')} CROSS")
    
    # Check transaction failure reason
    tx_hash = "31efc8a4b744bebe6e8d4c8d3d37dc5c3a986039508dcb72705a24fef50a8cc4"
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status == 0:
            # Try to get revert reason
            tx = w3.eth.get_transaction(tx_hash)
            try:
                w3.eth.call({
                    'to': tx['to'],
                    'from': tx['from'],
                    'value': tx['value'],
                    'data': tx['input'],
                    'gas': tx['gas'],
                    'gasPrice': tx['gasPrice']
                }, tx['blockNumber'] - 1)
            except Exception as e:
                print(f"Revert Reason: {e}")
    except:
        print("Could not fetch receipt or reason.")

if __name__ == "__main__":
    check()
