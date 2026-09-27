export const BASE_CHAIN_ID = "0x2105";
const ADDRESS = /^0x[0-9a-fA-F]{40}$/;
const HEX_QUANTITY = /^0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)$/;

export function validAddress(address: string | undefined): address is string {
  return typeof address === "string" && ADDRESS.test(address);
}

async function rpc(url: string, method: string, params: unknown[]): Promise<string> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error("RPC unavailable");
  const data: unknown = await response.json();
  if (!data || typeof data !== "object" || !("result" in data) ||
      typeof data.result !== "string" || !HEX_QUANTITY.test(data.result)) {
    throw new Error("RPC returned invalid data");
  }
  return data.result;
}

export async function checkBaseRpc(url: string): Promise<void> {
  // Check the configured RPC before reporting a balance under a named chain.
  const chainId = await rpc(url, "eth_chainId", []);
  if (BigInt(chainId) !== BigInt(BASE_CHAIN_ID)) throw new Error("RPC network mismatch");
}

export async function walletSnapshot(url: string, address: string) {
  await checkBaseRpc(url);
  const [balanceHex, nonceHex, blockHex] = await Promise.all([
    rpc(url, "eth_getBalance", [address, "latest"]),
    rpc(url, "eth_getTransactionCount", [address, "latest"]),
    rpc(url, "eth_blockNumber", []),
  ]);
  const wei = BigInt(balanceHex);
  const whole = wei / 10n ** 18n;
  const fraction = (wei % 10n ** 18n).toString().padStart(18, "0").replace(/0+$/, "");
  return {
    chain: "base",
    chainId: 8453,
    address,
    balanceWei: wei.toString(),
    balanceEth: fraction ? `${whole}.${fraction}` : whole.toString(),
    transactionCount: Number(BigInt(nonceHex)),
    blockNumber: Number(BigInt(blockHex)),
    source: "configured Base mainnet JSON-RPC",
  };
}
