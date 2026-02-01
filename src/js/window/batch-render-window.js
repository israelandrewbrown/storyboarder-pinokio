const remote = require('@electron/remote')
const { ipcRenderer } = require('electron')
const path = require('path')

document.addEventListener('DOMContentLoaded', () => {
  const currentWindow = remote.getCurrentWindow()
  const closeButton = document.getElementById('close-button')

  closeButton.addEventListener('click', () => {
    currentWindow.close()
  })

  // Parse URL parameters
  const urlParams = new URLSearchParams(window.location.search)
  const currentPath = urlParams.get('currentPath')
  const boardFilename = urlParams.get('boardFilename')

  // Request scene list from main process
  ipcRenderer.send('batch-render:request-scenes', { currentPath, boardFilename })

  ipcRenderer.on('batch-render:scenes-list', (event, scenes) => {
    const appDiv = document.getElementById('batch-render-app')
    appDiv.innerHTML = '<h1>Batch Render</h1>'
    appDiv.innerHTML += `<p>Found ${scenes.length} scenes in project folder:</p>`
    const ul = document.createElement('ul')
    scenes.forEach(scene => {
      const li = document.createElement('li')
      li.textContent = path.basename(scene)
      ul.appendChild(li)
    })
    appDiv.appendChild(ul)
    appDiv.innerHTML += '<p>Batch rendering logic is still under development.</p>'
    appDiv.appendChild(closeButton)
  })
})
