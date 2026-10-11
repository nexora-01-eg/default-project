const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("organizer", {
  getDefaultFolders: () => ipcRenderer.invoke("get-default-folders"),
  pickFolder: () => ipcRenderer.invoke("pick-folder"),
  scan: (dir) => ipcRenderer.invoke("scan", dir),
  organize: (targetDir, dryRun) => ipcRenderer.invoke("organize", { targetDir, dryRun }),
  findDuplicates: (dir) => ipcRenderer.invoke("find-duplicates", dir),
  trash: (filePath) => ipcRenderer.invoke("trash", filePath),
});
