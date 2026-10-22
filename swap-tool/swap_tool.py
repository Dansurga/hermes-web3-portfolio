#!/usr/bin/env python3
"""Swap native (MATIC/ETH/BNB) -> token via DEX router, recipient configurable.
Usage:
  python swap_tool.py new-wallet [--file wallet.json]
  python swap_tool.py swap --chain polygon --router sushi --token USDC --amount 1.25 --to 0xRECIPIENT [--from-keyfile wallet.json] [--min-out 0] [--no-send]
"""
import argparse, json, os, sys, time, secrets

from web3 import Web3

# ---------- chain configs ----------
CHAINS = {
    "polygon": {
        "name": "Polygon", "id": 137, "native": "MATIC",
        "wrapped": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC
        "rpc": "https://polygon.drpc.org",
        "explorer": "https://polygonscan.com/tx/",
        "tokens": {
            "USDC": {"addr": "0x2791Bca1F2De4661ED88a30c99A7A9449AA84174", "dec": 6},
            "USDT": {"addr": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "dec": 6},
        },
    },
    "bsc": {
        "name": "BSC", "id": 56, "native": "BNB",
        "wrapped": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
        "rpc": "https://bsc-dataseed.binance.org",
        "explorer": "https://bscscan.com/tx/",
        "tokens": {
            "USDC": {"addr": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "dec": 18},
            "USDT": {"addr": "0x55d398326f99059fF775485246999027B3197955", "dec": 18},
            "BUSD": {"addr": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", "dec": 18},
        },
    },
    "ethereum": {
        "name": "Ethereum", "id": 1, "native": "ETH",
        "wrapped": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "rpc": "https://ethereum-rpc.publicnode.com",
        "explorer": "https://etherscan.io/tx/",
        "tokens": {
            "USDC": {"addr": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "dec": 6},
            "USDT": {"addr": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "dec": 6},
        },
    },
}

# DEX routers (address -> label). 'eth_slot' = which swap fn name to use.
ROUTERS = {
    "sushi": {
        "polygon": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "ethereum": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        "bsc": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "fn": "swapExactETHForTokens",
    },
    "quickswap": {
        "polygon": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        "fn": "swapExactETHForTokens",  # UniV2 fork: native swap = swapExactETHForTokens
    },
    "pancake": {
        "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        "ethereum": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",  # Pancake V3 swap router (not used for v2 path)
        "fn": "swapExactETHForTokens",
    },
}

SWAP_ABI = [
    {"inputs": [{"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}],
     "name": "swapExactETHForTokens", "outputs": [{"name": "amounts", "type": "uint256[]"}],
     "stateMutability": "payable", "type": "function"},
    {"inputs": [{"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"},
                {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}],
     "name": "swapExactMATICForTokens", "outputs": [{"name": "amounts", "type": "uint256[]"}],
     "stateMutability": "payable", "type": "function"},
]

def load_wallet(path):
    with open(path) as f:
        return json.load(f)

def new_wallet(path):
    acct = Web3().eth.account.create()
    data = {"address": acct.address, "private_key": acct.key.hex()}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)
    return data

def connect(chain):
    return Web3(Web3.HTTPProvider(CHAINS[chain]["rpc"], request_kwargs={"timeout": 30}))

def do_swap(args):
    chain_cfg = CHAINS[args.chain]
    router_cfg = ROUTERS[args.router]
    if args.chain not in router_cfg:
        sys.exit(f"[!] router '{args.router}' nggak ada di chain {args.chain}")
    router_addr = router_cfg[args.chain]
    fn_name = router_cfg["fn"]

    wallet = load_wallet(args.keyfile)
    w3 = connect(args.chain)
    assert w3.is_connected(), "RPC gagal"
    acct = w3.eth.account.from_key(wallet["private_key"])
    sender = acct.address

    token = chain_cfg["tokens"].get(args.token.upper())
    if not token:
        sys.exit(f"[!] token {args.token} nggak dikenal di {args.chain}: {list(chain_cfg['tokens'])}")
    to = w3.to_checksum_address(args.to)
    wrapped = w3.to_checksum_address(chain_cfg["wrapped"])
    router = w3.to_checksum_address(router_addr)

    amount_in = w3.to_wei(args.amount, "ether")  # native has 18 dec
    min_out = int(args.min_out * 10 ** token["dec"])

    w3.eth.default_account = sender
    router_c = w3.eth.contract(address=router, abi=SWAP_ABI)
    deadline = int(time.time()) + 600

    print(f"[{chain_cfg['name']}] swapExact{'MATIC' if fn_name=='swapExactMATICForTokens' else 'ETH'}ForTokens")
    print(f"  from  : {sender}  (native bal: {float(w3.from_wei(w3.eth.get_balance(sender), 'ether')):.6f})")
    print(f"  amount: {args.amount} {chain_cfg['native']} -> {args.token}")
    print(f"  router: {router_addr} ({args.router})")
    print(f"  path  : {chain_cfg['wrapped']} -> {token['addr']}")
    print(f"  to    : {to}")
    print(f"  minOut: {args.min_out} {args.token}")

    tx = router_c.functions[fn_name](
        min_out,
        [wrapped, w3.to_checksum_address(token["addr"])],
        to,
        deadline,
    ).build_transaction({
        "from": sender,
        "value": amount_in,
        "nonce": w3.eth.get_transaction_count(sender),
        "gas": 250000,
        "gasPrice": w3.eth.gas_price,
        "chainId": chain_cfg["id"],
    })

    if args.no_send:
        print("\n[--no-send] TX: ")
        return tx

    signed = w3.eth.account.sign_transaction(tx, wallet["private_key"])
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"\n  TX: {h.hex()}")
    print(f"  {chain_cfg['explorer']}{h.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=120)
    print(f"  status: {'OK' if rcpt.status == 1 else 'FAILED'}")
    return h.hex()

def main():
    ap = argparse.ArgumentParser(description="Native->Token swap via DEX router (recipient configurable)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    nw = sub.add_parser("new-wallet", help="generate fresh wallet")
    nw.add_argument("--file", default="/root/swap_tool/wallet.json")

    sw = sub.add_parser("swap")
    sw.add_argument("--chain", choices=list(CHAINS), default="polygon")
    sw.add_argument("--router", choices=list(ROUTERS), default="sushi")
    sw.add_argument("--token", default="USDC")
    sw.add_argument("--amount", type=float, required=True)
    sw.add_argument("--to", required=True, help="recipient address (bisa custom, bisa bukan dari wallet ini)")
    sw.add_argument("--min-out", type=float, default=0)
    sw.add_argument("--keyfile", default="/root/swap_tool/wallet.json")
    sw.add_argument("--no-send", action="store_true")

    args = ap.parse_args()
    if args.cmd == "new-wallet":
        w = new_wallet(args.file)
        print(f"NEW WALLET: {w['address']}")
        print(f"PRIVATE KEY: {w['private_key']}")
        print(f"(saved to {args.file}, chmod 600)")
    else:
        do_swap(args)

if __name__ == "__main__":
    main()