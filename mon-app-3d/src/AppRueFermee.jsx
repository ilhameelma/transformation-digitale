import React, { useState, useEffect, useMemo } from 'react';
import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import ComparePage, { Ligne, Section, fetchJson, prepareTrips, COLOR_NEUTRAL, COLOR_GOOD, COLOR_BAD } from './ComparePage.jsx';

const BASE = { id: 'actuel_ref', label: 'Situation actuelle', hex: '#3cd2ff' };
const SIM = { id: 'rue_fermee', label: 'Rue fermée', hex: '#ff4b4b' };

const estTransversale = (f) => !!(f.properties && f.properties.type === 'transversale');
const avenueFeatures = (closure) => closure.features.filter((f) => !estTransversale(f));
const sg = (x, d = 1) => `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(x).toFixed(d).replace('.', ',')}`;

function effetRues(kA, kF, seuil = 0.1) {
  const a = kA && kA.congestion_par_rue;
  const f = kF && kF.congestion_par_rue;
  if (!a || !f) return null;
  const diffs = Object.keys(a).filter((e) => e in f).map((e) => ({ rue: e, avant: a[e], apres: f[e], d: f[e] - a[e] }));
  return {
    n: diffs.length, seuil,
    plus: diffs.filter((x) => x.d >= seuil).length,
    moins: diffs.filter((x) => x.d <= -seuil).length,
    top: [...diffs].sort((x, y) => y.d - x.d).slice(0, 3).filter((x) => x.d >= seuil),
  };
}

