import { isAddress } from "@solana/addresses";

const MAINNET_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d";

export function validSolanaAddress(value: string | undefined): value is string {
  return typeof value === "string" && isAddress(value);
}

export async function solanaWalletSnapshot(rpcUrl: string, walletAddress: string) {
  const genesisResponse = await fetch(rpcUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getGenesisHash" }),
    signal: AbortSignal.timeout(8000),
  });
  if (!genesisResponse.ok) throw new Error("Solana RPC unavailable");
  const genesis: unknown = await genesisResponse.json();
  if ((genesis as { result?: unknown } | null)?.result !== MAINNET_GENESIS) {
    throw new Error("Solana RPC network mismatch");
  }
  const response = await fetch(rpcUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getBalance", params: [walletAddress, { commitment: "confirmed" }] }),
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error("Solana RPC unavailable");
  const payload: unknown = await response.json();
  const result = (payload as { result?: { value?: unknown; context?: { slot?: unknown } } } | null)?.result;
  if (typeof result?.value !== "number" || !Number.isSafeInteger(result.value) || result.value < 0 ||
      typeof result.context?.slot !== "number" || !Number.isSafeInteger(result.context.slot)) {
    throw new Error("Invalid Solana RPC response");
  }
  const lamports = result.value;
  const slot = result.context.slot;
  return {
    chain: "solana",
    address: walletAddress,
    balanceLamports: String(lamports),
    balanceSol: `${Math.floor(lamports / 1e9)}.${String(lamports % 1e9).padStart(9, "0")}`.replace(/\.0+$/, ""),
    slot,
    source: "configured Solana mainnet JSON-RPC",
  };
}
