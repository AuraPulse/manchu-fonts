export type RomanError = {
  start: number;
  end: number;
  raw: string;
};

export type PreviewSegment = {
  kind: 'manchu' | 'unknown' | 'passthrough';
  text: string;
  sourceStart: number;
  sourceEnd: number;
};

type NormalizedUnit = {
  value: string;
  sourceStart: number;
  sourceEnd: number;
};

const ALIAS_RULES: Array<{ raw: string; value: string }> = [
  { raw: 's\u030c', value: 'š' },
  { raw: 'u\u0304', value: 'ū' },
  { raw: 'sh', value: 'š' },
  { raw: 'uu', value: 'ū' },
  { raw: 'x', value: 'š' },
  { raw: 'v', value: 'ū' },
  { raw: 'ü', value: 'ū' },
];

const TOKEN_MAP = new Map<string, string>([
  ['ng', 'ᠩ'],
  ['a', 'ᠠ'],
  ['e', 'ᡝ'],
  ['i', 'ᡳ'],
  ['o', 'ᠣ'],
  ['u', 'ᡠ'],
  ['ū', 'ᡡ'],
  ['n', 'ᠨ'],
  ['b', 'ᠪ'],
  ['p', 'ᡦ'],
  ['k', 'ᡴ'],
  ['g', 'ᡤ'],
  ['h', 'ᡥ'],
  ['m', 'ᠮ'],
  ['l', 'ᠯ'],
  ['s', 'ᠰ'],
  ['š', 'ᡧ'],
  ['t', 'ᡨ'],
  ['d', 'ᡩ'],
  ['c', 'ᠴ'],
  ['j', 'ᠵ'],
  ['y', 'ᠶ'],
  ['r', 'ᡵ'],
  ['f', 'ᡶ'],
  ['w', 'ᠸ'],
]);

const TOKENS = [...TOKEN_MAP.keys()].sort((left, right) => right.length - left.length);
const PASSTHROUGH_PATTERN = /[\p{White_Space}\p{P}\p{S}\p{N}]/u;

const normalizeRomanWithMap = (input: string): { normalized: string; units: NormalizedUnit[] } => {
  const lowerCased = input.toLowerCase();
  const units: NormalizedUnit[] = [];

  for (let index = 0; index < lowerCased.length; ) {
    const remaining = lowerCased.slice(index);
    const alias = ALIAS_RULES.find((rule) => remaining.startsWith(rule.raw));

    if (alias) {
      units.push({
        value: alias.value,
        sourceStart: index,
        sourceEnd: index + alias.raw.length,
      });
      index += alias.raw.length;
      continue;
    }

    const currentCharacter = String.fromCodePoint(lowerCased.codePointAt(index)!);
    units.push({
      value: currentCharacter,
      sourceStart: index,
      sourceEnd: index + currentCharacter.length,
    });
    index += currentCharacter.length;
  }

  return {
    normalized: units.map((unit) => unit.value).join(''),
    units,
  };
};

const isPassthrough = (value: string) => PASSTHROUGH_PATTERN.test(value);

const matchesKnownToken = (normalized: string, index: number) =>
  TOKENS.some((token) => normalized.startsWith(token, index));

export const normalizeRoman = (input: string): string => normalizeRomanWithMap(input).normalized;

export const buildPreviewSegments = (input: string): PreviewSegment[] => {
  const { normalized, units } = normalizeRomanWithMap(input);
  const segments: PreviewSegment[] = [];

  for (let index = 0; index < normalized.length; ) {
    const currentValue = normalized[index]!;

    if (isPassthrough(currentValue)) {
      let end = index + 1;
      while (end < normalized.length && isPassthrough(normalized[end]!)) {
        end += 1;
      }

      segments.push({
        kind: 'passthrough',
        text: input.slice(units[index]!.sourceStart, units[end - 1]!.sourceEnd),
        sourceStart: units[index]!.sourceStart,
        sourceEnd: units[end - 1]!.sourceEnd,
      });
      index = end;
      continue;
    }

    const matchedToken = TOKENS.find((token) => normalized.startsWith(token, index));

    if (matchedToken) {
      const mapped = TOKEN_MAP.get(matchedToken)!;
      const tokenEnd = index + matchedToken.length - 1;
      segments.push({
        kind: 'manchu',
        text: mapped,
        sourceStart: units[index]!.sourceStart,
        sourceEnd: units[tokenEnd]!.sourceEnd,
      });
      index += matchedToken.length;
      continue;
    }

    let end = index + 1;
    while (
      end < normalized.length &&
      !isPassthrough(normalized[end]!) &&
      !matchesKnownToken(normalized, end)
    ) {
      end += 1;
    }

    segments.push({
      kind: 'unknown',
      text: input.slice(units[index]!.sourceStart, units[end - 1]!.sourceEnd),
      sourceStart: units[index]!.sourceStart,
      sourceEnd: units[end - 1]!.sourceEnd,
    });
    index = end;
  }

  return segments;
};

export const romanToManchu = (input: string): { manchuText: string; errors: RomanError[] } => {
  const segments = buildPreviewSegments(input);

  return {
    manchuText: segments.map((segment) => segment.text).join(''),
    errors: segments
      .filter((segment) => segment.kind === 'unknown')
      .map((segment) => ({
        start: segment.sourceStart,
        end: segment.sourceEnd,
        raw: segment.text,
      })),
  };
};
