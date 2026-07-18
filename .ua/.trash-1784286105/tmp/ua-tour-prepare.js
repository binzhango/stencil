#!/usr/bin/env node
const fs = require('fs');

const [graphPath, layersPath, outputPath] = process.argv.slice(2);
if (!graphPath || !layersPath || !outputPath) {
  console.error('Usage: node ua-tour-prepare.js <graph> <layers> <output>');
  process.exit(1);
}

try {
  const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  const layerData = JSON.parse(fs.readFileSync(layersPath, 'utf8'));
  const layers = Array.isArray(layerData) ? layerData : layerData.layers || [];
  const fileLevelTypes = new Set([
    'file', 'config', 'document', 'service', 'pipeline',
    'table', 'schema', 'resource', 'endpoint',
  ]);
  const input = {
    nodes: (graph.nodes || [])
      .filter((node) => fileLevelTypes.has(node.type))
      .map(({ id, name, filePath, summary, type }) => ({
        id, name, filePath, summary, type,
      })),
    edges: graph.edges || [],
    layers: layers.map(({ id, name, description }) => ({ id, name, description })),
  };
  fs.writeFileSync(outputPath, JSON.stringify(input, null, 2) + '\n');
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
