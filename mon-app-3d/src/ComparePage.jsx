import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
export const COLOR_BAD = '#ff4b4b';
export const COLOR_GOOD = '#4bd37b';
export const COLOR_NEUTRAL = '#8a9bb0';
const SECONDES_DE_BOUCLE = 10;

export const fetchJson = (url, fallback) =>
  fetch(url).then((r) => (r.ok ? r.json() : fallback)).catch(() => fallback);

export const prepareTrips = (raw) =>
  (Array.isArray(raw) ? raw : [])
    .map((v) => ({
      id: String(v.id),
      type: v.type || 'car',
      path: v.path.map((p) => [p[0], p[1]]),
      timestamps: v.path.map((p) => p[2]),
    }))
    .filter((t) => t.path.length > 1);

const KPIS = [
  { key: 'temps_trajet_moyen_s', label: 'Temps de trajet moyen', unit: ' s', digits: 0, worseIfHigher: true },
  { key: 'vitesse_moyenne_kmh', label: 'Vitesse moyenne', unit: ' km/h', digits: 1, worseIfHigher: false },
  { key: 'congestion_moyenne', label: 'Congestion moyenne', unit: ' %', digits: 0, factor: 100, diffUnit: ' pts', worseIfHigher: true },
  { key: 'co2_total_g', label: 'CO₂ total', unit: ' kg', digits: 0, factor: 0.001, worseIfHigher: true },
  { key: 'trajets_termines', label: 'Trajets terminés', unit: '', digits: 0, neutral: true },
];

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

function KpiTable({ base, sim }) {
  const rows = KPIS.map((d) => ({ d, c: compareKpi(d, base.kpi && base.kpi[d.key], sim.kpi && sim.kpi[d.key]) })).filter((r) => r.c);
  if (rows.length === 0) return <div style={{ color: COLOR_NEUTRAL, padding: 20 }}>Indicateurs indisponibles.</div>;
  const th = { textAlign: 'right', padding: '8px 14px', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 };
  const td = { textAlign: 'right', padding: '8px 14px', fontSize: 14 };
  return (
    <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 10, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: 'white' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333' }}>
            <th style={{ ...th, textAlign: 'left', color: COLOR_NEUTRAL }}>Indicateur</th>
            <th style={{ ...th, color: base.scenario.hex }}>{base.scenario.label}</th>
            <th style={{ ...th, color: sim.scenario.hex }}>{sim.scenario.label}</th>
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

// Blocs d'indicateurs propres à un scénario (même style que le tableau principal)
export function Ligne({ label, a, b, digits = 1, unite = '', facteur = 1 }) {
  const ok = a != null && b != null;
  const va = ok ? a * facteur : null;
  const vb = ok ? b * facteur : null;
  const d = ok ? vb - va : null;
  const f = (x) => (x === null ? '–' : x.toFixed(digits));
  const couleur = d === null || Math.abs(d) < Math.pow(10, -digits) ? COLOR_NEUTRAL : d < 0 ? COLOR_GOOD : COLOR_BAD;
  return (
    <tr style={{ borderBottom: '1px solid #222' }}>
      <td style={{ color: '#cfd8e3', padding: '6px 0' }}>{label}</td>
      <td style={{ textAlign: 'right' }}>{f(va)}{unite}</td>
      <td style={{ textAlign: 'right', fontWeight: 'bold' }}>{f(vb)}{unite}</td>
      <td style={{ textAlign: 'right', color: couleur, fontWeight: 'bold' }}>
        {d === null ? '–' : `${d > 0 ? '+' : ''}${f(d)}`}
      </td>
    </tr>
  );
}

export function Section({ titre, note, cols = ['Actuel', 'Scénario'], children }) {
  return (
    <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 14 }}>
      <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 6 }}>{titre}</div>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', color: 'white' }}>
        <thead>
          <tr style={{ color: COLOR_NEUTRAL, fontSize: 11 }}>
            <th></th>
            <th style={{ textAlign: 'right' }}>{cols[0]}</th>
            <th style={{ textAlign: 'right' }}>{cols[1]}</th>
            <th style={{ textAlign: 'right' }}>Écart</th>
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
      {note && <div style={{ color: COLOR_NEUTRAL, fontSize: 11, marginTop: 6, lineHeight: 1.4 }}>{note}</div>}
    </div>
  );
}

