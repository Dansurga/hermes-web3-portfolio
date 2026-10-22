# Web3 / Crypto Automation Portfolio

Hands-on automation projects built for EVM chains, Solana ecosystem tooling, Telegram bots, and X (Twitter) engagement automation. All projects are production-tested against live networks.

## 1. swap-tool — Multi-chain DEX Swap Tool (EVM)
- **Language:** Python 3, web3.py
- **Chains:** Polygon, BSC, Ethereum
- **DEX routers:** SushiSwap, QuickSwap, PancakeSwap
- **Features:**
  - Native → token swaps (`swapExactETHForTokens` / `swapExactMATICForTokens`)
  - Configurable recipient address
  - Fresh wallet generation (chmod 600 key handling)
  - TX broadcast + receipt verification, `--no-send` dry-run mode
- **Proof:** live-tested swap on BSC (Pancake V2): `0xca59ce2d...` on BscScan

## 2. solana-scanner — Wallet Connect + Message Signing (headless)
- **Language:** Python 3, Camoufox (anti-detect browser), eth-account
- **Features:**
  - EIP-1193 + EIP-6963 provider injection for headless wallet connect
  - `personal_sign`, `eth_signTypedData_v4` signing backed by local private key
  - Works on wallet-gated web3 sites without a browser extension
  - Chain-agnostic (chainId configurable), persistent browser profile support
- **Proof:** used to connect/sign on multiple wallet-gated web3 sites headlessly

## 3. x-automation — Batch X (Twitter) Engagement Executor
- **Language:** Python 3
- **Features:**
  - Batch follow / like / retweet via intent URLs
  - Multi-account rotation (15 accounts in production)
  - Per-account auth_token/ct0 cookie handling
  - JSON task queue + per-task result logging
- **Proof:** 54/54 tasks succeeded across 15 accounts (B3 campaigns)

## 4. telegram-bot — Telegram Bot Backend
- **Language:** Python 3, python-telegram-bot
- **Features:**
  - Command handlers, config-driven setup
  - SQLite-backed storage (accounts, sessions, history)
  - Health-check / export utilities
- **Proof:** deployed as a live Telegram bot (proxy account manager)

---

### Stack summary
Python 3 · web3.py · eth-account · Playwright/Camoufox · python-telegram-bot · SQLite · REST APIs (DEX, blockchain RPC, X GraphQL) · Linux VPS deployment (systemd)

### Contact
Available for freelance: web3 bots, Solana/EVm tooling, Telegram automation, wallet automation, on-chain monitoring.
