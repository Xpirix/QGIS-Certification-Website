import maplibregl from 'maplibre-gl';
import Feature from 'ol/Feature';
import Map from 'ol/Map';
import Overlay from 'ol/Overlay';
import View from 'ol/View';
import {defaults as defaultControls} from 'ol/control/defaults';
import Polygon from 'ol/geom/Polygon';
import TileLayer from 'ol/layer/Tile';
import VectorLayer from 'ol/layer/Vector';
import {fromLonLat} from 'ol/proj';
import {getVectorContext} from 'ol/render';
import OSM from 'ol/source/OSM';
import VectorSource from 'ol/source/Vector';
import Fill from 'ol/style/Fill';
import Stroke from 'ol/style/Stroke';
import Style from 'ol/style/Style';

import {MapModal} from './modal';
import {equalEarth} from './projection';

const OCEAN = '#aad3df';
const OCEAN_LINE = '#8fb8c4';
const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const REDUCE_MOTION = window.matchMedia(
  '(prefers-reduced-motion: reduce)',
).matches;

let osmProtocolRegistered = false;

/**
 * Let MapLibre fetch OSM tiles with a referrer. The site sends
 * Referrer-Policy: same-origin, and OSM refuses tiles without one.
 */
function registerOsmProtocol() {
  if (osmProtocolRegistered) {
    return;
  }
  osmProtocolRegistered = true;
  maplibregl.addProtocol('osm', async (params, abortController) => {
    const response = await fetch(params.url.replace('osm://', 'https://'), {
      referrerPolicy: 'origin',
      signal: abortController.signal,
    });
    if (!response.ok) {
      throw new Error(`Tile request failed with status ${response.status}`);
    }
    return {data: await response.arrayBuffer()};
  });
}

/**
 * Globe and flat map views with a toggle between them, after the maps on
 * qgis.org. The flat map is Equal Earth, the globe is MapLibre.
 *
 * Subclasses draw their content through the hooks: onGlobeLoad, onFlatLoad,
 * fitGlobe, fitFlat, onFlatClick, restoreSelection, clearSelection,
 * readExtraUrlState and writeExtraUrlState.
 */
export class GlobeFlatMap {
  /**
   * @param {HTMLElement} container The map container from the template.
   * @param {{globeCenter?: Array<number>, globeZoom?: number, rotate?: boolean}} [options]
   *   Where the globe starts, and whether it turns while idle.
   */
  constructor(container, {globeCenter = [10, 30], globeZoom = 2.2, rotate = true} = {}) {
    this.container = container;
    this.globeElement = container.querySelector('.map-globe-view');
    this.flatElement = container.querySelector('.map-flat-view');
    this.toggles = [...container.querySelectorAll('.map-view-toggle')];
    this.globeCenter = globeCenter;
    this.globeZoom = globeZoom;
    this.rotate = rotate && !REDUCE_MOTION;

    this.currentView = 'flat';
    this.globeMap = null;
    this.flatMap = null;
    this.flatProjection = equalEarth();
    this.globeMarkers = [];
    this.isRotating = false;
    this.rotationFrame = null;

    this.modal = new MapModal(() => {
      this.clearSelection();
      this.updateUrlState();
    });
  }

  /**
   * Read the URL, wire the toggle buttons and show the first view.
   */
  init() {
    this.readUrlState();
    for (const toggle of this.toggles) {
      toggle.addEventListener('click', () => this.switchView(toggle.dataset.view));
    }
    this.showView(this.currentView);
  }

  onGlobeLoad() {}
  onFlatLoad() {}
  fitGlobe() {}
  fitFlat() {}
  onFlatClick() {
    return false;
  }
  restoreSelection() {}
  clearSelection() {}
  readExtraUrlState() {}
  writeExtraUrlState() {}

  /**
   * @param {string} view Either globe or flat.
   */
  switchView(view) {
    this.currentView = view === 'globe' ? 'globe' : 'flat';
    this.updateUrlState();
    this.showView(this.currentView);
  }

  /**
   * Show one view, building its map the first time it is needed.
   *
   * @param {string} view Either globe or flat.
   */
  showView(view) {
    const globe = view === 'globe';
    this.globeElement.hidden = !globe;
    this.flatElement.hidden = globe;
    for (const toggle of this.toggles) {
      const active = toggle.dataset.view === view;
      toggle.classList.toggle('is-active', active);
      toggle.setAttribute('aria-pressed', String(active));
    }

    if (globe) {
      if (this.globeMap) {
        this.globeMap.resize();
        this.updateMarkerVisibility();
      } else {
        this.initGlobe();
      }
    } else {
      this.stopRotation();
      if (this.flatMap) {
        this.flatMap.updateSize();
      } else {
        this.initFlat();
      }
    }
  }

