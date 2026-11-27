import React, { useState, useEffect, useMemo } from 'react';
import { GeoJsonLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import ComparePage, { Ligne, Section, fetchJson, prepareTrips, COLOR_NEUTRAL } from './ComparePage.jsx';

const BASE = { id: 'actuel_bus', label: 'Situation actuelle', hex: '#3cd2ff' };
const SIM = { id: 'voie_reservee', label: 'Voie réservée aux bus', hex: '#4bd37b' };

const TRONCONS_AXE = ['4330541#3', '4330541#7', '4330541#9', '4330541#10', '4330541#11', '4330541#12', '4330541#15', '4330541#18'];
const DIX_TIRAGES = {
  voituresAxe: { ecart: '+22,4 s (+7 %)', ecartType: '8,5 s', detail: 'plus lentes dans 10 tirages sur 10' },
  bus: { ecart: '−20,8 s (−9 %)', ecartType: '10,4 s', detail: 'plus rapides dans 10 tirages sur 10' },
};

const moyenneAxe = (kpi) => {
  if (!kpi || !kpi.congestion_par_rue) return null;
  const vals = TRONCONS_AXE.map((id) => kpi.congestion_par_rue[id]).filter((v) => v !== undefined);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
};

export default function AppVoieReservee() {
  const [data, setData] = useState(null);

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
    ]).then(([buildings, tA, tV, kA, kV, bA, bV, kpiAxe, axe]) =>
      setData({ buildings, tA: prepareTrips(tA), tV: prepareTrips(tV), kA, kV, bA, bV, kpiAxe, axe }));
  }, []);

  const axeFC = useMemo(() => {
    if (!data || !data.axe) return null;
    const pick = (kind) => ({ type: 'FeatureCollection', features: data.axe.features.filter((f) => f.properties.kind === kind) });
    return { axe: pick('axe'), voie: pick('voie_reservee') };
  }, [data]);

  const center = useMemo(() => {
    if (!axeFC) return null;
    const pts = axeFC.axe.features.flatMap((f) => f.geometry.coordinates);
    if (!pts.length) return null;
    return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  }, [axeFC]);

  if (!data) {
    return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;
  }

  const makeLayers = (isSim, time) => {
    const trips = isSim ? data.tV : data.tA;
    const cars = trips.filter((t) => t.type !== 'bus');
    const buses = trips.filter((t) => t.type === 'bus');
    const layers = [];
    if (axeFC) {
      layers.push(new GeoJsonLayer({
        id: 'axe', data: axeFC.axe, stroked: true, filled: false,
        getLineColor: isSim ? [150, 150, 150, 200] : [255, 215, 0, 255],
        lineWidthUnits: 'meters', getLineWidth: isSim ? 0.6 : 6, lineWidthMinPixels: isSim ? 1 : 4,
        parameters: { depthCompare: 'always' },
      }));
      if (isSim) {
        layers.push(new GeoJsonLayer({
          id: 'voie-reservee', data: axeFC.voie, stroked: true, filled: false,
          getLineColor: [40, 220, 120, 255], lineWidthUnits: 'meters', getLineWidth: 3, lineWidthMinPixels: 3,
          parameters: { depthCompare: 'always' },
        }));
      }
    }
    layers.push(new TripsLayer({
      id: 'cars', data: cars, getPath: (d) => d.path, getTimestamps: (d) => d.timestamps,
      getColor: [60, 210, 255], widthUnits: 'meters', getWidth: 1.8, widthMinPixels: 3, rounded: true, trailLength: 60, currentTime: time,
    }));
    layers.push(new TripsLayer({
      id: 'buses', data: buses, getPath: (d) => d.path, getTimestamps: (d) => d.timestamps,
      getColor: [255, 150, 0], widthUnits: 'meters', getWidth: 2.5, widthMinPixels: 5, rounded: true, trailLength: 120, currentTime: time,
    }));
    return layers;
  };

  const { kA, kV, bA, bV, kpiAxe } = data;
  const nbBusA = data.tA.filter((t) => t.type === 'bus').length;
  const nbBusV = data.tV.filter((t) => t.type === 'bus').length;

  const legend = (
    <>
      <span><span style={{ color: '#3cd2ff' }}>●</span> Voitures</span>
      <span><span style={{ color: '#ff9600' }}>●</span> Bus (actuel : {nbBusA} · voie réservée : {nbBusV})</span>
      <span><span style={{ color: '#ffd700' }}>━</span> Axe étudié (actuel)</span>
      <span><span style={{ color: '#28dc78' }}>━</span> Voie réservée aux bus</span>
    </>
  );

  const extra = (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 12 }}>
      <Section titre="Axe 4330541 (tirage 1)" cols={['Actuel', 'Voie réservée']}
        note="Congestion de l'axe : moyenne des 8 tronçons. Elle reste élevée dans les deux cas : le blocage vient surtout des feux.">
        {kpiAxe && <Ligne label={`Voitures de l'axe (${kpiAxe.actuel_bus?.n ?? '?'})`} a={kpiAxe.actuel_bus?.duree_moyenne_s} b={kpiAxe.voie_reservee?.duree_moyenne_s} unite=" s" />}
        <Ligne label="Congestion de l'axe" a={moyenneAxe(kA)} b={moyenneAxe(kV)} facteur={100} digits={0} unite=" %" />
      </Section>
      <Section titre={`Bus de l'axe (${bV?.axe_bus_termines ?? '?'}, tirage 1)`} cols={['Actuel', 'Voie réservée']}
        note="Bus dont la ligne emprunte l'axe, comparés sur les mêmes bus dans les deux scénarios.">
        <Ligne label="Temps de trajet moyen" a={bA?.axe_duree_moyenne_s} b={bV?.axe_duree_moyenne_s} unite=" s" />
        <Ligne label="Attente moyenne" a={bA?.axe_attente_moyenne_s} b={bV?.axe_attente_moyenne_s} unite=" s" />
      </Section>
      <div style={{ background: 'rgba(10, 15, 25, 0.85)', border: '1px solid #333', borderRadius: 12, padding: 14, fontSize: 13, lineHeight: 1.6 }}>
        <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 6 }}>Conclusion (10 tirages, ancien modèle : une seule ligne de bus)</div>
        <div>Voitures de l'axe : <b style={{ color: '#ffb347' }}>{DIX_TIRAGES.voituresAxe.ecart}</b>, écart-type {DIX_TIRAGES.voituresAxe.ecartType}, {DIX_TIRAGES.voituresAxe.detail}.</div>
        <div>Bus : <b style={{ color: '#4ade80' }}>{DIX_TIRAGES.bus.ecart}</b>, écart-type {DIX_TIRAGES.bus.ecartType}, {DIX_TIRAGES.bus.detail}.</div>
        <div style={{ color: COLOR_NEUTRAL, fontSize: 11, marginTop: 6 }}>
          Hypothèses : 1 bus toutes les 5 min, pas de priorité aux feux. Les chiffres du tirage 1 servent à la démo, les conclusions viennent des 10 tirages.
        </div>
      </div>
    </div>
  );

  return (
    <ComparePage
      title="Scénario : voie réservée aux bus"
      subtitle="Rabat Hassan, axe 4330541. Données de trafic simulées (SUMO), pas observées. Animation : tirage 1."
      base={{ scenario: BASE, trips: data.tA, kpi: kA }}
      sim={{ scenario: SIM, trips: data.tV, kpi: kV }}
      buildings={data.buildings} center={center} makeLayers={makeLayers}
      legend={legend} extra={extra} zoomLabel="🔍 Zoom sur l'axe"
    />
  );
}