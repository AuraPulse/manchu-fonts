import { getAugmentationPreset } from './augmentation';

describe('getAugmentationPreset', () => {
  it('returns lighter and heavier configs with different strengths', () => {
    const light = getAugmentationPreset('light');
    const medium = getAugmentationPreset('medium');
    const heavy = getAugmentationPreset('heavy');

    expect(light.patchShape).toBe('circle');
    expect(medium.patchShape).toBe('mixed');
    expect(heavy.patchShape).toBe('mixed');
    expect(light.pixelDropoutRatioMax).toBeLessThan(heavy.pixelDropoutRatioMax);
    expect(light.patchCountMax).toBeLessThan(heavy.patchCountMax);
  });

  it('disables augmentation for off preset', () => {
    expect(getAugmentationPreset('off').enabled).toBe(false);
  });
});
