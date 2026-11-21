import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, TextLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const FALLBACK_VIEW = { longitude: -6.8416, latitude: 34.0209, zoom: 16, pitch: 60, bearing: 20, maxPitch: 85 };

// Durée de la simulation de démo : lue dans les données (dernier instant des trajectoires)
const DUREE_PAR_DEFAUT = 1500;
const SECONDES_DE_BOUCLE = 10; // une boucle de la démo dure ~10 s à l'écran

// Tronçons de l'axe 4330541 (pour la congestion de l'axe)
const TRONCONS_AXE = ['4330541#3', '4330541#7', '4330541#9', '4330541#10', '4330541#11', '4330541#12', '4330541#15', '4330541#18'];

// Conclusions des 10 tirages (valeurs issues des simulations, pas du tirage 1)
const DIX_TIRAGES = {
  voituresAxe: { ecart: '+22,4 s (+7 %)', ecartType: '8,5 s', detail: 'plus lentes dans 10 tirages sur 10' },
  bus: { ecart: '−20,8 s (−9 %)', ecartType: '10,4 s', detail: 'plus rapides dans 10 tirages sur 10' },
};

const SCENARIOS = [
  { id: 'actuel_bus', label: 'Situation actuelle', sous: 'Bus dans la circulation' },
  { id: 'voie_reservee', label: 'Voie réservée aux bus', sous: '1 voie sur 2 de l\'axe 4330541' },
];

const fetchJson = (url, fallback) =>
  fetch(url).then(r => (r.ok ? r.json() : fallback)).catch(() => fallback);

const prepareTrips = (raw) =>
  (raw || [])
    .map(v => ({
      type: v.type || 'car',
      path: v.path.map(p => [p[0], p[1]]),
      timestamps: v.path.map(p => p[2]),
    }))
    .filter(t => t.path.length > 1);

const moyenneAxe = (kpi) => {
  if (!kpi || !kpi.congestion_par_rue) return null;
  const vals = TRONCONS_AXE.map(id => kpi.congestion_par_rue[id]).filter(v => v !== undefined);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
};

function Ligne({ label, a, b, digits = 1, unite = '', facteur = 1 }) {
  const ok = a !== null && a !== undefined && b !== null && b !== undefined;
  const va = ok ? a * facteur : null;
  const vb = ok ? b * facteur : null;
  const d = ok ? vb - va : null;
  const fmt = (x) => (x === null ? '–' : x.toFixed(digits).replace('.', ','));
  const couleur = d === null || Math.abs(d) < Math.pow(10, -digits) ? '#8a9bb0' : d < 0 ? '#4ade80' : '#ffb347';
  return (
    <tr>
      <td style={{ color: '#8a9bb0', padding: '4px 0' }}>{label}</td>
      <td style={{ textAlign: 'right' }}>{fmt(va)}{unite}</td>
      <td style={{ textAlign: 'right' }}>{fmt(vb)}{unite}</td>
      <td style={{ textAlign: 'right', color: couleur, fontWeight: 'bold' }}>
        {d === null ? '–' : `${d > 0 ? '+' : d < 0 ? '−' : ''}${fmt(Math.abs(d))}`}
      </td>
    </tr>
  );
}

function Section({ titre, note, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 4 }}>{titre}</div>
      <table style={{ width: '100%', fontSize: 12.5, borderCollapse: 'collapse' }}>
        <tbody>{children}</tbody>
      </table>
      {note && <div style={{ color: '#8a9bb0', fontSize: 11, marginTop: 4, lineHeight: 1.35 }}>{note}</div>}
    </div>
  );
}

