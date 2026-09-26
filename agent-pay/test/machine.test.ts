import { afterEach, describe, expect, it, vi } from "vitest";
import app, { BASE_COLLECTOR, BASE_MAINNET, SOLANA_COLLECTOR, SOLANA_MAINNET } from "../src/index";
import { walletSnapshot } from "../src/rpc";
import { solanaWalletSnapshot } from "../src/solana";

const address = "0x000000000000000000000000000000000000dEaD";
const solanaAddress = "Ew8mbrKwD6LGaSX28a6XGmXqeQSs2hykRibjXVhftTRC";
const env = {
  BASE_RPC_URL: "https://rpc.example.test/secret",
  SOLANA_RPC_URL: "https://solana.example.test/secret",
  REQUEST_RATE_LIMITER: { limit: vi.fn(async () => ({ success: true })) },
};

afterEach(() => vi.unstubAllGlobals());

describe("machine payment boundary", () => {
  it("reports deployment configuration without exposing RPC secrets", async () => {
    const info = await app.request("/machine/info", {}, env);
    expect(info.status).toBe(200);
    const body = await info.json() as { configuredNetworks: { base: boolean; solana: boolean } };
    expect(body.configuredNetworks).toEqual({ base: true, solana: true });
    expect(JSON.stringify(body)).not.toContain(env.BASE_RPC_URL);
    const empty = await (await app.request("/machine/info", {}, {})).json() as typeof body;
    expect(empty.configuredNetworks).toEqual({ base: false, solana: false });
  });
  it("rejects invalid addresses before charging", async () => {
    const res = await app.request("/machine/wallet?address=invalid", {}, env);
    expect(res.status).toBe(400);
    expect((await app.request("/machine/solana-wallet?address=invalid", {}, env)).status).toBe(400);
  });

  it("fails closed without an RPC", async () => {
    const res = await app.request(`/machine/wallet?address=${address}`, {}, {});
    expect(res.status).toBe(503);
  });

  it("rejects excess requests before hitting the RPC or facilitator", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const limitedEnv = { ...env, REQUEST_RATE_LIMITER: { limit: async () => ({ success: false }) } };
    const res = await app.request(`/machine/wallet?address=${address}`, {}, limitedEnv);
    expect(res.status).toBe(429);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("challenges a valid unpaid request without reading chain data", async () => {
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => new Response(JSON.stringify(
      url.endsWith("/supported") ? {
        kinds: [
          { x402Version: 2, scheme: "exact", network: BASE_MAINNET },
          { x402Version: 2, scheme: "exact", network: SOLANA_MAINNET },
        ],
      } : { jsonrpc: "2.0", id: 1, result: url === env.BASE_RPC_URL ? "0x2105" : "0x0" },
    ), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await app.request(`/machine/wallet?address=${address}`, {}, env);
    expect(res.status).toBe(402);
    const required = res.headers.get("payment-required");
    expect(required).toBeTruthy();
    const challenge = JSON.parse(atob(required!));
    expect(challenge.accepts).toEqual(expect.arrayContaining([
      expect.objectContaining({ network: BASE_MAINNET, payTo: BASE_COLLECTOR }),
      expect.objectContaining({ network: SOLANA_MAINNET, payTo: SOLANA_COLLECTOR }),
    ]));
    expect(fetchMock.mock.calls.some(([url]) => url === env.BASE_RPC_URL)).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/supported"))).toBe(true);
    expect(fetchMock.mock.calls.some(([, init]) => String(init?.body ?? "").includes("eth_getBalance"))).toBe(true);
    expect(await res.text()).not.toContain("balanceWei");
  });

  it("does not issue a payable challenge when the RPC fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("unavailable", { status: 503 })));
    const res = await app.request(`/machine/wallet?address=${address}`, {}, env);
    expect(res.status).toBe(503);
    expect(res.headers.get("payment-required")).toBeNull();
    expect(await res.text()).not.toContain(env.BASE_RPC_URL);
  });

  it("checks the RPC network before reporting chain data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      jsonrpc: "2.0", id: 1, result: "0x1",
    }), { status: 200 })));
    await expect(walletSnapshot(env.BASE_RPC_URL, address)).rejects.toThrow("RPC network mismatch");
  });

  it("formats an exact wei balance and returns a block reference", async () => {
    const values: Record<string, string> = {
      eth_chainId: "0x2105",
      eth_getBalance: "0x1bc16d674ec80000", // 2 ETH
      eth_getTransactionCount: "0x3",
      eth_blockNumber: "0x42",
    };
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init: RequestInit) => {
      const { method } = JSON.parse(init.body as string);
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: values[method] }), { status: 200 });
    }));
    const snapshot = await walletSnapshot(env.BASE_RPC_URL, address);
    expect(snapshot).toMatchObject({ chainId: 8453, balanceWei: "2000000000000000000", balanceEth: "2", transactionCount: 3, blockNumber: 66 });
  });

  it("challenges for a valid Solana snapshot on either payment chain", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => new Response(JSON.stringify(
      url.endsWith("/supported") ? {
        kinds: [
          { x402Version: 2, scheme: "exact", network: BASE_MAINNET },
          { x402Version: 2, scheme: "exact", network: SOLANA_MAINNET },
        ],
      } : String(init?.body).includes("getGenesisHash") ?
        { jsonrpc: "2.0", id: 1, result: "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d" } :
        { jsonrpc: "2.0", id: 1, result: { value: 1230000000, context: { slot: 42 } } },
    ), { status: 200 })));
    const res = await app.request(`/machine/solana-wallet?address=${solanaAddress}`, {}, env);
    expect(res.status).toBe(402);
    const challenge = JSON.parse(atob(res.headers.get("payment-required")!));
    expect(challenge.accepts).toEqual(expect.arrayContaining([
      expect.objectContaining({ network: BASE_MAINNET, payTo: BASE_COLLECTOR }),
      expect.objectContaining({ network: SOLANA_MAINNET, payTo: SOLANA_COLLECTOR }),
    ]));
  });

  it("refuses an invalid Solana RPC response before payment", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "upstream" }), { status: 200 })));
    await expect(solanaWalletSnapshot(env.SOLANA_RPC_URL, solanaAddress)).rejects.toThrow();
    const res = await app.request(`/machine/solana-wallet?address=${solanaAddress}`, {}, env);
    expect(res.status).toBe(503);
    expect(res.headers.get("payment-required")).toBeNull();
  });

  it("refuses a Solana RPC on another network", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ result: "devnet-genesis" }), { status: 200 })));
    const res = await app.request(`/machine/solana-wallet?address=${solanaAddress}`, {}, env);
    expect(res.status).toBe(503);
    expect(res.headers.get("payment-required")).toBeNull();
  });
});