  initGlobe() {
    registerOsmProtocol();
    this.globeMap = new maplibregl.Map({
      container: this.globeElement,
      center: this.globeCenter,
      zoom: this.globeZoom,
      maxZoom: 18,
      minZoom: 0,
      attributionControl: {compact: true},
      style: {
        version: 8,
        projection: {type: 'globe'},
        sources: {
          osm: {
            type: 'raster',
            tiles: ['osm://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            maxzoom: 19,
            attribution: OSM_ATTRIBUTION,
          },
        },
        layers: [{id: 'osm', type: 'raster', source: 'osm'}],
        sky: {
          'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0],
        },
      },
    });
    this.globeMap.addControl(
      new maplibregl.NavigationControl({showCompass: false}),
      'top-left',
    );

    this.globeMap.on('load', () => {
      this.onGlobeLoad();
      this.fitGlobe();
      this.globeMap.on('move', () => this.updateMarkerVisibility());
      this.updateMarkerVisibility();
      if (this.currentView === 'globe') {
        this.restoreSelection();
        window.setTimeout(() => this.startRotation(), 500);
      }
    });

    for (const event of ['mousedown', 'touchstart', 'wheel', 'dblclick']) {
      this.globeMap.on(event, () => this.stopRotation());
    }
  }

  /**
   * @param {HTMLElement} markerElement The marker.
   * @param {Array<number>} lonLat Longitude and latitude.
   */
  addGlobeMarker(markerElement, lonLat) {
    const marker = new maplibregl.Marker({element: markerElement, anchor: 'center'})
      .setLngLat(lonLat)
      .addTo(this.globeMap);
    this.globeMarkers.push({marker, lonLat, element: markerElement});
  }

  initFlat() {
    const projection = this.flatProjection;
    const extent = projection.getExtent();
    const view = new View({
      projection,
      center: fromLonLat([0, 20], projection),
      extent,
      constrainOnlyCenter: true,
      showFullExtent: true,
      enableRotation: false,
    });

    const outline = this.worldOutline();
    const tiles = new TileLayer({
      source: new OSM({
        tileLoadFunction: (tile, src) => {
          const image = tile.getImage();
          image.referrerPolicy = 'origin';
          image.src = src;
        },
      }),
    });
    // Reprojected tiles stop at 85 degrees and come out jagged, so clip them to the world outline.
    const mask = new Style({fill: new Fill({color: 'black'})});
    tiles.on('postrender', (event) => {
      const context = event.context;
      context.globalCompositeOperation = 'destination-in';
      getVectorContext(event).drawFeature(outline, mask);
      context.globalCompositeOperation = 'source-over';
    });

    this.flatMap = new Map({
      target: this.flatElement,
      controls: defaultControls({rotate: false}),
      layers: [
        new VectorLayer({
          source: new VectorSource({features: [outline]}),
          style: new Style({
            fill: new Fill({color: OCEAN}),
            stroke: new Stroke({color: OCEAN_LINE, width: 1}),
          }),
        }),
        tiles,
      ],
      view,
    });
    view.fit(extent, {padding: [8, 8, 8, 8]});
    view.setMinZoom(view.getZoom());

    this.flatMap.on('singleclick', (event) => {
      if (!event.originalEvent.target.closest('.map-marker')) {
        this.onFlatClick(event);
      }
    });

    this.onFlatLoad();
    this.fitFlat();
    this.restoreSelection();
  }

  /**
   * @returns {Feature} The edge of the Equal Earth world, meridians 180 east and west.
   */
  worldOutline() {
    const ring = [];
    for (let lat = -90; lat <= 90; lat += 1) {
      ring.push([180, lat]);
    }
    for (let lat = 90; lat >= -90; lat -= 1) {
      ring.push([-180, lat]);
    }
    return new Feature(
      new Polygon([ring.map((lonLat) => fromLonLat(lonLat, this.flatProjection))]),
    );
  }

  /**
   * @param {HTMLElement} markerElement The marker.
   * @param {Array<number>} lonLat Longitude and latitude.
   */
  addFlatMarker(markerElement, lonLat) {
    this.flatMap.addOverlay(
      new Overlay({
        element: markerElement,
        position: fromLonLat(lonLat, this.flatProjection),
        positioning: 'center-center',
        stopEvent: false,
      }),
    );
  }

  /**
   * @param {Array<number>} lonLat Longitude and latitude.
   * @returns {boolean} Whether the point faces the reader on the globe.
   */
  isOnVisibleHemisphere([lon, lat]) {
    const center = this.globeMap.getCenter();
    let deltaLon = lon - center.lng;
    while (deltaLon > 180) deltaLon -= 360;
    while (deltaLon < -180) deltaLon += 360;

    const toRad = Math.PI / 180;
    const a =
      Math.sin(((lat - center.lat) * toRad) / 2) ** 2 +
      Math.cos(center.lat * toRad) *
        Math.cos(lat * toRad) *
        Math.sin((deltaLon * toRad) / 2) ** 2;
    const distance = (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))) / toRad;
    return distance <= 85;
  }

  updateMarkerVisibility() {
    if (!this.globeMap) {
      return;
    }
    for (const {lonLat, element} of this.globeMarkers) {
      element.classList.toggle('is-behind', !this.isOnVisibleHemisphere(lonLat));
    }
  }

  readUrlState() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('view') === 'globe') {
      this.currentView = 'globe';
    }
    this.readExtraUrlState(params);
  }

  updateUrlState() {
    const params = new URLSearchParams(window.location.search);
    params.set('view', this.currentView);
    this.writeExtraUrlState(params);
    const url = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState(null, '', url);
  }

  startRotation() {
    if (!this.rotate || this.isRotating || !this.globeMap) {
      return;
    }
    this.isRotating = true;
    const secondsPerTurn = 30;
    const maxSpinZoom = 5;
    const slowSpinZoom = 3;

    const turn = () => {
      if (!this.isRotating) {
        return;
      }
      const zoom = this.globeMap.getZoom();
      if (zoom < maxSpinZoom) {
        let degreesPerSecond = 360 / secondsPerTurn;
        if (zoom > slowSpinZoom) {
          degreesPerSecond *= (maxSpinZoom - zoom) / (maxSpinZoom - slowSpinZoom);
        }
        const center = this.globeMap.getCenter();
        center.lng -= degreesPerSecond / 60;
        this.globeMap.easeTo({center, duration: 1000 / 60, easing: (t) => t});
      }
      this.rotationFrame = window.requestAnimationFrame(turn);
    };
    this.rotationFrame = window.requestAnimationFrame(turn);
  }

  stopRotation() {
    this.isRotating = false;
    if (this.rotationFrame) {
      window.cancelAnimationFrame(this.rotationFrame);
      this.rotationFrame = null;
    }
  }
}
