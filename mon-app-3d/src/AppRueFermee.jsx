import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, TextLayer, ScatterplotLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const FALLBACK_VIEW = { longitude: -6.8416, latitude: 34.0209, zoom: 16, pitch: 60, bearing: 20, maxPitch: 85 };
const DUREE_PAR_DEFAUT = 900;
const SECONDES_DE_BOUCLE = 10; // une boucle de la démo dure ~10 s à l'écran

const SCENARIOS = [
  { id: 'actuel_ref', label: 'Situation actuelle', sous: 'Toutes les rues ouvertes' },
  { id: 'rue_fermee', label: 'Rue fermée', sous: 'Avenue Allal Ben Abdellah (~360 m) et ses carrefours' },
];

const fetchJson = (url, fallback) =>
  fetch(url).then(r => (r.ok ? r.json() : fallback)).catch(() => fallback);

const prepareTrips = (raw) =>
  (raw || [])
    .map(v => ({
      id: String(v.id),
      path: v.path.map(p => [p[0], p[1]]),
      timestamps: v.path.map(p => p[2]),
    }))
    .filter(t => t.path.length > 1);

// Tronçons de l'avenue (les rues transversales fermées aux carrefours ont type 'transversale')
const estTransversale = f => !!(f.properties && f.properties.type === 'transversale');
const avenueFeatures = closure => closure.features.filter(f => !estTransversale(f));

const fmtNum = (x, digits) => (x === null || x === undefined ? '–' : x.toFixed(digits).replace('.', ','));
const fmtSigne = (x, digits = 1) => (x === null || x === undefined ? '–' : `${x > 0 ? '+' : x < 0 ? '−' : ''}${fmtNum(Math.abs(x), digits)}`);

// Carte d'un indicateur.
// Situation actuelle : valeur de l'indicateur. Rue fermée : valeur du scénario + écart par rapport à l'actuelle.
// meilleur : 'bas' (une baisse est une amélioration), 'haut', ou 'neutre' (pas de bon sens)
function Carte({ titre, a, b, ferme, digits = 1, unite = '', facteur = 1, meilleur = 'bas', pct = true }) {
  const ok = [a, b].every(v => v !== null && v !== undefined);
  const va = a !== null && a !== undefined ? a * facteur : null;
  const vb = b !== null && b !== undefined ? b * facteur : null;
  const d = ok ? vb - va : null;
  const rel = ok && pct && va !== 0 ? (d / va) * 100 : null;
  const nul = d === null || Math.abs(d) < Math.pow(10, -digits);
  const bon = !nul && ((meilleur === 'bas' && d < 0) || (meilleur === 'haut' && d > 0));
  const couleur = nul || meilleur === 'neutre' ? '#c9d4e2' : bon ? '#4ade80' : '#ffb347';
  const fleche = nul ? '＝' : d > 0 ? '▲' : '▼';
  return (
    <div style={{ background: '#161a22', border: `1px solid ${ferme ? 'rgba(255,40,40,0.35)' : '#2a3140'}`, borderRadius: 8, padding: '8px 10px' }}>
      <div style={{ color: '#8a9bb0', fontSize: 11 }}>{titre}</div>
      <div style={{ color: '#ffffff', fontSize: 22, fontWeight: 'bold', lineHeight: 1.25 }}>
        {fmtNum(ferme ? vb : va, digits)}{unite}
      </div>
      {ferme ? (
        <div style={{ fontSize: 11.5, color: couleur, fontWeight: 'bold' }}>
          {fleche} {fmtSigne(d, digits)}{unite}{rel !== null ? ` (${fmtSigne(rel, 1)} %)` : ''}
          <span style={{ color: '#8a9bb0', fontWeight: 'normal' }}> vs actuel ({fmtNum(va, digits)}{unite})</span>
        </div>
      ) : (
        <div style={{ fontSize: 11, color: '#8a9bb0' }}>Situation actuelle</div>
      )}
    </div>
  );
}

// Effet sur les autres rues : compare la congestion de chaque rue mesurée dans les deux scénarios
function effetRues(kA, kF, seuil = 0.10) {
  const a = kA && kA.congestion_par_rue;
  const f = kF && kF.congestion_par_rue;
  if (!a || !f) return null;
  const diffs = Object.keys(a).filter(e => e in f).map(e => ({ rue: e, avant: a[e], apres: f[e], d: f[e] - a[e] }));
  return {
    n: diffs.length,
    plus: diffs.filter(x => x.d >= seuil).length,
    moins: diffs.filter(x => x.d <= -seuil).length,
    top: [...diffs].sort((x, y) => y.d - x.d).slice(0, 3).filter(x => x.d >= seuil),
    seuil,
  };
}

