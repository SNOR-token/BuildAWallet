import assert from 'node:assert/strict';

import { onRequestGet } from '../functions/studio.js';

const kp = await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const jwk = {...await crypto.subtle.exportKey('jwk',kp.publicKey),kid:'test-key'};
const b64 = value => Buffer.from(typeof value==='string'?value:JSON.stringify(value)).toString('base64url');
const issue = async exp => {
  const message = `${b64({alg:'RS256',kid:'test-key'})}.${b64({iss:'https://team.cloudflareaccess.com',aud:['app-audience'],sub:'user-123',exp})}`;
  const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5',kp.privateKey,new TextEncoder().encode(message));
  return `${message}.${Buffer.from(signature).toString('base64url')}`;
};
const originalFetch = globalThis.fetch;
globalThis.fetch = async () => Response.json({keys:[jwk]});
const env = {ACCESS_TEAM_DOMAIN:'team',ACCESS_AUD:'app-audience',ASSETS:{fetch:async()=>new Response('<h1>Studio</h1>',{headers:{'content-type':'text/html'}})}};
const request = token => new Request('https://buildawallet.xyz/studio',{headers:token?{'Cf-Access-Jwt-Assertion':token}:{}});
assert.equal((await onRequestGet({request:request(),env})).status,401);
assert.equal((await onRequestGet({request:request(await issue(Date.now()/1000-10)),env})).status,401);
const valid = await onRequestGet({request:request(await issue(Date.now()/1000+300)),env});
assert.equal(valid.status,200);
assert.equal(await valid.text(),'<h1>Studio</h1>');
globalThis.fetch = originalFetch;
console.log('Studio Access JWT checks passed');
