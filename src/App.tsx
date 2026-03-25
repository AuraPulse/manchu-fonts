import { useDeferredValue, useEffect, useRef, useState } from 'react';
import { ManchuPreview } from './components/ManchuPreview';
import { MixedFontPreview, type MixedPreviewItem } from './components/MixedFontPreview';
import { FONT_OPTIONS } from './generated/fontManifest';
import { copyUnicodeText } from './lib/clipboard';
import { ensureFontFaces } from './lib/fonts';
import { exportPreviewAsPdf, exportPreviewAsPng } from './lib/export';
import { buildPreviewSegments, normalizeRoman, romanToManchu } from './lib/manchu';

const DEFAULT_INPUT = 'manju gisun\nabkai';
const DEFAULT_PAGE = 'single';
const DEFAULT_MIXED_INPUT = 'manju';

const PAGE_OPTIONS = [
  { id: 'single', label: 'Single Preview' },
  { id: 'mixed', label: 'Mixed Fonts' },
] as const;

type PageId = (typeof PAGE_OPTIONS)[number]['id'];
type ExportState =
  | 'idle'
  | 'single-vertical-png'
  | 'single-vertical-pdf'
  | 'single-horizontal-png'
  | 'single-horizontal-pdf'
  | 'mixed-vertical-png'
  | 'mixed-vertical-pdf'
  | 'mixed-horizontal-png'
  | 'mixed-horizontal-pdf'
  | 'done'
  | 'failed';

const getPageFromHash = (hash: string): PageId =>
  hash === '#mixed' ? 'mixed' : DEFAULT_PAGE;

const toSafeFileStem = (value: string, fallback: string) => {
  const stem = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return stem || fallback;
};

