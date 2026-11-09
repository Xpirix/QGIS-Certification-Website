import {element} from './dom';

/**
 * Build a round logo marker that works on both the globe and the flat map.
 *
 * @param {string} src Logo URL.
 * @param {string} label Accessible name, also shown as the tooltip.
 * @param {function(): void} onActivate Called on click, Enter or Space.
 * @param {{large?: boolean}} [options] Draw the bigger marker used on the world map.
 * @returns {HTMLElement} The marker element.
 */
export function logoMarker(src, label, onActivate, {large = false} = {}) {
  const marker = element('div', large ? 'map-marker map-marker--large' : 'map-marker');
  marker.setAttribute('role', 'button');
  marker.setAttribute('tabindex', '0');
  marker.setAttribute('aria-label', label);
  marker.title = label;

  const image = element('img', 'map-marker__image');
  image.src = src;
  image.alt = '';
  marker.appendChild(image);

  marker.addEventListener('click', (event) => {
    event.stopPropagation();
    onActivate();
  });
  marker.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  });
  return marker;
}
