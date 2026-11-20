import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, TextLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';

// Configuration de la vue initiale (centrée sur Rabat Hassan)
const INITIAL_VIEW_STATE = {
  longitude: -6.8416, 
  latitude: 34.0209, 
  zoom: 15.3, 
  pitch: 60, 
  bearing: 20, 
  maxPitch: 85
};

// Style de carte sombre (Carto Dark Matter)
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export default function App() {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [time, setTime] = useState(0);
  const [data, setData] = useState({ buildings: null, trips: [], kpi: null });
  const [isDroneMode, setIsDroneMode] = useState(false);
  const [loading, setLoading] = useState(true);
  const [streetLabels, setStreetLabels] = useState([]);

  // 1. Chargement des données au démarrage
  useEffect(() => {
    Promise.all([
      fetch('/data/buildings.geojson').then(r => r.json()).catch(() => null),
      fetch('/data/trajectories_actuel.json').then(r => r.json()).catch(() => []),
      fetch('/data/kpi_actuel.json').then(r => r.json()).catch(() => null),
      fetch('/data/network_edges.geojson').then(r => r.json()).catch(() => null)
    ]).then(([buildings, rawTrips, kpi, networkEdges]) => {
      // Préparer les trajets
      const trips = rawTrips.map(v => ({
        path: v.path.map(p => [p[0], p[1]]),
        timestamps: v.timestamps || v.path.map(p => p[2])
      })).filter(t => t.path.length > 1);
      
      setData({ buildings, trips, kpi });
      
      // Préparer les étiquettes (Top 3)
      if (kpi && kpi.congestion_par_rue && networkEdges) {
        const streetRates = kpi.congestion_par_rue;
        const edgeInfo = {};
        networkEdges.features.forEach(f => {
          const rawId = f.properties.osmid || f.properties.id;
          if (!rawId) return;
          const idMatches = String(rawId).match(/\d+/g);
          if (idMatches && f.geometry && f.geometry.type === "LineString") {
            let coords = f.geometry.coordinates;
            const midPoint = coords[Math.floor(coords.length / 2)];
            let name = String(f.properties.name || "Rue").replace(/[\u0600-\u06FF]/g, '').replace(/["'\[\]]/g, '').trim();
            if (name === "") name = "Rue sans nom";
            idMatches.forEach(id => {
              edgeInfo[id] = { name: name, position: [midPoint[0], midPoint[1], 20] };
            });
          }
        });
        
        const sortedStreets = Object.entries(streetRates).sort((a, b) => b[1] - a[1]);
        const top3 = [];
        for (const [edgeId, rate] of sortedStreets) {
          if (top3.length >= 3) break;
          if (edgeInfo[edgeId]) {
            top3.push({
              name: edgeInfo[edgeId].name,
              position: edgeInfo[edgeId].position,
              rate: rate,
              label: rate > 0.75 ? "Sévère" : rate > 0.5 ? "Élevée" : "Modérée"
            });
          }
        }
        setStreetLabels(top3);
      }
      
      setLoading(false);
    });
  }, []);

  // 2. Animation du temps (trafic)
  useEffect(() => {
    let animationFrameId;
    let t = 0;
    const animate = () => {
      t = (t + 0.5) % 300; // Boucle sur 300 secondes
      setTime(t);
      animationFrameId = requestAnimationFrame(animate);
    };
    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  // 3. Logique du vol de drone
  const handleDroneFlight = () => {
    setIsDroneMode(true);
    setViewState({ 
      ...viewState, 
      longitude: viewState.longitude + 0.002, 
      latitude: viewState.latitude - 0.002, 
      zoom: 17.5, 
      pitch: 50, 
      bearing: 0, 
      transitionDuration: 3000 
    });
    setTimeout(() => { 
      setViewState(prev => ({ 
        ...prev, 
        zoom: 16.5, 
        pitch: 65, 
        bearing: 30, 
        transitionDuration: 3000 
      })); 
    }, 3500);
    setTimeout(() => { 
      setViewState({ 
        ...INITIAL_VIEW_STATE, 
        transitionDuration: 4000 
      }); 
      setIsDroneMode(false); 
    }, 7000);
  };

  // 4. Définition des couches deck.gl
  const layers = [];
  
  if (data.buildings) {
    layers.push(new GeoJsonLayer({
      id: 'buildings', 
      data: data.buildings, 
      extruded: true,
      getElevation: f => f.properties.height || 10,
      getFillColor: [40, 45, 55], 
      pickable: false,
      material: { ambient: 0.4, diffuse: 0.6, shininess: 32 }
    }));
  }
  
  if (data.trips.length > 0) {
    layers.push(new TripsLayer({
      id: 'trips', 
      data: data.trips, 
      getPath: d => d.path,
      getTimestamps: d => d.timestamps, 
      getColor: [60, 210, 255],
      widthMinPixels: 4, 
      rounded: true, 
      trailLength: 150, 
      currentTime: time
    }));
  }
  
  if (streetLabels.length > 0) {
    layers.push(new TextLayer({
      id: 'street-labels', 
      data: streetLabels, 
      getPosition: d => d.position,
      getText: d => `${d.name}\n${d.label}`, 
      getSize: 12,
      getColor: [255, 255, 255, 255], 
      getBackgroundColor: [20, 25, 35, 220],
      backgroundPadding: [4, 2], 
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'bottom', 
      getPixelOffset: [0, -15], 
      billboard: true
    }));
  }

  // Affichage pendant le chargement
  if (loading) {
    return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '20px 40px', color: 'white', display: 'flex', flexDirection: 'column' }}>
      
      {/* EN-TÊTE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '28px', color: '#fff' }}>Jumeau numérique 3D : Rabat Hassan</h1>
          <p style={{ margin: '5px 0 0 0', color: '#8a9bb0', fontSize: '14px' }}>Données de trafic simulées (SUMO).</p>
        </div>
        <Link to="/cesium" style={{ background: '#3cd2ff', color: '#000', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold' }}>
          Voir la vue réaliste (Cesium)
        </Link>
      </div>

      {/* ZONE DE LA CARTE */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <div style={{ 
          position: 'relative', 
          width: '100%', 
          maxWidth: '1200px', 
          height: '600px', // Hauteur fixe pour bien voir la carte
          borderRadius: '12px', 
          overflow: 'hidden', 
          border: '1px solid #333',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          background: '#000'
        }}>
          
          {/* Panneau KPI */}
          {data.kpi && (
            <div style={{ position: 'absolute', top: 20, left: 20, zIndex: 1000, background: 'rgba(10, 15, 25, 0.85)', color: 'white', padding: 20, borderRadius: 8, border: '1px solid rgba(60, 210, 255, 0.3)', backdropFilter: 'blur(8px)', width: 260 }}>
              <h4 style={{ margin: '0 0 12px', color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: '1.5px' }}>Situation Actuelle</h4>
              <div style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0', fontSize: 13 }}><span style={{ color: '#8a9bb0' }}>Temps trajet</span><span style={{ fontWeight: 'bold' }}>{data.kpi.temps_trajet_moyen_s?.toFixed(0)} s</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0', fontSize: 13 }}><span style={{ color: '#8a9bb0' }}>Vitesse moy.</span><span style={{ fontWeight: 'bold' }}>{data.kpi.vitesse_moyenne_kmh?.toFixed(1)} km/h</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0', fontSize: 13 }}><span style={{ color: '#8a9bb0' }}>Congestion</span><span style={{ fontWeight: 'bold', color: '#ff4b4b' }}>{(data.kpi.congestion_moyenne * 100).toFixed(0)} %</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0', fontSize: 13 }}><span style={{ color: '#8a9bb0' }}>CO₂ total</span><span style={{ fontWeight: 'bold' }}>{(data.kpi.co2_total_g / 1000).toFixed(0)} kg</span></div>
            </div>
          )}

          {/* Bouton Drone */}
          <button onClick={handleDroneFlight} disabled={isDroneMode} style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 1000, background: isDroneMode ? '#ff4b4b' : '#3cd2ff', color: isDroneMode ? 'white' : '#000', border: 'none', padding: '12px 20px', borderRadius: 30, fontWeight: 'bold', cursor: isDroneMode ? 'not-allowed' : 'pointer', fontSize: 14, boxShadow: '0 4px 15px rgba(60, 210, 255, 0.4)' }}>
            {isDroneMode ? '⏹ Vol en cours...' : '🎬 Lancer le vol'}
          </button>

          {/* La carte Deck.gl + MapLibre */}
          <DeckGL 
            viewState={viewState} 
            onViewStateChange={({ viewState }) => setViewState(viewState)} 
            controller={true} 
            layers={layers} 
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
          >
            <Map 
              mapStyle={MAP_STYLE} 
              style={{ width: '100%', height: '100%' }} 
            />
          </DeckGL>
        </div>
      </div>
    </div>
  );
}