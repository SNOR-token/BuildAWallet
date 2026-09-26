import { Hono } from "hono";
import { paymentMiddleware, x402ResourceServer } from "@x402/hono";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { ExactEvmScheme } from "@x402/evm/exact/server";
import { ExactSvmScheme } from "@x402/svm/exact/server";
import { validAddress, walletSnapshot } from "./rpc";

export interface Env {
  BASE_RPC_URL?: string;
  REQUEST_RATE_LIMITER?: { limit(options: { key: string }): Promise<{ success: boolean }> };
}

const app = new Hono<{ Bindings: Env; Variables: { snapshot: Awaited<ReturnType<typeof walletSnapshot>> } }>();
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
  status: "mainnet endpoint",
  network: "base",
  paidEndpoint: "/machine/wallet?address=0x...",
  price: "$0.01 USDC per request",
  paymentOptions: [
    { network: "base", collector: BASE_COLLECTOR },
    { network: "solana", collector: SOLANA_COLLECTOR },
  ],
  capabilities: ["read-only native balance and transaction count"],
  custody: false,
}));

// Validate before the challenge. A bad address never incurs a payment.
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
  return paymentMiddleware({
    "GET /machine/wallet": {
      accepts: [
        { scheme: "exact", price: "$0.01", network: BASE_MAINNET, payTo: BASE_COLLECTOR },
        { scheme: "exact", price: "$0.01", network: SOLANA_MAINNET, payTo: SOLANA_COLLECTOR },
      ],
      description: "Base mainnet native balance, transaction count and block number",
      mimeType: "application/json",
    },
  }, resourceServer)(c, next);
});

app.get("/machine/wallet", (c) => c.json(c.get("snapshot")));

export default app;
