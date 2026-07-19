const fs = require('fs');

const [graphPath, layersPath, tourPath, outputPath, commitHash] = process.argv.slice(2);
const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
let layers = JSON.parse(fs.readFileSync(layersPath, 'utf8'));
let tour = JSON.parse(fs.readFileSync(tourPath, 'utf8'));
layers = Array.isArray(layers) ? layers : (layers.layers || []);
tour = Array.isArray(tour) ? tour : (tour.steps || []);

const nodeIds = new Set(graph.nodes.map((node) => node.id));
const fileTypes = new Set([
  'file', 'config', 'document', 'service', 'pipeline', 'table', 'schema', 'resource', 'endpoint',
]);
const fileNodeIds = graph.nodes.filter((node) => fileTypes.has(node.type)).map((node) => node.id);
const prefixes = /^(file|config|document|service|pipeline|table|schema|resource|endpoint):/;
const kebab = (value) => String(value || 'unnamed')
  .trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const normalizeRefs = (refs) => (Array.isArray(refs) ? refs : [])
  .map((entry) => (entry && typeof entry === 'object' ? entry.id : entry))
  .filter((entry) => typeof entry === 'string')
  .map((entry) => (prefixes.test(entry) ? entry : `file:${entry}`))
  .filter((entry) => nodeIds.has(entry));

const assigned = new Set();
layers = layers.map((layer) => {
  const refs = normalizeRefs(layer.nodeIds || layer.nodes).filter((id) => {
    if (assigned.has(id)) return false;
    assigned.add(id);
    return true;
  });
  return {
    id: layer.id || `layer:${kebab(layer.name)}`,
    name: layer.name || 'Unnamed Layer',
    description: layer.description || 'Project components grouped by architectural responsibility.',
    nodeIds: refs,
  };
}).filter((layer) => layer.nodeIds.length > 0);

const unassigned = fileNodeIds.filter((id) => !assigned.has(id));
if (unassigned.length) {
  const fallback = layers.find((layer) => layer.id === 'layer:project-support');
  if (fallback) fallback.nodeIds.push(...unassigned);
  else layers.push({
    id: 'layer:project-support',
    name: 'Project Support',
    description: 'Configuration, documentation, and support files used across the project.',
    nodeIds: unassigned,
  });
}

tour = tour.map((step, index) => {
  const refs = normalizeRefs(step.nodeIds || step.nodesToInspect);
  const normalized = {
    order: Number.isInteger(step.order) ? step.order : index + 1,
    title: step.title || `Tour Step ${index + 1}`,
    description: step.description || step.whyItMatters || 'Explore this part of the project.',
    nodeIds: refs,
  };
  if (typeof step.languageLesson === 'string') normalized.languageLesson = step.languageLesson;
  return normalized;
}).filter((step) => step.nodeIds.length > 0)
  .sort((a, b) => a.order - b.order)
  .map((step, index) => ({ ...step, order: index + 1 }));

const assembled = {
  version: '1.0.0',
  project: {
    name: 'office-stencil',
    languages: ['docx', 'json', 'markdown', 'pptx', 'python', 'toml', 'typed', 'unknown', 'yaml'],
    frameworks: ['Celery', 'FastAPI', 'GitHub Actions', 'Pytest', 'Uvicorn'],
    description: 'A reusable Office document template render engine for DOCX, XLSX, and PPTX.',
    analyzedAt: new Date().toISOString(),
    gitCommitHash: commitHash,
  },
  nodes: graph.nodes,
  edges: graph.edges,
  layers,
  tour,
};

fs.writeFileSync(outputPath, `${JSON.stringify(assembled, null, 2)}\n`);
process.stdout.write(JSON.stringify({
  nodes: assembled.nodes.length,
  edges: assembled.edges.length,
  layers: assembled.layers.length,
  tourSteps: assembled.tour.length,
  unassignedRecovered: unassigned.length,
}));
