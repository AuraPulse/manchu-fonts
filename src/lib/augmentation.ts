export type AugmentPreset = 'off' | 'light' | 'medium' | 'heavy';
export type PatchShape = 'rectangle' | 'circle' | 'mixed';

export type StrokeAugmentationConfig = {
  enabled: boolean;
  threshold: number;
  pixelDropoutApplyProb: number;
  pixelDropoutRatioMin: number;
  pixelDropoutRatioMax: number;
  patchDropoutApplyProb: number;
  patchCountMin: number;
  patchCountMax: number;
  patchSizeMin: number;
  patchSizeMax: number;
  patchShape: PatchShape;
};

export type DatasetPreviewRenderOptions = {
  text: string;
  fontFamily: string;
  canvasWidth: number;
  canvasHeight: number;
  paddingPercentage: number;
  seed: number;
  config: StrokeAugmentationConfig;
};

const PROBE_FONT_SIZE = 256;
const DEFAULT_BACKGROUND = 255;
const DEFAULT_FOREGROUND = 0;

export const getAugmentationPreset = (preset: AugmentPreset): StrokeAugmentationConfig => {
  switch (preset) {
    case 'light':
      return {
        enabled: true,
        threshold: 220,
        pixelDropoutApplyProb: 0.45,
        pixelDropoutRatioMin: 0.006,
        pixelDropoutRatioMax: 0.018,
        patchDropoutApplyProb: 0.35,
        patchCountMin: 1,
        patchCountMax: 2,
        patchSizeMin: 2,
        patchSizeMax: 4,
        patchShape: 'circle',
      };
    case 'medium':
      return {
        enabled: true,
        threshold: 220,
        pixelDropoutApplyProb: 0.65,
        pixelDropoutRatioMin: 0.01,
        pixelDropoutRatioMax: 0.03,
        patchDropoutApplyProb: 0.65,
        patchCountMin: 1,
        patchCountMax: 3,
        patchSizeMin: 2,
        patchSizeMax: 6,
        patchShape: 'mixed',
      };
    case 'heavy':
      return {
        enabled: true,
        threshold: 220,
        pixelDropoutApplyProb: 0.9,
        pixelDropoutRatioMin: 0.02,
        pixelDropoutRatioMax: 0.06,
        patchDropoutApplyProb: 0.9,
        patchCountMin: 3,
        patchCountMax: 6,
        patchSizeMin: 3,
        patchSizeMax: 9,
        patchShape: 'mixed',
      };
    case 'off':
    default:
      return {
        enabled: false,
        threshold: 220,
        pixelDropoutApplyProb: 0,
        pixelDropoutRatioMin: 0.01,
        pixelDropoutRatioMax: 0.03,
        patchDropoutApplyProb: 0,
        patchCountMin: 1,
        patchCountMax: 3,
        patchSizeMin: 2,
        patchSizeMax: 6,
        patchShape: 'rectangle',
      };
  }
};

export const cloneAugmentationConfig = (
  config: StrokeAugmentationConfig,
): StrokeAugmentationConfig => ({ ...config });

const createSeededRandom = (seed: number) => {
  let state = seed >>> 0;

  return () => {
    state += 0x6d2b79f5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

const randomInt = (random: () => number, min: number, max: number) =>
  Math.floor(random() * (max - min + 1)) + min;

const randomFloat = (random: () => number, min: number, max: number) =>
  min + random() * (max - min);

const fillWhite = (data: Uint8ClampedArray, index: number) => {
  data[index] = DEFAULT_BACKGROUND;
  data[index + 1] = DEFAULT_BACKGROUND;
  data[index + 2] = DEFAULT_BACKGROUND;
  data[index + 3] = 255;
};

const isStrokePixel = (data: Uint8ClampedArray, index: number, threshold: number) => {
  const grayscale = (data[index] + data[index + 1] + data[index + 2]) / 3;
  return grayscale < threshold;
};

const collectStrokePixels = (imageData: ImageData, threshold: number) => {
  const pixels: Array<{ x: number; y: number }> = [];
  const { data, width, height } = imageData;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      if (isStrokePixel(data, index, threshold)) {
        pixels.push({ x, y });
      }
    }
  }

  return pixels;
};

const shuffleInPlace = <T,>(values: T[], random: () => number) => {
  for (let index = values.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1));
    const current = values[index]!;
    values[index] = values[swapIndex]!;
    values[swapIndex] = current;
  }
};

const applyPixelDropout = (imageData: ImageData, config: StrokeAugmentationConfig, random: () => number) => {
  if (random() >= config.pixelDropoutApplyProb) {
    return;
  }

  const strokePixels = collectStrokePixels(imageData, config.threshold);
  if (strokePixels.length === 0) {
    return;
  }

  const ratio = randomFloat(random, config.pixelDropoutRatioMin, config.pixelDropoutRatioMax);
  const dropCount = Math.max(1, Math.floor(strokePixels.length * ratio));
  shuffleInPlace(strokePixels, random);

  for (const pixel of strokePixels.slice(0, dropCount)) {
    const index = (pixel.y * imageData.width + pixel.x) * 4;
    fillWhite(imageData.data, index);
  }
};

