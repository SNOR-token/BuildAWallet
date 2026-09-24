import assert from 'node:assert/strict';
import {sealSecret,openSecret} from '../extension-wallet/vault.mjs';

const secret=crypto.getRandomValues(new Uint8Array(32));
const password='long independent vault password';
const first=await sealSecret(secret,password);
const second=await sealSecret(secret,password);
assert.notEqual(first.salt,second.salt);
assert.notEqual(first.iv,second.iv);
assert.notEqual(first.ciphertext,second.ciphertext);
assert.deepEqual(await openSecret(first,password),secret);
await assert.rejects(openSecret(first,'wrong password 1234'),/Unable to unlock/);
await assert.rejects(openSecret({...first,ciphertext:second.ciphertext},password),/Unable to unlock/);
await assert.rejects(sealSecret(secret,'short'),/at least 12/);
console.log('Vault round-trip, wrong password, tamper and randomization checks passed');
