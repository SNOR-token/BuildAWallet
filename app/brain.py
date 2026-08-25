"""The wallet architect: a self-contained conversation engine.

No external model and no API keys. It reads free text, pulls out the options
somebody is asking for (or refusing), answers questions about them, and keeps
steering the build forward one decision at a time.
"""

from __future__ import annotations

import random
import re
from typing import Any

from catalog import (ACCENTS, ASSETS, BY_ID, CUSTODY, FEATURES, GROUPS,
                     NETWORKS, PLATFORMS, PRIVACY, SECURITY, STYLES, THEMES,
                     TOTAL_OPTIONS, label)

# --------------------------------------------------------------- matching ---

_INDEX: list[tuple[re.Pattern, str]] = []
for _oid, _o in BY_ID.items():
    for _k in _o["kw"] + [_o["label"].lower()]:
        _INDEX.append((re.compile(r"(?<![a-z0-9])" + re.escape(_k.lower()) + r"s?(?![a-z0-9])"), _oid))
_INDEX.sort(key=lambda p: -len(p[0].pattern))

NEG = re.compile(r"\b(no|not|non|never|without|skip|drop|remove|delete|exclude|don't|dont|do not|avoid|lose|hate|except)\b")
YES = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|please|sounds good|go on|do it|add them|add it|all of (them|those)|everything|both|absolutely|definitely|perfect|great|love it|why not)\b")
ALL = re.compile(r"\b(all of them|everything|all|the lot|every one|max|maximum|kitchen sink|go wild)\b")
AUTO = re.compile(r"\b(surprise me|you (pick|choose|decide)|your call|whatever you|recommend|suggestion|what should i|dealer'?s choice|up to you|standard|typical|usual|defaults?)\b")
SKIP = re.compile(r"\b(skip|next|move on|pass|nothing|none|later|no thanks|not now|doesn'?t matter)\b")
DONE = re.compile(r"\b(build it|that'?s it|i'?m done|finish|done|ship it|complete|finalize|finalise|make it|generate)\b")
QUESTION = re.compile(r"^(what|whats|what's|why|how|which|who|when|is |are |can |could |should |do |does |explain|tell me|difference)|\?\s*$")

CLAUSE = re.compile(r"\s*(,|;|\.|\band\b|\bplus\b|\balso\b|\bbut\b|\bthen\b|\bor\b)\s*")
NEG_REACH = 34  # characters a refusal carries forward inside one clause


def _clauses(text: str):
    """Split into (clause, joiner-before-it) pairs."""
    parts = CLAUSE.split(text)
    out = [(parts[0], "")]
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i + 1], parts[i].strip()))
    return [(c, j) for c, j in out if c.strip()]


def match_options(text: str) -> tuple[list[str], list[str]]:
    """Return (wanted, refused) option ids found in free text.

    A refusal only reaches the options that follow it inside the same clause,
    so "mpc so there is no seed phrase" adds MPC and drops the seed phrase
    rather than throwing both away. An "or" carries the refusal one clause
    further, which is how "without staking or swaps" is meant to read.
    """
    t = " " + text.lower() + " "
    wanted, refused = [], []
    carry = False
    for clause, joiner in _clauses(t):
        cues = [m.end() for m in NEG.finditer(clause)]
        clause_neg = bool(cues)
        inherited = carry and joiner == "or" and not clause_neg
        spans: list[tuple[int, int]] = []
        for pat, oid in _INDEX:
            for m in pat.finditer(clause):
                if any(s <= m.start() < e or s < m.end() <= e for s, e in spans):
                    continue
                spans.append((m.start(), m.end()))
                near = [c for c in cues if 0 <= m.start() - c <= NEG_REACH]
                (refused if (near or inherited) else wanted).append(oid)
                break
        carry = clause_neg or inherited
    return _dedupe(wanted), _dedupe(refused)


