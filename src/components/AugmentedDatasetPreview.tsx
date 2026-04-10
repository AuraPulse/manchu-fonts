import { useEffect, useRef, useState } from 'react';
import { FONT_OPTIONS } from '../generated/fontManifest';
import {
  renderAugmentedDatasetPreview,
  type StrokeAugmentationConfig,
} from '../lib/augmentation';

type AugmentedDatasetPreviewProps = {
  text: string;
  fontId: string;
  seed: number;
  config: StrokeAugmentationConfig;
  presetLabel: string;
};

export function AugmentedDatasetPreview({
  text,
  fontId,
  seed,
  config,
  presetLabel,
}: AugmentedDatasetPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderStatus, setRenderStatus] = useState<'idle' | 'ready' | 'empty' | 'failed'>('idle');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const selectedFont =
      FONT_OPTIONS.find((font) => font.id === fontId) ??
      FONT_OPTIONS[0];

    if (!selectedFont) {
      setRenderStatus('failed');
      return;
    }

    if (!text.trim()) {
      const context = canvas.getContext('2d');
      if (context) {
        canvas.width = 480;
        canvas.height = 64;
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
      }
      setRenderStatus('empty');
      return;
    }

    let isCancelled = false;

    const render = async () => {
      try {
        const didRender = await renderAugmentedDatasetPreview(canvas, {
          text,
          fontFamily: selectedFont.family,
          canvasWidth: 480,
          canvasHeight: 64,
          paddingPercentage: 0.05,
          seed,
          config,
        });

        if (!isCancelled) {
          setRenderStatus(didRender ? 'ready' : 'failed');
        }
      } catch {
        if (!isCancelled) {
          setRenderStatus('failed');
        }
      }
    };

    void render();

    return () => {
      isCancelled = true;
    };
  }, [config, fontId, seed, text]);

  return (
    <article className="preview-panel preview-panel--dataset">
      <div className="preview-panel__header">
        <div className="preview-panel__title">
          <h3>Augmented</h3>
          <span>480 x 64 dataset-style preview</span>
        </div>
      </div>
      <div className="dataset-preview-frame">
        <canvas
          ref={canvasRef}
          aria-label="Augmented dataset preview"
          className="dataset-preview-canvas"
          width={480}
          height={64}
        />
      </div>
      <p className="dataset-preview-caption" role="status" aria-live="polite">
        {renderStatus === 'ready'
          ? `${presetLabel}. Pixel ${Math.round(config.pixelDropoutApplyProb * 100)}%, patch ${Math.round(config.patchDropoutApplyProb * 100)}%, seed ${seed}`
          : null}
        {renderStatus === 'empty' ? 'Enter Roman text to see the augmented preview.' : null}
        {renderStatus === 'failed' ? 'Canvas preview unavailable in this environment.' : null}
      </p>
    </article>
  );
}
