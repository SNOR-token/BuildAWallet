import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname);
const outdir = resolve(root, 'dist');
await mkdir(outdir,{recursive:true});
await build({entryPoints:[resolve(root,'src/popup.mjs')],outfile:resolve(outdir,'popup.bundle.js'),bundle:true,
  platform:'browser',target:'chrome120',format:'esm',minify:false,sourcemap:false,legalComments:'inline'});
for(const file of ['manifest.json','popup.html','popup.css'])await copyFile(resolve(root,file),resolve(outdir,file));
console.log('Built Sepolia-only unpacked prototype:',outdir);
