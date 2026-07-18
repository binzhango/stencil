#!/usr/bin/env node
const fs = require('fs');

const [graphPath, outputPath] = process.argv.slice(2);
if (!graphPath || !outputPath) {
  process.stderr.write('Usage: node ua-arch-prepare.js <graph.json> <input.json>\n');
  process.exit(1);
}

const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
const fileLevelTypes = new Set([
  'file', 'config', 'document', 'service', 'pipeline', 'table', 'schema', 'resource', 'endpoint',
]);
const fileNodes = (graph.nodes || [])
  .filter((node) => fileLevelTypes.has(node.type))
  .map(({ id, type, name, filePath, summary, tags }) => ({ id, type, name, filePath, summary, tags }));
const ids = new Set(fileNodes.map((node) => node.id));
const allEdges = (graph.edges || []).filter((edge) => ids.has(edge.source) && ids.has(edge.target));
const importEdges = allEdges.filter((edge) => edge.type === 'imports');

fs.writeFileSync(outputPath, JSON.stringify({ fileNodes, importEdges, allEdges }, null, 2));