export default function AppRueFermee() {
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      fetchJson('/data/buildings.geojson', null),
      fetchJson('/data/trajectories_actuel_ref.json', []),
      fetchJson('/data/trajectories_rue_fermee.json', []),
      fetchJson('/data/kpi_actuel_ref.json', null),
      fetchJson('/data/kpi_rue_fermee.json', null),
      fetchJson('/data/kpi_axe_rue_fermee.json', null),
      fetchJson('/data/tirages_rue_fermee.json', null),
      fetchJson('/data/closure.geojson', null),
      fetchJson('/data/rue_fermee_troncons.geojson', null),
    ]).then(([buildings, tA, tF, kA, kF, kpiAxe, tirages, closureOsm, troncons]) =>
      setData({ buildings, tA: prepareTrips(tA), tF: prepareTrips(tF), kA, kF, kpiAxe, tirages, closure: troncons || closureOsm }));
  }, []);

  const center = useMemo(() => {
    if (!data || !data.closure) return null;
    const pts = avenueFeatures(data.closure).flatMap((f) => f.geometry.coordinates);
    if (!pts.length) return null;
    return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  }, [data]);

  const extremites = useMemo(() => {
    if (!data || !data.closure) return [];
    const pts = avenueFeatures(data.closure).flatMap((f) => f.geometry.coordinates);
    if (pts.length < 2) return [];
    let best = [pts[0], pts[1]], max = -1;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2;
        if (d > max) { max = d; best = [pts[i], pts[j]]; }
      }
    }
    return best;
  }, [data]);

  const concernees = useMemo(
    () => new Set(((data && data.kpiAxe && data.kpiAxe.ids_concernees) || []).map(String)),
    [data]
  );

  if (!data) {
    return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;
  }

  const makeLayers = (isSim, time) => {
    const trips = isSim ? data.tF : data.tA;
    const layers = [];
    if (data.closure) {
      layers.push(new GeoJsonLayer({
        id: 'closure', data: data.closure, stroked: true, filled: false,
        getLineColor: (f) => (isSim ? (estTransversale(f) ? [255, 90, 170, 255] : [255, 40, 40, 255]) : [255, 215, 0, 160]),
        lineWidthUnits: 'meters',
        getLineWidth: (f) => (isSim ? (estTransversale(f) ? 5 : 7) : 3),
        lineWidthMinPixels: isSim ? 5 : 2,
        parameters: { depthCompare: 'always' },
        updateTriggers: { getLineColor: [isSim], getLineWidth: [isSim], lineWidthMinPixels: [isSim] },
      }));
      if (isSim) {
        layers.push(new ScatterplotLayer({
          id: 'closure-ends', data: extremites, getPosition: (d) => d, getFillColor: [255, 40, 40],
          getLineColor: [255, 255, 255], stroked: true, lineWidthMinPixels: 2,
          radiusUnits: 'pixels', getRadius: 8, parameters: { depthCompare: 'always' },
        }));
      }
    }
    layers.push(new TripsLayer({
      id: 'cars', data: trips, getPath: (d) => d.path, getTimestamps: (d) => d.timestamps,
      getColor: (d) => (concernees.has(d.id) ? [255, 159, 67] : [60, 210, 255]),
      widthUnits: 'meters', getWidth: (d) => (concernees.has(d.id) ? 2.6 : 1.8), widthMinPixels: 3, rounded: true,
      trailLength: 60, currentTime: time,
    }));
    return layers;
  };

  const { kA, kF, kpiAxe: axe, tirages: tir } = data;
  const rues = effetRues(kA, kF);
  const aTransv = data.closure && data.closure.features.some(estTransversale);

  const legend = (
    <>
      <span><span style={{ color: '#3cd2ff' }}>●</span> Voitures</span>
      <span><span style={{ color: '#ff9f43' }}>●</span> Voitures qui passaient par la rue ({concernees.size})</span>
      <span><span style={{ color: '#ff2828' }}>━</span> Avenue fermée (jaune = ouverte, à gauche)</span>
      {aTransv && <span><span style={{ color: '#ff5aaa' }}>━</span> Transversales fermées aux carrefours</span>}
    </>
  );

  const extra = (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 12 }}>
      {axe && (
        <Section titre="Voitures de la rue (tirage 1)" cols={['Actuel', 'Rue fermée']}
          note={`${axe.voitures_axe} voitures passent par la section : ${axe.deviees} déviées, ${axe.sans_itineraire} sans itinéraire possible (départ ou arrivée dans la zone fermée, donc retirées : cela explique les trajets terminés en moins). Durée comparée sur les ${axe.comparables} voitures terminées dans les deux cas.`}>
          <Ligne label="Durée moyenne" a={axe.actuel_ref?.duree_moyenne_s} b={axe.rue_fermee?.duree_moyenne_s} unite=" s" />
        </Section>
      )}
      {rues && (
        <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 14, fontSize: 13, lineHeight: 1.6 }}>
          <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 6 }}>Effet sur les autres rues</div>
          <div>
            Sur {rues.n} rues mesurées dans les deux cas :{' '}
            <b style={{ color: rues.plus > 0 ? COLOR_BAD : '#c9d4e2' }}>{rues.plus} plus congestionnées</b>,{' '}
            <b style={{ color: rues.moins > 0 ? COLOR_GOOD : '#c9d4e2' }}>{rues.moins} moins congestionnées</b>{' '}
            (variation d'au moins {Math.round(rues.seuil * 100)} points).
          </div>
          {rues.top.length > 0 && (
            <div style={{ color: COLOR_NEUTRAL, fontSize: 11, marginTop: 4 }}>
              Plus fortes hausses (identifiants SUMO) : {rues.top.map((x) => `${x.rue} (${Math.round(x.avant * 100)} % → ${Math.round(x.apres * 100)} %)`).join(' ; ')}
            </div>
          )}
          <div style={{ color: COLOR_NEUTRAL, fontSize: 11, marginTop: 4 }}>Indicatif : un seul tirage, congestion mesurée par minute sur 15 min.</div>
        </div>
      )}
      {tir && (
        <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 14, fontSize: 13, lineHeight: 1.6 }}>
          <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 6 }}>Conclusion ({tir.n_tirages} tirages)</div>
          <div>
            Voitures de la rue : <b style={{ color: tir.ecart_moyen_axe_s > 0 ? '#ffb347' : '#4ade80' }}>{sg(tir.ecart_moyen_axe_s)} s</b>,
            {' '}écart-type {tir.ecart_type_axe_s.toFixed(1).replace('.', ',')} s, plus lentes dans {tir.plus_lent} tirages sur {tir.n_tirages} et plus rapides dans {tir.plus_rapide}.
          </div>
          <div>Toutes les voitures communes : <b>{sg(tir.ecart_moyen_tous_s)} s</b>, écart-type {tir.ecart_type_tous_s.toFixed(1).replace('.', ',')} s.</div>
          <div style={{ color: COLOR_NEUTRAL, fontSize: 11, marginTop: 6 }}>
            Même demande dans les deux cas ; seules les voitures qui passaient par la rue sont déviées. Les chiffres du tirage 1 servent à la démo, la conclusion vient des {tir.n_tirages} tirages.
          </div>
        </div>
      )}
    </div>
  );

  return (
    <ComparePage
      title="Scénario : rue fermée"
      subtitle="Rabat Hassan, Avenue Allal Ben Abdellah. Données de trafic simulées (SUMO), pas observées. Animation : tirage 1."
      base={{ scenario: BASE, trips: data.tA, kpi: kA }}
      sim={{ scenario: SIM, trips: data.tF, kpi: kF }}
      buildings={data.buildings} center={center} makeLayers={makeLayers}
      legend={legend} extra={extra} zoomLabel="🔍 Zoom sur la rue"
    />
  );
}