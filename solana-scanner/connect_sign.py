#!/usr/bin/env python3
"""Wallet connect + signature helper: injects an EIP-1193 (+EIP-6963) provider backed by our
own private key, so sites that ask to "connect wallet" / "sign a message" work headless.

usage: connect_sign.py <profile> <site_url> <connect_regex> [sign_regex] [proxy]
"""
import json
import sys

from camoufox.sync_api import Camoufox

from eth_account import Account
from eth_account.messages import encode_defunct

W = json.load(open("config/wallet.json"))
ADDR, PK = W["address"], W["private_key"]
CHAIN = int(sys.argv[6]) if len(sys.argv) > 6 else 4663

def _arg(i, default=None):
    return sys.argv[i] if len(sys.argv) > i else default


PROFILE = f"/root/garapan/profiles/{_arg(1, 'default')}"
SITE = _arg(2, "")
CONNECT = _arg(3, "")
SIGN = _arg(4, r"^sign|sign one message|sign message|verify wallet|confirm")
PROXY = _arg(5, "socks5://127.0.0.1:1080")

SHIM = """
(() => {
  const ADDR = '%s';
  const CHAIN_HEX = '0x%x';
  const provider = {
    isMetaMask: true, isConnected: () => true,
    chainId: CHAIN_HEX, networkVersion: String(%d), selectedAddress: ADDR,
    async request(args) {
      const m = (args && args.method) || '';
      const p = (args && args.params) || [];
      switch (m) {
        case 'eth_requestAccounts': case 'eth_accounts': case 'wallet_requestPermissions':
          window.dispatchEvent(new CustomEvent('accountsChanged', {detail: [ADDR]}));
          return m === 'wallet_requestPermissions' ? [{parentCapability: 'eth_accounts'}] : [ADDR];
        case 'eth_chainId': return CHAIN_HEX;
        case 'net_version': return String(%d);
        case 'personal_sign': {
          const msg = (typeof p[0] === 'string' && p[0].slice(0,2) === '0x') ? p[0] : String(p[0] || '');
          const addr = p[1] || ADDR;
          return await window.__hermes_sign(msg, addr);
        }
        case 'eth_sign': return await window.__hermes_sign(p[1] || '', ADDR);
        case 'eth_signTypedData_v4': case 'eth_signTypedData':
          return await window.__hermes_typed(JSON.stringify(p[1]), ADDR);
        case 'eth_getBalance': return '0x0';
        case 'eth_blockNumber': return '0x1';
        case 'wallet_switchEthereumChain': case 'wallet_addEthereumChain':
          window.dispatchEvent(new CustomEvent('chainChanged', {detail: CHAIN_HEX})); return null;
        default: return null;
      }
    },
    on() {}, removeListener() {}, addListener() {},
    enable: async () => [ADDR],
    send(m, cb) { const c = typeof m === 'string' ? {method: m, params: arguments[1]} : m;
      provider.request(c).then(r => (cb ? cb(null, {jsonrpc: '2.0', id: c.id || 1, result: r}) : null)); },
    sendAsync(m, cb) { provider.request(m).then(r => cb(null, {jsonrpc: '2.0', id: m.id || 1, result: r})); },
  };
  Object.defineProperty(window, 'ethereum', {value: provider, configurable: true, writable: true});
  window.ethereum.providers = [provider, provider];
  const info = {uuid: 'a1b2c3d4-0000-4000-8000-000000000001', name: 'MetaMask', rdns: 'io.metamask',
                icon: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4='};
  const announce = () => window.dispatchEvent(new CustomEvent('eip6963:announceProvider', {detail: Object.freeze({info, provider})}));
  window.addEventListener('eip6963:requestProvider', announce);
  setTimeout(announce, 0);
  window.dispatchEvent(new Event('ethereum#initialized'));
})();
""" % (W["address"], CHAIN, CHAIN, CHAIN)


def sign_msg(msg, addr):
    if isinstance(msg, str) and msg.startswith("0x"):
        try:
            data = bytes.fromhex(msg[2:])
        except Exception:
            data = msg.encode()
    else:
        data = str(msg).encode()
    s = Account.sign_message(encode_defunct(data), private_key=PK)
    return "0x" + s.signature.hex()


