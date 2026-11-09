import {element} from './dom';

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Turn a two letter ISO code into its flag emoji, for example MG into 🇲🇬.
 *
 * @param {string} code Two letter ISO country code.
 * @returns {string} The flag, or an empty string for anything else.
 */
export function flagEmoji(code) {
  if (!/^[A-Z]{2}$/.test(code || '')) {
    return '';
  }
  return String.fromCodePoint(
    ...[...code].map((letter) => 0x1f1e6 + letter.charCodeAt(0) - 65),
  );
}

/**
 * Build one entry of the popup: a logo, a linked name, detail lines and an
 * optional button.
 *
 * @param {{logo: string, name: string, href?: string, lines?: Array<string>,
 *   action?: {label: string, href: string}}} entry What to show.
 * @returns {HTMLElement} The entry element.
 */
export function popupEntry({logo, name, href, lines = [], action}) {
  const article = element('article', 'map-popup-entry');

  const image = element('img', 'map-popup-entry__logo');
  image.src = logo;
  image.alt = '';
  image.loading = 'lazy';

  const info = element('div', 'map-popup-entry__info');
  const heading = element('h3', 'title is-6 mb-1');
  if (href) {
    const link = element('a', '', name);
    link.href = href;
    heading.appendChild(link);
  } else {
    heading.textContent = name;
  }
  info.appendChild(heading);

  for (const line of lines) {
    info.appendChild(element('p', 'is-size-7 has-text-grey-dark', line));
  }

  if (action) {
    const button = element('a', 'button is-small is-primary3 is-outlined mt-2');
    button.href = action.href;
    button.target = '_blank';
    button.rel = 'noopener';
    const icon = element('span', 'icon');
    const glyph = element('i', 'fas fa-external-link-alt');
    glyph.setAttribute('aria-hidden', 'true');
    icon.appendChild(glyph);
    button.append(
      icon,
      element('span', '', action.label),
      element('span', 'is-sr-only', ' (opens in a new tab)'),
    );
    info.appendChild(button);
  }

  article.append(image, info);
  return article;
}

/**
 * A popup window over a dimmed backdrop, shared by every map on the page.
 */
export class MapModal {
  /**
   * @param {function(): void} onClose Called after the popup closes.
   */
  constructor(onClose) {
    this.onClose = onClose;
    this.returnFocus = null;

    this.overlay = element('div', 'map-popup-overlay');
    this.overlay.addEventListener('click', () => this.close());

    this.dialog = element('div', 'map-popup');
    this.dialog.setAttribute('role', 'dialog');
    this.dialog.setAttribute('aria-modal', 'true');
    this.dialog.setAttribute('aria-labelledby', 'map-popup-title');

    this.closeButton = element('button', 'map-popup__close', '×');
    this.closeButton.type = 'button';
    this.closeButton.setAttribute('aria-label', 'Close');
    this.closeButton.addEventListener('click', () => this.close());

    const card = element('div', 'card map-popup__card');
    const content = element('div', 'card-content');
    this.title = element('h2', 'title is-5 mb-1');
    this.title.id = 'map-popup-title';
    this.subtitle = element('p', 'map-popup__subtitle');
    this.body = element('div', 'map-popup__body');
    content.append(this.title, this.subtitle, this.body);
    card.appendChild(content);

    this.dialog.append(this.closeButton, card);
    document.body.append(this.overlay, this.dialog);

    document.addEventListener('keydown', (event) => this.handleKey(event));
  }

  /**
   * @returns {boolean} Whether the popup is showing.
   */
  get isOpen() {
    return this.dialog.classList.contains('is-active');
  }

  /**
   * Show the popup.
   *
   * @param {{country?: string, title: string, subtitle?: string,
   *   entries: Array<HTMLElement>}} content What to show.
   */
  open({country, title, subtitle, entries}) {
    const flag = flagEmoji(country);
    const heading = [];
    if (flag) {
      const flagElement = element('span', 'flag-emoji mr-2', flag);
      flagElement.setAttribute('aria-hidden', 'true');
      heading.push(flagElement);
    }
    heading.push(document.createTextNode(title));
    this.title.replaceChildren(...heading);

    this.subtitle.textContent = subtitle || '';
    this.subtitle.classList.toggle('is-hidden', !subtitle);
    this.body.replaceChildren(...entries);
    this.body.scrollTop = 0;

    if (!this.isOpen) {
      this.returnFocus = document.activeElement;
    }
    this.overlay.classList.add('is-active');
    this.dialog.classList.add('is-active');
    this.closeButton.focus({preventScroll: true});
  }

  /**
   * Hide the popup and give focus back to where it was.
   */
  close() {
    if (!this.isOpen) {
      return;
    }
    this.overlay.classList.remove('is-active');
    this.dialog.classList.remove('is-active');
    if (this.returnFocus && this.returnFocus.focus) {
      this.returnFocus.focus({preventScroll: true});
    }
    this.returnFocus = null;
    this.onClose();
  }

  /**
   * Close on Escape and keep Tab inside the popup while it is open.
   *
   * @param {KeyboardEvent} event The key press.
   */
  handleKey(event) {
    if (!this.isOpen) {
      return;
    }
    if (event.key === 'Escape') {
      this.close();
      return;
    }
    if (event.key !== 'Tab') {
      return;
    }
    const focusable = [...this.dialog.querySelectorAll(FOCUSABLE)];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}
