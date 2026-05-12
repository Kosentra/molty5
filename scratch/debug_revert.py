from web3 import Web3

RPC_URL = "https://rpc.crossonline.io"
TX_HASH = "47f81ac2b7342d006812b6005817c433354cf5bd328b794e2fa0201c01ac7a31"

def check():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    try:
        tx = w3.eth.get_transaction(TX_HASH)
        # Try to simulate the call at the same block
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
            
        receipt = w3.eth.get_transaction_receipt(TX_HASH)
        print(f"Status: {receipt.status}")
        print(f"Gas Used: {receipt.gasUsed}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