export default function AppRueFermee() {
  const [viewState, setViewState] = useState(FALLBACK_VIEW);
  const [scenario, setScenario] = useState('actuel_ref');
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const tRef = useRef(0);

  // Les deux scénarios sont chargés au démarrage : le bouton change ensuite instantanément
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
    ]).then(([buildings, tA, tF, kA, kF, kpiAxe, tirages, closureOsm, troncons]) => {
      setData({
        buildings,
        trips: { actuel_ref: prepareTrips(tA), rue_fermee: prepareTrips(tF) },
        kpi: { actuel_ref: kA, rue_fermee: kF },
        kpiAxe, tirages,
        // dessin exact des troncons fermes (SUMO) ; a defaut, trace OpenStreetMap
        closure: troncons || closureOsm,
      });
      setLoading(false);
    });
  }, []);

  // Centre de la section fermée
  const centre = useMemo(() => {
    if (!data || !data.closure) return null;
    const pts = avenueFeatures(data.closure).flatMap(f => f.geometry.coordinates);
    if (!pts.length) return null;
    return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  }, [data]);

  useEffect(() => {
    if (centre) setViewState(v => ({ ...v, longitude: centre[0], latitude: centre[1], zoom: 16.3 }));
  }, [centre]);

  // Extrémités de la section (pour les repères visibles à l'écran)
  const extremites = useMemo(() => {
    if (!data || !data.closure) return [];
    const pts = avenueFeatures(data.closure).flatMap(f => f.geometry.coordinates);
    if (pts.length < 2) return [];
    // les tronçons ne sont pas dans l'ordre du tracé : on prend les 2 points les plus éloignés
    let best = [pts[0], pts[1]];
    let max = -1;
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

  if (loading) {
    return <div style={{ color: 'white', padding: 50, background: '#0f1115', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Chargement des données...</div>;
  }

  const ferme = scenario === 'rue_fermee';
  const trips = data.trips[scenario];
  const manque = trips.length === 0;
  const layers = [];

  if (data.buildings) {
    layers.push(new GeoJsonLayer({
      id: 'buildings', data: data.buildings, extruded: true,
      getElevation: f => f.properties.height || 10,
      getFillColor: [40, 45, 55], pickable: false,
      material: { ambient: 0.4, diffuse: 0.6, shininess: 32 },
    }));
  }

  if (data.closure) {
    layers.push(new GeoJsonLayer({
      id: 'closure', data: data.closure, stroked: true, filled: false,
      getLineColor: f => (ferme ? (estTransversale(f) ? [255, 90, 170, 255] : [255, 40, 40, 255]) : [255, 215, 0, 160]),
      lineWidthUnits: 'meters',
      getLineWidth: f => (ferme ? (estTransversale(f) ? 5 : 7) : 3),
      lineWidthMinPixels: ferme ? 5 : 2,
      parameters: { depthCompare: 'always' }, // reste visible meme derriere les batiments
      updateTriggers: { getLineColor: [ferme], getLineWidth: [ferme], lineWidthMinPixels: [ferme] },
    }));
    if (ferme) {
      layers.push(new ScatterplotLayer({
        id: 'closure-ends', data: extremites, getPosition: d => d, getFillColor: [255, 40, 40],
        getLineColor: [255, 255, 255], stroked: true, lineWidthMinPixels: 2,
        radiusUnits: 'pixels', getRadius: 8, parameters: { depthCompare: 'always' },
      }));
    }
  }
  if (centre) {
    layers.push(new TextLayer({
      id: 'closure-label', data: [{ position: [centre[0], centre[1], 30] }],
      getPosition: d => d.position,
      getText: () => (ferme ? 'Avenue Allal Ben Abdellah : FERMEE' : 'Avenue Allal Ben Abdellah : ouverte'),
      getSize: 13, getColor: [255, 255, 255, 255], getBackgroundColor: [20, 25, 35, 220],
      backgroundPadding: [5, 3], getTextAnchor: 'middle', getAlignmentBaseline: 'bottom',
      getPixelOffset: [0, -20], billboard: true,
      updateTriggers: { getText: [ferme] },
    }));
  }

  layers.push(new TripsLayer({
    id: 'cars', data: trips, getPath: d => d.path, getTimestamps: d => d.timestamps,
    getColor: d => (concernees.has(d.id) ? [255, 159, 67] : [60, 210, 255]),
    widthUnits: 'meters', getWidth: d => (concernees.has(d.id) ? 2.6 : 1.8), widthMinPixels: 3, rounded: true,
    trailLength: 60, currentTime: time,
    updateTriggers: { getColor: [concernees], getWidth: [concernees] },
  }));

  const kA = data.kpi.actuel_ref;
  const kF = data.kpi.rue_fermee;
  const axe = data.kpiAxe;
  const tir = data.tirages;
  const rues = effetRues(kA, kF);

  return (
    <div style={{ minHeight: '100vh', background: '#0f1115', padding: '20px 40px', color: 'white', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 26, color: '#fff' }}>Scénario : rue fermée</h1>
          <p style={{ margin: '5px 0 0', color: '#8a9bb0', fontSize: 14 }}>
            Rabat Hassan, Avenue Allal Ben Abdellah. Données de trafic simulées (SUMO), pas observées. Animation : tirage 1.
          </p>
        </div>
        <Link to="/" style={{ background: '#333', color: '#fff', padding: '10px 20px', textDecoration: 'none', borderRadius: 6, fontWeight: 'bold', border: '1px solid #555' }}>
          ← Vue principale
        </Link>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        {SCENARIOS.map(s => (
          <button key={s.id} onClick={() => setScenario(s.id)} style={{
            flex: 1, maxWidth: 320, textAlign: 'left', cursor: 'pointer', padding: '10px 14px', borderRadius: 8,
            border: scenario === s.id ? `2px solid ${s.id === 'rue_fermee' ? '#ff2828' : '#3cd2ff'}` : '1px solid #333',
            background: scenario === s.id ? (s.id === 'rue_fermee' ? 'rgba(255,40,40,0.12)' : 'rgba(60,210,255,0.12)') : '#161a22',
            color: 'white',
          }}>
            <div style={{ fontWeight: 'bold', fontSize: 14 }}>{s.label}</div>
            <div style={{ fontSize: 12, color: '#8a9bb0' }}>{s.sous}</div>
          </button>
        ))}
        {centre && (
          <button onClick={() => setViewState(v => ({ ...v, longitude: centre[0], latitude: centre[1], zoom: 18.2, pitch: 55 }))}
            style={{ marginLeft: 'auto', cursor: 'pointer', padding: '0 18px', borderRadius: 8, border: '1px solid #ff6b6b', background: '#161a22', color: '#ff6b6b' }}>
            🔍 Zoom sur la rue
          </button>
        )}
        <button onClick={() => setPlaying(p => !p)} style={{ marginLeft: centre ? 0 : 'auto', cursor: 'pointer', padding: '0 18px', borderRadius: 8, border: '1px solid #333', background: '#161a22', color: 'white' }}>
          {playing ? '⏸ Pause' : '▶ Lecture'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ position: 'relative', flex: 1, height: 640, borderRadius: 12, overflow: 'hidden', border: '1px solid #333', boxShadow: '0 10px 30px rgba(0,0,0,0.5)', background: '#000' }}>
          <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, background: 'rgba(10,15,25,0.85)', padding: '8px 12px', borderRadius: 6, fontSize: 12, lineHeight: 1.6 }}>
            <div><span style={{ color: '#3cd2ff' }}>●</span> Voitures ({trips.length})</div>
            <div><span style={{ color: '#ff9f43' }}>●</span> Voitures qui passaient par la rue ({concernees.size})</div>
            <div><span style={{ color: ferme ? '#ff2828' : '#ffd700' }}>━</span> {ferme ? 'Avenue fermée' : 'Rue étudiée (ouverte)'}</div>
            {ferme && data.closure && data.closure.features.some(estTransversale) && (
              <div><span style={{ color: '#ff5aaa' }}>━</span> Rues transversales fermées aux carrefours</div>
            )}
            <div style={{ color: '#8a9bb0' }}>t = {Math.round(time)} s / {dureeSim} s</div>
          </div>
          {manque && (
            <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10, background: 'rgba(120,30,30,0.9)', padding: '8px 12px', borderRadius: 6, fontSize: 12, maxWidth: 320 }}>
              Trajectoires introuvables : lancer scenario_rue_fermee.ps1 (voir scenario_rue_fermee.md).
            </div>
          )}
          <div style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 10, background: 'rgba(10,15,25,0.85)', padding: '5px 10px', borderRadius: 6, fontSize: 11, color: '#ffb347' }}>
            Données simulées (SUMO)
          </div>
          <DeckGL viewState={viewState} onViewStateChange={({ viewState }) => setViewState(viewState)} controller layers={layers}
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
            <Map mapStyle={MAP_STYLE} style={{ width: '100%', height: '100%' }} />
          </DeckGL>
        </div>

        <div style={{ width: 400, maxHeight: 640, overflowY: 'auto', background: 'rgba(10,15,25,0.85)', padding: 16, borderRadius: 12, border: '1px solid rgba(60,210,255,0.3)' }}>
          <div style={{ color: ferme ? '#ff6b6b' : '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 2 }}>
            {ferme ? 'Indicateurs : rue fermée' : 'Indicateurs : situation actuelle'}
          </div>
          <div style={{ color: '#8a9bb0', fontSize: 11, marginBottom: 8 }}>
            {ferme
              ? 'Tirage 1. Écart par rapport à la situation actuelle (vert : amélioration, orange : dégradation).'
              : 'Tirage 1. Toutes les rues ouvertes.'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
            <Carte ferme={ferme} titre="Temps de trajet moyen (réseau)" a={kA?.temps_trajet_moyen_s} b={kF?.temps_trajet_moyen_s} unite=" s" />
            <Carte ferme={ferme} titre="Vitesse moyenne" a={kA?.vitesse_moyenne_kmh} b={kF?.vitesse_moyenne_kmh} unite=" km/h" meilleur="haut" />
            <Carte ferme={ferme} titre="Congestion moyenne" a={kA?.congestion_moyenne} b={kF?.congestion_moyenne} facteur={100} unite=" pt" pct={false} />
            <Carte ferme={ferme} titre="CO₂ total" a={kA?.co2_total_g} b={kF?.co2_total_g} facteur={0.001} unite=" kg" />
            <Carte ferme={ferme} titre="Trajets terminés" a={kA?.trajets_termines} b={kF?.trajets_termines} digits={0} meilleur="neutre" />
            <Carte ferme={ferme} titre="Voitures de la rue (durée)" a={axe?.actuel_ref?.duree_moyenne_s} b={axe?.rue_fermee?.duree_moyenne_s} unite=" s" />
          </div>

          {axe && (
            <div style={{ color: '#8a9bb0', fontSize: 11, marginBottom: 12, lineHeight: 1.4 }}>
              {ferme ? (
                <>
                  {axe.voitures_axe} voitures de la demande passent par la section fermée : {axe.deviees} déviées, {axe.sans_itineraire} sans
                  itinéraire possible (départ ou arrivée dans la zone fermée, donc retirées : ce qui explique les trajets terminés en moins).
                  Durée comparée sur les {axe.comparables} voitures terminées dans les deux cas.
                </>
              ) : (
                <>
                  {axe.voitures_axe} voitures de la demande passent par la section (avenue et carrefours) qui sera fermée dans le
                  scénario « Rue fermée ». Durée calculée sur les {axe.comparables} voitures terminées dans les deux scénarios.
                </>
              )}
            </div>
          )}

          {ferme && rues && (
            <div style={{ marginBottom: 12, fontSize: 12.5, lineHeight: 1.5 }}>
              <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 4 }}>
                Effet sur les autres rues
              </div>
              <div>
                Sur {rues.n} rues mesurées dans les deux cas :{' '}
                <b style={{ color: rues.plus > 0 ? '#ffb347' : '#c9d4e2' }}>{rues.plus} plus congestionnées</b>,{' '}
                <b style={{ color: rues.moins > 0 ? '#4ade80' : '#c9d4e2' }}>{rues.moins} moins congestionnées</b>{' '}
                (variation d'au moins {Math.round(rues.seuil * 100)} points).
              </div>
              {rues.top.length > 0 && (
                <div style={{ color: '#8a9bb0', fontSize: 11, marginTop: 4 }}>
                  Plus fortes hausses (identifiants SUMO) :{' '}
                  {rues.top.map(x => `${x.rue} (${Math.round(x.avant * 100)} % → ${Math.round(x.apres * 100)} %)`).join(' ; ')}
                </div>
              )}
              <div style={{ color: '#8a9bb0', fontSize: 11, marginTop: 4 }}>
                Indicatif : un seul tirage, congestion mesurée par minute sur 15 min.
              </div>
            </div>
          )}

          {ferme && tir && (
            <div style={{ borderTop: '1px solid #2a3140', paddingTop: 10, fontSize: 12.5, lineHeight: 1.5 }}>
              <div style={{ color: '#3cd2ff', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 4 }}>
                Conclusion ({tir.n_tirages} tirages)
              </div>
              <div>
                Voitures de la rue : <b style={{ color: tir.ecart_moyen_axe_s > 0 ? '#ffb347' : '#4ade80' }}>{fmtSigne(tir.ecart_moyen_axe_s)} s</b>,
                {' '}écart-type {fmtNum(tir.ecart_type_axe_s, 1)} s, plus lentes dans {tir.plus_lent} tirages sur {tir.n_tirages}
                {' '}et plus rapides dans {tir.plus_rapide}.
              </div>
              <div>
                Toutes les voitures communes : <b>{fmtSigne(tir.ecart_moyen_tous_s)} s</b>, écart-type {fmtNum(tir.ecart_type_tous_s, 1)} s.
              </div>
              <div style={{ color: '#8a9bb0', fontSize: 11, marginTop: 6 }}>
                Même demande dans les deux cas ; seules les voitures qui passaient par la rue sont déviées. Les chiffres du tirage 1
                servent à la démo, la conclusion vient des {tir.n_tirages} tirages.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}