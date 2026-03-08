import * as esbuild from 'esbuild';
import { copyFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';

const isWatch = process.argv.includes('--watch');

// Copy VAD runtime files (ONNX model, worklet, WASM) to static directory
const wasmDir = 'promaia/web/static/vad';
if (!existsSync(wasmDir)) mkdirSync(wasmDir, { recursive: true });

// VAD model + worklet
const vadDist = 'node_modules/@ricky0123/vad-web/dist';
if (existsSync(vadDist)) {
    for (const file of readdirSync(vadDist)) {
        if (file.endsWith('.onnx') || file === 'vad.worklet.bundle.min.js') {
            copyFileSync(join(vadDist, file), join(wasmDir, file));
            console.log(`  copied ${file}`);
        }
    }
}

// ONNX runtime WASM
const onnxDist = 'node_modules/onnxruntime-web/dist';
if (existsSync(onnxDist)) {
    for (const file of readdirSync(onnxDist)) {
        if (file.endsWith('.wasm') || file.endsWith('.mjs')) {
            copyFileSync(join(onnxDist, file), join(wasmDir, file));
            console.log(`  copied ${file}`);
        }
    }
}

const config = {
    entryPoints: ['promaia/web/static/js/talk.src.js'],
    bundle: true,
    outfile: 'promaia/web/static/js/talk.js',
    format: 'iife',
    target: ['es2020'],
    sourcemap: true,
    minify: !isWatch,
};

if (isWatch) {
    const ctx = await esbuild.context(config);
    await ctx.watch();
    console.log('Watching for changes...');
} else {
    await esbuild.build(config);
    console.log('Build complete');
}
