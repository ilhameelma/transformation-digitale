import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, TextLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';


const INITIAL_VIEW_STATE = {
  longitude: -6.8416,
  latitude: 34.0209,
  zoom: 15.3,
  pitch: 60,
  bearing: 20,
  maxPitch: 85
};

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const LOOP_SECONDS = 300;

const SCENARIOS = [
  { id: 'actuel', label: 'Situation actuelle', color: [60, 210, 255], hex: '#3cd2ff', shortLabel: 'Actuel' },
  { id: 'pic', label: 'Pic de trafic +30 %', color: [255, 170, 40], hex: '#ffaa28', shortLabel: 'Pic' },
  { id: 'rue_fermee', label: 'Rue Fermée', color: [255, 75, 75], hex: '#ff4b4b', shortLabel: 'Fermée' },
  { id: 'voie_reservee', label: 'Voie Réservée', color: [75, 211, 123], hex: '#4bd37b', shortLabel: 'Bus' }
];
const scenarioById = (id) => SCENARIOS.find((s) => s.id === id) || SCENARIOS[0];

const KPIS = [
  { key: 'temps_trajet_moyen_s', label: 'Temps de trajet moyen', unit: ' s', digits: 0, worseIfHigher: true },
  { key: 'vitesse_moyenne_kmh', label: 'Vitesse moyenne', unit: ' km/h', digits: 1, worseIfHigher: false },
  { key: 'congestion_moyenne', label: 'Congestion moyenne', unit: ' %', digits: 0, factor: 100, diffUnit: ' pts', worseIfHigher: true },
  { key: 'co2_total_g', label: 'CO₂ total', unit: ' kg', digits: 0, factor: 0.001, worseIfHigher: true },
  { key: 'co2_par_vehicule_g', label: 'CO₂ par véhicule', unit: ' g', digits: 0, worseIfHigher: true },
  { key: 'trajets_termines', label: 'Trajets terminés', unit: '', digits: 0, neutral: true }
];

const COLOR_BAD = '#ff4b4b';
const COLOR_GOOD = '#4bd37b';
const COLOR_NEUTRAL = '#8a9bb0';

async function loadScenario(id) {
  const getJson = (url, fallback) =>
    fetch(url).then((r) => (r.ok ? r.json() : fallback)).catch(() => fallback);
  const [kpi, raw] = await Promise.all([
    getJson(`/data/kpi_${id}.json`, null),
    getJson(`/data/trajectories_${id}.json`, [])
  ]);
  const trips = (Array.isArray(raw) ? raw : [])
    .map((v) => ({
      path: v.path.map((p) => [p[0], p[1]]),
      timestamps: v.timestamps || v.path.map((p) => p[2])
    }))
    .filter((t) => t.path.length > 1);
  return { kpi, trips, missing: !kpi && trips.length === 0 };
}

function buildLabels(kpi, networkEdges, max) {
  if (!kpi || !kpi.congestion_par_rue || !networkEdges) return [];
  const edgeInfo = {};
  networkEdges.features.forEach((f) => {
    const rawId = f.properties.osmid || f.properties.id;
    if (!rawId) return;
    const idMatches = String(rawId).match(/\d+/g);
    if (idMatches && f.geometry && f.geometry.type === 'LineString') {
      const coords = f.geometry.coordinates;
      const mid = coords[Math.floor(coords.length / 2)];
      let name = String(f.properties.name || 'Rue');
      if (name.startsWith('[')) {
        const m = name.match(/'([^']+)'|"([^"]+)"/);
        name = m ? (m[1] || m[2]) : name.replace(/[[\]]/g, '');
      }
      name = name.replace(/[\u0600-\u06FF]/g, '').replace(/\s+/g, ' ').trim();
      if (name === '') name = 'Rue sans nom';
      idMatches.forEach((id) => {
        edgeInfo[id] = { name, position: [mid[0], mid[1], 20] };
      });
    }
  });
  const sorted = Object.entries(kpi.congestion_par_rue).sort((a, b) => b[1] - a[1]);
  const out = [];
  for (const [edgeId, rate] of sorted) {
    if (out.length >= max) break;
    const info = edgeInfo[edgeId];
    if (!info) continue;
    const tooClose = out.some(
      (e) => Math.hypot(info.position[0] - e.position[0], info.position[1] - e.position[1]) < 0.003
    );
    if (tooClose) continue;
    out.push({
      name: info.name,
      position: info.position,
      rate,
      label: rate > 0.75 ? 'Sévère' : rate > 0.5 ? 'Élevée' : 'Modérée'
    });
  }
  return out;
}

