import { Hono } from "hono";
import { paymentMiddleware, x402ResourceServer } from "@x402/hono";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { ExactSvmScheme } from "@x402/svm/exact/server";
import { validAddress, walletSnapshot } from "./rpc";
import { solanaWalletSnapshot, validSolanaAddress } from "./solana";

export interface Env {
  BASE_RPC_URL?: string;
  SOLANA_RPC_URL?: string;
  REQUEST_RATE_LIMITER?: { limit(options: { key: string }): Promise<{ success: boolean }> };
}

type Snapshot = Awaited<ReturnType<typeof walletSnapshot>> | Awaited<ReturnType<typeof solanaWalletSnapshot>>;
const app = new Hono<{ Bindings: Env; Variables: { snapshot: Snapshot } }>();
export const SOLANA_COLLECTOR = "Ew8mbrKwD6LGaSX28a6XGmXqeQSs2hykRibjXVhftTRC";
export const BASE_COLLECTOR = "0xBcCA6AED433d9020C50D44560F9679F1B5eB511d";
export const SOLANA_MAINNET = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp";
export const BASE_MAINNET = "eip155:8453";
const facilitator = new HTTPFacilitatorClient({ url: "https://facilitator.payai.network" });
const resourceServer = new x402ResourceServer(facilitator);
resourceServer.register(SOLANA_MAINNET, new ExactSvmScheme());
resourceServer.register(BASE_MAINNET, new ExactEvmScheme());

app.get("/machine/info", (c) => c.json({
  name: "BuildAWallet machine services",
  status: "read-only mainnet data; check configuredNetworks before use",
  configuredNetworks: {
    base: Boolean(c.env?.BASE_RPC_URL && c.env?.REQUEST_RATE_LIMITER),
    solana: Boolean(c.env?.SOLANA_RPC_URL && c.env?.REQUEST_RATE_LIMITER),
  },
  paidEndpoints: ["/machine/wallet?address=0x...", "/machine/solana-wallet?address=..."],
  price: "$0.01 USDC per request",
  paymentOptions: [
    { network: "base", collector: BASE_COLLECTOR },
    { network: "solana", collector: SOLANA_COLLECTOR },
  ],
  capabilities: ["read-only Base native balance and transaction count", "read-only Solana SOL balance"],
  custody: false,
}));

const routeConfig: Parameters<typeof paymentMiddleware>[0] = {
  "GET /machine/wallet": {
    accepts: [
      { scheme: "exact", price: "$0.01", network: BASE_MAINNET, payTo: BASE_COLLECTOR },
      { scheme: "exact", price: "$0.01", network: SOLANA_MAINNET, payTo: SOLANA_COLLECTOR },
    ],
    description: "Base mainnet native balance, transaction count and block number",
    mimeType: "application/json",
  },
  "GET /machine/solana-wallet": {
    accepts: [
      { scheme: "exact", price: "$0.01", network: BASE_MAINNET, payTo: BASE_COLLECTOR },
      { scheme: "exact", price: "$0.01", network: SOLANA_MAINNET, payTo: SOLANA_COLLECTOR },
    ],
    description: "Solana mainnet SOL balance and slot",
    mimeType: "application/json",
  },
};

// Validate and obtain data before the challenge. A failed lookup never incurs a payment.
app.use("/machine/wallet", async (c, next) => {
  const address = c.req.query("address");
  if (!validAddress(address)) return c.json({ error: "valid EVM address required" }, 400);
  if (!c.env?.BASE_RPC_URL || !c.env.REQUEST_RATE_LIMITER) {
    return c.json({ error: "payment service is not configured" }, 503);
  }
  const ip = c.req.header("CF-Connecting-IP") ?? "unknown";
  const { success } = await c.env.REQUEST_RATE_LIMITER.limit({ key: `machine-wallet:${ip}` });
  if (!success) return c.json({ error: "request rate limit exceeded" }, 429, { "Retry-After": "60" });
  try {
    // Fetch the whole result before asking for payment so an RPC error cannot charge a buyer.
    c.set("snapshot", await walletSnapshot(c.env.BASE_RPC_URL, address));
  } catch {
    return c.json({ error: "Base mainnet RPC unavailable or misconfigured" }, 503);
  }
  return paymentMiddleware(routeConfig, resourceServer)(c, next);
});

app.get("/machine/wallet", (c) => c.json(c.get("snapshot")));

app.use("/machine/solana-wallet", async (c, next) => {
  const address = c.req.query("address");
  if (!validSolanaAddress(address)) return c.json({ error: "valid Solana address required" }, 400);
  if (!c.env?.SOLANA_RPC_URL || !c.env.REQUEST_RATE_LIMITER) {
    return c.json({ error: "payment service is not configured" }, 503);
  }
  const ip = c.req.header("CF-Connecting-IP") ?? "unknown";
  const { success } = await c.env.REQUEST_RATE_LIMITER.limit({ key: `solana-wallet:${ip}` });
  if (!success) return c.json({ error: "request rate limit exceeded" }, 429, { "Retry-After": "60" });
  try {
    c.set("snapshot", await solanaWalletSnapshot(c.env.SOLANA_RPC_URL, address));
  } catch {
    return c.json({ error: "Solana mainnet RPC unavailable or misconfigured" }, 503);
  }
  return paymentMiddleware(routeConfig, resourceServer)(c, next);
});

app.get("/machine/solana-wallet", (c) => c.json(c.get("snapshot")));

export default app;
