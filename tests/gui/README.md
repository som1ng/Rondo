# GUI regression tests

Run on a Windows machine with Node.js and Microsoft Edge installed:

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm test
```

The tests extract the embedded HTML from `apps/gui/ui_view.h`,
launch headless Edge, and use simulated native messages. They cover layout,
navigation, diagnostics presentation, scrolling, dialogs, and window controls.
They do not execute injection or verify native window dragging / monitor DPI.

For an existing Playwright installation, `DLL_GUI_PLAYWRIGHT` may name its
absolute package path instead of installing another local copy.

`native-smoke.mjs <Rondo.exe>` launches the real GUI visibly, waits for WebView2
and its native process list, then closes through the window button. It requires
WebView2 Evergreen and uses an isolated temporary profile with a loopback CDP port.
`tests/gui_distribution_tests.py` runs it against the extracted x64/x86 archive.
