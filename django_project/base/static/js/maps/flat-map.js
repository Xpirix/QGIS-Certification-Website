import Feature from 'ol/Feature';
import Map from 'ol/Map';
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

const OCEAN = '#aad3df';
const OCEAN_LINE = '#8fb8c4';

/**
 * @param {import('ol/proj/Projection').default} projection The Equal Earth projection.
 * @returns {Feature} The edge of the Equal Earth world, meridians 180 east and west.
 */
function worldOutline(projection) {
  const ring = [];
  for (let lat = -90; lat <= 90; lat += 1) {
    ring.push([180, lat]);
  }
  for (let lat = 90; lat >= -90; lat -= 1) {
    ring.push([-180, lat]);
  }
  return new Feature(new Polygon([ring.map((lonLat) => fromLonLat(lonLat, projection))]));
}

/**
 * Build the flat Equal Earth map with OSM tiles clipped to the world outline,
 * fitted to the whole world.
 *
 * @param {HTMLElement} target Where to draw the map.
 * @param {import('ol/proj/Projection').default} projection The Equal Earth projection.
 * @returns {Map} The map.
 */
export function createFlatMap(target, projection) {
  const extent = projection.getExtent();
  const view = new View({
    projection,
    center: fromLonLat([0, 20], projection),
    extent,
    constrainOnlyCenter: true,
    showFullExtent: true,
    enableRotation: false,
  });

  const outline = worldOutline(projection);
  const tiles = new TileLayer({
    source: new OSM({
      // The site sends Referrer-Policy: same-origin, and OSM refuses tiles without a referrer.
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

  const map = new Map({
    target,
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
  return map;
}
