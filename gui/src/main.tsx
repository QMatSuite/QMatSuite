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
if (window.qv) {
  window.qv.onMainMessage((data) => {
    console.log('[QV] Main process message:', data)
  })
}
