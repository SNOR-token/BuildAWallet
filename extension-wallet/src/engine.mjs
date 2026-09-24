import { HDNodeWallet, Mnemonic, Transaction, getAddress, getBytes, parseEther, parseUnits } from 'ethers';
import { openSecret, sealSecret } from '../vault.mjs';

export const CHAIN_ID = 11155111n; // Ethereum Sepolia only.

function derive(entropy) {
  return HDNodeWallet.fromMnemonic(Mnemonic.fromEntropy(entropy));
}

export async function createAccount(password) {
  const entropy = crypto.getRandomValues(new Uint8Array(32));
  const wallet = derive(entropy);
  const record = await sealSecret(entropy, password);
  entropy.fill(0);
  return { address: wallet.address, phrase: wallet.mnemonic.phrase, vault: record };
}

export async function importAccount(phrase, password) {
  if (typeof phrase !== 'string' || !Mnemonic.isValidMnemonic(phrase.trim())) throw Error('Invalid recovery phrase');
  const mnemonic = Mnemonic.fromPhrase(phrase.trim());
  const entropy = getBytes(mnemonic.entropy);
  const wallet = derive(entropy);
  const record = await sealSecret(entropy, password);
  entropy.fill(0);
  return { address: wallet.address, vault: record };
}

export async function unlockAccount(record, expectedAddress, password) {
  const entropy = await openSecret(record, password);
  const wallet = derive(entropy);
  entropy.fill(0);
  if (wallet.address !== getAddress(expectedAddress)) throw Error('Vault address mismatch');
  return wallet;
}

export function reviewTransfer(input) {
  const to = getAddress(input.to);
  const value = parseEther(input.amount);
  const gasLimit = BigInt(input.gasLimit);
  const nonce = Number(input.nonce);
  const maxFeePerGas = parseUnits(input.maxFeeGwei, 'gwei');
  const maxPriorityFeePerGas = parseUnits(input.priorityFeeGwei, 'gwei');
  if (value <= 0n || gasLimit < 21_000n || gasLimit > 500_000n ||
      !Number.isSafeInteger(nonce) || nonce < 0 || maxFeePerGas <= 0n ||
      maxPriorityFeePerGas < 0n || maxPriorityFeePerGas > maxFeePerGas) throw Error('Invalid transaction fields');
  const maximumFeeWei = gasLimit * maxFeePerGas;
  return {
    transaction: { type:2, chainId:CHAIN_ID, to, value, nonce, gasLimit, maxFeePerGas, maxPriorityFeePerGas },
    maximumFeeWei,
    totalMaximumWei: value + maximumFeeWei,
  };
}

export async function signReviewedTransfer(wallet, reviewed) {
  if (!wallet || !reviewed || reviewed.transaction.chainId !== CHAIN_ID ||
      reviewed.transaction.type !== 2) throw Error('Sepolia review required');
  const signed = await wallet.signTransaction(reviewed.transaction);
  const decoded = Transaction.from(signed);
  const tx = reviewed.transaction;
  if (decoded.chainId !== CHAIN_ID || decoded.from !== wallet.address ||
      decoded.type !== tx.type || decoded.to !== tx.to || decoded.value !== tx.value ||
      decoded.nonce !== tx.nonce || decoded.gasLimit !== tx.gasLimit ||
      decoded.maxFeePerGas !== tx.maxFeePerGas ||
      decoded.maxPriorityFeePerGas !== tx.maxPriorityFeePerGas || decoded.data !== '0x')
    throw Error('Signed transaction mismatch');
  return signed;
}
