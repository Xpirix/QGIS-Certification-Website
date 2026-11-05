import GeoJSON from 'ol/format/GeoJSON';

const COUNTRIES_URL = '/static/json/geo.json';

let pending = null;

/**
 * Fetch the country polygons once and share the result with every map.
 *
 * @returns {Promise<Object>} The raw GeoJSON feature collection.
 */
export function loadCountries() {
  if (!pending) {
    pending = fetch(COUNTRIES_URL).then((response) => {
      if (!response.ok) {
        throw new Error(`Could not load ${COUNTRIES_URL}`);
      }
      return response.json();
    });
  }
  return pending;
}

/**
 * Read a GeoJSON feature collection into the given projection.
 *
 * @param {Object} collection A GeoJSON feature collection in EPSG:4326.
 * @param {import('ol/proj/Projection').default} projection Target projection.
 * @returns {Array<import('ol/Feature').default>} The read features.
 */
export function readFeatures(collection, projection) {
  return new GeoJSON({
    dataProjection: 'EPSG:4326',
    featureProjection: projection,
  }).readFeatures(collection);
}

