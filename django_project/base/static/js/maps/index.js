import 'ol/ol.css';
import 'maplibre-gl/dist/maplibre-gl.css';

import {initSiteMap} from './sites';
import {initWorldMap} from './world';

const MAPS = {
  world: initWorldMap,
  site: initSiteMap,
};

/**
 * Start every map declared on the page with a data-map attribute.
 */
export function boot() {
  document.querySelectorAll('[data-map]').forEach((container) => {
    const init = MAPS[container.dataset.map];
    const payload = document.getElementById(container.dataset.mapData);
    const status = container.querySelector('.map-status');
    if (!init || !payload) {
      return;
    }
    init(container, JSON.parse(payload.textContent))
      .then(() => status.classList.add('is-hidden'))
      .catch((error) => {
        console.error(error);
        status.textContent = 'We could not load the map. Refresh the page to try again.';
        status.classList.add('is-error');
      });
  });
}
