#!/usr/bin/env node
const fs = require('fs');

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  console.error('Usage: node ua-tour-analyze.js <input> <output>');
  process.exit(1);
}

try {
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const nodes = Array.isArray(input.nodes) ? input.nodes : [];
  const edges = Array.isArray(input.edges) ? input.edges : [];
  const layers = Array.isArray(input.layers) ? input.layers : [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const fanIn = new Map(nodes.map((node) => [node.id, 0]));
  const fanOut = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of edges) {
    if (byId.has(edge.source) && byId.has(edge.target)) {
      fanOut.set(edge.source, fanOut.get(edge.source) + 1);
      fanIn.set(edge.target, fanIn.get(edge.target) + 1);
    }
  }
  const rank = (counts, label) => nodes
    .map((node) => ({ id: node.id, [label]: counts.get(node.id), name: node.name }))
    .sort((a, b) => b[label] - a[label] || a.id.localeCompare(b.id))
    .slice(0, 20);
  const fanInRanking = rank(fanIn, 'fanIn');
  const fanOutRanking = rank(fanOut, 'fanOut');

  const codeFiles = nodes.filter((node) => node.type === 'file');
  const sortedFanOut = [...codeFiles].sort((a, b) => fanOut.get(b.id) - fanOut.get(a.id));
  const topOutIds = new Set(sortedFanOut.slice(0, Math.max(1, Math.ceil(codeFiles.length * 0.1))).map((n) => n.id));
  const sortedFanIn = [...codeFiles].sort((a, b) => fanIn.get(a.id) - fanIn.get(b.id));
  const lowInIds = new Set(sortedFanIn.slice(0, Math.max(1, Math.ceil(codeFiles.length * 0.25))).map((n) => n.id));
  const entryNames = new Set([
    'index.ts','index.js','main.ts','main.js','app.ts','app.js','server.ts','server.js','mod.rs',
    'main.go','main.py','main.rs','manage.py','app.py','wsgi.py','asgi.py','run.py','__main__.py',
    'Application.java','Main.java','Program.cs','config.ru','index.php','App.swift','Application.kt','main.cpp','main.c',
  ]);
  const entryPointCandidates = nodes.map((node) => {
    let score = 0;
    const path = node.filePath || '';
    const name = node.name || path.split('/').pop();
    if (node.type === 'file') {
      if (entryNames.has(name)) score += 3;
      if (path.split('/').length <= 2) score += 1;
      if (topOutIds.has(node.id)) score += 1;
      if (lowInIds.has(node.id)) score += 1;
    } else if (node.type === 'document') {
      if (path === 'README.md') score += 5;
      else if (/^[^/]+\.md$/i.test(path)) score += 2;
    }
    return { id: node.id, score, name, summary: node.summary };
  }).filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id))
    .slice(0, 5);

  const codeStart = entryPointCandidates.find((candidate) => byId.get(candidate.id)?.type === 'file')
    || [...codeFiles].sort((a, b) => fanOut.get(b.id) - fanOut.get(a.id))[0];
  const adjacency = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if ((edge.type === 'imports' || edge.type === 'calls') && byId.has(edge.source) && byId.has(edge.target)) {
      adjacency.get(edge.source).push(edge.target);
    }
  }
  const order = [], depthMap = {}, byDepth = {};
  if (codeStart) {
    const queue = [[codeStart.id, 0]], visited = new Set([codeStart.id]);
    while (queue.length) {
      const [id, depth] = queue.shift();
      order.push(id);
      depthMap[id] = depth;
      (byDepth[depth] ||= []).push(id);
      for (const next of adjacency.get(id) || []) {
        if (!visited.has(next)) {
          visited.add(next);
          queue.push([next, depth + 1]);
        }
      }
    }
  }

  const inventory = (types) => nodes.filter((node) => types.has(node.type))
    .map(({ id, name, type, summary }) => ({ id, name, type, summary }));
  const nonCodeFiles = {
    documentation: inventory(new Set(['document'])),
    infrastructure: inventory(new Set(['service', 'pipeline', 'resource'])),
    data: inventory(new Set(['table', 'schema', 'endpoint'])),
    config: inventory(new Set(['config'])),
  };

  const directional = new Set(edges
    .filter((e) => (e.type === 'imports' || e.type === 'calls') && byId.has(e.source) && byId.has(e.target))
    .map((e) => `${e.source}\u0000${e.target}\u0000${e.type}`));
  const graph = new Map(nodes.map((node) => [node.id, new Set()]));
  for (const edge of edges) {
    if ((edge.type === 'imports' || edge.type === 'calls')
      && directional.has(`${edge.target}\u0000${edge.source}\u0000${edge.type}`)) {
      graph.get(edge.source)?.add(edge.target);
      graph.get(edge.target)?.add(edge.source);
    }
  }
  const seedPairs = [];
  for (const [id, neighbors] of graph) {
    for (const other of neighbors) if (id < other) seedPairs.push([id, other]);
  }
  const clusters = [];
  for (const pair of seedPairs) {
    const cluster = new Set(pair);
    let changed = true;
    while (changed && cluster.size < 5) {
      changed = false;
      for (const node of nodes) {
        if (cluster.has(node.id)) continue;
        const connections = [...cluster].filter((member) =>
          edges.some((e) => (e.source === node.id && e.target === member) || (e.source === member && e.target === node.id))).length;
        if (connections >= 2) {
          cluster.add(node.id);
          changed = true;
          if (cluster.size >= 5) break;
        }
      }
    }
    const ids = [...cluster].sort();
    if (!clusters.some((c) => c.nodes.join('\u0000') === ids.join('\u0000'))) {
      const edgeCount = edges.filter((e) => cluster.has(e.source) && cluster.has(e.target)).length;
      clusters.push({ nodes: ids, edgeCount });
    }
  }
  clusters.sort((a, b) => b.edgeCount - a.edgeCount || b.nodes.length - a.nodes.length);

  const nodeSummaryIndex = Object.fromEntries(nodes.map(({ id, name, type, summary }) =>
    [id, { name, type, summary }]));
  const results = {
    scriptCompleted: true,
    entryPointCandidates,
    fanInRanking,
    fanOutRanking,
    bfsTraversal: { startNode: codeStart?.id || null, order, depthMap, byDepth },
    nonCodeFiles,
    clusters: clusters.slice(0, 10),
    layers: { count: layers.length, list: layers },
    nodeSummaryIndex,
    totalNodes: nodes.length,
    totalEdges: edges.length,
  };
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2) + '\n');
  process.exit(0);
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
