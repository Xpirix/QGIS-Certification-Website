import Overlay from 'ol/Overlay';
import {createEmpty, extend, extendCoordinate, isEmpty} from 'ol/extent';
import WKT from 'ol/format/WKT';
import Point from 'ol/geom/Point';
import {transform} from 'ol/proj';

import {loadCountries, readFeatures} from './countries';
import {createFlatMap} from './flat-map';
import {logoPin} from './markers';
import {equalEarth} from './projection';

const MAX_ZOOM = 12;
const PADDING = 60;
const DECIMALS = 6;

/**
 * Let people place a training centre by clicking the flat map. The point goes
 * into the form field as WKT in longitude and latitude.
 *
 * @param {HTMLElement} container The map container.
 * @param {{input: string, country: string, logo: string|null}} data The id of
 *   the form field, the organisation's country and its logo.
 * @returns {Promise<void>} Resolves once the map is drawn.
 */
export async function initLocationPicker(container, data) {
  const input = document.getElementById(data.input);
  const clear = document.querySelector(`[data-map-clear="${data.input}"]`);
  const projection = equalEarth();
  const wkt = new WKT();
  const countries = await loadCountries();
  const home = countries.features.find((feature) => feature.properties.ISO2 === data.country);

  const map = createFlatMap(container.querySelector('.map-flat-view'), projection);
  const marker = new Overlay({
    element: logoPin(data.logo || container.dataset.defaultLogo),
    positioning: 'center-center',
    stopEvent: false,
  });
  map.addOverlay(marker);

  const place = (coordinate) => {
    marker.setPosition(coordinate);
    clear.classList.toggle('is-hidden', !coordinate);
  };

  if (input.value) {
    const point = wkt.readGeometry(input.value, {
      dataProjection: 'EPSG:4326',
      featureProjection: projection,
    });
    place(point.getCoordinates());
  }

  const extent = createEmpty();
  if (home) {
    const [feature] = readFeatures({type: 'FeatureCollection', features: [home]}, projection);
    extend(extent, feature.getGeometry().getExtent());
  }
  if (marker.getPosition()) {
    extendCoordinate(extent, marker.getPosition());
  }
  if (!isEmpty(extent)) {
    map.getView().fit(extent, {
      padding: [PADDING, PADDING, PADDING, PADDING],
      maxZoom: MAX_ZOOM,
    });
  }

  map.on('singleclick', (event) => {
    const [lon, lat] = transform(event.coordinate, projection, 'EPSG:4326');
    // Clicks in the corners outside the curved world edge have no longitude.
    if (!(Math.abs(lon) <= 180 && Math.abs(lat) <= 90)) {
      return;
    }
    input.value = wkt.writeGeometry(new Point([lon, lat]), {decimals: DECIMALS});
    place(event.coordinate);
  });

  clear.addEventListener('click', () => {
    input.value = '';
    place(undefined);
  });
}