const fmt = (v, digits) => Number(v).toFixed(digits);

function compareKpi(def, a, b) {
  if (a == null || b == null) return null;
  const f = def.factor || 1;
  const va = a * f;
  const vb = b * f;
  const diff = vb - va;
  const pct = va !== 0 ? (diff / va) * 100 : null;
  let color = COLOR_NEUTRAL;
  if (!def.neutral && Math.abs(diff) > 0.5 * Math.pow(10, -def.digits)) {
    const worse = def.worseIfHigher ? diff > 0 : diff < 0;
    color = worse ? COLOR_BAD : COLOR_GOOD;
  }
  return { va, vb, diff, pct, color };
}

// --- COMPOSANTS DE LA CARTE ---
function MapPanel({ viewState, onViewStateChange, buildings, scenario, data, labels, time, height, kpiOverlay, droneButton }) {
  const layers = [];

  if (buildings) {
    layers.push(new GeoJsonLayer({
      id: 'buildings',
      data: buildings,
      extruded: true,
      getElevation: (f) => f.properties.height || 10,
      getFillColor: [40, 45, 55],
      pickable: false,
      material: { ambient: 0.4, diffuse: 0.6, shininess: 32 }
    }));
  }

  if (data && data.trips.length > 0) {
    layers.push(new TripsLayer({
      id: 'trips',
      data: data.trips,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: scenario.color,
      widthMinPixels: 4,
      rounded: true,
      trailLength: 150,
      currentTime: time
    }));
  }

  if (labels && labels.length > 0) {
    layers.push(new TextLayer({
      id: 'street-labels',
      data: labels,
      getPosition: (d) => d.position,
      getText: (d) => `${d.name}\n${d.label}`,
      getSize: 12,
      characterSet: 'auto',
      getColor: [255, 255, 255, 255],
      getBackgroundColor: [20, 25, 35, 220],
      backgroundPadding: [4, 2],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'bottom',
      getPixelOffset: [0, -15],
      billboard: true
    }));
  }

  return (
    <div style={{
      position: 'relative', width: '100%', height, borderRadius: 12, overflow: 'hidden',
      border: `1px solid ${scenario.hex}55`, boxShadow: '0 10px 30px rgba(0,0,0,0.5)', background: '#000',
      transition: 'all 0.3s ease'
    }}>
      {/* Bandeau du scénario */}
      <div style={{
        position: 'absolute', top: 12, right: 12, zIndex: 1000, background: 'rgba(10, 15, 25, 0.85)',
        border: `1px solid ${scenario.hex}`, color: scenario.hex, padding: '6px 12px', borderRadius: 20,
        fontSize: 12, fontWeight: 'bold'
      }}>
        {scenario.label} · données simulées (SUMO)
      </div>

      {kpiOverlay}
      {droneButton}

      {data && data.missing && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.7)', color: '#fff', textAlign: 'center', padding: 30, fontSize: 14
        }}>
          Scénario « {scenario.label} » pas encore simulé.<br />
          Lancez le script du scénario, puis rechargez la page.
        </div>
      )}

      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => onViewStateChange(vs)}
        controller={true}
        layers={layers}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
      >
        <Map mapStyle={MAP_STYLE} style={{ width: '100%', height: '100%' }} />
      </DeckGL>
    </div>
  );
}

