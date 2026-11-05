import {boundingExtent} from 'ol/extent';
import {fromLonLat} from 'ol/proj';

import {loadCountries, readFeatures} from './countries';
import {GlobeFlatMap} from './globe-flat-map';
import {logoMarker} from './markers';
import {popupEntry} from './modal';

const MAX_ZOOM = 12;
const PADDING = 60;

/**
 * Training centres of one organisation, on a globe and a flat map.
 */
class SiteMap extends GlobeFlatMap {
  /**
   * @param {HTMLElement} container The map container.
   * @param {{country: string, organisation: string, logo: string|null,
   *   markers: Array<{name: string, lon: number, lat: number, address: string, url: string}>}} data
   *   The training centres to mark.
   * @param {Object|null} home GeoJSON feature of the organisation's country.
   */
  constructor(container, data, home) {
    const first = data.markers[0];
    super(container, {
      rotate: false,
      globeCenter: first ? [first.lon, first.lat] : [0, 20],
    });
    this.data = data;
    this.home = home;
    this.logo = data.logo || container.dataset.defaultLogo;
    this.init();
  }

  /**
   * @param {Object} centre One training centre from the payload.
   * @returns {HTMLElement} Its marker.
   */
  markerFor(centre) {
    return logoMarker(this.logo, centre.name, () => {
      this.stopRotation();
      this.showCentre(centre);
    });
  }

  onGlobeLoad() {
    for (const centre of this.data.markers) {
      this.addGlobeMarker(this.markerFor(centre), [centre.lon, centre.lat]);
    }
  }

  fitGlobe() {
    const points = this.data.markers.length
      ? this.data.markers.map((centre) => [centre.lon, centre.lat])
      : this.homeLonLats();
    if (!points.length) {
      return;
    }
    const lons = points.map(([lon]) => lon);
    const lats = points.map(([, lat]) => lat);
    this.globeMap.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      {padding: PADDING, maxZoom: MAX_ZOOM, duration: 0},
    );
  }

  /**
   * @returns {Array<Array<number>>} Every vertex of the home country, in lon and lat.
   */
  homeLonLats() {
    if (!this.home) {
      return [];
    }
    const {type, coordinates} = this.home.geometry;
    return coordinates.flat(type === 'MultiPolygon' ? 2 : 1);
  }

  onFlatLoad() {
    for (const centre of this.data.markers) {
      this.addFlatMarker(this.markerFor(centre), [centre.lon, centre.lat]);
    }
  }

  fitFlat() {
    const view = this.flatMap.getView();
    const padding = [PADDING, PADDING, PADDING, PADDING];
    if (this.data.markers.length) {
      const points = this.data.markers.map((centre) =>
        fromLonLat([centre.lon, centre.lat], this.flatProjection),
      );
      view.fit(boundingExtent(points), {padding, maxZoom: MAX_ZOOM});
    } else if (this.home) {
      const [feature] = readFeatures(
        {type: 'FeatureCollection', features: [this.home]},
        this.flatProjection,
      );
      view.fit(feature.getGeometry().getExtent(), {padding});
    }
  }

  /**
   * Open the popup for one training centre.
   *
   * @param {Object} centre One training centre from the payload.
   */
  showCentre(centre) {
    const onItsPage = centre.url === window.location.pathname;
    this.modal.open({
      country: this.data.country,
      title: this.home ? this.home.properties.NAME : centre.name,
      entries: [
        popupEntry({
          logo: this.logo,
          name: centre.name,
          href: onItsPage ? undefined : centre.url,
          lines: [centre.address, `Run by ${this.data.organisation}`].filter(Boolean),
        }),
      ],
    });
  }
}

/**
 * Draw the training centres of one organisation.
 *
 * @param {HTMLElement} container The map container.
 * @param {Object} data The payload from the view.
 * @returns {Promise<void>} Resolves once the map is drawn.
 */
export async function initSiteMap(container, data) {
  const countries = await loadCountries();
  const home = countries.features.find(
    (feature) => feature.properties.ISO2 === data.country,
  );
  new SiteMap(container, data, home || null);
}
