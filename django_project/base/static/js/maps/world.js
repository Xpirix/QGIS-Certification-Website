import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Fill from 'ol/style/Fill';
import Stroke from 'ol/style/Stroke';
import Style from 'ol/style/Style';

import {loadCountries, readFeatures} from './countries';
import {GlobeFlatMap} from './globe-flat-map';
import {logoMarker} from './markers';
import {popupEntry} from './modal';

const COUNTRY_FILL = '#589632';
const COUNTRY_LINE = '#3d6b22';
const SOURCE = 'organisation-countries';

/**
 * @param {string} hex A hex colour.
 * @param {number} alpha Opacity from 0 to 1.
 * @returns {string} The colour as rgba().
 */
function rgba(hex, alpha) {
  const value = parseInt(hex.slice(1), 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}

/**
 * Countries with at least one certifying organisation, on a globe and a flat map.
 */
class WorldMap extends GlobeFlatMap {
  /**
   * @param {HTMLElement} container The map container.
   * @param {Object<string, {count: number, organisations: Array<Object>}>} data
   *   Organisations keyed by two letter ISO country code.
   * @param {Object} countries GeoJSON country polygons.
   */
  constructor(container, data, countries) {
    super(container, {globeCenter: [10, 30]});
    this.data = data;
    this.defaultLogo = container.dataset.defaultLogo;
    this.countries = {
      type: 'FeatureCollection',
      features: countries.features.filter((feature) => data[feature.properties.ISO2]),
    };
    this.countryNames = Object.fromEntries(
      this.countries.features.map((feature) => [
        feature.properties.ISO2,
        feature.properties.NAME,
      ]),
    );
    this.located = Object.entries(data).flatMap(([code, entry]) =>
      entry.organisations
        .filter((organisation) => organisation.lon !== null && organisation.lat !== null)
        .map((organisation) => ({code, organisation})),
    );
    this.activeCountry = null;
    this.activeOrganisation = null;
    this.hoveredCountry = null;
    this.init();
  }

  /**
   * @param {Object} organisation One organisation from the payload.
   * @returns {HTMLElement} Its logo marker.
   */
  markerFor(organisation) {
    return logoMarker(
      organisation.logo || this.defaultLogo,
      organisation.name,
      () => {
        this.stopRotation();
        this.showOrganisation(organisation.slug);
      },
      {large: true},
    );
  }

  onGlobeLoad() {
    const map = this.globeMap;
    map.addSource(SOURCE, {type: 'geojson', data: this.countries, promoteId: 'ISO2'});
    map.addLayer({
      id: `${SOURCE}-fill`,
      type: 'fill',
      source: SOURCE,
      paint: {
        'fill-color': COUNTRY_FILL,
        'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.75, 0.5],
      },
    });
    map.addLayer({
      id: `${SOURCE}-line`,
      type: 'line',
      source: SOURCE,
      paint: {'line-color': COUNTRY_LINE, 'line-width': 1.5},
    });

    map.on('mousemove', `${SOURCE}-fill`, (event) => {
      this.setGlobeHover(event.features[0]?.properties.ISO2 || null);
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', `${SOURCE}-fill`, () => {
      this.setGlobeHover(null);
      map.getCanvas().style.cursor = '';
    });
    map.on('click', `${SOURCE}-fill`, (event) => {
      if (event.originalEvent.target.closest('.map-marker')) {
        return;
      }
      const code = event.features[0]?.properties.ISO2;
      if (code) {
        this.stopRotation();
        this.showCountry(code);
      }
    });

    for (const {organisation} of this.located) {
      this.addGlobeMarker(this.markerFor(organisation), [organisation.lon, organisation.lat]);
    }
  }

  /**
   * @param {string|null} code The hovered country, or null.
   */
  setGlobeHover(code) {
    if (code === this.hoveredCountry) {
      return;
    }
    if (this.hoveredCountry) {
      this.globeMap.setFeatureState({source: SOURCE, id: this.hoveredCountry}, {hover: false});
    }
    this.hoveredCountry = code;
    if (code) {
      this.globeMap.setFeatureState({source: SOURCE, id: code}, {hover: true});
    }
  }

  onFlatLoad() {
    const styleFor = (opacity) =>
      new Style({
        fill: new Fill({color: rgba(COUNTRY_FILL, opacity)}),
        stroke: new Stroke({color: COUNTRY_LINE, width: 1.5}),
      });
    const normal = styleFor(0.5);
    const hover = styleFor(0.75);

    this.countryLayer = new VectorLayer({
      source: new VectorSource({
        features: readFeatures(this.countries, this.flatProjection),
      }),
      style: (feature) => (feature.get('ISO2') === this.hoveredCountry ? hover : normal),
    });
    this.flatMap.addLayer(this.countryLayer);

    this.flatMap.on('pointermove', (event) => {
      if (event.dragging) {
        return;
      }
      const code = this.countryAt(event.pixel);
      if (code !== this.hoveredCountry) {
        this.hoveredCountry = code;
        this.countryLayer.changed();
      }
      this.flatMap.getTargetElement().style.cursor = code ? 'pointer' : '';
    });

    for (const {organisation} of this.located) {
      this.addFlatMarker(this.markerFor(organisation), [organisation.lon, organisation.lat]);
    }
  }

  onFlatClick(event) {
    const code = this.countryAt(event.pixel);
    if (code) {
      this.showCountry(code);
    }
  }

  /**
   * @param {Array<number>} pixel A pixel on the flat map.
   * @returns {string|null} The country code there, if it has organisations.
   */
  countryAt(pixel) {
    const feature = this.flatMap.forEachFeatureAtPixel(pixel, (found) => found, {
      layerFilter: (layer) => layer === this.countryLayer,
    });
    return feature ? feature.get('ISO2') : null;
  }

  /**
   * Open the popup listing the organisations of one country.
   *
   * @param {string} code Two letter ISO country code.
   */
  showCountry(code) {
    const entry = this.data[code];
    if (!entry) {
      return;
    }
    this.activeCountry = code;
    this.activeOrganisation = null;
    const noun =
      entry.count === 1 ? 'certifying organisation' : 'certifying organisations';
    this.modal.open({
      country: code,
      title: this.countryNames[code] || code,
      subtitle: `${entry.count} ${noun}`,
      entries: entry.organisations.map((organisation) => this.entryFor(organisation)),
    });
    this.updateUrlState();
  }

  /**
   * Open the popup for one organisation, from its marker.
   *
   * @param {string} slug The organisation's slug.
   */
  showOrganisation(slug) {
    for (const [code, entry] of Object.entries(this.data)) {
      const organisation = entry.organisations.find((candidate) => candidate.slug === slug);
      if (organisation) {
        this.activeOrganisation = slug;
        this.activeCountry = null;
        this.modal.open({
          country: code,
          title: this.countryNames[code] || code,
          entries: [this.entryFor(organisation)],
        });
        this.updateUrlState();
        return;
      }
    }
  }

  /**
   * @param {Object} organisation One organisation from the payload.
   * @returns {HTMLElement} Its entry in the popup.
   */
  entryFor(organisation) {
    return popupEntry({
      logo: organisation.logo || this.defaultLogo,
      name: organisation.name,
      href: organisation.url,
      action: organisation.website
        ? {label: 'Visit website', href: organisation.website}
        : undefined,
    });
  }

  restoreSelection() {
    if (this.activeOrganisation) {
      this.showOrganisation(this.activeOrganisation);
    } else if (this.activeCountry) {
      this.showCountry(this.activeCountry);
    }
  }

  clearSelection() {
    this.activeCountry = null;
    this.activeOrganisation = null;
  }

  readExtraUrlState(params) {
    this.activeOrganisation = params.get('organisation');
    this.activeCountry = params.get('country');
  }

  writeExtraUrlState(params) {
    params.delete('organisation');
    params.delete('country');
    if (this.activeOrganisation) {
      params.set('organisation', this.activeOrganisation);
    } else if (this.activeCountry) {
      params.set('country', this.activeCountry);
    }
  }
}

/**
 * Draw the map of certifying organisations by country.
 *
 * @param {HTMLElement} container The map container.
 * @param {Object<string, {count: number, organisations: Array<Object>}>} data
 *   Organisations keyed by two letter ISO country code.
 * @returns {Promise<void>} Resolves once the map is drawn.
 */
export async function initWorldMap(container, data) {
  new WorldMap(container, data, await loadCountries());
}
