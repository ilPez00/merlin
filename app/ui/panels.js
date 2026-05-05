class PanelManager {
  constructor() {
    this.maxPanels = 5;
    this.container = document.getElementById('panel-container');
  }

  spawn(title, content, accent = null, panelId = null) {
    const id = panelId || 'panel-' + Date.now();
    this._remove(id);

    const panel = document.createElement('div');
    panel.className = 'hud-panel';
    panel.dataset.panelId = id;
    if (accent) panel.style.borderTopColor = accent;

    panel.innerHTML =
      '<div class="panel-header">' +
        '<span class="panel-title">' + this._esc(title) + '</span>' +
        '<button class="panel-close" data-panel-id="' + id + '">✕</button>' +
      '</div>' +
      '<div class="panel-body">' + this._esc(content) + '</div>';

    panel.querySelector('.panel-close').addEventListener('click', () => this.close(id));
    this.container.prepend(panel);
    requestAnimationFrame(() => panel.classList.add('visible'));
    this._prune();
    return id;
  }

  update(panelId, content) {
    const panel = document.querySelector('[data-panel-id="' + panelId + '"]');
    if (panel) {
      const body = panel.querySelector('.panel-body');
      if (body) body.innerHTML = this._esc(content);
    }
  }

  close(id) {
    const el = document.querySelector('[data-panel-id="' + id + '"]');
    if (!el) return;
    el.classList.remove('visible');
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 350);
  }

  closeAll() {
    document.querySelectorAll('.hud-panel').forEach(p => {
      p.classList.remove('visible');
      setTimeout(() => { if (p.parentNode) p.parentNode.removeChild(p); }, 350);
    });
  }

  _remove(id) {
    const existing = document.querySelector('[data-panel-id="' + id + '"]');
    if (existing) existing.remove();
  }

  _prune() {
    const panels = this.container.querySelectorAll('.hud-panel');
    while (panels.length > this.maxPanels) {
      panels[0].remove();
    }
  }

  _esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
}

export const panels = new PanelManager();