function App() {
  const [activePage, setActivePage] = useState<PageId>(() => getPageFromHash(window.location.hash));
  const [input, setInput] = useState(DEFAULT_INPUT);
  const [mixedInput, setMixedInput] = useState(DEFAULT_MIXED_INPUT);
  const [mixedQuery, setMixedQuery] = useState(DEFAULT_MIXED_INPUT);
  const [selectedMixedFontIds, setSelectedMixedFontIds] = useState(() => FONT_OPTIONS.map((font) => font.id));
  const [fontId, setFontId] = useState(FONT_OPTIONS[0]?.id ?? '');
  const [fontSize, setFontSize] = useState(56);
  const [lineGap, setLineGap] = useState(0.08);
  const [columnGap, setColumnGap] = useState(1.75);
  const [showHorizontalDebug, setShowHorizontalDebug] = useState(true);
  const [showUnicodeText, setShowUnicodeText] = useState(true);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [exportState, setExportState] = useState<ExportState>('idle');
  const singleVerticalPreviewRef = useRef<HTMLDivElement>(null);
  const singleHorizontalPreviewRef = useRef<HTMLDivElement>(null);
  const mixedVerticalPreviewRef = useRef<HTMLDivElement>(null);
  const mixedHorizontalPreviewRef = useRef<HTMLDivElement>(null);

  const deferredInput = useDeferredValue(input);

  useEffect(() => {
    ensureFontFaces();
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      setActivePage(getPageFromHash(window.location.hash));
    };

    window.addEventListener('hashchange', handleHashChange);

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  useEffect(() => {
    setCopyState('idle');
  }, [deferredInput]);

  useEffect(() => {
    setExportState('idle');
  }, [activePage, deferredInput, mixedQuery, selectedMixedFontIds, fontId, fontSize, lineGap, columnGap, showHorizontalDebug]);

  const normalized = normalizeRoman(deferredInput);
  const previewSegments = buildPreviewSegments(deferredInput);
  const { manchuText, errors } = romanToManchu(deferredInput);
  const mixedPreviewItems: MixedPreviewItem[] = FONT_OPTIONS
    .filter((font) => selectedMixedFontIds.includes(font.id))
    .map((font) => ({
      id: font.id,
      fontId: font.id,
      fontLabel: font.label,
      fontFamily: font.family,
      roman: mixedQuery,
      segments: buildPreviewSegments(mixedQuery),
    }));

  const navigateToPage = (page: PageId) => {
    window.location.hash = page === 'mixed' ? 'mixed' : 'single';
    setActivePage(page);
  };

  const toggleMixedFont = (fontIdToToggle: string) => {
    setSelectedMixedFontIds((current) =>
      current.includes(fontIdToToggle)
        ? current.filter((id) => id !== fontIdToToggle)
        : [...current, fontIdToToggle],
    );
  };

  const copyUnicode = async () => {
    const didCopy = await copyUnicodeText(manchuText);

    if (didCopy) {
      setCopyState('copied');
    } else {
      setCopyState('failed');
    }
  };

  const exportPreview = async (
    node: HTMLDivElement | null,
    exportKey: Exclude<ExportState, 'idle' | 'done' | 'failed'>,
    fileName: string,
    format: 'png' | 'pdf',
  ) => {
    if (!node) {
      setExportState('failed');
      return;
    }

    setExportState(exportKey);

    try {
      if (format === 'png') {
        await exportPreviewAsPng(node, fileName);
      } else {
        await exportPreviewAsPdf(node, fileName);
      }

      setExportState('done');
    } catch {
      setExportState('failed');
    }
  };

  const renderSinglePreviewPage = () => (
    <>
      <div className="sidebar">
        <section className="panel panel--input">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Input</p>
              <h2>Roman Input</h2>
            </div>
            <span className="status-badge">{errors.length === 0 ? 'Ready' : `${errors.length} unresolved`}</span>
          </div>

          <label className="field">
            <span className="field__label">Roman text</span>
            <textarea
              aria-label="Roman input"
              className="roman-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Example: manju gisun"
              rows={7}
            />
          </label>

          <div className="info-grid">
            <article className="info-card">
              <p className="info-card__label">Normalized</p>
              <p className="info-card__value">{normalized || '—'}</p>
            </article>
            <article className="info-card">
              <p className="info-card__label">Unicode length</p>
              <p className="info-card__value">{manchuText.length}</p>
            </article>
          </div>

          {errors.length > 0 ? (
            <div className="error-box" role="status" aria-live="polite">
              <p className="error-box__title">Unknown fragments</p>
              <div className="error-list">
                {errors.map((error) => (
                  <span key={`${error.start}-${error.end}`} className="error-chip">
                    {error.raw} [{error.start}, {error.end})
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="panel panel--controls">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Controls</p>
              <h2>Font & Layout</h2>
            </div>
          </div>

          <label className="field">
            <span className="field__label">Font</span>
            <select
              aria-label="Font selector"
              className="select-field"
              value={fontId}
              onChange={(event) => setFontId(event.target.value)}
            >
              {FONT_OPTIONS.map((font) => (
                <option key={font.id} value={font.id}>
                  {font.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field__label">Font size: {fontSize}px</span>
            <input
              aria-label="Font size"
              type="range"
              min="28"
              max="112"
              step="2"
              value={fontSize}
              onChange={(event) => setFontSize(Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span className="field__label">Tracking: {lineGap.toFixed(2)}em</span>
            <input
              aria-label="Line gap"
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={lineGap}
              onChange={(event) => setLineGap(Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span className="field__label">Column gap: {columnGap.toFixed(2)}</span>
            <input
              aria-label="Column gap"
              type="range"
              min="1"
              max="3"
              step="0.05"
              value={columnGap}
              onChange={(event) => setColumnGap(Number(event.target.value))}
            />
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={showHorizontalDebug}
              onChange={(event) => setShowHorizontalDebug(event.target.checked)}
            />
            <span>Show horizontal preview</span>
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={showUnicodeText}
              onChange={(event) => setShowUnicodeText(event.target.checked)}
            />
            <span>Show Unicode output</span>
          </label>
        </section>

        {showUnicodeText ? (
          <section className="panel panel--unicode">
            <div className="panel__header">
              <div>
                <p className="eyebrow">Output</p>
                <h2>Unicode</h2>
              </div>
              <button className="copy-button" type="button" onClick={copyUnicode}>
                Copy Unicode
              </button>
            </div>
            <pre className="unicode-output">{manchuText || '—'}</pre>
            <p className="copy-status" role="status" aria-live="polite">
              {copyState === 'copied' ? 'Copied to clipboard' : null}
              {copyState === 'failed' ? 'Copy failed, please copy manually' : null}
            </p>
          </section>
        ) : null}
      </div>

      <ManchuPreview
        verticalPreviewRef={singleVerticalPreviewRef}
        horizontalPreviewRef={singleHorizontalPreviewRef}
        onExportVerticalPng={() =>
          exportPreview(singleVerticalPreviewRef.current, 'single-vertical-png', `${fontId || 'single'}-vertical.png`, 'png')
        }
        onExportVerticalPdf={() =>
          exportPreview(singleVerticalPreviewRef.current, 'single-vertical-pdf', `${fontId || 'single'}-vertical.pdf`, 'pdf')
        }
        onExportHorizontalPng={() =>
          exportPreview(singleHorizontalPreviewRef.current, 'single-horizontal-png', `${fontId || 'single'}-horizontal.png`, 'png')
        }
        onExportHorizontalPdf={() =>
          exportPreview(singleHorizontalPreviewRef.current, 'single-horizontal-pdf', `${fontId || 'single'}-horizontal.pdf`, 'pdf')
        }
        exportState={exportState}
        text={manchuText}
        segments={previewSegments}
        fontId={fontId}
        fontSize={fontSize}
        lineGap={lineGap}
        columnGap={columnGap}
        showHorizontalDebug={showHorizontalDebug}
      />
    </>
  );

  const renderMixedPage = () => (
    <>
      <div className="sidebar">
        <section className="panel panel--mixed-editor">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Mixed Font</p>
              <h2>All Fonts Preview</h2>
            </div>
            <span className="status-badge">{FONT_OPTIONS.length} fonts</span>
          </div>

          <form
            className="mixed-query-form"
            onSubmit={(event) => {
              event.preventDefault();
              setMixedQuery(mixedInput.trim() || DEFAULT_MIXED_INPUT);
            }}
          >
            <label className="field">
              <span className="field__label">Roman text</span>
              <input
                aria-label="All fonts Roman input"
                className="select-field"
                type="text"
                value={mixedInput}
                onChange={(event) => setMixedInput(event.target.value)}
                placeholder="Example: manju"
              />
            </label>

            <div className="button-row">
              <button className="copy-button" type="submit">
                Show in all fonts
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setSelectedMixedFontIds(FONT_OPTIONS.map((font) => font.id))}
              >
                Select all
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setSelectedMixedFontIds([])}
              >
                Clear all
              </button>
            </div>
          </form>

          <div className="font-filter-panel">
            <div className="font-filter-panel__header">
              <p className="field__label">Visible fonts</p>
              <span className="status-badge">
                {selectedMixedFontIds.length}/{FONT_OPTIONS.length}
              </span>
            </div>
            <div className="font-checkbox-grid">
              {FONT_OPTIONS.map((font) => (
                <label key={font.id} className="font-checkbox">
                  <input
                    aria-label={`Toggle ${font.label}`}
                    type="checkbox"
                    checked={selectedMixedFontIds.includes(font.id)}
                    onChange={() => toggleMixedFont(font.id)}
                  />
                  <span>{font.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="info-grid">
            <article className="info-card">
              <p className="info-card__label">Current word</p>
              <p className="info-card__value">{mixedQuery || '—'}</p>
            </article>
            <article className="info-card">
              <p className="info-card__label">Preview count</p>
              <p className="info-card__value">{mixedPreviewItems.length}</p>
            </article>
          </div>
        </section>

        <section className="panel panel--controls">
          <div className="panel__header">
            <div>
              <p className="eyebrow">Display</p>
              <h2>Layout</h2>
            </div>
          </div>

          <label className="field">
            <span className="field__label">Font size: {fontSize}px</span>
            <input
              aria-label="Mixed font size"
              type="range"
              min="28"
              max="112"
              step="2"
              value={fontSize}
              onChange={(event) => setFontSize(Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span className="field__label">Tracking: {lineGap.toFixed(2)}em</span>
            <input
              aria-label="Mixed line gap"
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={lineGap}
              onChange={(event) => setLineGap(Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span className="field__label">Column gap: {columnGap.toFixed(2)}</span>
            <input
              aria-label="Mixed column gap"
              type="range"
              min="1"
              max="3"
              step="0.05"
              value={columnGap}
              onChange={(event) => setColumnGap(Number(event.target.value))}
            />
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={showHorizontalDebug}
              onChange={(event) => setShowHorizontalDebug(event.target.checked)}
            />
            <span>Show horizontal preview</span>
          </label>
        </section>
      </div>

      <MixedFontPreview
        items={mixedPreviewItems}
        fontSize={fontSize}
        lineGap={lineGap}
        columnGap={columnGap}
        showHorizontalDebug={showHorizontalDebug}
        verticalPreviewRef={mixedVerticalPreviewRef}
        horizontalPreviewRef={mixedHorizontalPreviewRef}
        onExportVerticalPng={() =>
          exportPreview(
            mixedVerticalPreviewRef.current,
            'mixed-vertical-png',
            `${toSafeFileStem(mixedQuery, 'mixed-fonts')}-vertical.png`,
            'png',
          )
        }
        onExportVerticalPdf={() =>
          exportPreview(
            mixedVerticalPreviewRef.current,
            'mixed-vertical-pdf',
            `${toSafeFileStem(mixedQuery, 'mixed-fonts')}-vertical.pdf`,
            'pdf',
          )
        }
        onExportHorizontalPng={() =>
          exportPreview(
            mixedHorizontalPreviewRef.current,
            'mixed-horizontal-png',
            `${toSafeFileStem(mixedQuery, 'mixed-fonts')}-horizontal.png`,
            'png',
          )
        }
        onExportHorizontalPdf={() =>
          exportPreview(
            mixedHorizontalPreviewRef.current,
            'mixed-horizontal-pdf',
            `${toSafeFileStem(mixedQuery, 'mixed-fonts')}-horizontal.pdf`,
            'pdf',
          )
        }
        exportState={exportState}
      />
    </>
  );

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero__title">
          <h1>Manchu Preview</h1>
          <span className="status-badge">Static frontend</span>
        </div>
        <nav className="nav-bar" aria-label="Page navigation">
          {PAGE_OPTIONS.map((page) => (
            <button
              key={page.id}
              className={`nav-button${activePage === page.id ? ' nav-button--active' : ''}`}
              type="button"
              onClick={() => navigateToPage(page.id)}
            >
              {page.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="layout">
        {activePage === 'single' ? renderSinglePreviewPage() : renderMixedPage()}
      </main>

      <p className="export-status" role="status" aria-live="polite">
        {exportState === 'done' ? 'Export complete' : null}
        {exportState === 'failed' ? 'Export failed' : null}
      </p>
    </div>
  );
}

export default App;
