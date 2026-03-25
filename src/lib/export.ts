const EXPORT_BACKGROUND = '#ffffff';

const downloadDataUrl = (dataUrl: string, fileName: string) => {
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = fileName;
  link.click();
};

const makeExportImage = async (node: HTMLElement) => {
  await document.fonts.ready;
  const { toPng } = await import('html-to-image');

  const previousExportFlag = node.dataset.exporting;

  node.dataset.exporting = 'true';

  try {
    const dataUrl = await toPng(node, {
      backgroundColor: EXPORT_BACKGROUND,
      cacheBust: true,
      pixelRatio: 2,
    });

    const image = new Image();

    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Failed to load exported image.'));
      image.src = dataUrl;
    });

    return {
      dataUrl,
      width: image.width,
      height: image.height,
    };
  } finally {
    if (previousExportFlag === undefined) {
      delete node.dataset.exporting;
    } else {
      node.dataset.exporting = previousExportFlag;
    }
  }
};

export const exportPreviewAsPng = async (node: HTMLElement, fileName: string) => {
  const { dataUrl } = await makeExportImage(node);
  downloadDataUrl(dataUrl, fileName);
};

export const exportPreviewAsPdf = async (node: HTMLElement, fileName: string) => {
  const { dataUrl, width, height } = await makeExportImage(node);
  const { jsPDF } = await import('jspdf');
  const pdf = new jsPDF({
    orientation: width >= height ? 'landscape' : 'portrait',
    unit: 'px',
    format: [width, height],
    compress: true,
  });

  pdf.addImage(dataUrl, 'PNG', 0, 0, width, height);
  pdf.save(fileName);
};
