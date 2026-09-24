import { formatEther, formatUnits } from 'ethers';
import { createAccount, importAccount, reviewTransfer, signReviewedTransfer, unlockAccount } from './engine.mjs';

const $ = id => document.getElementById(id);
let account, reviewed;
async function saveAccount(next) {
  await chrome.storage.local.set({ wallet: { address:next.address, vault:next.vault } });
  account={address:next.address,vault:next.vault};
  show('account');
  $('address').textContent=account.address;
}
function show(id) {
  for(const section of ['setup','backup','account','approval','signed'])$(section).hidden=section!==id;
  $('status').textContent='';
}
async function act(task) {
  try { await task(); } catch(error) { $('status').textContent=error.message||'Action failed'; }
}

await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
({wallet:account}=await chrome.storage.local.get('wallet'));
if(account){$('address').textContent=account.address;show('account');}else show('setup');
$('create').addEventListener('click',()=>act(async()=>{
  const password=$('newPassword').value;
  const next=await createAccount(password);
  await saveAccount(next);
  $('newPassword').value='';
  $('phrase').textContent=next.phrase;
  show('backup');
}));
$('import').addEventListener('click',()=>act(async()=>{
  const next=await importAccount($('importPhrase').value,$('newPassword').value);
  await saveAccount(next);
  $('importPhrase').value='';$('newPassword').value='';
}));
$('backupDone').addEventListener('click',()=>{ $('phrase').textContent=''; show('account'); });
$('review').addEventListener('click',()=>act(async()=>{
  reviewed=reviewTransfer(Object.fromEntries(['to','amount','nonce','gasLimit','maxFeeGwei','priorityFeeGwei'].map(id=>[id,$(id).value.trim()])));
  $('summary').textContent=[
    'Chain: Ethereum Sepolia (11155111)',
    `From: ${account.address}`,
    `To: ${reviewed.transaction.to}`,
    `Amount: ${formatEther(reviewed.transaction.value)} test ETH`,
    `Nonce: ${reviewed.transaction.nonce}`,
    `Gas limit: ${reviewed.transaction.gasLimit}`,
    `Max fee per gas: ${formatUnits(reviewed.transaction.maxFeePerGas,'gwei')} gwei`,
    `Priority fee per gas: ${formatUnits(reviewed.transaction.maxPriorityFeePerGas,'gwei')} gwei`,
    `Maximum gas cost: ${formatEther(reviewed.maximumFeeWei)} test ETH`,
    `Maximum total: ${formatEther(reviewed.totalMaximumWei)} test ETH`,
  ].join('\n');
  show('approval');
}));
$('cancel').addEventListener('click',()=>{reviewed=undefined;$('unlockPassword').value='';show('account');});
$('sign').addEventListener('click',()=>act(async()=>{
  if(!account||!reviewed)throw Error('Review transaction first');
  const wallet=await unlockAccount(account.vault,account.address,$('unlockPassword').value);
  $('unlockPassword').value='';
  $('raw').value=await signReviewedTransfer(wallet,reviewed);
  reviewed=undefined;
  show('signed');
}));
$('closeSigned').addEventListener('click',()=>{$('raw').value='';show('account');});
$('forget').addEventListener('click',()=>act(async()=>{
  if(!confirm('Remove the encrypted account from this browser? Make sure your recovery phrase is safely backed up.'))return;
  await chrome.storage.local.remove('wallet');account=undefined;reviewed=undefined;$('phrase').textContent='';$('raw').value='';show('setup');
}));
