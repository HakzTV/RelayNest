/* The bridge uses pywebview's local JavaScript API, without a network control server. */
(() => {
  let listener = () => {};
  const ready = new Promise(resolve => {
    if (window.pywebview && window.pywebview.api) resolve();
    else window.addEventListener('pywebviewready', resolve, { once: true });
  });
  window.relay = {
    chooseFolder: async () => { await ready; return window.pywebview.api.choose_folder(); },
    start: async (mode, value, target) => {
      await ready;
      const result = await window.pywebview.api.start(mode, value, target);
      if (!result.ok) throw new Error(result.error);
    },
    stop: async () => { await ready; return window.pywebview.api.stop(); },
    onEvent: callback => { listener = callback; }
  };
  async function poll() {
    try {
      await ready;
      const events = await window.pywebview.api.poll();
      events.forEach(event => listener(event));
    } catch (error) { console.error('RelayNest bridge error:', error); }
    setTimeout(poll, 250);
  }
  poll();
})();
