import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import { execFileSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const packageJson = JSON.parse(await readFile(resolve(root, 'package.json'), 'utf8'));
const packageLock = JSON.parse(await readFile(resolve(root, 'package-lock.json'), 'utf8'));
const staticRoot = resolve(root, 'static');
const vendorRoot = resolve(root, 'assets/vendor');

await mkdir(resolve(staticRoot, 'css'), { recursive: true });
await mkdir(resolve(staticRoot, 'js'), { recursive: true });
await mkdir(resolve(staticRoot, 'vendor'), { recursive: true });
await mkdir(vendorRoot, { recursive: true });

await execFileSync(resolve(root, 'node_modules/.bin/tailwindcss'), [
  '-i', resolve(root, 'assets/source/app.css'),
  '-o', resolve(staticRoot, 'css/app.css'),
  '--minify',
], { cwd: root, stdio: 'inherit' });

await build({
  entryPoints: [resolve(root, 'assets/source/cornerstone-renderer.js')],
  bundle: true,
  format: 'iife',
  globalName: 'LumoraCornerstone',
  minify: true,
  sourcemap: false,
  outfile: resolve(staticRoot, 'js/cornerstone-renderer.js'),
  platform: 'browser',
});

const copies = {
  'htmx.min.js': 'htmx.org/dist/htmx.min.js',
  'alpine.min.js': 'alpinejs/dist/cdn.min.js',
  'chart.umd.min.js': 'chart.js/dist/chart.umd.min.js',
  'tabulator.min.js': 'tabulator-tables/dist/js/tabulator.min.js',
  'tabulator.min.css': 'tabulator-tables/dist/css/tabulator.min.css',
};
for (const [output, source] of Object.entries(copies)) {
  await cp(resolve(root, 'node_modules', source), resolve(vendorRoot, output));
}

const packageNames = Object.keys({ ...packageJson.dependencies, ...packageJson.devDependencies }).sort();
const manifest = {
  generated_by: 'npm run build:assets',
  rendering_bundle: {
    path: 'static/js/cornerstone-renderer.js',
    package: '@cornerstonejs/core',
    purpose: 'rendering path only; DICOM parsing and WASM codecs remain server-side',
  },
  dependencies: packageNames.map((name) => {
    const packageData = packageLock.packages[`node_modules/${name}`] ?? {};
    return {
      name,
      version: packageData.version ?? 'SEE_PACKAGE_METADATA',
      license: packageData.license ?? 'SEE_PACKAGE_METADATA',
    };
  }),
  vendored: Object.keys(copies).map((name) => ({
    path: `assets/vendor/${name}`,
    source: copies[name],
  })),
};
await writeFile(resolve(vendorRoot, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
