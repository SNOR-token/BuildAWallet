(() => {
  const chat = document.querySelector('.pane-chat');
  const toggle = document.querySelector('#chatToggle');
  toggle.addEventListener('click', () => {
    const closed = chat.classList.toggle('is-hidden');
    toggle.textContent = closed ? 'Open AI chat' : 'Hide AI chat';
    toggle.setAttribute('aria-expanded', String(!closed));
  });
})();
