const fs = require('fs');

const [mode, scanPath, outputPath, projectRoot, commitHash] = process.argv.slice(2);
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'));
if (mode === 'fingerprint-input') {
  fs.writeFileSync(outputPath, `${JSON.stringify({
    projectRoot,
    sourceFilePaths: scan.files.map((file) => file.path),
    gitCommitHash: commitHash,
  }, null, 2)}\n`);
} else if (mode === 'meta') {
  fs.writeFileSync(outputPath, `${JSON.stringify({
    lastAnalyzedAt: new Date().toISOString(),
    gitCommitHash: commitHash,
    version: '1.0.0',
    analyzedFiles: scan.files.length,
  }, null, 2)}\n`);
} else {
  throw new Error(`Unknown mode: ${mode}`);
}
