import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';

const SCENARIOS = [
  { id: 'actuel', label: 'Situation actuelle', hex: '#3cd2ff' },
  { id: 'pic', label: 'Pic +30 %', hex: '#ffaa28' },
  { id: 'rue_fermee', label: 'Rue fermée', hex: '#ff4b4b' },
  { id: 'voie_reservee', label: 'Voie réservée', hex: '#4bd37b' },
];

export default function VueCesium() {
  const [params, setParams] = useSearchParams();
  const scenario = params.get('scenario') || 'actuel';

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '20px 40px', color: 'white', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, color: '#fff' }}>Vue Réaliste (Cesium) : Rabat Hassan</h1>
          <p style={{ margin: '5px 0 0', color: '#8a9bb0', fontSize: 14 }}>
            Rendu 3D immersif avec bâtiments OSM et trafic CZML. Données simulées (SUMO).
          </p>
        </div>
        <Link to="/" style={{ background: '#333', color: '#fff', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold', border: '1px solid #555' }}>
          ← Retour à la vue analytique
        </Link>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        {SCENARIOS.map((s) => (
          <button key={s.id} onClick={() => setParams({ scenario: s.id })} style={{
            background: scenario === s.id ? s.hex : 'transparent', color: scenario === s.id ? '#000' : '#fff',
            border: `1px solid ${s.hex}`, padding: '8px 16px', borderRadius: 20, fontWeight: 'bold', cursor: 'pointer',
          }}>{s.label}</button>
        ))}
      </div>

      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '100%', maxWidth: 1200, height: 600, borderRadius: 12, overflow: 'hidden', border: '1px solid #333', background: '#000' }}>
          <iframe
            key={scenario}
            src={`/test_cesium_final.html?scenario=${scenario}`}
            style={{ width: '100%', height: '100%', border: 'none' }}
            title="Vue Cesium 3D"
          />
        </div>
      </div>
    </div>
  );
}