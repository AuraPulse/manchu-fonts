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

构建输出位于 `dist/`，由于 Vite `base` 已设为 `./`，可以直接用于 GitHub Pages 或其他静态托管。
