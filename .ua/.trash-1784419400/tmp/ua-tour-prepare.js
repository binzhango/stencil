#!/usr/bin/env node
const fs = require('fs');

const [graphPath, layersPath, outputPath] = process.argv.slice(2);
if (!graphPath || !layersPath || !outputPath) {
  console.error('Usage: node ua-tour-prepare.js <graph> <layers> <output>');
  process.exit(1);
}

try {
  const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  const rawLayers = JSON.parse(fs.readFileSync(layersPath, 'utf8'));
  const fileLevelTypes = new Set([
    'file', 'config', 'document', 'service', 'pipeline',
    'table', 'schema', 'resource', 'endpoint',
  ]);
  const nodes = (graph.nodes || [])
    .filter((node) => fileLevelTypes.has(node.type))
    .map(({ id, name, filePath, summary, type }) => ({ id, name, filePath, summary, type }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = (graph.edges || []).filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
  );
  const layers = (Array.isArray(rawLayers) ? rawLayers : rawLayers.layers || [])
    .map(({ id, name, description }) => ({ id, name, description }));
  fs.writeFileSync(outputPath, JSON.stringify({ nodes, edges, layers }, null, 2) + '\n');
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
