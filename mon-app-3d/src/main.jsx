import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App.jsx' // Ta vue Deck.gl actuelle
import VueCesium from './VueCesium.jsx' // La nouvelle vue
import AppVoieReservee from './AppVoieReservee.jsx' // Scénario voie réservée aux bus
import AppRueFermee from './AppRueFermee.jsx' // Scénario rue fermée
import './index.css'

// Configuration des routes
const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
  },
  {
    path: "/cesium",
    element: <VueCesium />,
  },
  {
    path: "/voie-reservee",
    element: <AppVoieReservee />,
  },
  {
    path: "/rue-fermee",
    element: <AppRueFermee />,
  },
]);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)