function MapPanel({ viewState, onViewStateChange, layers, scenario, height, missing }) {
  return (
    <div style={{
      position: 'relative', width: '100%', height, borderRadius: 12, overflow: 'hidden',
      border: `1px solid ${scenario.hex}55`, boxShadow: '0 10px 30px rgba(0,0,0,0.5)', background: '#000',
    }}>
      <div style={{
        position: 'absolute', top: 12, right: 12, zIndex: 1000, background: 'rgba(10, 15, 25, 0.85)',
        border: `1px solid ${scenario.hex}`, color: scenario.hex, padding: '6px 12px', borderRadius: 20,
        fontSize: 12, fontWeight: 'bold',
      }}>
        {scenario.label} · données simulées (SUMO)
      </div>
      {missing && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', color: '#fff', textAlign: 'center', padding: 30, fontSize: 14 }}>
          Trajectoires introuvables pour « {scenario.label} ».<br />Lancez le script du scénario puis rechargez.
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

/**
 * Page de comparaison commune (même design que le scénario « pic »).
 * base / sim : { scenario: {id,label,hex}, trips, kpi }
 * makeLayers(isSim, time) : couches propres au scénario (rue fermée, bus, voie...)
 */
export default function ComparePage({ title, subtitle, base, sim, buildings, center, makeLayers, legend, extra, zoomLabel = '🔍 Zoom' }) {
  const [viewState, setViewState] = useState({
    longitude: center ? center[0] : -6.8416, latitude: center ? center[1] : 34.0209,
    zoom: 16.3, pitch: 60, bearing: 20, maxPitch: 85,
  });
  const [compare, setCompare] = useState(true);
  const [shown, setShown] = useState('sim');
  const [playing, setPlaying] = useState(true);
  const [time, setTime] = useState(0);
  const tRef = useRef(0);

  const cLon = center ? center[0] : null;
  const cLat = center ? center[1] : null;
  useEffect(() => {
    if (cLon !== null) setViewState((v) => ({ ...v, longitude: cLon, latitude: cLat }));
  }, [cLon, cLat]);

  const dureeSim = useMemo(() => {
    let m = 0;
    [base.trips, sim.trips].forEach((list) => list.forEach((t) => {
      const last = t.timestamps[t.timestamps.length - 1];
      if (last > m) m = last;
    }));
    return m > 0 ? Math.ceil(m) : 900;
  }, [base.trips, sim.trips]);

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

  const buildingsLayer = buildings && new GeoJsonLayer({
    id: 'buildings', data: buildings, extruded: true,
    getElevation: (f) => f.properties.height || 10,
    getFillColor: [40, 45, 55], pickable: false,
    material: { ambient: 0.4, diffuse: 0.6, shininess: 32 },
  });

  const panel = (isSim, height) => {
    const side = isSim ? sim : base;
    return (
      <MapPanel
        viewState={viewState} onViewStateChange={setViewState} height={height}
        scenario={side.scenario} missing={side.trips.length === 0}
        layers={[buildingsLayer, ...makeLayers(isSim, time)].filter(Boolean)}
      />
    );
  };

  const bk = base.kpi, sk = sim.kpi;
  const impact = bk && sk && bk.temps_trajet_moyen_s
    ? ((sk.temps_trajet_moyen_s - bk.temps_trajet_moyen_s) / bk.temps_trajet_moyen_s) * 100 : null;

  const chip = (active, hex) => ({
    background: active ? hex : 'transparent', color: active ? '#000' : '#fff',
    border: `1px solid ${hex}`, padding: '8px 16px', borderRadius: 20, fontWeight: 'bold', fontSize: 13, cursor: 'pointer',
  });
  const ghost = { background: '#161a22', color: '#fff', border: '1px solid #444', padding: '8px 16px', borderRadius: 20, fontWeight: 'bold', fontSize: 13, cursor: 'pointer' };

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '10px 20px 30px', color: 'white', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, color: '#fff' }}>{title}</h1>
          <p style={{ margin: '2px 0 0 0', color: COLOR_NEUTRAL, fontSize: 13 }}>{subtitle}</p>
        </div>
        <Link to="/" style={{ background: '#333', color: '#fff', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold', border: '1px solid #555' }}>
          ← Vue principale
        </Link>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 12, maxWidth: 1500, margin: '0 auto 12px', background: 'rgba(255,255,255,0.02)', padding: '8px 16px', borderRadius: 12, border: '1px solid rgba(255,255,255,0.05)' }}>
        <span style={{ color: COLOR_NEUTRAL, fontSize: 13, fontWeight: 'bold', letterSpacing: 1 }}>SCÉNARIO :</span>
        {!compare && (
          <>
            <button onClick={() => setShown('base')} style={chip(shown === 'base', base.scenario.hex)}>{base.scenario.label}</button>
            <button onClick={() => setShown('sim')} style={chip(shown === 'sim', sim.scenario.hex)}>{sim.scenario.label}</button>
          </>
        )}
        {compare && <span style={{ color: sim.scenario.hex, fontWeight: 'bold', fontSize: 13 }}>{sim.scenario.label}</span>}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          {compare && impact !== null && (
            <span style={{ fontSize: 12, color: impact > 0 ? COLOR_BAD : COLOR_GOOD, background: impact > 0 ? 'rgba(255,75,75,0.1)' : 'rgba(75,211,123,0.1)', padding: '4px 10px', borderRadius: 20, border: `1px solid ${impact > 0 ? COLOR_BAD : COLOR_GOOD}44`, fontWeight: 'bold' }}>
              Impact Temps : {impact > 0 ? '+' : ''}{impact.toFixed(1)} %
            </span>
          )}
          {center && (
            <button style={ghost} onClick={() => setViewState((v) => ({ ...v, longitude: center[0], latitude: center[1], zoom: 18.2, pitch: 55, transitionDuration: 1500 }))}>
              {zoomLabel}
            </button>
          )}
          <button style={ghost} onClick={() => setPlaying((p) => !p)}>{playing ? '⏸ Pause' : '▶ Lecture'}</button>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', background: compare ? 'rgba(60, 210, 255, 0.15)' : 'transparent', border: `1px solid ${compare ? '#3cd2ff' : '#444'}`, padding: '4px 12px', borderRadius: 30 }}>
            <span style={{ fontSize: 12, fontWeight: 'bold', color: compare ? '#3cd2ff' : COLOR_NEUTRAL }}>MODE COMPARAISON</span>
            <div style={{ width: 32, height: 18, background: compare ? '#3cd2ff' : '#444', borderRadius: 20, position: 'relative' }}>
              <div style={{ width: 14, height: 14, background: 'white', borderRadius: '50%', position: 'absolute', top: 2, left: compare ? 16 : 2, transition: 'all 0.3s' }} />
            </div>
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} style={{ display: 'none' }} />
          </label>
        </div>
      </div>

      {legend && (
        <div style={{ maxWidth: 1500, margin: '0 auto 10px', fontSize: 12, color: '#cfd8e3', display: 'flex', gap: 18, flexWrap: 'wrap' }}>
          {legend}
          <span style={{ color: COLOR_NEUTRAL }}>t = {Math.round(time)} s / {dureeSim} s</span>
        </div>
      )}

      <div style={{ maxWidth: 1500, margin: '0 auto' }}>
        {compare ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {panel(false, 480)}
            {panel(true, 480)}
          </div>
        ) : (
          panel(shown === 'sim', 520)
        )}
        <div style={{ marginTop: 12 }}>
          <KpiTable base={base} sim={sim} />
        </div>
        {extra && <div style={{ marginTop: 12 }}>{extra}</div>}
      </div>
    </div>
  );
}