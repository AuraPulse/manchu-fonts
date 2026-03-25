import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { FONT_OPTIONS } from './generated/fontManifest';
import { copyUnicodeText } from './lib/clipboard';
import * as exportModule from './lib/export';
import { romanToManchu } from './lib/manchu';

vi.mock('./lib/clipboard', () => ({
  copyUnicodeText: vi.fn(),
}));

vi.mock('./lib/export', () => ({
  exportPreviewAsPng: vi.fn(),
  exportPreviewAsPdf: vi.fn(),
}));

describe('App', () => {
  beforeEach(() => {
    window.location.hash = '';
    vi.clearAllMocks();
    vi.mocked(copyUnicodeText).mockResolvedValue(true);
    vi.mocked(exportModule.exportPreviewAsPng).mockResolvedValue(undefined);
    vi.mocked(exportModule.exportPreviewAsPdf).mockResolvedValue(undefined);
  });

  it('updates font family when the selector changes', async () => {
    const user = userEvent.setup();
    render(<App />);

    const selector = screen.getByLabelText('Font selector');
    const options = screen.getAllByRole('option');
    const verticalPreview = screen.getByLabelText('Vertical Manchu preview');

    await user.selectOptions(selector, options[1]!);

    expect(verticalPreview.getAttribute('data-font-family')).toBeTruthy();
    expect(verticalPreview.getAttribute('data-font-family')).not.toEqual('');
  });

  it('applies slider changes to preview styles', async () => {
    render(<App />);

    const fontSize = screen.getByLabelText('Font size');
    const lineGap = screen.getByLabelText('Line gap');
    const verticalPreview = screen.getByLabelText('Vertical Manchu preview');

    fireEvent.change(fontSize, { target: { value: '72' } });
    fireEvent.change(lineGap, { target: { value: '0.2' } });

    expect(verticalPreview).toHaveStyle({
      fontSize: '72px',
      letterSpacing: '0.2em',
    });
  });

  it('shows unicode output and copies the same value', async () => {
    const user = userEvent.setup();
    render(<App />);

    const expected = romanToManchu('manju gisun\nabkai').manchuText;
    expect(
      screen.getByText(
        (_, element) =>
          element?.classList.contains('unicode-output') === true &&
          element.textContent === expected,
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Copy Unicode' }));

    expect(copyUnicodeText).toHaveBeenCalledWith(expected);
    expect(screen.getByText('Copied to clipboard')).toBeInTheDocument();
  });

  it('exports preview as png and pdf', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Export single vertical preview as PNG' }));
    await user.click(screen.getByRole('button', { name: 'Export single horizontal preview as PDF' }));

    expect(exportModule.exportPreviewAsPng).toHaveBeenCalledTimes(1);
    expect(exportModule.exportPreviewAsPdf).toHaveBeenCalledTimes(1);
  });

  it('shows mixed-font items with different font families together', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Mixed Fonts' }));
    await user.clear(screen.getByLabelText('All fonts Roman input'));
    await user.type(screen.getByLabelText('All fonts Roman input'), 'abkai');
    await user.click(screen.getByRole('button', { name: 'Show in all fonts' }));

    const mixedPreview = screen.getByLabelText('Horizontal mixed Manchu preview');
    const items = mixedPreview.querySelectorAll('.mixed-item');

    expect(items.length).toBe(FONT_OPTIONS.length);
    expect(items[0]?.getAttribute('data-font-family')).not.toEqual(items[1]?.getAttribute('data-font-family'));
    expect(screen.getByText('abkai')).toBeInTheDocument();
  });

  it('lets me exclude fonts from the mixed-font preview with checkboxes', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Mixed Fonts' }));

    const mixedPreview = screen.getByLabelText('Horizontal mixed Manchu preview');
    expect(mixedPreview.querySelectorAll('.mixed-item').length).toBe(FONT_OPTIONS.length);

    await user.click(screen.getByLabelText(`Toggle ${FONT_OPTIONS[0]!.label}`));
    await user.click(screen.getByLabelText(`Toggle ${FONT_OPTIONS[1]!.label}`));

    expect(mixedPreview.querySelectorAll('.mixed-item').length).toBe(FONT_OPTIONS.length - 2);
  });

  it('exports the mixed-font page as png and pdf', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Mixed Fonts' }));
    await user.click(screen.getByRole('button', { name: 'Export mixed vertical preview as PNG' }));
    await user.click(screen.getByRole('button', { name: 'Export mixed horizontal preview as PDF' }));

    expect(exportModule.exportPreviewAsPng).toHaveBeenCalledTimes(1);
    expect(exportModule.exportPreviewAsPdf).toHaveBeenCalledTimes(1);
  });

  it('switches between pages from the navigation bar', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText('Roman Input')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Mixed Fonts' }));

    expect(screen.getByText('All Fonts Preview')).toBeInTheDocument();
    expect(screen.queryByText('Roman Input')).not.toBeInTheDocument();
  });
});
