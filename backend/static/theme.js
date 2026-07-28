(function () {
  const STORAGE_KEY = 'gameshelf-theme';
  const THEMES = ['dark', 'light', 'midnight', 'forest'];

  function normalize(theme) {
    return THEMES.includes(theme) ? theme : 'dark';
  }

  function apply(theme) {
    const selected = normalize(theme);
    document.documentElement.dataset.theme = selected;
    document.documentElement.style.colorScheme = selected === 'light' ? 'light' : 'dark';
    try {
      localStorage.setItem(STORAGE_KEY, selected);
    } catch (_) {
      // The theme still applies for this page if browser storage is unavailable.
    }
    window.dispatchEvent(new CustomEvent('gameshelf-theme-change', { detail: selected }));
    return selected;
  }

  let savedTheme = 'dark';
  try {
    savedTheme = localStorage.getItem(STORAGE_KEY) || 'dark';
  } catch (_) {
    // Keep the current dark theme as the safe default.
  }

  window.GameShelfTheme = {
    themes: THEMES,
    get: () => normalize(document.documentElement.dataset.theme),
    set: apply,
  };

  apply(savedTheme);
})();
