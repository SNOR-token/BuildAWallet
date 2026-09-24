const fields=['assets','networks','custody','security','features','platforms','privacy','style','theme','accent'];
const nameEl=document.querySelector('#name'),statusEl=document.querySelector('#status'),choices=document.querySelector('#choices');
function validate(data){
  if(!data||data.schema!=='buildawallet.blueprint.v1'||!data.spec||typeof data.spec!=='object'||Array.isArray(data.spec))throw Error('Choose a BuildAWallet Studio configuration.');
  const spec=data.spec, clean={name:String(spec.name||'Wallet design').slice(0,32)};
  for(const key of fields){const value=spec[key];if(Array.isArray(value))clean[key]=value.filter(x=>typeof x==='string'&&x.length<80).slice(0,50);else if(typeof value==='string')clean[key]=value.slice(0,80);}
  return clean;
}
function render(spec){nameEl.textContent=spec.name;choices.replaceChildren();for(const key of fields){const value=spec[key],values=Array.isArray(value)?value:value?[value]:[];if(!values.length)continue;const row=document.createElement('section'),label=document.createElement('strong'),text=document.createElement('span');label.textContent=key;text.textContent=values.join(', ');row.append(label,text);choices.append(row);}statusEl.textContent='Imported design choices. No wallet has been created.';}
chrome.storage.local.get('blueprint').then(({blueprint})=>{if(blueprint)render(validate(blueprint));});
document.querySelector('#file').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>250000)throw Error('Configuration file is too large.');const data=JSON.parse(await file.text()),spec=validate(data);await chrome.storage.local.set({blueprint:{schema:data.schema,spec}});render(spec);}catch(error){statusEl.textContent=error.message||'Could not import that file.';}event.target.value='';});