function KpiOverlay({ kpi, scenario }) {
  if (!kpi) return null;
  const rows = KPIS.filter((d) => !d.neutral && kpi[d.key] != null).slice(0, 4);
  return (
    <div style={{ position: 'absolute', top: 20, left: 20, zIndex: 1000, background: 'rgba(10, 15, 25, 0.85)', color: 'white', padding: 20, borderRadius: 8, border: `1px solid ${scenario.hex}44`, backdropFilter: 'blur(8px)', width: 260 }}>
      <h4 style={{ margin: '0 0 12px', color: scenario.hex, fontSize: 11, textTransform: 'uppercase', letterSpacing: '1.5px' }}>{scenario.label}</h4>
      {rows.map((d) => {
        const isCongestion = d.key === 'congestion_moyenne';
        const value = kpi[d.key] * (d.factor || 1);
        const color = isCongestion && value > 20 ? COLOR_BAD : 'white';
        return (
          <div key={d.key} style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0', fontSize: 13 }}>
            <span style={{ color: COLOR_NEUTRAL }}>{d.label}</span>
            <span style={{ fontWeight: 'bold', color }}>{fmt(value, d.digits)}{d.unit}</span>
          </div>
        );
      })}
    </div>
  );
}

function DroneButton({ onClick, isDroneMode }) {
  return (
    <button onClick={onClick} disabled={isDroneMode} style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 1000, background: isDroneMode ? COLOR_BAD : '#3cd2ff', color: isDroneMode ? 'white' : '#000', border: 'none', padding: '12px 20px', borderRadius: 30, fontWeight: 'bold', cursor: isDroneMode ? 'not-allowed' : 'pointer', fontSize: 14, boxShadow: '0 4px 15px rgba(60, 210, 255, 0.4)' }}>
      {isDroneMode ? '⏹ Vol en cours...' : '🎬 Lancer le vol'}
    </button>
  );
}

