#!/usr/bin/env node
const fs = require('fs');

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  console.error('Usage: node ua-tour-analyze.js <input> <output>');
  process.exit(1);
}

try {
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const nodes = input.nodes || [];
  const edges = input.edges || [];
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const fanIn = new Map(nodes.map((node) => [node.id, 0]));
  const fanOut = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of edges) {
    if (fanIn.has(edge.target)) fanIn.set(edge.target, fanIn.get(edge.target) + 1);
    if (fanOut.has(edge.source)) fanOut.set(edge.source, fanOut.get(edge.source) + 1);
  }

  const ranking = (counts, key) => nodes
    .map((node) => ({ id: node.id, [key]: counts.get(node.id), name: node.name }))
    .sort((a, b) => b[key] - a[key] || a.id.localeCompare(b.id))
    .slice(0, 20);
  const fanInRanking = ranking(fanIn, 'fanIn');
  const fanOutRanking = ranking(fanOut, 'fanOut');

  const codeExtension = /(?:\.(?:py|js|jsx|ts|tsx|mjs|cjs|go|rs|java|kt|swift|c|cc|cpp|h|hpp|cs|rb|php|sh)|(?:^|\/)Dockerfile)$/i;
  const codeNodes = nodes.filter((node) => node.type === 'file' && codeExtension.test(node.filePath || ''));
  const codeNodeIds = new Set(codeNodes.map((node) => node.id));
  const sortedFanOut = codeNodes.map((node) => fanOut.get(node.id)).sort((a, b) => a - b);
  const sortedFanIn = codeNodes.map((node) => fanIn.get(node.id)).sort((a, b) => a - b);
  const percentile = (values, p) => values.length ? values[Math.min(values.length - 1, Math.floor(p * values.length))] : 0;
  const topOutThreshold = percentile(sortedFanOut, 0.9);
  const bottomInThreshold = percentile(sortedFanIn, 0.25);
  const entryNames = new Set([
    'index.ts', 'index.js', 'main.ts', 'main.js', 'app.ts', 'app.js', 'server.ts', 'server.js',
    'mod.rs', 'main.go', 'main.py', 'main.rs', 'manage.py', 'app.py', 'wsgi.py', 'asgi.py',
    'run.py', '__main__.py', 'Application.java', 'Main.java', 'Program.cs', 'config.ru',
    'index.php', 'App.swift', 'Application.kt', 'main.cpp', 'main.c',
  ]);
  const entryPointCandidates = nodes.map((node) => {
    let score = 0;
    const path = node.filePath || '';
    const depth = path.split('/').filter(Boolean).length;
    if (codeNodeIds.has(node.id)) {
      if (entryNames.has(node.name)) score += 3;
      if (depth <= 2) score += 1;
      if (fanOut.get(node.id) >= topOutThreshold) score += 1;
      if (fanIn.get(node.id) <= bottomInThreshold) score += 1;
    } else if (node.type === 'document') {
      if (path === 'README.md') score += 5;
      else if (depth === 1 && path.endsWith('.md')) score += 2;
    }
    return { id: node.id, score, name: node.name, summary: node.summary };
  }).filter((candidate) => candidate.score > 0)
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id))
    .slice(0, 5);

  const codeStart = entryPointCandidates.find((candidate) => codeNodeIds.has(candidate.id))
    || fanOutRanking.find((candidate) => codeNodeIds.has(candidate.id));
  const adjacency = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if ((edge.type === 'imports' || edge.type === 'calls') && adjacency.has(edge.source)) {
      adjacency.get(edge.source).push(edge.target);
    }
  }
  const order = [];
  const depthMap = {};
  const byDepth = {};
  if (codeStart) {
    const queue = [codeStart.id];
    depthMap[codeStart.id] = 0;
    while (queue.length) {
      const current = queue.shift();
      order.push(current);
      const depth = depthMap[current];
      (byDepth[depth] ||= []).push(current);
      for (const next of adjacency.get(current) || []) {
        if (!(next in depthMap)) {
          depthMap[next] = depth + 1;
          queue.push(next);
        }
      }
    }
  }

  const inventoryItem = (node) => ({ id: node.id, name: node.name, type: node.type, summary: node.summary });
  const nonCodeFiles = {
    documentation: nodes.filter((node) => node.type === 'document').map(inventoryItem),
    infrastructure: nodes.filter((node) => ['service', 'pipeline', 'resource'].includes(node.type)).map(inventoryItem),
    data: nodes.filter((node) => ['table', 'schema', 'endpoint'].includes(node.type)).map(inventoryItem),
    config: nodes.filter((node) => node.type === 'config').map(inventoryItem),
  };

  const relation = new Map();
  for (const edge of edges.filter((edge) => edge.type === 'imports' || edge.type === 'calls')) {
    relation.set(`${edge.source}\u0000${edge.target}`, true);
  }
  const pairClusters = [];
  const seenPairs = new Set();
  for (const edge of edges.filter((edge) => edge.type === 'imports' || edge.type === 'calls')) {
    if (!relation.has(`${edge.target}\u0000${edge.source}`)) continue;
    const key = [edge.source, edge.target].sort().join('\u0000');
    if (!seenPairs.has(key)) {
      seenPairs.add(key);
      pairClusters.push(new Set([edge.source, edge.target]));
    }
  }
  for (const cluster of pairClusters) {
    for (const node of nodes) {
      if (cluster.has(node.id) || cluster.size >= 5) continue;
      const links = [...cluster].filter((member) =>
        relation.has(`${node.id}\u0000${member}`) || relation.has(`${member}\u0000${node.id}`),
      ).length;
      if (links >= 2) cluster.add(node.id);
    }
  }
  const clusters = pairClusters.map((cluster) => {
    const members = [...cluster];
    const memberSet = new Set(members);
    const edgeCount = edges.filter((edge) => memberSet.has(edge.source) && memberSet.has(edge.target)).length;
    return { nodes: members, edgeCount };
  }).sort((a, b) => b.edgeCount - a.edgeCount).slice(0, 10);

  const nodeSummaryIndex = Object.fromEntries(nodes.map((node) => [node.id, {
    name: node.name, type: node.type, summary: node.summary,
  }]));
  const result = {
    scriptCompleted: true,
    entryPointCandidates,
    fanInRanking,
    fanOutRanking,
    bfsTraversal: { startNode: codeStart?.id || null, order, depthMap, byDepth },
    nonCodeFiles,
    clusters,
    layers: { count: input.layers.length, list: input.layers },
    nodeSummaryIndex,
    totalNodes: nodes.length,
    totalEdges: edges.length,
  };
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
} catch (error) {
  console.error(error.stack || error.message);
  process.exit(1);
}
