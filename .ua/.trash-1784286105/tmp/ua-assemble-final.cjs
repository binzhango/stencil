#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[2];
const gitCommitHash = process.argv[3];
const uaDir = path.join(projectRoot, '.ua');
const graphPath = path.join(uaDir, 'intermediate', 'assembled-graph.json');
const layersPath = path.join(uaDir, 'intermediate', 'layers.json');
const tourPath = path.join(uaDir, 'intermediate', 'tour.json');

const base = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
let layers = JSON.parse(fs.readFileSync(layersPath, 'utf8'));
let tour = JSON.parse(fs.readFileSync(tourPath, 'utf8'));
if (!Array.isArray(layers)) layers = layers.layers || [];
if (!Array.isArray(tour)) tour = tour.steps || [];

const nodeIds = new Set(base.nodes.map((node) => node.id));
const knownPrefixes = /^(file|config|document|service|pipeline|table|schema|resource|endpoint):/;
const kebab = (value) => String(value || 'unnamed')
  .trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const normalizeRef = (value) => {
  const raw = typeof value === 'string' ? value : value?.id;
  if (!raw) return null;
  return knownPrefixes.test(raw) ? raw : `file:${raw}`;
};

layers = layers.map((layer) => {
  const refs = layer.nodeIds || layer.nodes || [];
  return {
    id: layer.id || `layer:${kebab(layer.name)}`,
    name: layer.name || 'Unnamed Layer',
    description: layer.description || 'No description available',
    nodeIds: refs.map(normalizeRef).filter((id) => id && nodeIds.has(id)),
  };
});

tour = tour.map((step, index) => {
  const refs = step.nodeIds || step.nodesToInspect || [];
  const normalized = {
    order: Number.isInteger(step.order) ? step.order : index + 1,
    title: step.title || `Step ${index + 1}`,
    description: step.description || step.whyItMatters || 'No description available',
    nodeIds: refs.map(normalizeRef).filter((id) => id && nodeIds.has(id)),
  };
  if (typeof step.languageLesson === 'string') normalized.languageLesson = step.languageLesson;
  return normalized;
}).sort((a, b) => a.order - b.order);

const graph = {
  version: '1.0.0',
  project: {
    name: 'office-stencil',
    languages: ['docx', 'json', 'markdown', 'pptx', 'python', 'toml', 'typed', 'unknown', 'yaml'],
    frameworks: ['Celery', 'FastAPI', 'GitHub Actions', 'Pytest', 'Uvicorn'],
    description: 'A reusable Office document template render engine for DOCX, XLSX, and PPTX.',
    analyzedAt: new Date().toISOString(),
    gitCommitHash,
  },
  nodes: base.nodes,
  edges: base.edges,
  layers,
  tour,
};

fs.writeFileSync(graphPath, `${JSON.stringify(graph, null, 2)}\n`);