const applyPatchDropout = (imageData: ImageData, config: StrokeAugmentationConfig, random: () => number) => {
  if (random() >= config.patchDropoutApplyProb) {
    return;
  }

  const strokePixels = collectStrokePixels(imageData, config.threshold);
  if (strokePixels.length === 0) {
    return;
  }

  const patchCount = randomInt(random, config.patchCountMin, config.patchCountMax);

  for (let patchIndex = 0; patchIndex < patchCount; patchIndex += 1) {
    const center = strokePixels[randomInt(random, 0, strokePixels.length - 1)]!;
    const patchWidth = randomInt(random, config.patchSizeMin, config.patchSizeMax);
    const patchHeight = randomInt(random, config.patchSizeMin, config.patchSizeMax);
    const x0 = Math.max(0, center.x - Math.floor(patchWidth / 2));
    const y0 = Math.max(0, center.y - Math.floor(patchHeight / 2));
    const x1 = Math.min(imageData.width, x0 + patchWidth);
    const y1 = Math.min(imageData.height, y0 + patchHeight);
    const shape =
      config.patchShape === 'mixed'
        ? (random() < 0.5 ? 'rectangle' : 'circle')
        : config.patchShape;

    const radiusX = Math.max((x1 - x0) / 2, 1);
    const radiusY = Math.max((y1 - y0) / 2, 1);
    const centerX = x0 + (x1 - x0 - 1) / 2;
    const centerY = y0 + (y1 - y0 - 1) / 2;

    for (let y = y0; y < y1; y += 1) {
      for (let x = x0; x < x1; x += 1) {
        const index = (y * imageData.width + x) * 4;
        if (!isStrokePixel(imageData.data, index, config.threshold)) {
          continue;
        }

        if (shape === 'circle') {
          const normalizedX = (x - centerX) / radiusX;
          const normalizedY = (y - centerY) / radiusY;
          if (normalizedX * normalizedX + normalizedY * normalizedY > 1) {
            continue;
          }
        }

        fillWhite(imageData.data, index);
      }
    }
  }
};

const findBoundingBox = (imageData: ImageData, threshold: number) => {
  const { data, width, height } = imageData;
  let left = width;
  let top = height;
  let right = -1;
  let bottom = -1;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      if (!isStrokePixel(data, index, threshold)) {
        continue;
      }

      left = Math.min(left, x);
      top = Math.min(top, y);
      right = Math.max(right, x);
      bottom = Math.max(bottom, y);
    }
  }

  if (right < left || bottom < top) {
    return null;
  }

  return {
    x: left,
    y: top,
    width: right - left + 1,
    height: bottom - top + 1,
  };
};

export const renderAugmentedDatasetPreview = async (
  canvas: HTMLCanvasElement,
  options: DatasetPreviewRenderOptions,
) => {
  let context: CanvasRenderingContext2D | null = null;
  try {
    context = canvas.getContext('2d');
  } catch {
    return false;
  }
  if (!context) {
    return false;
  }

  const { text, fontFamily, canvasWidth, canvasHeight, paddingPercentage, seed, config } = options;

  canvas.width = canvasWidth;
  canvas.height = canvasHeight;
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvasWidth, canvasHeight);

  if (!text.trim()) {
    return true;
  }

  if ('fonts' in document) {
    await document.fonts.ready;
  }

  const probeCanvas = document.createElement('canvas');
  let probeContext: CanvasRenderingContext2D | null = null;
  try {
    probeContext = probeCanvas.getContext('2d');
  } catch {
    return false;
  }
  if (!probeContext) {
    return false;
  }

  const margin = 64;
  probeCanvas.width = 4096;
  probeCanvas.height = 512;
  probeContext.fillStyle = '#ffffff';
  probeContext.fillRect(0, 0, probeCanvas.width, probeCanvas.height);
  probeContext.font = `${PROBE_FONT_SIZE}px "${fontFamily}"`;
  probeContext.textBaseline = 'alphabetic';
  probeContext.fillStyle = '#000000';

  const metrics = probeContext.measureText(text);
  const drawX = margin - (metrics.actualBoundingBoxLeft || 0);
  const drawY = margin + (metrics.actualBoundingBoxAscent || PROBE_FONT_SIZE * 0.8);
  probeContext.fillText(text, drawX, drawY);

  const probeImageData = probeContext.getImageData(0, 0, probeCanvas.width, probeCanvas.height);
  const box = findBoundingBox(probeImageData, 220);

  if (!box) {
    return true;
  }

  const leftPadding = Math.ceil(canvasWidth * paddingPercentage);
  const topPadding = Math.ceil(canvasHeight * paddingPercentage);
  const bottomPadding = Math.ceil(canvasHeight * paddingPercentage);
  const availableWidth = Math.max(1, canvasWidth - leftPadding);
  const availableHeight = Math.max(1, canvasHeight - topPadding - bottomPadding);
  const scale = Math.min(availableWidth / box.width, availableHeight / box.height);
  const scaledWidth = Math.max(1, Math.min(availableWidth, Math.floor(box.width * scale)));
  const scaledHeight = Math.max(1, Math.min(availableHeight, Math.floor(box.height * scale)));
  const yOffset = topPadding + Math.max(0, Math.floor((availableHeight - scaledHeight) / 2));

  context.imageSmoothingEnabled = true;
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvasWidth, canvasHeight);
  context.drawImage(
    probeCanvas,
    box.x,
    box.y,
    box.width,
    box.height,
    leftPadding,
    yOffset,
    scaledWidth,
    scaledHeight,
  );

  if (!config.enabled) {
    return true;
  }

  const imageData = context.getImageData(0, 0, canvasWidth, canvasHeight);
  const random = createSeededRandom(seed);
  applyPixelDropout(imageData, config, random);
  applyPatchDropout(imageData, config, random);
  context.putImageData(imageData, 0, 0);
  return true;
};
