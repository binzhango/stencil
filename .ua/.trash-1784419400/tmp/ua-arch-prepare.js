const fs = require('fs');

const graph = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const fileTypes = new Set(['file', 'config', 'document', 'service', 'pipeline', 'table', 'schema', 'resource', 'endpoint']);
const fileNodes = graph.nodes
  .filter((node) => fileTypes.has(node.type))
  .map(({ id, type, name, filePath, summary, tags }) => ({ id, type, name, filePath, summary, tags }));
const fileIds = new Set(fileNodes.map((node) => node.id));
const allEdges = graph.edges.filter((edge) => fileIds.has(edge.source) && fileIds.has(edge.target));
const input = { fileNodes, importEdges: allEdges.filter((edge) => edge.type === 'imports'), allEdges };
fs.writeFileSync(process.argv[3], JSON.stringify(input, null, 2));