def sign_typed(payload, addr):
    from eth_account.messages import encode_typed_data
    obj = json.loads(payload) if isinstance(payload, str) else payload
    try:
        s = Account.sign_message(encode_typed_data(full_message=obj), private_key=PK)
    except Exception:
        obj2 = dict(obj)
        td = dict(obj2.get("types", {}))
        obj2["types"] = {k: [dict(f, type=f.get("type", "").replace("uint", "uint256") if f.get("type") == "uint" else f.get("type")) for f in v] for k, v in td.items()}
        s = Account.sign_message(encode_typed_data(full_message=obj2), private_key=PK)
    return "0x" + s.signature.hex()


def main():
    res = {"address": ADDR}
    with Camoufox(persistent_context=True, user_data_dir=PROFILE, headless="virtual", geoip=False,
                  proxy={"server": PROXY}, humanize=True, os=["linux"]) as ctx:
        ctx.add_init_script(SHIM)
        pg = ctx.new_page()
        pg.add_init_script(SHIM)   # page-level: context-level init scripts are unreliable here
        pg.expose_function("__hermes_sign", sign_msg)
        pg.expose_function("__hermes_typed", sign_typed)
        pg.goto(SITE, timeout=70000, wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        res["eth_at_load"] = pg.evaluate("() => typeof window.ethereum + ':' + !!(window.ethereum && window.ethereum.isMetaMask)")
        # re-announce late: Hydration may attach EIP-6963 listeners after our first announce
        pg.evaluate("""() => {const p = window.ethereum;
            const info = {uuid:'a1b2c3d4-0000-4000-8000-000000000001', name:'MetaMask', rdns:'io.metamask',
                          icon:'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4='};
            const ev = () => window.dispatchEvent(new CustomEvent('eip6963:announceProvider', {detail: Object.freeze({info, provider: p})}));
            [0, 800, 2000, 4000, 7000].forEach(t => setTimeout(ev, t));
            window.dispatchEvent(new Event('eip6963:requestProvider'));}""")
        pg.wait_for_timeout(4000)
        res["provider_ok"] = pg.evaluate("() => typeof (globalThis.ethereum && globalThis.ethereum.request)")
        # force a client-side remount: the wallet section only re-checks for a provider on mount
        pg.evaluate("""() => {history.pushState({}, '', '/'); history.pushState({}, '', '/whitelist');
            window.dispatchEvent(new PopStateEvent('popstate'));}""")
        pg.wait_for_timeout(9000)
        res["buttons_after_remount"] = pg.evaluate("() => [...document.querySelectorAll('button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,12)")
        # belt & braces: some builds do not run context init scripts on a persistent context
        pg.evaluate(SHIM)
        pg.wait_for_timeout(3000)
        res["eth_present"] = pg.evaluate("() => typeof window.ethereum + ':' + !!(window.ethereum && window.ethereum.isMetaMask)")
        # the site only looks for a wallet at load time -> reload so it renders the connect UI
        pg.reload(timeout=70000, wait_until="domcontentloaded")
        pg.wait_for_timeout(7000)
        click = """(rx) => {const re=new RegExp(rx,'i');
            const b=[...document.querySelectorAll('button,a')].find(x=>re.test((x.innerText||'').trim()));
            if(!b) return 'nobtn'; if(b.disabled) return 'disabled'; b.click(); return (b.innerText||'').trim().slice(0,40);}"""
        res["connect"] = pg.evaluate(click, CONNECT)
        pg.wait_for_timeout(6000)
        res["after_connect"] = (pg.evaluate("() => document.body.innerText") or "")[:600]
        # some wallets show an account-picker modal
        for lbl in ["MetaMask", "0x%s" % ADDR[2:6], "^connect$", "^continue$", "^confirm$", "^sign$"]:
            c = pg.evaluate(click, lbl)
            if c not in ("nobtn", "disabled"):
                res.setdefault("picks", []).append(f"{lbl} -> {c}")
                pg.wait_for_timeout(5000)
        res["sign_click"] = pg.evaluate(click, SIGN)
        pg.wait_for_timeout(9000)
        res["final_text"] = (pg.evaluate("() => document.body.innerText") or "")[:900]
        res["url"] = pg.url
    print(json.dumps(res, indent=1)[:2500])


if __name__ == "__main__":
    main()