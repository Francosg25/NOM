// Component work only: jsdom does not measure browser paint or scrolling.
// Usage: node scripts/profile-reader.mjs reading.json output.json
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const project = fileURLToPath(new URL('../', import.meta.url));
const require = createRequire(path.join(project, 'frontend/package.json'));
const { build } = require('esbuild');
const { JSDOM } = require('jsdom');
const reading = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost/' });
for (const name of ['window', 'document', 'location', 'history', 'localStorage', 'HTMLElement']) {
  globalThis[name] = dom.window[name];
}
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
process.env.NODE_ENV = 'production';
const cache = path.join(project, 'frontend/node_modules/.cache');
mkdirSync(cache, { recursive: true });
const bundle = path.join(cache, 'nom-reader-profile.mjs');
await build({
  stdin: { contents: `export {default as DocumentReading} from './src/DocumentReading';
    export {LanguageProvider} from './src/i18n';
    export {default as React} from 'react';
    export {createRoot} from 'react-dom/client'; export {flushSync} from 'react-dom';`,
    resolveDir: path.join(project, 'frontend'), loader: 'tsx' },
  outfile: bundle, bundle: true, platform: 'node', format: 'esm', packages: 'external',
  jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' },
});
const { React, DocumentReading, LanguageProvider, createRoot, flushSync } = await import(pathToFileURL(bundle));
const mount = [], counts = [];
let partCount = 1, maxPartElements = 0, renderedCharacters = 0;
const version = { id: 1, content: '', reading };
const load = async () => { throw new Error('No network belongs in this component probe'); };
for (let attempt = 0; attempt < 6; attempt++) {
  const host = document.getElementById('root');
  const root = createRoot(host);
  const started = performance.now();
  flushSync(() => root.render(React.createElement(LanguageProvider, null,
    React.createElement(DocumentReading, { version, load }))));
  const elapsed = performance.now() - started;
  if (attempt) { mount.push(elapsed); counts.push(host.querySelectorAll('*').length); }
  if (attempt === 5) {
    const selector = host.querySelector('.reading-pagination select');
    partCount = selector?.options.length || 1;
    for (let index = 0; index < partCount; index++) {
      if (selector) flushSync(() => {
        selector.value = String(index);
        selector.dispatchEvent(new window.Event('change', { bubbles: true }));
      });
      maxPartElements = Math.max(maxPartElements, host.querySelectorAll('*').length);
      renderedCharacters += host.querySelector('.document-reading').textContent.replace(/\s/g, '').length;
    }
  }
  flushSync(() => root.unmount());
}
const result = { environment: 'production React + jsdom; no layout/paint measurement',
  blocks_in_source: reading.blocks.length, first_part_elements: Math.max(...counts),
  parts: partCount, max_part_elements: maxPartElements, non_whitespace_characters_across_parts: renderedCharacters,
  mount_median_ms: +mount.sort((a, b) => a - b)[Math.floor(mount.length / 2)].toFixed(2),
  mount_samples_ms: mount.map((v) => +v.toFixed(2)) };
if (process.argv[3]) writeFileSync(process.argv[3], JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result));
dom.window.close();
