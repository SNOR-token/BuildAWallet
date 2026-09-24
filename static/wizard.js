(() => {
  'use strict';
  const key = 'baw.wizard.v1';
  const stages = [
    { title: 'What should it hold?', help: 'Name your wallet and choose your first assets.', group: 'assets', multi: true, name: true },
    { title: 'Where should it work?', help: 'Pick the networks you care about.', group: 'networks', multi: true },
    { title: 'Who controls the keys?', help: 'Choose the custody model and safety controls.', group: 'custody', extra: 'security' },
    { title: 'What should it do?', help: 'Choose features and privacy preferences.', group: 'features', multi: true, extra: 'privacy' },
    { title: 'Where will you use it?', help: 'Choose a platform and visual style.', group: 'platforms', multi: true, extra: 'style' }
  ];
  const $ = s => document.querySelector(s);
  let draft = {}, step = 0, catalog;
  try { draft = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) {}
  if (!draft || typeof draft !== 'object') draft = {};
  const encode = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function group(key) { return catalog.groups.find(g => g.key === key); }
  function choiceMarkup(groupKey) {
    const g = group(groupKey);
    if (!g) return '';
    const value = draft[groupKey] || (g.multi ? [] : '');
    return `<h3>${encode(g.title)}</h3><div class="choices">` + g.items.map(item => {
      const selected = Array.isArray(value) ? value.includes(item.id) : value === item.id;
      return `<label class="choice"><input type="${g.multi ? 'checkbox' : 'radio'}" name="${g.key}" value="${encode(item.id)}" ${selected ? 'checked' : ''}><span><strong>${encode(item.label)}</strong><small>${encode(item.blurb || '')}</small></span></label>`;
    }).join('') + '</div>';
  }
  function capture() {
    const s = stages[step];
    if (s.name) draft.name = $('#walletName').value.trim().slice(0,32);
    for (const groupKey of [s.group,s.extra].filter(Boolean)) {
      const g = group(groupKey);
      const checked = [...document.querySelectorAll(`input[name="${groupKey}"]:checked`)].map(x => x.value);
      draft[groupKey] = g.multi ? checked : (checked[0] || '');
    }
    localStorage.setItem(key, JSON.stringify(draft));
  }
  function render() {
    const s = stages[step];
    $('#stepCount').textContent = `STEP ${step+1} OF ${stages.length}`;
    $('#progress').style.width = `${(step+1)*20}%`;
    $('#questionPanel').innerHTML = `<h2>${s.title}</h2><p>${s.help}</p>` +
      (s.name ? `<div class="field"><label for="walletName">Wallet name</label><input id="walletName" maxlength="32" autocomplete="off" placeholder="My wallet" value="${encode(draft.name || '')}"></div>` : '') +
      choiceMarkup(s.group) + (s.extra ? choiceMarkup(s.extra) : '');
    $('#prev').disabled = step === 0;
    $('#next').textContent = step === stages.length-1 ? 'Continue to email sign-in →' : 'Continue →';
    $('#error').hidden = true;
  }
  $('#prev').onclick = () => { capture(); step--; render(); };
  $('#next').onclick = () => {
    capture();
    if (step === 0 && !draft.name) { $('#error').textContent = 'Give your wallet a name to continue.'; $('#error').hidden = false; return; }
    if (step < stages.length-1) { step++; render(); return; }
    localStorage.setItem('baw.wizard.completed', '1');
    location.assign('/auth');
  };
  fetch('/api/catalog').then(r => { if (!r.ok) throw Error('API unavailable'); return r.json(); })
    .catch(() => fetch('/catalog.json').then(r => { if (!r.ok) throw Error('Catalog unavailable'); return r.json(); }))
    .then(data => { catalog = data; render(); })
    .catch(() => { $('#questionPanel').textContent = 'The wallet choices could not load. Please refresh this page.'; $('#next').disabled = true; });
})();
