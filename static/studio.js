(() => {
  const chat = document.querySelector('.pane-chat');
  document.querySelector('#exportExtension').addEventListener('click', () => {
    let draft;
    try { draft = JSON.parse(localStorage.getItem('baw.draft.v1') || 'null'); } catch (_) {}
    if (!draft || !draft.spec) { document.querySelector('#deployStatus').textContent = 'Finish loading your Studio design before exporting.'; return; }
    const payload = { schema: 'buildawallet.blueprint.v1', spec: draft.spec };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'buildawallet-extension-config.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  });
  const toggle = document.querySelector('#chatToggle');
  toggle.addEventListener('click', () => {
    const closed = chat.classList.toggle('is-hidden');
    toggle.textContent = closed ? 'Open AI chat' : 'Hide AI chat';
    toggle.setAttribute('aria-expanded', String(!closed));
  });
})();