function KpiTable({ base, sim, simScenario }) {
  const baseScenario = scenarioById('actuel');
  const rows = KPIS.map((d) => ({ d, c: compareKpi(d, base && base[d.key], sim && sim[d.key]) })).filter((r) => r.c);
  if (rows.length === 0) return <div style={{ color: COLOR_NEUTRAL, padding: 20 }}>Indicateurs indisponibles.</div>;
  const th = { textAlign: 'right', padding: '8px 14px', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 };
  const td = { textAlign: 'right', padding: '8px 14px', fontSize: 14 };
  return (
    <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 10, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: 'white' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333' }}>
            <th style={{ ...th, textAlign: 'left', color: COLOR_NEUTRAL }}>Indicateur</th>
            <th style={{ ...th, color: baseScenario.hex }}>{baseScenario.label}</th>
            <th style={{ ...th, color: simScenario.hex }}>{simScenario.label}</th>
            <th style={{ ...th, color: COLOR_NEUTRAL }}>Écart</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ d, c }) => (
            <tr key={d.key} style={{ borderBottom: '1px solid #222' }}>
              <td style={{ ...td, textAlign: 'left', color: '#cfd8e3' }}>{d.label}</td>
              <td style={td}>{fmt(c.va, d.digits)}{d.unit}</td>
              <td style={{ ...td, fontWeight: 'bold' }}>{fmt(c.vb, d.digits)}{d.unit}</td>
              <td style={{ ...td, color: c.color, fontWeight: 'bold' }}>
                {c.diff > 0 ? '+' : ''}{fmt(c.diff, d.digits)}{d.diffUnit || d.unit}
                {c.pct != null && !d.diffUnit ? ` (${c.pct > 0 ? '+' : ''}${fmt(c.pct, 0)} %)` : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- PAGE PRINCIPALE ---
export default function App() {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [time, setTime] = useState(0);
  const [common, setCommon] = useState({ loaded: false, buildings: null, networkEdges: null });
  const [scenarioData, setScenarioData] = useState({});
  const [selected, setSelected] = useState('actuel');
  const [compare, setCompare] = useState(false);
  const [isDroneMode, setIsDroneMode] = useState(false);
  const timeRef = useRef(0);

  const simId = selected !== 'actuel' ? selected : 'pic';
  const neededIds = compare ? ['actuel', simId] : [selected];

  useEffect(() => {
    const getJson = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    Promise.all([getJson('/data/buildings.geojson'), getJson('/data/network_edges.geojson')]).then(
      ([buildings, networkEdges]) => setCommon({ loaded: true, buildings, networkEdges })
    );
  }, []);

  useEffect(() => {
    neededIds.forEach((id) => {
      if (scenarioData[id]) return;
      loadScenario(id).then((d) => setScenarioData((prev) => ({ ...prev, [id]: d })));
    });
  }, [selected, compare]);

  const labels = useMemo(() => {
    const out = {};
    Object.entries(scenarioData).forEach(([id, d]) => {
      out[id] = buildLabels(d.kpi, common.networkEdges, 3);
    });
    return out;
  }, [scenarioData, common.networkEdges]);

  // Animation (temps)
  useEffect(() => {
    let animationFrameId;
    const animate = () => {
      timeRef.current = (timeRef.current + 0.2) % LOOP_SECONDS;
      setTime(timeRef.current);
      animationFrameId = requestAnimationFrame(animate);
    };
    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  const handleDroneFlight = () => {
    setIsDroneMode(true);
    setViewState(prev => ({
      ...prev,
      longitude: prev.longitude + 0.002,
      latitude: prev.latitude - 0.002,
      zoom: 17.5, pitch: 50, bearing: 0, transitionDuration: 3000
    }));
    setTimeout(() => {
      setViewState((prev) => ({ ...prev, zoom: 16.5, pitch: 65, bearing: 30, transitionDuration: 3000 }));
    }, 3500);
    setTimeout(() => {
      setViewState({ ...INITIAL_VIEW_STATE, transitionDuration: 4000 });
      setIsDroneMode(false);
    }, 7000);
  };

  const ready = common.loaded && neededIds.every((id) => scenarioData[id]);
  if (!ready) return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;

  // Hauteur dynamique pour éviter le scroll
  const mapHeight = compare ? 'calc(100vh - 380px)' : 'calc(100vh - 250px)';

  const selectedScenario = scenarioById(selected);
  const simScenario = scenarioById(simId);
  const baseKpi = scenarioData['actuel']?.kpi;
  const simKpi = scenarioData[simId]?.kpi;
  const impactPct = (baseKpi && simKpi) ? ((simKpi.temps_trajet_moyen_s - baseKpi.temps_trajet_moyen_s) / baseKpi.temps_trajet_moyen_s) * 100 : null;

  const chip = (active, hex) => ({
    background: active ? hex : 'transparent', color: active ? '#000' : '#fff',
    border: `1px solid ${hex}`, padding: '8px 16px', borderRadius: 20, fontWeight: 'bold', fontSize: 13, cursor: 'pointer', transition: 'all 0.2s ease'
  });

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '10px 20px', color: 'white', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>

      {/* EN-TÊTE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, color: '#fff' }}>Jumeau numérique 3D : Rabat Hassan</h1>
          <p style={{ margin: '2px 0 0 0', color: COLOR_NEUTRAL, fontSize: 13 }}>Données de trafic simulées (SUMO).</p>
        </div>
        <Link to={`/cesium?scenario=${selected}`} style={{ background: '#3cd2ff', color: '#000', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold' }}>
          Voir la vue réaliste (Cesium)
        </Link>
      </div>

      {/* BARRE D'OUTILS */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 12, maxWidth: 1500, width: '100%', alignSelf: 'center', background: 'rgba(255,255,255,0.02)', padding: '8px 16px', borderRadius: 12, border: '1px solid rgba(255,255,255,0.05)' }}>
        <span style={{ color: COLOR_NEUTRAL, fontSize: 13, fontWeight: 'bold', letterSpacing: 1 }}>SCÉNARIOS :</span>
        {SCENARIOS.map((s) => {
          const pageDediee = { rue_fermee: '/rue-fermee', voie_reservee: '/voie-reservee' }[s.id];
          return pageDediee ? (
            <Link key={s.id} to={pageDediee} style={{ ...chip(false, s.hex), textDecoration: 'none' }}>
              {s.label} ↗
            </Link>
          ) : (
            <button key={s.id} onClick={() => setSelected(s.id)} style={chip(selected === s.id, s.hex)}>
              {s.label}
            </button>
          );
        })}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {compare && impactPct !== null && (
            <span style={{ fontSize: 12, color: impactPct > 0 ? COLOR_BAD : COLOR_GOOD, background: impactPct > 0 ? 'rgba(255,75,75,0.1)' : 'rgba(75,211,123,0.1)', padding: '4px 10px', borderRadius: 20, border: `1px solid ${impactPct > 0 ? COLOR_BAD : COLOR_GOOD}44`, fontWeight: 'bold' }}>
              Impact Temps : {impactPct > 0 ? '+' : ''}{impactPct.toFixed(1)} %
            </span>
          )}
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', background: compare ? 'rgba(60, 210, 255, 0.15)' : 'transparent', border: `1px solid ${compare ? '#3cd2ff' : '#444'}`, padding: '4px 12px', borderRadius: 30, transition: 'all 0.3s' }}>
            <span style={{ fontSize: 12, fontWeight: 'bold', color: compare ? '#3cd2ff' : COLOR_NEUTRAL }}>MODE COMPARAISON</span>
            <div style={{ width: 32, height: 18, background: compare ? '#3cd2ff' : '#444', borderRadius: 20, position: 'relative', transition: 'all 0.3s' }}>
              <div style={{ width: 14, height: 14, background: 'white', borderRadius: '50%', position: 'absolute', top: 2, left: compare ? 16 : 2, transition: 'all 0.3s' }} />
            </div>
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      {/* CARTES */}
      <div style={{ display: 'flex', justifyContent: 'center', flex: 1, minHeight: 0 }}>
        <div style={{ width: '100%', maxWidth: compare ? 1500 : 1200, transition: 'all 0.5s ease', display: 'flex', flexDirection: 'column' }}>
          {compare ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <MapPanel viewState={viewState} onViewStateChange={setViewState} buildings={common.buildings}
                  scenario={scenarioById('actuel')} data={scenarioData.actuel} labels={labels.actuel} time={time} height={mapHeight}
                  droneButton={<DroneButton onClick={handleDroneFlight} isDroneMode={isDroneMode} />} />
                <MapPanel viewState={viewState} onViewStateChange={setViewState} buildings={common.buildings}
                  scenario={simScenario} data={scenarioData[simId]} labels={labels[simId]} time={time} height={mapHeight}
                  droneButton={<DroneButton onClick={handleDroneFlight} isDroneMode={isDroneMode} />} />
              </div>
              <div style={{ marginTop: 12, flex: '0 0 auto' }}>
                <KpiTable base={baseKpi} sim={simKpi} simScenario={simScenario} />
              </div>
            </>
          ) : (
            <MapPanel viewState={viewState} onViewStateChange={setViewState} buildings={common.buildings}
              scenario={selectedScenario} data={scenarioData[selected]} labels={labels[selected]} time={time} height={mapHeight}
              kpiOverlay={<KpiOverlay kpi={scenarioData[selected] && scenarioData[selected].kpi} scenario={selectedScenario} />}
              droneButton={<DroneButton onClick={handleDroneFlight} isDroneMode={isDroneMode} />} />
          )}
        </div>
      </div>
    </div>
  );
}