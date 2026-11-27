import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App.jsx'
import VueCesium from './VueCesium.jsx'
import AppVoieReservee from './AppVoieReservee.jsx'
import AppRueFermee from './AppRueFermee.jsx'
import './index.css'

const router = createBrowserRouter([
  { path: "/", element: <App /> },
  { path: "/cesium", element: <VueCesium /> },
  { path: "/voie-reservee", element: <AppVoieReservee /> },
  { path: "/rue-fermee", element: <AppRueFermee /> },
]);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)