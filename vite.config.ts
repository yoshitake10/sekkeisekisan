import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * dist/ をファイルサーバーから file:// で直接開いても動くようにする。
 *
 * Vite 既定の出力は <script type="module" crossorigin> だが、file:// では
 * モジュールスクリプトと crossorigin 付きCSSが CORS で読み込めず、画面が
 * 真っ白になる（README の「社内ファイルサーバーに置くだけ」が成り立たない）。
 * そこで本番ビルドは IIFE 形式の通常スクリプト1本にまとめ、index.html から
 * type="module" / crossorigin / modulepreload を外す。
 * http(s) 配信（GitHub Pages・イントラWebサーバー）でもそのまま動く。
 */
function classicScriptForFileProtocol(): Plugin {
  return {
    name: 'classic-script-for-file-protocol',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler(html) {
        return html
          .replace(/<script type="module" crossorigin src=/g, '<script defer src=')
          .replace(/<link rel="stylesheet" crossorigin href=/g, '<link rel="stylesheet" href=')
          .replace(/\s*<link rel="modulepreload" crossorigin href="[^"]*">/g, '')
      },
    },
  }
}

export default defineConfig({
  plugins: [react(), classicScriptForFileProtocol()],
  base: './',
  build: {
    chunkSizeWarningLimit: 4000,
    modulePreload: false,
    rollupOptions: {
      output: {
        format: 'iife',
        inlineDynamicImports: true,
      },
    },
  },
})
