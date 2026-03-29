# Manchu Font Visualizer

一个可部署到 GitHub Pages 的纯前端满文字体可视化工具。

## Features

- 输入宽松 ASCII 风格的 Manchu Roman
- 自动规范化常见别名，例如 `sh -> š`、`v -> ū`
- 实时转换为 Unicode 满文
- 在内置 `ttf` 字体间切换预览
- 支持竖排主视图、横排调试视图、Unicode 复制

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

构建输出位于 `dist/`。

## Dataset Generation

可以直接把 `AllWords.txt` 生成为 Hugging Face 风格的词图数据集：

```bash
python3 scripts/generate_manchu_hf_dataset.py \
  --words-file AllWords.txt \
  --fonts XM_ShuKai.ttf "Sungar PaKa.ttf" \
  --output-dir dataset/hf-ready \
  --canvas-width 480 \
  --canvas-height 64 \
  --seed 42
```

输出结构如下：

```text
dataset/hf-ready/
  train/
    images/<font_id>/*.png
    metadata.csv
    metadata_hf.csv
  validation/
    images/<font_id>/*.png
    metadata.csv
    metadata_hf.csv
  summary.json
```

`metadata.csv` 的列顺序固定为 `im,roman,manchu`。同时会额外生成 `metadata_hf.csv`，列顺序为 `file_name,roman,manchu`，更适合直接给 Hugging Face `ImageFolder` 使用。默认画布固定为 `480x64`，内容会等比缩放后左对齐放置，并在垂直方向居中。

## GitHub Pages

这个仓库使用 GitHub Actions 部署到 GitHub Pages。

1. 在仓库的 `Settings -> Pages` 中，把 `Source` 设为 `GitHub Actions`
2. 不要使用 `Deploy from a branch`
3. 推送到 `main` 后，等待 `.github/workflows/deploy.yml` 完成

这个仓库把 Vite `base` 设为 `./`，这样同一份构建产物既能跑在 GitHub Pages 项目地址 `/<repo>/` 下，也能跑在自定义域名根路径下。

如果 `Pages` 仍然指向分支根目录，GitHub 会直接服务源码里的 `index.html`，浏览器就会去请求 `./src/main.tsx`，然后出现模块脚本 MIME 报错。
