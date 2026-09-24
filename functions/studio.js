// The Studio requires a verified Cloudflare Access application JWT.
const unauthorized = () => new Response('Email confirmation is required. Return to /auth.', {status:401,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}});
const decode = text => JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(text.replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0))));

export async function onRequestGet({request,env}) {
  if (!env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) {
    return new Response('Studio email verification is not configured yet.', {status:503});
  }
  const token = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!token) return unauthorized();
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return unauthorized();
    const header = decode(parts[0]);
    const claims = decode(parts[1]);
    const issuer = `https://${env.ACCESS_TEAM_DOMAIN}.cloudflareaccess.com`;
    if (header.alg !== 'RS256' || !header.kid || claims.iss !== issuer ||
        !Array.isArray(claims.aud) || !claims.aud.includes(env.ACCESS_AUD) ||
        !claims.exp || claims.exp <= Date.now()/1000 ||
        (claims.nbf && claims.nbf > Date.now()/1000) || !claims.sub) return unauthorized();
    const certs = await fetch(`${issuer}/cdn-cgi/access/certs`);
    if (!certs.ok) throw Error('Access keys unavailable');
    const {keys} = await certs.json();
    const jwk = keys.find(key => key.kid === header.kid && key.kty === 'RSA');
    if (!jwk) return unauthorized();
    const key = await crypto.subtle.importKey('jwk', jwk, {name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'}, false, ['verify']);
    const signature = Uint8Array.from(atob(parts[2].replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0));
    const valid = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, signature, new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
    if (!valid) return unauthorized();
    const url = new URL(request.url);
    url.pathname = '/studio.html';
    const response = await env.ASSETS.fetch(new Request(url, request));
    const headers = new Headers(response.headers);
    headers.set('cache-control','private, no-store');
    return new Response(response.body,{status:response.status,headers});
  } catch (_) {
    return unauthorized();
  }
}
