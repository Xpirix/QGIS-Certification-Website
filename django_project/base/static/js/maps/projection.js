import proj4 from 'proj4';
import {get as getProjection} from 'ol/proj';
import {register} from 'ol/proj/proj4';

const CODE = 'EqualEarth';
const DEFINITION =
  '+proj=eqearth +lon_0=0 +x_0=0 +y_0=0 +R=6371008.7714 +units=m +no_defs +type=crs';
const EXTENT = [-17243959.06, -8392927.6, 17243959.06, 8392927.6];
const WORLD_EXTENT = [-180, -90, 180, 90];

/**
 * Return the Equal Earth projection, registering it with proj4 on first use.
 *
 * @returns {import('ol/proj/Projection').default} The Equal Earth projection.
 */
export function equalEarth() {
  let projection = getProjection(CODE);
  if (!projection) {
    proj4.defs(CODE, DEFINITION);
    register(proj4);
    projection = getProjection(CODE);
    projection.setExtent(EXTENT);
    projection.setWorldExtent(WORLD_EXTENT);
  }
  return projection;
}
