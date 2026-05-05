const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  toggleClickThrough: () => ipcRenderer.send('toggle-clickthrough'),
  resizeHud: (dims) => ipcRenderer.send('resize-hud', dims),
  onClickThroughChanged: (callback) => ipcRenderer.on('clickthrough-changed', (_, val) => callback(val)),
});
