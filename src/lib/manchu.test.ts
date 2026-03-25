import { buildPreviewSegments, normalizeRoman, romanToManchu } from './manchu';

describe('normalizeRoman', () => {
  it('normalizes mixed case and ASCII aliases', () => {
    expect(normalizeRoman('SHuV')).toBe('šuū');
  });
});

describe('romanToManchu', () => {
  it('keeps longest match for ng', () => {
    expect(romanToManchu('angga').manchuText).toBe('ᠠᠩᡤᠠ');
  });

  it('preserves whitespace and punctuation', () => {
    expect(romanToManchu('manju, gisun.').manchuText).toBe('ᠮᠠᠨᠵᡠ, ᡤᡳᠰᡠᠨ.');
  });

  it('returns unknown fragments without swallowing the rest', () => {
    const result = romanToManchu('qa');

    expect(result.manchuText).toBe('qᠠ');
    expect(result.errors).toEqual([
      {
        start: 0,
        end: 1,
        raw: 'q',
      },
    ]);
  });
});

describe('buildPreviewSegments', () => {
  it('marks unknown segments for highlighting', () => {
    expect(buildPreviewSegments('manju z')).toEqual([
      {
        kind: 'manchu',
        text: 'ᠮ',
        sourceStart: 0,
        sourceEnd: 1,
      },
      {
        kind: 'manchu',
        text: 'ᠠ',
        sourceStart: 1,
        sourceEnd: 2,
      },
      {
        kind: 'manchu',
        text: 'ᠨ',
        sourceStart: 2,
        sourceEnd: 3,
      },
      {
        kind: 'manchu',
        text: 'ᠵ',
        sourceStart: 3,
        sourceEnd: 4,
      },
      {
        kind: 'manchu',
        text: 'ᡠ',
        sourceStart: 4,
        sourceEnd: 5,
      },
      {
        kind: 'passthrough',
        text: ' ',
        sourceStart: 5,
        sourceEnd: 6,
      },
      {
        kind: 'unknown',
        text: 'z',
        sourceStart: 6,
        sourceEnd: 7,
      },
    ]);
  });
});