def _dedupe(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


# ------------------------------------------------------------- knowledge ----

KNOWLEDGE = {
    "gas": "Gas is the fee a network charges to process a transaction. It goes to validators, not to the wallet. A gas tank or paymaster lets you pay it in a stablecoin, or lets the wallet cover it for the user.",
    "seed phrase": "A seed phrase is twelve or twenty four words that regenerate every private key in the wallet. Anyone holding the words holds the money, which is why MPC and smart accounts exist as alternatives.",
    "private key": "The secret that authorises spending. Whatever custody model you pick, the whole product is really a story about where that secret lives and who can reach it.",
    "l2": "An L2 is a chain that settles onto Ethereum but charges cents instead of dollars. Base, Arbitrum and Optimism are the common three, and supporting one is nearly the same work as supporting all of them.",
    "layer 2": "An L2 is a chain that settles onto Ethereum but charges cents instead of dollars. Base, Arbitrum and Optimism are the common three.",
    "stablecoin": "A token pegged to a currency, usually the dollar. Most real world wallet use, payments and remittances especially, is stablecoin traffic rather than volatile assets.",
    "defi": "DeFi is on-chain finance: swapping, lending, staking, all run by contracts rather than a company. In a wallet it usually shows up as swap, earn and borrow screens.",
    "kyc": "KYC is identity verification. Self custody does not need it, but the moment you sell users crypto for card money, the on-ramp provider or you will require it.",
    "custody": "Custody is the question of who can move the funds. Self custody means only the user, custodial means you, and MPC or multisig sit between the two by splitting the power.",
    "web3": "Web3 is the loose name for apps that use a wallet as the login and the payment method at once. A dApp browser and WalletConnect are how a wallet talks to them.",
    "rug": "A rug pull is a token whose creators drain the liquidity. Transaction simulation, a scam filter and holder checks in a token radar are the three defences worth building.",
    "cold storage": "Cold storage means keys held offline, on a hardware device or on paper. Pair it with a watch only view so balances are visible without exposing anything.",
    "hot wallet": "A hot wallet is connected to the internet, convenient and more exposed. Most designs use a hot spending account alongside a cold or multisig vault.",
    "fees": "Two different fees exist: the network fee, which the chain charges, and your fee, usually a small spread on swaps or on-ramp volume. Be explicit about both.",
    "regulation": "Rules follow custody. Hold user keys or exchange money and you are a licensed business in most countries. Pure self custody software keeps you out of that, which is why most independent wallets start there.",
    "make money": "Wallets typically earn from swap spread, on-ramp revenue share, staking commission, card interchange or a pro subscription. Pick one before you pick features.",
    "monetize": "The honest options are swap spread, on-ramp share, staking commission, card interchange or a subscription. Everything else is a rounding error.",
    "business model": "Swap spread and on-ramp revenue share carry most independent wallets. Cards and subscriptions come later, once retention is proven.",
    "how long": "A focused first version, one chain, send, receive and swap, is a few months of work for a small team. Every extra chain and every regulated feature adds more than it looks like it should.",
    "how much": "Cost tracks the custody model and the regulated features. Self custody software is the cheap end. Cards, on-ramps and holding user keys bring partners, licences and audits with them.",
    "build it for me": "This site designs the wallet and hands you a spec. Take the blueprint to a developer, or use it as the brief for one, since every option here names the real thing it maps to.",
    "who are you": "I am the architect for this build: a planner that knows 150 wallet options, what they cost and which ones belong together. I turn what you say into the spec on the right.",
    "revenue": "Wallets typically earn from swap spread, on-ramp revenue share, staking commission, card interchange or a pro subscription. Pick one before you pick features.",
}

CONCEPT_KW = sorted(KNOWLEDGE, key=len, reverse=True)


def lookup_knowledge(text: str) -> str | None:
    t = text.lower()
    for k in CONCEPT_KW:
        if k in t:
            return KNOWLEDGE[k]
    return None


# ---------------------------------------------------------------- insights --

INSIGHTS = {
    "btc": "Bitcoin does not share code with the Ethereum side of the wallet, so treat it as its own module from day one.",
    "xmr": "Monero cannot be served by the usual public indexers, so it pulls a node requirement in with it.",
    "sol": "Solana uses a different address format and its own token standard, so the send screen needs two layouts.",
    "usdt": "Most USDT volume in the world moves on Tron. If this is for payments, support that pair specifically.",
    "meme": "Long tail tokens without a scam filter turn the wallet into a spam inbox, so I would pair the two.",
    "c_custodial": "Holding user keys makes you a regulated money business in most countries. Worth knowing before it ships.",
    "c_seed": "Seed phrases are the biggest drop off point in onboarding. An encrypted backup or social recovery softens that a lot.",
    "c_mpc": "No seed phrase removes the scariest onboarding screen. It does mean running signing infrastructure, so budget for uptime.",
    "c_aa": "Smart accounts unlock sponsored gas, batching and recovery rules, which is most of the modern wallet feature list in one decision.",
    "c_multisig": "Multisig needs a co-signer experience: invites, pending approvals, notifications. It is a product on its own.",
    "f_onramp": "Buying with a card drags KYC and per country provider rules along with it. Keep the rest of the wallet usable without it.",
    "f_card": "A debit card means a bank partner (a BIN sponsor) and real compliance work. Great retention, long lead time.",
    "f_swap": "Swaps are where most wallets make their money, through a small spread on the quote.",
    "f_dapp": "Apple has rules about in-app browsers reaching token sales, so the iOS build usually ships a curated app list instead.",
    "f_stake": "Staking needs unbonding times shown honestly, or support tickets arrive the first time somebody cannot withdraw.",
    "f_tax": "Tax export is dull and enormously sticky. People do not leave a wallet that holds their cost basis.",
    "f_ai": "An in-app copilot is the same idea as this conversation: it reads the transaction and explains it before signing.",
    "s_sim": "Transaction simulation stops more losses than every warning banner ever written.",
    "v_nokyc": "No KYC works for self custody. The on-ramp is the one place identity checks are unavoidable, so make it optional.",
    "p_tg": "A Telegram mini app has no install step at all, which is why referral growth there is unlike anything on the app stores.",
    "p_ext": "The extension is where desktop DeFi happens. If DeFi is the point, it is not optional.",
    "f_family": "Family accounts need an adult approval flow and limits, so they lean on the spending limit work rather than duplicating it.",
    "f_business": "Business users want roles and an audit trail more than they want charts.",
    "f_remit": "Remittance users judge the product on the last mile: local cash out. Pick the corridor before the chain.",
    "f_gas": "Sponsored gas needs a smart account to work, so those two travel together.",
}


# ----------------------------------------------------------------- presets --

PRESETS = {
    "beginner": {
        "kw": ["beginner", "first time", "my mum", "my mom", "grandma", "newbie", "non technical", "normal people", "easy"],
        "name": "Onboard",
        "purpose": "First time users who have never held crypto",
        "spec": {
            "assets": ["btc", "eth", "sol", "usdc"],
            "networks": ["n_base", "n_poly"],
            "custody": "c_mpc",
            "security": ["s_bio", "s_passkey", "s_social", "s_scam", "s_sim", "s_cloud"],
            "features": ["f_send", "f_onramp", "f_swap", "f_portfolio", "f_learn", "f_names", "f_support", "f_history", "f_i18n"],
            "platforms": ["p_ios", "p_android"],
            "privacy": ["v_noanalytics"],
            "style": "st_play", "theme": "t_light", "accent": "a_blue",
        },
    },
    "degen": {
        "kw": ["degen", "trader", "trading", "memecoin trader", "aped", "ape", "fast"],
        "name": "Nightshift",
        "purpose": "Active traders chasing new tokens",
        "spec": {
            "assets": ["eth", "sol", "meme", "erc20", "usdc", "bnb"],
            "networks": ["n_eth", "n_base", "n_arb", "n_zk"],
            "custody": "c_aa",
            "security": ["s_bio", "s_sim", "s_scam", "s_approve", "s_autolock"],
            "features": ["f_send", "f_swap", "f_bridge", "f_radar", "f_limit", "f_whale", "f_dapp", "f_wc", "f_portfolio", "f_alerts", "f_gas", "f_batch", "f_airdrop"],
            "platforms": ["p_ios", "p_ext", "p_web"],
            "privacy": ["v_noanalytics"],
            "style": "st_neon", "theme": "t_dark", "accent": "a_green",
        },
    },
    "privacy": {
        "kw": ["privacy", "private", "anonymous", "cypherpunk", "surveillance", "paranoid"],
        "name": "Quiet",
        "purpose": "People who want nobody watching their money",
        "spec": {
            "assets": ["btc", "xmr", "zec", "eth"],
            "networks": ["n_ln", "n_liquid"],
            "custody": "c_seed",
            "security": ["s_pin", "s_duress", "s_airgap", "s_hwsupport", "s_shamir", "s_autolock", "s_open"],
            "features": ["f_send", "f_history", "f_book", "f_watch", "f_inherit_tab"],
            "platforms": ["p_android", "p_desktop"],
            "privacy": ["v_nokyc", "v_tor", "v_node", "v_coin", "v_stealth", "v_noanalytics", "v_local"],
            "style": "st_minimal", "theme": "t_dark", "accent": "a_cyan",
        },
    },
    "business": {
        "kw": ["business", "company", "treasury", "startup", "team", "dao treasury", "corporate", "b2b"],
        "name": "Ledgerline",
        "purpose": "A company treasury with more than one signer",
        "spec": {
            "assets": ["btc", "eth", "usdc", "usdt", "rwa"],
            "networks": ["n_eth", "n_base", "n_arb"],
            "custody": "c_multisig",
            "security": ["s_2fa", "s_passkey", "s_allow", "s_limits", "s_delay", "s_approve", "s_audit", "s_hwsupport"],
            "features": ["f_send", "f_business", "f_payroll", "f_tax", "f_history", "f_book", "f_request", "f_portfolio", "f_earn", "f_multi", "f_watch"],
            "platforms": ["p_web", "p_desktop", "p_api"],
            "privacy": ["v_noanalytics"],
            "style": "st_minimal", "theme": "t_light", "accent": "a_blue",
        },
    },
    "bitcoiner": {
        "kw": ["bitcoin only", "bitcoin maxi", "just bitcoin", "only btc", "sats only"],
        "name": "Hardline",
        "purpose": "Bitcoin only, held for the long run",
        "spec": {
            "assets": ["btc"],
            "networks": ["n_ln"],
            "custody": "c_hw",
            "security": ["s_pin", "s_hwsupport", "s_shamir", "s_airgap", "s_inherit", "s_open", "s_duress"],
            "features": ["f_send", "f_qr", "f_history", "f_watch", "f_dca", "f_inherit_tab", "f_book"],
            "platforms": ["p_ios", "p_android", "p_desktop"],
            "privacy": ["v_nokyc", "v_node", "v_coin", "v_tor", "v_stealth"],
            "style": "st_brutal", "theme": "t_dark", "accent": "a_orange",
        },
    },
    "payments": {
        "kw": ["payment", "remittance", "send money home", "sending money home", "money home", "pay people", "everyday spending", "merchant", "shop owner"],
        "name": "Sendwell",
        "purpose": "Everyday payments and money sent across borders",
        "spec": {
            "assets": ["usdc", "usdt", "trx", "xlm", "btc", "eurc"],
            "networks": ["n_ln", "n_base", "n_poly"],
            "custody": "c_hybrid",
            "security": ["s_bio", "s_pin", "s_social", "s_limits", "s_scam"],
            "features": ["f_send", "f_qr", "f_request", "f_remit", "f_offramp", "f_onramp", "f_names", "f_book", "f_pay_bills", "f_split", "f_i18n", "f_support", "f_merchant"],
            "platforms": ["p_ios", "p_android", "p_tg"],
            "privacy": ["v_noanalytics"],
            "style": "st_play", "theme": "t_light", "accent": "a_green",
        },
    },
    "family": {
        "kw": ["family", "kids", "children", "teenager", "allowance", "my son", "my daughter"],
        "name": "Kinvault",
        "purpose": "A household: adults, teenagers and a shared pot",
        "spec": {
            "assets": ["btc", "eth", "usdc"],
            "networks": ["n_base"],
            "custody": "c_aa",
            "security": ["s_bio", "s_limits", "s_allow", "s_social", "s_scam", "s_inherit"],
            "features": ["f_send", "f_family", "f_goals", "f_dca", "f_learn", "f_portfolio", "f_onramp", "f_alerts", "f_book"],
            "platforms": ["p_ios", "p_android", "p_watch"],
            "privacy": ["v_noanalytics"],
            "style": "st_play", "theme": "t_light", "accent": "a_purple",
        },
    },
    "gaming": {
        "kw": ["gaming", "game", "gamer", "in-game", "play to earn", "metaverse"],
        "name": "Playkey",
        "purpose": "Players moving in-game assets between worlds",
        "spec": {
            "assets": ["sol", "eth", "nft_asset", "matic", "usdc"],
            "networks": ["n_poly", "n_base", "n_zk"],
            "custody": "c_aa",
            "security": ["s_bio", "s_sim", "s_scam", "s_autolock"],
            "features": ["f_send", "f_game", "f_session", "f_gas", "f_nft", "f_swap", "f_dapp", "f_wc", "f_airdrop", "f_widget"],
            "platforms": ["p_ios", "p_android", "p_ext", "p_tg"],
            "privacy": [],
            "style": "st_neon", "theme": "t_dark", "accent": "a_pink",
        },
    },
}

NAME_IDEAS = ["Northvault", "Keyring", "Tidepool", "Marlin", "Sable", "Basecamp", "Orchard",
              "Hearth", "Lumen", "Anchor", "Foxglove", "Quarry", "Beacon", "Salt", "Harbor"]


PRESET_CUE = re.compile(r"\b(it'?s for|its for|this is for|for |aimed at|built for|audience|users? are|meant for|i am a|i'?m a|we are a|we'?re a)\b")


def _preset_allowed(text: str, state: dict) -> bool:
    """A persona only reshapes the build while we are still asking who it is for."""
    if AUTO.search(text) or SKIP.search(text) or ALL.search(text):
        return False
    if "purpose" not in state.get("answered", []):
        return True
    return bool(PRESET_CUE.search(text))


def detect_preset(text: str) -> str | None:
    t = text.lower()
    for key, p in PRESETS.items():
        for k in p["kw"]:
            if k in t:
                return key
    return None


# ------------------------------------------------------------------ topics --

def _ids(items):
    return [i["id"] for i in items]


def _names(spec, field, limit=5):
    ids = spec.get(field) or []
    if isinstance(ids, str):
        ids = [ids] if ids else []
    names = [label(i) for i in ids]
    if not names:
        return ""
    if len(names) > limit:
        return _join(names[:limit]) + f" and {len(names) - limit} more"
    return _join(names)


TOPICS = [
    {
        "key": "name",
        "field": "name",
        "q": "What should this wallet be called? Anything at all, you can rename it later.",
        "q2": lambda s: f"It is called **{s['name']}** at the moment. Happy with that, or shall we rename it?",
        "chips": lambda s: [{"label": n, "send": f"Call it {n}"} for n in random.sample(NAME_IDEAS, 3)]
                            + [{"label": "You pick", "send": "You pick a name"}],
    },
    {
        "key": "purpose",
        "field": "purpose",
        "q": "Who is it for? One line is plenty, and it quietly decides most of what follows.",
        "q2": lambda s: f"I have it down as: {s['purpose']}. Anyone else it needs to serve?",
        "chips": lambda s: [
            {"label": "First timers", "send": "It is for beginners who have never held crypto"},
            {"label": "Active traders", "send": "It is for degen traders"},
            {"label": "Payments and remittances", "send": "It is for everyday payments and remittances"},
            {"label": "A company treasury", "send": "It is for a business treasury"},
            {"label": "Privacy first", "send": "It is for privacy focused people"},
            {"label": "Just me", "send": "It is for me, a long term holder"},
        ],
    },
    {
        "key": "assets",
        "field": "assets",
        "q": "Which coins and tokens should it support?",
        "q2": lambda s: f"It holds {_names(s, 'assets')} right now. Anything to add or drop?",
        "chips": lambda s: [
            {"label": "Bitcoin", "send": "Bitcoin"},
            {"label": "Ethereum", "send": "Ethereum"},
            {"label": "Solana", "send": "Solana"},
            {"label": "Stablecoins", "send": "USDC and USDT"},
            {"label": "Any ERC-20", "send": "Any ERC-20 token"},
            {"label": "Everything you have", "send": "Support everything"},
        ],
        "rec": ["btc", "eth", "sol", "usdc", "usdt", "erc20"],
    },
    {
        "key": "networks",
        "field": "networks",
        "q": "Which networks should it run on? Layer 2s are where the cheap transactions live.",
        "q2": lambda s: f"Networks so far: {_names(s, 'networks')}. Add any others?",
        "chips": lambda s: [
            {"label": "Ethereum + L2s", "send": "Ethereum mainnet, Base, Arbitrum and Optimism"},
            {"label": "Base only", "send": "Just Base"},
            {"label": "Lightning", "send": "Bitcoin Lightning"},
            {"label": "Let users add any", "send": "Custom RPC networks"},
            {"label": "You choose", "send": "You choose the networks"},
        ],
        "rec": ["n_eth", "n_base", "n_arb", "n_custom"],
    },
    {
        "key": "custody",
        "field": "custody",
        "q": "Now the big one: who holds the keys?",
        "q2": lambda s: f"Custody is set to {_names(s, 'custody')}. Keep it, or try another model?",
        "chips": lambda s: [
            {"label": "Seed phrase", "send": "Self custody with a seed phrase"},
            {"label": "No seed phrase (MPC)", "send": "MPC keyless"},
            {"label": "Smart account", "send": "Smart account with account abstraction"},
            {"label": "Hardware first", "send": "Hardware first"},
            {"label": "Multisig", "send": "Multisig vault"},
            {"label": "What is the difference?", "send": "What is the difference between these custody models?"},
        ],
        "rec": ["c_mpc"],
    },
    {
        "key": "security",
        "field": "security",
        "q": "What should protect it?",
        "q2": lambda s: f"Security layer: {_names(s, 'security')}. Want anything harder?",
        "chips": lambda s: [
            {"label": "Face ID", "send": "Biometric unlock"},
            {"label": "Social recovery", "send": "Social recovery"},
            {"label": "Simulate transactions", "send": "Transaction simulation"},
            {"label": "Scam filter", "send": "Scam and spam token filter"},
            {"label": "Spending limits", "send": "Spending limits"},
            {"label": "Lock it down hard", "send": "Give me the strongest security you have"},
        ],
        "rec": ["s_bio", "s_sim", "s_scam", "s_social", "s_approve", "s_autolock"],
    },
    {
        "key": "features",
        "field": "features",
        "q": "What should people be able to do inside it, beyond send and receive?",
        "q2": lambda s: f"Features so far: {_names(s, 'features', 6)}. What else?",
        "chips": lambda s: [
            {"label": "Swap", "send": "In-app swap"},
            {"label": "Buy with card", "send": "Buy with card or bank"},
            {"label": "Staking", "send": "Staking"},
            {"label": "NFTs", "send": "NFT gallery"},
            {"label": "dApp browser", "send": "dApp browser and WalletConnect"},
            {"label": "Portfolio charts", "send": "Portfolio and P&L"},
        ],
        "rec": ["f_send", "f_swap", "f_onramp", "f_portfolio", "f_history", "f_book"],
    },
    {
        "key": "features2",
        "field": "features",
        "q": "Anything unusual to set it apart? This is where wallets stop looking like each other.",
        "q2": lambda s: "Anything unusual to set it apart? This is where wallets stop looking like each other.",
        "chips": lambda s: [
            {"label": "Debit card", "send": "Crypto debit card"},
            {"label": "Recurring buys", "send": "Recurring buys"},
            {"label": "Tax export", "send": "Tax and CSV export"},
            {"label": "Sponsored gas", "send": "Sponsored gas so users never buy gas"},
            {"label": "AI copilot", "send": "Built-in AI copilot"},
            {"label": "Payment links", "send": "Payment requests and invoices"},
            {"label": "Nothing else", "send": "Nothing else for now"},
        ],
        "rec": ["f_gas", "f_dca", "f_alerts", "f_tax"],
    },
    {
        "key": "platforms",
        "field": "platforms",
        "q": "Where does it live?",
        "q2": lambda s: f"Shipping on {_names(s, 'platforms')}. Anywhere else?",
        "chips": lambda s: [
            {"label": "iPhone and Android", "send": "iOS and Android"},
            {"label": "Browser extension", "send": "Browser extension"},
            {"label": "Web app", "send": "Web app"},
            {"label": "Telegram mini app", "send": "Telegram mini app"},
            {"label": "Everywhere", "send": "All the platforms"},
        ],
        "rec": ["p_ios", "p_android", "p_web"],
    },
    {
        "key": "privacy",
        "field": "privacy",
        "q": "How private should it be?",
        "q2": lambda s: f"Privacy so far: {_names(s, 'privacy')}. Go further?",
        "chips": lambda s: [
            {"label": "No KYC", "send": "No KYC for self custody"},
            {"label": "No tracking", "send": "No analytics, no tracking"},
            {"label": "Route over Tor", "send": "Tor or proxy routing"},
            {"label": "Own node", "send": "Own node and private RPC"},
            {"label": "Normal is fine", "send": "Standard privacy is fine"},
        ],
        "rec": ["v_noanalytics", "v_nokyc"],
    },
    {
        "key": "style",
        "field": "style",
        "q": "Last one: how should it look?",
        "q2": lambda s: f"The look is {_names(s, 'style')}. Try a different one?",
        "chips": lambda s: [
            {"label": "Calm and minimal", "send": "Calm and minimal, light mode"},
            {"label": "Neon and cyber", "send": "Neon cyber, dark mode, green accent"},
            {"label": "Glass and gradient", "send": "Glass and gradient, purple"},
            {"label": "Bold and blocky", "send": "Bold and blocky, orange"},
            {"label": "Playful", "send": "Playful and friendly, blue"},
        ],
        "rec": ["st_minimal"],
    },
]

TOPIC_BY_KEY = {t["key"]: t for t in TOPICS}


def blank_spec() -> dict[str, Any]:
    return {"name": "", "purpose": "", "assets": [], "networks": [], "custody": "",
            "security": [], "features": [], "platforms": [], "privacy": [],
            "style": "", "theme": "t_dark", "accent": "a_green"}


def fresh_state() -> dict[str, Any]:
    return {"asked": [], "answered": [], "skipped": [], "said": [], "pending": [],
            "current": "", "turns": 0, "finished": False}


SINGLE = {"custody", "style", "theme", "accent"}
GROUP_OF = {}
for _g in GROUPS:
    for _it in _g["items"]:
        GROUP_OF[_it["id"]] = _g["key"]
for _it in THEMES:
    GROUP_OF[_it["id"]] = "theme"
for _it in ACCENTS:
    GROUP_OF[_it["id"]] = "accent"

GROUP_TOPIC = {"assets": "assets", "networks": "networks", "custody": "custody",
               "security": "security", "features": "features", "platforms": "platforms",
               "privacy": "privacy", "style": "style", "theme": "style", "accent": "style"}


def apply_option(spec: dict, oid: str, on: bool) -> bool:
    """Add or remove one option. True if the spec actually changed."""
    g = GROUP_OF.get(oid)
    if not g:
        return False
    if g in SINGLE:
        if on:
            if spec.get(g) == oid:
                return False
            spec[g] = oid
            return True
        if spec.get(g) == oid:
            spec[g] = ""
            return True
        return False
    lst = spec.setdefault(g, [])
    if on and oid not in lst:
        lst.append(oid)
        return True
    if not on and oid in lst:
        lst.remove(oid)
        return True
    return False


def _close(state: dict, key: str) -> None:
    if key and key not in state["answered"]:
        state["answered"].append(key)


def _mark_answered(state: dict, oid: str) -> None:
    topic = GROUP_TOPIC.get(GROUP_OF.get(oid, ""), "")
    if not topic:
        return
    if topic == "features" and "features" in state["answered"]:
        topic = "features2"
    if topic not in state["answered"]:
        state["answered"].append(topic)


def next_topic(spec: dict, state: dict) -> dict | None:
    closed = set(state.get("skipped", [])) | set(state.get("answered", []))
    for t in TOPICS:
        if t["key"] in closed:
            continue
        if t["key"] == "features2" and len(spec.get("features", [])) < 3:
            continue
        return t
    return None


def filled_count(spec: dict) -> int:
    n = 0
    for k, v in spec.items():
        if isinstance(v, list):
            n += len(v)
        elif v and k not in ("name", "purpose"):
            n += 1
    return n


def progress(spec: dict, state: dict) -> int:
    closed = set(state.get("skipped", [])) | set(state.get("answered", []))
    return min(100, round(len(closed) * 100 / len(TOPICS)))


# ------------------------------------------------------------------- names --

NAME_RE = re.compile(r"\b(?:call it|name it|named|call the wallet|it'?s called|the name is|name:|rename it to|rename to)\s+(.{2,32})", re.I)
GREET = re.compile(r"^(hi|hey|hello|yo|hiya|howdy|sup|good (morning|afternoon|evening)|hey there|start|begin|let'?s go|ok)\b[\s!.,]*$", re.I)
RESET = re.compile(r"\b(start over|reset|clear everything|wipe it|from scratch|start again)\b", re.I)
NOT_A_NAME = {"yes", "no", "maybe", "idk", "dunno", "thanks", "thank you", "cool", "nice", "help",
              "wallet", "crypto", "a wallet", "test", "asdf", "none", "whatever"}


def extract_name(text: str) -> str | None:
    m = NAME_RE.search(text)
    if m:
        return _clean_name(m.group(1))
    t = text.strip().strip('."\'!,?')
    if GREET.match(t) or t.lower() in NOT_A_NAME:
        return None
    if 1 <= len(t.split()) <= 4 and len(t) <= 32 and not QUESTION.match(t.lower()):
        return _clean_name(t)
    return None


def _clean_name(s: str) -> str:
    s = s.strip().strip('."\'!,?')
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^(it|the wallet|wallet)\s+", "", s, flags=re.I)
    return s[:32].strip()


# ------------------------------------------------------------------ engine --

OPENER = ("I am the wallet architect. Describe the wallet you want and I will build it here on the right, "
          "piece by piece, out of {n} options. Nothing is fixed: change your mind as often as you like.\n\n"
          "What should this wallet be called?")


def opening() -> dict:
    spec, state = blank_spec(), fresh_state()
    state["asked"].append("name")
    state["current"] = "name"
    chips = TOPIC_BY_KEY["name"]["chips"](spec) + [
        {"label": "Skip ahead, I know what I want", "send": "Call it Northvault. It is for people who want everything in one place."}]
    return _out([OPENER.format(n=TOTAL_OPTIONS)], chips, spec, state)


def respond(message: str, spec: dict, state: dict) -> dict:
    msg = (message or "").strip()
    low = msg.lower()
    for k, v in fresh_state().items():
        state.setdefault(k, v)
    state["turns"] += 1

    if RESET.search(low):
        out = opening()
        out["reply"] = "Cleared. Blank slate.\n\n" + out["reply"].split("\n\n", 1)[1]
        return out

    lines: list[str] = []
    changed_on: list[str] = []
    changed_off: list[str] = []
    already: list[str] = []
    current = TOPIC_BY_KEY.get(state.get("current") or "") or next_topic(spec, state)
    finishing = bool(DONE.search(low)) and filled_count(spec) >= 5

    # greeting with nothing else in it
    if GREET.match(msg) and not msg.lower().startswith("ok "):
        if current:
            state["current"] = current["key"]
            return _out(["Hello. Let us build something.", _question(current, spec)],
                        _chips_for(current, spec, []), spec, state)

    # a whole persona in one line
    preset = detect_preset(low) if _preset_allowed(low, state) else None
    if preset and not NEG.search(low):
        p = PRESETS[preset]
        added = 0
        for key, val in p["spec"].items():
            if key in SINGLE and spec.get(key):
                continue          # never overwrite a decision already made
            if key not in SINGLE and spec.get(key):
                continue          # never rewrite a list the user has filled
            for oid in (val if isinstance(val, list) else [val]):
                if apply_option(spec, oid, True):
                    added += 1
        if not added:
            preset = None
        if not spec.get("purpose"):
            spec["purpose"] = p["purpose"]
            if "purpose" not in state["answered"]:
                state["answered"].append("purpose")
        if not spec.get("name"):
            spec["name"] = p["name"]
            if "name" not in state["answered"]:
                state["answered"].append("name")
        lines.append(f"That tells me a lot. I have laid down a starting point for {p['purpose'][0].lower() + p['purpose'][1:]}: "
                     f"{added} choices, already showing in the preview. We will walk through them and you can change anything.")

    # explicit options
    wanted, refused = match_options(low)
    if state.get("pending") and YES.search(low) and not ALL.search(low) and not wanted and not refused:
        wanted = list(state["pending"])
        state["pending"] = []
    for oid in refused:
        if apply_option(spec, oid, False):
            changed_off.append(oid)
            _mark_answered(state, oid)
    for oid in wanted:
        if oid in refused:
            continue
        if apply_option(spec, oid, True):
            changed_on.append(oid)
            _mark_answered(state, oid)
        elif not preset:
            already.append(oid)

    # topic shortcuts
    handled = False
    if not wanted and not preset:
        if current and ALL.search(low) and current.get("rec"):
            batch = [o for o in (_all_for(current["key"]) or current["rec"]) if o not in refused]
            for oid in batch:
                if apply_option(spec, oid, True):
                    changed_on.append(oid)
            _close(state, current["key"])
            handled = True
            lines.append("Everything it is. That is a lot of surface area to build, but it is your wallet."
                         if len(batch) > 6 else "Taking the strongest option there.")
        elif current and AUTO.search(low) and current.get("rec"):
            for oid in [o for o in current["rec"] if o not in refused]:
                if apply_option(spec, oid, True):
                    changed_on.append(oid)
            _close(state, current["key"])
            handled = True
            lines.append("Picked the set I would ship first.")
        elif current and SKIP.search(low) and not finishing:
            if current["key"] not in state["skipped"]:
                state["skipped"].append(current["key"])
            handled = True
            lines.append("Skipped. We can come back to it.")
        elif not current and (AUTO.search(low) or ALL.search(low) or "what else" in low or "more feature" in low):
            extra = _next_best(spec)
            if extra:
                state["pending"] = extra
                lines.append("Things this wallet does not have yet that would suit it: " +
                             _join([label(o) for o in extra]) + ". Want them?")
                return _out(lines, [{"label": "Yes, add those", "send": "yes"},
                                    {"label": "Show me the full vault", "send": "open the vault"},
                                    {"label": "No, it is finished", "send": "that's it"}], spec, state, done=True)

    # name and purpose
    if current and current["key"] == "name" and not handled and not preset:
        if AUTO.search(low) or "you pick" in low:
            spec["name"] = random.choice(NAME_IDEAS)
            _close(state, "name")
            lines.append(f"I will call it **{spec['name']}**. Rename it whenever.")
        elif not spec.get("name") or NAME_RE.search(msg):
            nm = extract_name(msg)
            if nm:
                spec["name"] = nm
                if "name" not in state["answered"]:
                    state["answered"].append("name")
                lines.append(f"**{nm}**. Good name for it.")
    elif NAME_RE.search(msg):
        nm = extract_name(msg)
        if nm:
            spec["name"] = nm
            lines.append(f"Renamed to **{nm}**.")

    if current and current["key"] == "purpose" and not handled and not preset and not QUESTION.match(low):
        if len(msg.split()) >= 2:
            spec["purpose"] = _clean_purpose(msg)
            if "purpose" not in state["answered"]:
                state["answered"].append("purpose")
            if not preset:
                lines.append(f"Noted, built for {spec['purpose']}. That decides more than people expect, "
                             f"so I will keep pulling it into what I suggest.")

    # questions
    asked_question = bool(QUESTION.match(low))
    question_offer: list[str] = []
    if asked_question:
        answer, question_offer = _answer_question(low, wanted + already, spec, current)
        if answer:
            lines.append(answer)

    # acknowledge
    if changed_on and not preset:
        lines.append(_ack([label(o) for o in changed_on]))
    if changed_off:
        lines.append("Taken out: " + _join([label(o) for o in changed_off]) + ".")
    if already and not changed_on and not asked_question:
        lines.append(_join([label(o) for o in already]) + " already in there.")

    # one relevant piece of advice
    for oid in changed_on:
        if oid in INSIGHTS and oid not in state["said"]:
            lines.append(INSIGHTS[oid])
            state["said"].append(oid)
            break

    # a suggested pairing
    pending: list[str] = list(question_offer)
    if not pending and not asked_question and not finishing:
        sug = _suggest(spec, state)
        if sug:
            pending = sug["ids"]
            lines.append(sug["text"])
            state["said"].extend(sug["ids"])
    state["pending"] = pending

    if not lines and YES.search(low):
        lines.append(random.choice(["Good.", "Right.", "Understood.", "Fine by me."]))
        handled = True
    if not lines and not finishing:
        lines.append(_confused(msg, current))

    if current and not asked_question and (changed_on or changed_off or already or preset or handled):
        _close(state, current["key"])

    # finish, either by request or by running out of questions
    if finishing:
        for t in TOPICS:
            if t["key"] not in state["answered"] and t["key"] not in state["skipped"]:
                state["skipped"].append(t["key"])
    nxt = None if finishing else next_topic(spec, state)
    if nxt:
        state["current"] = nxt["key"]
        if nxt["key"] not in state["asked"]:
            state["asked"].append(nxt["key"])
        lines.append(_question(nxt, spec))
        return _out(lines, _chips_for(nxt, spec, pending), spec, state)

    state["current"] = ""
    if not state["finished"]:
        state["finished"] = True
        lines.append(_finish_line(spec))
    else:
        lines.append(f"Updated: {filled_count(spec)} choices in the build now.")
    return _out(lines, [{"label": "Open the blueprint", "send": "show me the blueprint"},
                        {"label": "What else could it have?", "send": "what else could I add?"},
                        {"label": "Change the look", "send": "change the look"}],
                spec, state, done=True)


def _question(topic: dict, spec: dict) -> str:
    val = spec.get(topic["field"])
    if val and topic.get("q2"):
        return topic["q2"](spec)
    return topic["q"]


def _chips_for(topic: dict, spec: dict, pending: list[str]) -> list[dict]:
    chips = topic["chips"](spec) if callable(topic.get("chips")) else []
    if pending:
        chips = [{"label": "Yes, add those", "send": "yes"}] + chips
    if filled_count(spec) >= 12:
        chips = chips + [{"label": "That is enough, build it", "send": "build it"}]
    return chips


def _out(lines, chips, spec, state, done=False):
    return {"reply": "\n\n".join(l for l in lines if l), "chips": chips, "spec": spec,
            "state": state, "done": done, "progress": progress(spec, state),
            "count": filled_count(spec), "total": TOTAL_OPTIONS}


def _all_for(topic_key: str) -> list[str]:
    m = {"assets": _ids(ASSETS), "networks": _ids(NETWORKS), "security": _ids(SECURITY),
         "features": _ids(FEATURES), "features2": _ids(FEATURES), "platforms": _ids(PLATFORMS),
         "privacy": _ids(PRIVACY)}
    return m.get(topic_key, [])


BEST_EXTRAS = ["f_swap", "f_onramp", "f_portfolio", "s_sim", "f_gas", "f_names", "f_dca",
               "f_tax", "f_alerts", "s_social", "f_earn", "f_card", "f_request", "f_ai",
               "f_learn", "f_watch", "f_multi", "s_approve", "f_widget", "f_support"]


def _next_best(spec: dict, n: int = 4) -> list[str]:
    return [o for o in BEST_EXTRAS if not _has(spec, o)][:n]


def _clean_purpose(s: str) -> str:
    s = re.sub(r"^(it'?s |its |it is |for |this is |mainly )", "", s.strip(), flags=re.I)
    return s[:140].strip(" .")


def _join(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + " and " + names[-1]


def _ack(names: list[str]) -> str:
    if len(names) > 6:
        return f"Added {_join(names[:5])} and {len(names) - 5} more."
    opener = random.choice(["Added", "In it goes:", "Locked in:", "Noted:", "Done:", "On the build:"])
    if opener == "Added":
        return f"Added {_join(names)}."
    return f"{opener} {_join(names)}."


def _answer_question(low: str, mentioned: list[str], spec: dict, current: dict | None):
    if re.search(r"\b(recommend|should i|what would you|best|advice|suggest|what do you think|what else|anything else|missing)\b", low):
        if current and current.get("rec"):
            missing = [o for o in current["rec"] if not _has(spec, o)]
            if missing:
                return ("For what you have described I would take " + _join([label(o) for o in missing]) +
                        ". Say yes and they go in, or name your own.", missing)
        extra = _next_best(spec)
        if extra:
            return ("I would add " + _join([label(o) for o in extra]) +
                    " next. Ship the smallest wallet somebody would actually use, then add the one thing "
                    "they keep asking for.", extra)
    for oid in mentioned:
        b = BY_ID.get(oid, {}).get("blurb")
        if b:
            return f"**{label(oid)}**: {b}", []
    k = lookup_knowledge(low)
    if k:
        return k, []
    if current and current["key"] == "custody":
        return ("Short version. Seed phrase: total control, total responsibility. MPC: no phrase to lose, "
                "but you run signing infrastructure. Smart account: the account is a contract, so sponsored gas "
                "and recovery rules become possible. Hardware: keys never touch the phone. Multisig: several "
                "people must agree. Custodial: you hold the keys, and you become a regulated business.", [])
    return (FALLBACK_ANSWER, [])


FALLBACK_ANSWER = (
    "I can answer for the build itself: what any option means, what it costs you in complexity, "
    "and what I would pick. Ask me about custody, gas, stablecoins, KYC, scams or how wallets make money, "
    "or just tell me what to change.")


def _has(spec: dict, oid: str) -> bool:
    g = GROUP_OF.get(oid)
    if g in SINGLE:
        return spec.get(g) == oid
    return oid in spec.get(g, [])


PAIRS = [
    (["f_onramp"], ["f_offramp"], "You have a way in but no way out. Add selling back to a bank account?"),
    (["meme", "erc20"], ["s_scam", "s_sim"], "Long tail tokens invite scam airdrops. Want the scam filter and transaction simulation alongside them?"),
    (["c_seed"], ["s_social", "s_cloud"], "A seed phrase on its own loses people. Want social recovery and an encrypted backup as a net?"),
    (["c_aa"], ["f_gas", "f_batch"], "Smart accounts make sponsored gas and one tap batching almost free to add. Want them?"),
    (["f_dapp"], ["f_wc", "s_approve"], "A dApp browser usually ships with WalletConnect and an approval manager. Add both?"),
    (["f_stake", "f_earn"], ["f_portfolio"], "Once there is yield, people want to watch it accrue. Add portfolio and P&L?"),
    (["f_card"], ["f_goals"], "Cards pair well with round ups, which turn spending into saving. Add that?"),
    (["btc"], ["n_ln"], "Bitcoin on chain is slow and pricey for small payments. Add Lightning?"),
    (["f_business", "f_payroll"], ["c_multisig", "s_allow"], "Company money usually wants multisig and an address allowlist. Add those?"),
    (["f_remit"], ["f_i18n", "f_offramp"], "Remittances live or die on the last mile. Add local language, local currency and bank cash out?"),
    (["p_ext"], ["s_sim"], "Extensions are the favourite target of drainer sites. Add transaction simulation?"),
    (["xmr", "v_tor"], ["v_node"], "Private assets leak through public indexers. Add your own node and private RPC?"),
    (["f_nft"], ["nft_asset"], "Want NFTs treated as a real asset class in the portfolio too?"),
    (["f_family"], ["s_limits"], "Family accounts need spending limits to mean anything. Add them?"),
    (["f_swap"], ["f_bridge"], "Swapping across two chains is really bridging. Add a bridge behind the same screen?"),
    (["f_game"], ["f_session", "f_gas"], "Games need session keys and sponsored gas, or players sign every few seconds. Add them?"),
    (["p_ios", "p_android"], ["f_alerts", "f_widget"], "Phones give you push notifications and widgets nearly for free. Add price and payment alerts?"),
    (["f_tax"], ["f_history"], "Tax export needs a rich history behind it. Add that?"),
]


def _suggest(spec: dict, state: dict) -> dict | None:
    said = set(state.get("said", []))
    for triggers, adds, text in PAIRS:
        if not any(_has(spec, t) for t in triggers):
            continue
        missing = [a for a in adds if not _has(spec, a) and a not in said]
        if missing:
            return {"ids": missing, "text": text}
    return None


def _confused(msg: str, current: dict | None) -> str:
    return ("I did not catch a specific option in that, so nothing moved. You can name coins, security, "
            "platforms, anything at all, or open the vault and tap through all "
            f"{TOTAL_OPTIONS} options by hand.")


def _finish_line(spec: dict) -> str:
    name = spec.get("name") or "Your wallet"
    return (f"**{name}** is built: {filled_count(spec)} choices, {len(spec.get('assets', []))} assets and "
            f"{len(spec.get('features', []))} features. The blueprint tab has the whole spec, and Save turns it "
            f"into a link you can send to a developer. Nothing is final, keep changing it whenever you like.")
