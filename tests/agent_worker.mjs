import assert from 'node:assert/strict';
import worker from '../cloudflare-agent/src/index.mjs';

class MockD1 {
  credentials=new Map(); wallets=new Map(); audit=[];
  async batch(statements){for(const statement of statements)await statement.run();return statements.map(()=>({success:true}));}
  prepare(sql) { return {
    bind:(...values)=>({
      first:async()=>{
        if(sql.includes('FROM credentials WHERE token_hash'))return [...this.credentials.values()].find(x=>x.token_hash===values[0]&&!x.revoked)||null;
        if(sql.includes('FROM credentials WHERE id'))return this.credentials.get(values[0])||null;
        if(sql.includes('FROM watch_wallets WHERE id=?')&&!sql.includes('credential_id'))return this.wallets.get(values[0])||null;
        if(sql.includes('FROM watch_wallets WHERE id')) {const row=this.wallets.get(values[0]);return row?.credential_id===values[1]?row:null;}
        throw Error('Unexpected query');
      },
      run:async()=>{
        if(sql.startsWith('INSERT INTO credentials')) {const [id,token_hash,role,name]=values;this.credentials.set(id,{id,token_hash,role,name,revoked:0});return {};}
        if(sql.startsWith('INSERT INTO watch_wallets')) {const [id,credential_id,chain,address]=values;this.wallets.set(id,{id,credential_id,chain,address,status:'active'});return {};}
        if(sql.startsWith('UPDATE watch_wallets')) {this.wallets.get(values[0]).status='frozen';return {};}
        if(sql.startsWith('UPDATE credentials')) {this.credentials.get(values[0]).revoked=1;return {};}
        if(sql.startsWith('INSERT INTO audit')) {this.audit.push(values);return {};}
        throw Error('Unexpected write');
      },
    }),
    run:async()=>({}),
  }; }
}
const env={DB:new MockD1(),AGENT_BOOTSTRAP_SECRET:'a'.repeat(64),OPERATOR_BOOTSTRAP_SECRET:'b'.repeat(64)};
async function call(method,path,body,headers={}) {
  const request=new Request(`https://example.test${path}`,{method,headers:{...headers,...(body?{'content-type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
  const response=await worker.fetch(request,env);
  return {status:response.status,body:await response.json()};
}
assert.equal((await call('GET','/healthz')).body.execution,'disabled');
assert.equal((await call('GET','/v1/capabilities')).body.transaction_signing,false);
assert.equal((await call('POST','/v1/credentials/bootstrap',{role:'agent',name:'Test'},{'x-bootstrap-secret':'wrong'})).status,403);
const agent=(await call('POST','/v1/credentials/bootstrap',{role:'agent',name:'Test'},{'x-bootstrap-secret':env.AGENT_BOOTSTRAP_SECRET})).body;
const second=(await call('POST','/v1/credentials/bootstrap',{role:'agent',name:'Other'},{'x-bootstrap-secret':env.AGENT_BOOTSTRAP_SECRET})).body;
assert.equal(agent.role,'agent');
const auth={'authorization':`Bearer ${agent.token}`};
const address='0x000000000000000000000000000000000000dEaD';
assert.equal((await call('POST','/v1/wallets',{chain:'ethereum',address},auth)).status,400);
const saved=await call('POST','/v1/wallets',{chain:'sepolia',address},auth);
assert.equal(saved.status,201);assert.equal(saved.body.mode,'watch-only');
assert.equal((await call('GET',`/v1/wallets/${saved.body.wallet_id}`,undefined,auth)).body.address,address);
assert.equal((await call('GET',`/v1/wallets/${saved.body.wallet_id}`,undefined,{'authorization':`Bearer ${second.token}`})).status,404);
assert.equal((await call('POST',`/v1/wallets/${saved.body.wallet_id}/transactions`,{amount:1},auth)).status,501);
assert.equal((await call('POST','/v1/credentials/bootstrap',{role:'operator',name:'Other'},{'x-bootstrap-secret':env.AGENT_BOOTSTRAP_SECRET})).status,403);
const operator=(await call('POST','/v1/credentials/bootstrap',{role:'operator',name:'Supervisor'},{'x-bootstrap-secret':env.OPERATOR_BOOTSTRAP_SECRET})).body;
const oh={'authorization':`Bearer ${operator.token}`};
assert.equal((await call('POST',`/v1/wallets/${saved.body.wallet_id}/freeze`,{},auth)).status,401);
assert.equal((await call('POST',`/v1/wallets/${saved.body.wallet_id}/freeze`,{},oh)).status,200);
assert.equal((await call('GET',`/v1/wallets/${saved.body.wallet_id}`,undefined,auth)).body.status,'frozen');
assert.equal((await call('POST',`/v1/credentials/${agent.credential_id}/revoke`,{},oh)).status,200);
assert.equal((await call('GET',`/v1/wallets/${saved.body.wallet_id}`,undefined,auth)).status,401);
assert.equal(env.DB.audit.length,2);
console.log('Agent Worker credentials, isolation and no-execution checks passed');
