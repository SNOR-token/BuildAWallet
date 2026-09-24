// Encrypted local key storage primitive. No network, chain or signing functionality.
const encoder = new TextEncoder();
const ITERATIONS = 600_000;
const PREFIX = 'buildawallet.local-vault.v1';

function bytesToBase64(bytes) {
  let raw = '';
  for (const byte of bytes) raw += String.fromCharCode(byte);
  return btoa(raw);
}
function base64ToBytes(value, length) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) throw Error('Invalid vault encoding');
  const bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0));
  if (bytes.length !== length) throw Error('Invalid vault size');
  return bytes;
}
async function derive(password, salt) {
  if (typeof password !== 'string' || password.length < 12) throw Error('Use a password of at least 12 characters');
  const material = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt,iterations:ITERATIONS}, material,
    {name:'AES-GCM',length:256}, false, ['encrypt','decrypt']);
}
export async function sealSecret(secret, password) {
  if (!(secret instanceof Uint8Array) || secret.length !== 32) throw Error('Expected a 32-byte secret');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await derive(password, salt);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    {name:'AES-GCM',iv,additionalData:encoder.encode(PREFIX)}, key, secret));
  return {schema:PREFIX,kdf:'PBKDF2-SHA256',iterations:ITERATIONS,cipher:'AES-256-GCM',
    salt:bytesToBase64(salt),iv:bytesToBase64(iv),ciphertext:bytesToBase64(ciphertext)};
}
export async function openSecret(record, password) {
  if (!record || record.schema !== PREFIX || record.kdf !== 'PBKDF2-SHA256' ||
      record.iterations !== ITERATIONS || record.cipher !== 'AES-256-GCM') throw Error('Unsupported vault');
  const salt = base64ToBytes(record.salt,16), iv = base64ToBytes(record.iv,12);
  const ciphertext = base64ToBytes(record.ciphertext,48);
  const key = await derive(password,salt);
  try {
    const clear = new Uint8Array(await crypto.subtle.decrypt(
      {name:'AES-GCM',iv,additionalData:encoder.encode(PREFIX)}, key, ciphertext));
    if (clear.length !== 32) throw Error('Invalid vault contents');
    return clear;
  } catch { throw Error('Unable to unlock vault'); }
}
