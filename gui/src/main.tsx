import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Listen for main process ready message (optional)
if (window.qms) {
  window.qms.onMainMessage((data) => {
    console.log('[QMS] Main process message:', data)
  })
}
