#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const mode = process.argv[2];
const projectRoot = process.argv[3];
const uaDir = path.join(projectRoot, '.ua');
const assembledPath = path.join(uaDir, 'intermediate', 'assembled-graph.json');
const scanPath = path.join(uaDir, 'intermediate', 'scan-result.json');
const graphPath = path.join(uaDir, 'knowledge-graph.json');

if (mode === 'prepare') {
  const graph = JSON.parse(fs.readFileSync(assembledPath, 'utf8'));
  const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'));
  fs.writeFileSync(graphPath, `${JSON.stringify(graph, null, 2)}\n`);
  const input = {
    projectRoot,
    sourceFilePaths: scan.files.map((file) => file.path),
    gitCommitHash: graph.project.gitCommitHash,
  };
  fs.writeFileSync(
    path.join(uaDir, 'intermediate', 'fingerprint-input.json'),
    `${JSON.stringify(input, null, 2)}\n`,
  );
  process.stdout.write(`Prepared graph and ${input.sourceFilePaths.length} fingerprint paths.\n`);
} else if (mode === 'finalize') {
  const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'));
  const meta = {
    lastAnalyzedAt: graph.project.analyzedAt,
    gitCommitHash: graph.project.gitCommitHash,
    version: '1.0.0',
    analyzedFiles: scan.totalFiles,
  };
  fs.writeFileSync(path.join(uaDir, 'meta.json'), `${JSON.stringify(meta, null, 2)}\n`);
  process.stdout.write('Metadata written.\n');
} else {
  process.stderr.write('Expected mode: prepare or finalize\n');
  process.exit(1);
}
