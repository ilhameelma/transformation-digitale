import React from 'react';
import { Link } from 'react-router-dom';

export default function VueCesium() {
  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '20px 40px', color: 'white', display: 'flex', flexDirection: 'column' }}>
      
      {/* EN-TÊTE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '28px', color: '#fff' }}>Vue Réaliste (Cesium) : Rabat Hassan</h1>
          <p style={{ margin: '5px 0 0 0', color: '#8a9bb0', fontSize: '14px' }}>Rendu 3D immersif avec bâtiments OSM et trafic CZML.</p>
        </div>
        <Link to="/" style={{ background: '#333', color: '#fff', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold', border: '1px solid #555' }}>
          ← Retour à la vue analytique
        </Link>
      </div>

      {/* ZONE DE LA CARTE */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <div style={{ 
          position: 'relative', 
          width: '100%', 
          maxWidth: '1200px', 
          height: '600px', 
          borderRadius: '12px', 
          overflow: 'hidden', 
          border: '1px solid #333',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          background: '#000' // Fond noir en attendant le chargement
        }}>
          <iframe 
            src="/test_cesium_final.html" 
            style={{ width: '100%', height: '100%', border: 'none' }} 
            title="Vue Cesium 3D"
          />
        </div>
      </div>
    </div>
  );
}