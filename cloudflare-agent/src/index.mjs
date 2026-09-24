// D1-backed, watch-only agent control preview. No keys, approvals or execution.
const json = (body,status=200) => new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}});
const fail = (status,message) => json({error:message},status);
const hex = bytes => [...bytes].map(x=>x.toString(16).padStart(2,'0')).join('');
const id = prefix => prefix+crypto.randomUUID();
const hash = async value => hex(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))));

async function requireRole(request,db,role) {
  const bearer=/^Bearer (baw_[A-Za-z0-9_-]+)$/.exec(request.headers.get('authorization')||'');
  if(!bearer)return null;
  const credential=await db.prepare('SELECT id,role FROM credentials WHERE token_hash=? AND revoked=0').bind(await hash(bearer[1])).first();
  return credential?.role===role?credential:null;
}
async function bodyObject(request) {
  if(Number(request.headers.get('content-length')||0)>8192)throw Error('Request too large');
  const text=await request.text();
  if(text.length>8192)throw Error('Request too large');
  const body=JSON.parse(text);
  if(!body||typeof body!=='object'||Array.isArray(body))throw Error('Invalid JSON body');
  return body;
}

export default {
  async fetch(request,env) {
    const url=new URL(request.url),path=url.pathname,db=env.DB;
    if(!db)return fail(503,'Storage unavailable');
    try {
      if(request.method==='GET'&&path==='/healthz') {
        await db.prepare('SELECT 1 FROM credentials LIMIT 1').run();
        return json({ok:true,mode:'watch-only-preview',execution:'disabled'});
      }
      if(request.method==='GET'&&path==='/v1/capabilities')return json({network:'sepolia',mode:'watch-only-preview',custody:false,transaction_signing:false,broadcast:false});
      if(request.method==='POST'&&path==='/v1/credentials/bootstrap') {
        const body=await bodyObject(request),role=body.role;
        if(role!=='agent'&&role!=='operator')return fail(400,'Invalid role');
        const expected=role==='operator'?env.OPERATOR_BOOTSTRAP_SECRET:env.AGENT_BOOTSTRAP_SECRET;
        const supplied=request.headers.get('x-bootstrap-secret')||'';
        if(!expected||expected.length<32||!supplied||await hash(supplied)!==await hash(expected))return fail(403,'Bootstrap denied');
        const name=String(body.name||'').trim();
        if(!name||name.length>80)return fail(400,'Invalid name');
        const token='baw_'+hex(crypto.getRandomValues(new Uint8Array(32)));
        const credentialId=id('cred_');
        await db.prepare('INSERT INTO credentials(id,token_hash,role,name) VALUES(?,?,?,?)').bind(credentialId,await hash(token),role,name).run();
        return json({credential_id:credentialId,role,token,warning:'Copy this token now. It will not be shown again.'},201);
      }
      if(request.method==='POST'&&path==='/v1/wallets') {
        const agent=await requireRole(request,db,'agent');
        if(!agent)return fail(401,'Agent credential required');
        const body=await bodyObject(request);
        if(body.chain!=='sepolia'||typeof body.address!=='string'||!/^0x[0-9a-fA-F]{40}$/.test(body.address))return fail(400,'Sepolia address required');
        const walletId=id('watch_');
        await db.prepare('INSERT INTO watch_wallets(id,credential_id,chain,address) VALUES(?,?,?,?)').bind(walletId,agent.id,'sepolia',body.address).run();
        return json({wallet_id:walletId,chain:'sepolia',address:body.address,mode:'watch-only',status:'active'},201);
      }
      const walletMatch=/^\/v1\/wallets\/(watch_[0-9a-f-]+)$/.exec(path);
      if(request.method==='GET'&&walletMatch) {
        const agent=await requireRole(request,db,'agent');
        if(!agent)return fail(401,'Agent credential required');
        const wallet=await db.prepare('SELECT id,chain,address,status FROM watch_wallets WHERE id=? AND credential_id=?').bind(walletMatch[1],agent.id).first();
        if(!wallet)return fail(404,'Wallet descriptor not found');
        return json({wallet_id:wallet.id,chain:wallet.chain,address:wallet.address,status:wallet.status,mode:'watch-only'});
      }
      const freezeMatch=/^\/v1\/wallets\/(watch_[0-9a-f-]+)\/freeze$/.exec(path);
      if(request.method==='POST'&&freezeMatch) {
        const operator=await requireRole(request,db,'operator');
        if(!operator)return fail(401,'Operator credential required');
        const wallet=await db.prepare('SELECT id FROM watch_wallets WHERE id=?').bind(freezeMatch[1]).first();
        if(!wallet)return fail(404,'Wallet descriptor not found');
        await db.batch([
          db.prepare("UPDATE watch_wallets SET status='frozen' WHERE id=?").bind(wallet.id),
          db.prepare('INSERT INTO audit(credential_id,wallet_id,action) VALUES(?,?,?)').bind(operator.id,wallet.id,'wallet.frozen'),
        ]);
        return json({wallet_id:wallet.id,status:'frozen'});
      }
      const revokeMatch=/^\/v1\/credentials\/(cred_[0-9a-f-]+)\/revoke$/.exec(path);
      if(request.method==='POST'&&revokeMatch) {
        const operator=await requireRole(request,db,'operator');
        if(!operator)return fail(401,'Operator credential required');
        const credential=await db.prepare('SELECT id FROM credentials WHERE id=?').bind(revokeMatch[1]).first();
        if(!credential)return fail(404,'Credential not found');
        await db.batch([
          db.prepare('UPDATE credentials SET revoked=1 WHERE id=?').bind(credential.id),
          db.prepare('INSERT INTO audit(credential_id,wallet_id,action) VALUES(?,?,?)').bind(operator.id,null,'credential.revoked'),
        ]);
        return json({credential_id:credential.id,revoked:true});
      }
      if(path.startsWith('/v1/')&&request.method==='POST')return fail(501,'Transactions, approvals, custody and signing are not implemented on this Worker');
      return fail(404,'Not found');
    }catch(error) {
      if(error instanceof SyntaxError||error.message==='Invalid JSON body'||error.message==='Request too large')return fail(400,'Invalid request body');
      return fail(503,'Service unavailable');
    }
  },
};