export default function AppVoieReservee() {
  const [viewState, setViewState] = useState(FALLBACK_VIEW);
  const [scenario, setScenario] = useState('actuel_bus');
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const tRef = useRef(0);

  // Chargement des deux scénarios au démarrage : le changement de scénario est ensuite instantané
  useEffect(() => {
    Promise.all([
      fetchJson('/data/buildings.geojson', null),
      fetchJson('/data/trajectories_actuel_bus.json', []),
      fetchJson('/data/trajectories_voie_reservee.json', []),
      fetchJson('/data/kpi_actuel_bus.json', null),
      fetchJson('/data/kpi_voie_reservee.json', null),
      fetchJson('/data/kpi_bus_actuel_bus.json', null),
      fetchJson('/data/kpi_bus_voie_reservee.json', null),
      fetchJson('/data/kpi_axe.json', null),
      fetchJson('/data/axe_4330541.geojson', null),
    ]).then(([buildings, tA, tV, kA, kV, bA, bV, kpiAxe, axe]) => {
      setData({
        buildings,
        trips: { actuel_bus: prepareTrips(tA), voie_reservee: prepareTrips(tV) },
        kpi: { actuel_bus: kA, voie_reservee: kV },
        kpiBus: { actuel_bus: bA, voie_reservee: bV },
        kpiAxe,
        axe,
      });
      setLoading(false);
    });
  }, []);

  // Centrer la vue sur l'axe dès qu'il est chargé
  const axeCentre = useMemo(() => {
    if (!data || !data.axe) return null;
    const pts = data.axe.features
      .filter(f => f.properties.kind === 'axe')
      .flatMap(f => f.geometry.coordinates);
    if (!pts.length) return null;
    return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  }, [data]);

  useEffect(() => {
    if (axeCentre) setViewState(v => ({ ...v, longitude: axeCentre[0], latitude: axeCentre[1], zoom: 16.3 }));
  }, [axeCentre]);

  // Animation du temps
  const dureeSim = useMemo(() => {
    if (!data) return DUREE_PAR_DEFAUT;
    let m = 0;
    Object.values(data.trips).forEach(list => list.forEach(t => {
      const last = t.timestamps[t.timestamps.length - 1];
      if (last > m) m = last;
    }));
    return m > 0 ? Math.ceil(m) : DUREE_PAR_DEFAUT;
  }, [data]);

  useEffect(() => {
    if (!playing) return undefined;
    const pas = dureeSim / (SECONDES_DE_BOUCLE * 60);
    let id;
    const tick = () => {
      tRef.current = (tRef.current + pas) % dureeSim;
      setTime(tRef.current);
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [playing, dureeSim]);

  const cars = useMemo(() => (data ? data.trips[scenario].filter(t => t.type !== 'bus') : []), [data, scenario]);
  const buses = useMemo(() => (data ? data.trips[scenario].filter(t => t.type === 'bus') : []), [data, scenario]);

  const axeFeatures = useMemo(() => {
    if (!data || !data.axe) return { axe: null, voie: null };
    const pick = (kind) => ({ type: 'FeatureCollection', features: data.axe.features.filter(f => f.properties.kind === kind) });
    return { axe: pick('axe'), voie: pick('voie_reservee') };
  }, [data]);

  if (loading) {
    return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;
  }

  const reserve = scenario === 'voie_reservee';
  const layers = [];

  if (data.buildings) {
    layers.push(new GeoJsonLayer({
      id: 'buildings', data: data.buildings, extruded: true,
      getElevation: f => f.properties.height || 10,
      getFillColor: [40, 45, 55], pickable: false,
      material: { ambient: 0.4, diffuse: 0.6, shininess: 32 },
    }));
  }

  if (axeFeatures.axe) {
    layers.push(new GeoJsonLayer({
      id: 'axe', data: axeFeatures.axe, stroked: true, filled: false,
      getLineColor: reserve ? [150, 150, 150, 200] : [255, 215, 0, 255],
      lineWidthUnits: 'meters',
      getLineWidth: reserve ? 0.6 : 6,
      lineWidthMinPixels: reserve ? 1 : 4,
      updateTriggers: { getLineColor: [reserve], getLineWidth: [reserve], lineWidthMinPixels: [reserve] },
    }));
  }
  if (reserve && axeFeatures.voie) {
    layers.push(new GeoJsonLayer({
      id: 'voie-reservee', data: axeFeatures.voie, stroked: true, filled: false,
      getLineColor: [40, 220, 120, 255], lineWidthUnits: 'meters', getLineWidth: 3, lineWidthMinPixels: 3,
    }));
  }
  if (axeCentre) {
    layers.push(new TextLayer({
      id: 'axe-label', data: [{ position: [axeCentre[0], axeCentre[1], 30] }],
      getPosition: d => d.position,
      getText: () => (reserve ? 'Axe 4330541 : voie réservée aux bus' : 'Axe 4330541 : situation actuelle'),
      getSize: 13, getColor: [255, 255, 255, 255], getBackgroundColor: [20, 25, 35, 220],
      backgroundPadding: [5, 3], getTextAnchor: 'middle', getAlignmentBaseline: 'bottom',
      getPixelOffset: [0, -20], billboard: true,
      updateTriggers: { getText: [reserve] },
    }));
  }

  layers.push(new TripsLayer({
    id: 'cars', data: cars, getPath: d => d.path, getTimestamps: d => d.timestamps,
    getColor: [60, 210, 255], widthUnits: 'meters', getWidth: 1.8, widthMinPixels: 3, rounded: true, trailLength: 60, currentTime: time,
  }));
  layers.push(new TripsLayer({
    id: 'buses', data: buses, getPath: d => d.path, getTimestamps: d => d.timestamps,
    getColor: [255, 150, 0], widthUnits: 'meters', getWidth: 2.5, widthMinPixels: 5, rounded: true, trailLength: 120, currentTime: time,
  }));

  const kA = data.kpi.actuel_bus;
  const kV = data.kpi.voie_reservee;
  const bA = data.kpiBus.actuel_bus;
  const bV = data.kpiBus.voie_reservee;
  const axe = data.kpiAxe;

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '20px 40px', color: 'white', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 26, color: '#fff' }}>Scénario : voie réservée aux bus</h1>
          <p style={{ margin: '5px 0 0', color: '#8a9bb0', fontSize: 14 }}>
            Rabat Hassan, axe 4330541. Données de trafic simulées (SUMO), pas observées. Animation : tirage 1.
          </p>
        </div>
        <Link to="/" style={{ background: '#333', color: '#fff', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold', border: '1px solid #555' }}>
          ← Vue principale
        </Link>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        {SCENARIOS.map(s => (
          <button key={s.id} onClick={() => setScenario(s.id)} style={{
            flex: 1, maxWidth: 300, textAlign: 'left', cursor: 'pointer', padding: '10px 14px', borderRadius: 8,
            border: scenario === s.id ? '2px solid #3cd2ff' : '1px solid #333',
            background: scenario === s.id ? 'rgba(60,210,255,0.12)' : '#161a22', color: 'white',
          }}>
            <div style={{ fontWeight: 'bold', fontSize: 14 }}>{s.label}</div>
            <div style={{ fontSize: 12, color: '#8a9bb0' }}>{s.sous}</div>
          </button>
        ))}
        {axeCentre && (
          <button onClick={() => setViewState(v => ({ ...v, longitude: axeCentre[0], latitude: axeCentre[1], zoom: 18.6, pitch: 55 }))}
            style={{ marginLeft: 'auto', cursor: 'pointer', padding: '0 18px', borderRadius: 8, border: '1px solid #28dc78', background: '#161a22', color: '#28dc78' }}>
            🔍 Zoom sur l'axe
          </button>
        )}
        <button onClick={() => setPlaying(p => !p)} style={{ marginLeft: axeCentre ? 0 : 'auto', cursor: 'pointer', padding: '0 18px', borderRadius: 8, border: '1px solid #333', background: '#161a22', color: 'white' }}>
          {playing ? '⏸ Pause' : '▶ Lecture'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ position: 'relative', flex: 1, height: 640, borderRadius: 12, overflow: 'hidden', border: '1px solid #333', boxShadow: '0 10px 30px rgba(0,0,0,0.5)', background: '#000' }}>
          <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, background: 'rgba(10,15,25,0.85)', padding: '8px 12px', borderRadius: 6, fontSize: 12, lineHeight: 1.6 }}>
            <div><span style={{ color: '#3cd2ff' }}>●</span> Voitures (300)</div>
            <div><span style={{ color: '#ff9600' }}>●</span> Bus ({buses.length})</div>
            <div><span style={{ color: reserve ? '#28dc78' : '#ffd700' }}>━</span> {reserve ? 'Voie réservée aux bus' : 'Axe étudié'}</div>
            <div style={{ color: '#8a9bb0' }}>t = {Math.round(time)} s / {dureeSim} s</div>
          </div>
          <div style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10, background: 'rgba(10,15,25,0.85)', padding: '5px 10px', borderRadius: 6, fontSize: 11, color: '#ffb347' }}>
            Données simulées (SUMO)
          </div>
          <DeckGL viewState={viewState} onViewStateChange={({ viewState }) => setViewState(viewState)} controller layers={layers}
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
            <Map mapStyle={MAP_STYLE} style={{ width: '100%', height: '100%' }} />
          </DeckGL>
        </div>

        <div style={{ width: 400, maxHeight: 640, overflowY: 'auto', background: 'rgba(10,15,25,0.85)', padding: 16, borderRadius: 12, border: '1px solid rgba(60,210,255,0.3)' }}>
          <table style={{ width: '100%', fontSize: 11, color: '#8a9bb0', marginBottom: 8 }}>
            <thead><tr><th style={{ textAlign: 'left' }}></th><th style={{ textAlign: 'right' }}>Actuel</th><th style={{ textAlign: 'right' }}>Voie réservée</th><th style={{ textAlign: 'right' }}>Écart</th></tr></thead>
          </table>

          <Section titre="Voitures, tout le réseau (tirage 1)" note="Écarts non significatifs : 37 voitures sur 300 seulement passent par l'axe, l'effet est dilué.">
            <Ligne label="Temps de trajet moyen" a={kA?.temps_trajet_moyen_s} b={kV?.temps_trajet_moyen_s} unite=" s" />
            <Ligne label="Vitesse moyenne" a={kA?.vitesse_moyenne_kmh} b={kV?.vitesse_moyenne_kmh} unite=" km/h" />
            <Ligne label="Congestion moyenne" a={kA?.congestion_moyenne} b={kV?.congestion_moyenne} facteur={100} digits={1} unite=" %" />
            <Ligne label="CO₂ total" a={kA?.co2_total_g} b={kV?.co2_total_g} facteur={0.001} unite=" kg" />
          </Section>

          <Section titre="Axe 4330541 (tirage 1)" note="Congestion de l'axe : moyenne des 8 tronçons. Elle reste élevée dans les deux cas : le blocage vient surtout des feux.">
            {axe && <Ligne label={`Voitures de l'axe (${axe.actuel_bus?.n ?? '?'})`} a={axe.actuel_bus?.duree_moyenne_s} b={axe.voie_reservee?.duree_moyenne_s} unite=" s" />}
            <Ligne label="Congestion de l'axe" a={moyenneAxe(kA)} b={moyenneAxe(kV)} facteur={100} digits={0} unite=" %" />
          </Section>

          <Section titre={`Bus de l'axe (${bV?.axe_bus_termines ?? '?'}, tirage 1)`} note="Bus dont la ligne emprunte l'axe, comparés sur les mêmes bus dans les deux scénarios.">
            <Ligne label="Temps de trajet moyen" a={bA?.axe_duree_moyenne_s} b={bV?.axe_duree_moyenne_s} unite=" s" />
            <Ligne label="Attente moyenne" a={bA?.axe_attente_moyenne_s} b={bV?.axe_attente_moyenne_s} unite=" s" />
          </Section>

          <Section titre={`Tous les bus (${bV?.bus_termines ?? '?'}, tirage 1)`} note="Les lignes qui n'empruntent pas l'axe ne bénéficient pas de la voie réservée.">
            <Ligne label="Temps de trajet moyen" a={bA?.duree_moyenne_s} b={bV?.duree_moyenne_s} unite=" s" />
            <Ligne label="Attente moyenne" a={bA?.attente_moyenne_s} b={bV?.attente_moyenne_s} unite=" s" />
          </Section>

          <div style={{ borderTop: '1px solid #2a3140', paddingTop: 10, fontSize: 12.5, lineHeight: 1.5 }}>
            <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 4 }}>Conclusion (10 tirages, ancien modèle : une seule ligne de bus)</div>
            <div>Voitures de l'axe : <b style={{ color: '#ffb347' }}>{DIX_TIRAGES.voituresAxe.ecart}</b>, écart-type {DIX_TIRAGES.voituresAxe.ecartType}, {DIX_TIRAGES.voituresAxe.detail}.</div>
            <div>Bus : <b style={{ color: '#4ade80' }}>{DIX_TIRAGES.bus.ecart}</b>, écart-type {DIX_TIRAGES.bus.ecartType}, {DIX_TIRAGES.bus.detail}.</div>
            <div style={{ color: '#8a9bb0', fontSize: 11, marginTop: 6 }}>
              Hypothèses : 1 bus toutes les 5 min, pas de priorité aux feux. Les chiffres du tirage 1 servent à la démo, les conclusions viennent des 10 tirages.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}