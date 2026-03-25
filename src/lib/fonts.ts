import { FONT_OPTIONS } from '../generated/fontManifest';

let fontFacesInjected = false;

export const ensureFontFaces = (): void => {
  if (fontFacesInjected || typeof document === 'undefined') {
    return;
  }

  const style = document.createElement('style');
  style.dataset.fontRegistry = 'manchu-font-registry';
  style.textContent = FONT_OPTIONS.map(
    (font) => `
      @font-face {
        font-family: "${font.family}";
        src: url("${font.file}") format("truetype");
        font-display: swap;
      }
    `,
  ).join('\n');

  document.head.append(style);
  fontFacesInjected = true;
};
