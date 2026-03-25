import { FONT_OPTIONS } from '../generated/fontManifest';
import type { PreviewSegment } from '../lib/manchu';

export type ManchuPreviewProps = {
  text: string;
  segments: PreviewSegment[];
  fontId: string;
  fontSize: number;
  lineGap: number;
  columnGap: number;
  showHorizontalDebug: boolean;
  verticalPreviewRef?: React.RefObject<HTMLDivElement>;
  horizontalPreviewRef?: React.RefObject<HTMLDivElement>;
  onExportVerticalPng: () => void;
  onExportVerticalPdf: () => void;
  onExportHorizontalPng: () => void;
  onExportHorizontalPdf: () => void;
  exportState: string;
};

const joinClassNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ');

const renderSegments = (segments: PreviewSegment[]) =>
  segments.map((segment, index) => (
    <span
      key={`${segment.sourceStart}-${segment.sourceEnd}-${index}`}
      className={joinClassNames(
        'preview-segment',
        segment.kind === 'unknown' && 'preview-segment--unknown',
        segment.kind === 'passthrough' && 'preview-segment--passthrough',
      )}
    >
      {segment.text}
    </span>
  ));

export function ManchuPreview({
  text,
  segments,
  fontId,
  fontSize,
  lineGap,
  columnGap,
  showHorizontalDebug,
  verticalPreviewRef,
  horizontalPreviewRef,
  onExportVerticalPng,
  onExportVerticalPdf,
  onExportHorizontalPng,
  onExportHorizontalPdf,
  exportState,
}: ManchuPreviewProps) {
  const selectedFont =
    FONT_OPTIONS.find((font) => font.id === fontId) ??
    FONT_OPTIONS[0];

  const sharedStyle = {
    fontFamily: selectedFont.family,
    fontSize: `${fontSize}px`,
    letterSpacing: `${lineGap}em`,
    lineHeight: columnGap,
  };

  return (
    <section className="preview-card" aria-label="Manchu preview area">
      <div className="preview-card__header">
        <div>
          <p className="eyebrow">Preview</p>
          <h2>Manchu Preview</h2>
        </div>
        <div className="preview-card__meta">
          <p className="font-meta">{selectedFont.label}</p>
        </div>
      </div>

      <div className="preview-grid">
        <article className="preview-panel">
          <div className="preview-panel__header">
            <div className="preview-panel__title">
              <h3>Vertical</h3>
              <span>Main preview</span>
            </div>
            <div className="button-row">
              <button
                aria-label="Export single vertical preview as PNG"
                className="secondary-button"
                type="button"
                onClick={onExportVerticalPng}
              >
                {exportState === 'single-vertical-png' ? 'Exporting PNG...' : 'PNG'}
              </button>
              <button
                aria-label="Export single vertical preview as PDF"
                className="secondary-button"
                type="button"
                onClick={onExportVerticalPdf}
              >
                {exportState === 'single-vertical-pdf' ? 'Exporting PDF...' : 'PDF'}
              </button>
            </div>
          </div>
          <div
            aria-label="Vertical Manchu preview"
            className="preview-surface preview-surface--vertical"
            data-font-family={selectedFont.family}
            ref={verticalPreviewRef}
            style={sharedStyle}
          >
            {text ? renderSegments(segments) : <span className="preview-placeholder">Enter Roman text</span>}
          </div>
        </article>

        {showHorizontalDebug ? (
          <article className="preview-panel">
            <div className="preview-panel__header">
              <div className="preview-panel__title">
                <h3>Horizontal</h3>
                <span>Debug preview</span>
              </div>
              <div className="button-row">
                <button
                  aria-label="Export single horizontal preview as PNG"
                  className="secondary-button"
                  type="button"
                  onClick={onExportHorizontalPng}
                >
                  {exportState === 'single-horizontal-png' ? 'Exporting PNG...' : 'PNG'}
                </button>
                <button
                  aria-label="Export single horizontal preview as PDF"
                  className="secondary-button"
                  type="button"
                  onClick={onExportHorizontalPdf}
                >
                  {exportState === 'single-horizontal-pdf' ? 'Exporting PDF...' : 'PDF'}
                </button>
              </div>
            </div>
            <div
              aria-label="Horizontal Manchu preview"
              className="preview-surface preview-surface--horizontal"
              data-font-family={selectedFont.family}
              ref={horizontalPreviewRef}
              style={sharedStyle}
            >
              {text ? renderSegments(segments) : <span className="preview-placeholder">Enter Roman text</span>}
            </div>
          </article>
        ) : null}
      </div>
    </section>
  );
}
