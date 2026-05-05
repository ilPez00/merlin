const { app, BrowserWindow, ipcMain, globalShortcut, screen } = require('electron');
const path = require('path');

let hudWindow = null;
let clickThrough = true;

function createWindow() {
  const displays = screen.getAllDisplays();
  const primary = screen.getPrimaryDisplay();
  const { width, height } = primary.workAreaSize;

  hudWindow = new BrowserWindow({
    width,
    height,
    x: primary.bounds.x,
    y: primary.bounds.y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    focusable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  hudWindow.setIgnoreMouseEvents(true, { forward: true });
  hudWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  hudWindow.once('ready-to-show', () => {
    hudWindow.show();
  });

  // Register shortcut: Ctrl+Shift+H to toggle click-through
  globalShortcut.register('CommandOrControl+Shift+H', () => {
    clickThrough = !clickThrough;
    hudWindow.setIgnoreMouseEvents(clickThrough, { forward: true });
    hudWindow.webContents.send('clickthrough-changed', clickThrough);
    if (!clickThrough) {
      hudWindow.focus();
      hudWindow.setAlwaysOnTop(false);
    } else {
      hudWindow.setAlwaysOnTop(true);
      hudWindow.blur();
    }
  });

  // Register shortcut: Ctrl+Shift+Q to quit
  globalShortcut.register('CommandOrControl+Shift+Q', () => {
    app.quit();
  });

  // Auto-hide dock icon on macOS
  if (process.platform === 'darwin') {
    app.dock?.hide?.();
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  app.quit();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

// Handle toggle from renderer
ipcMain.on('toggle-clickthrough', () => {
  clickThrough = !clickThrough;
  hudWindow.setIgnoreMouseEvents(clickThrough, { forward: true });
  hudWindow.webContents.send('clickthrough-changed', clickThrough);
});

ipcMain.on('resize-hud', (e, { width, height }) => {
  if (hudWindow) {
    hudWindow.setSize(width, height);
  }
});
