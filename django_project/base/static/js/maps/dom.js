/**
 * Create an element with an optional class and text.
 *
 * @param {string} tag Tag name.
 * @param {string} [className] Class attribute.
 * @param {string} [text] Text content.
 * @returns {HTMLElement} The new element.
 */
export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text) {
    node.textContent = text;
  }
  return node;
}
