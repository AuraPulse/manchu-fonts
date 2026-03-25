import type { PreviewSegment } from '../lib/manchu';

export type MixedPreviewItem = {
  id: string;
  fontId: string;
  fontLabel: string;
  fontFamily: string;
  roman: string;
  segments: PreviewSegment[];
};

type MixedFontPreviewProps = {
  items: MixedPreviewItem[];
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

export function MixedFontPreview({
  items,
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
}: MixedFontPreviewProps) {
  const sharedStyle = {
    fontSize: `${fontSize}px`,
    letterSpacing: `${lineGap}em`,
    lineHeight: columnGap,
  };

  const renderMixedItems = (orientation: 'vertical' | 'horizontal') =>
    items.map((item) => (
      <article
        key={item.id}
        className="mixed-item"
        data-font-family={item.fontFamily}
      >
        <p className="mixed-item__label">{item.fontLabel}</p>
        <div
          className={`mixed-item__content mixed-item__content--${orientation}`}
          style={{ fontFamily: item.fontFamily }}
        >
          {item.segments.length > 0 ? renderSegments(item.segments) : <span className="preview-placeholder">Empty</span>}
        </div>
      </article>
    ));

  return (
    <section className="preview-card" aria-label="Mixed font preview area">
      <div className="preview-card__header">
        <div>
          <p className="eyebrow">Preview</p>
          <h2>Mixed Fonts</h2>
        </div>
      </div>

      <div className="preview-grid">
        <article className="preview-panel">
          <div className="preview-panel__header">
            <div className="preview-panel__title">
              <h3>Vertical</h3>
              <span>Multiple words, multiple fonts</span>
            </div>
            <div className="button-row">
              <button
                aria-label="Export mixed vertical preview as PNG"
                className="secondary-button"
                type="button"
                onClick={onExportVerticalPng}
              >
                {exportState === 'mixed-vertical-png' ? 'Exporting PNG...' : 'PNG'}
              </button>
              <button
                aria-label="Export mixed vertical preview as PDF"
                className="secondary-button"
                type="button"
                onClick={onExportVerticalPdf}
              >
                {exportState === 'mixed-vertical-pdf' ? 'Exporting PDF...' : 'PDF'}
              </button>
            </div>
          </div>
          <div
            aria-label="Vertical mixed Manchu preview"
            className="preview-surface preview-surface--mixed"
            ref={verticalPreviewRef}
            style={sharedStyle}
          >
            {renderMixedItems('vertical')}
          </div>
        </article>

        {showHorizontalDebug ? (
          <article className="preview-panel">
            <div className="preview-panel__header">
              <div className="preview-panel__title">
                <h3>Horizontal</h3>
                <span>Multiple words, multiple fonts</span>
              </div>
              <div className="button-row">
                <button
                  aria-label="Export mixed horizontal preview as PNG"
                  className="secondary-button"
                  type="button"
                  onClick={onExportHorizontalPng}
                >
                  {exportState === 'mixed-horizontal-png' ? 'Exporting PNG...' : 'PNG'}
                </button>
                <button
                  aria-label="Export mixed horizontal preview as PDF"
                  className="secondary-button"
                  type="button"
                  onClick={onExportHorizontalPdf}
                >
                  {exportState === 'mixed-horizontal-pdf' ? 'Exporting PDF...' : 'PDF'}
                </button>
              </div>
            </div>
            <div
              aria-label="Horizontal mixed Manchu preview"
              className="preview-surface preview-surface--mixed"
              ref={horizontalPreviewRef}
              style={sharedStyle}
            >
              {renderMixedItems('horizontal')}
            </div>
          </article>
        ) : null}
      </div>
    </section>
  );
}
