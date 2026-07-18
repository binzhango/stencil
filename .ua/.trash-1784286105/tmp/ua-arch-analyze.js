#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  process.stderr.write('Usage: node ua-arch-analyze.js <input.json> <output.json>\n');
  process.exit(1);
}

try {
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const fileNodes = Array.isArray(input.fileNodes) ? input.fileNodes : [];
  const importEdges = Array.isArray(input.importEdges) ? input.importEdges : [];
  const allEdges = Array.isArray(input.allEdges) ? input.allEdges : [];
  const nodeById = new Map(fileNodes.map((node) => [node.id, node]));
  const paths = fileNodes.map((node) => String(node.filePath || '').replace(/^\.\//, ''));

  const directorySegments = paths.map((filePath) => filePath.split('/').slice(0, -1));
  const common = [];
  if (directorySegments.length) {
    for (let i = 0; ; i += 1) {
      const value = directorySegments[0][i];
      if (value === undefined || !directorySegments.every((parts) => parts[i] === value)) break;
      common.push(value);
    }
  }

  const isFlat = paths.every((filePath) => !filePath.includes('/'));
  function flatGroup(filePath) {
    const base = path.posix.basename(filePath).toLowerCase();
    if (/^(test_.*|.*\.(test|spec)\.)/.test(base)) return 'test';
    if (/(^|\.)config\./.test(base) || /^(pyproject\.toml|package\.json|tsconfig\.json)$/.test(base)) return 'config';
    const ext = path.posix.extname(base).slice(1);
    return ext || 'root';
  }
  function groupFor(filePath) {
    if (isFlat) return flatGroup(filePath);
    const parts = filePath.split('/');
    if (common.length && parts.length > common.length + 1) return parts[common.length];
    if (!common.length) return parts.length > 1 ? parts[0] : 'root';
    return 'root';
  }

  const directoryGroups = {};
  const nodeTypeGroups = {};
  const groupById = new Map();
  for (const node of fileNodes) {
    const group = groupFor(node.filePath || node.name || 'root');
    groupById.set(node.id, group);
    (directoryGroups[group] ||= []).push(node.id);
    (nodeTypeGroups[node.type] ||= []).push(node.id);
  }

  const fileFanIn = Object.fromEntries(fileNodes.map((node) => [node.id, 0]));
  const fileFanOut = Object.fromEntries(fileNodes.map((node) => [node.id, 0]));
  const adjacency = Object.fromEntries(fileNodes.map((node) => [node.id, []]));
  const importCounts = new Map();
  const groupConnections = Object.fromEntries(Object.keys(directoryGroups).map((group) => [group, { importsFrom: [], importedBy: [] }]));
  const importsFromSets = Object.fromEntries(Object.keys(directoryGroups).map((group) => [group, new Set()]));
  const importedBySets = Object.fromEntries(Object.keys(directoryGroups).map((group) => [group, new Set()]));

  for (const edge of importEdges) {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) continue;
    adjacency[edge.source].push(edge.target);
    fileFanOut[edge.source] += 1;
    fileFanIn[edge.target] += 1;
    const from = groupById.get(edge.source);
    const to = groupById.get(edge.target);
    const key = `${from}\u0000${to}`;
    importCounts.set(key, (importCounts.get(key) || 0) + 1);
    if (from !== to) {
      importsFromSets[from].add(to);
      importedBySets[to].add(from);
    }
  }
  for (const group of Object.keys(groupConnections)) {
    groupConnections[group].importsFrom = [...importsFromSets[group]].sort();
    groupConnections[group].importedBy = [...importedBySets[group]].sort();
  }

  const interGroupImports = [...importCounts.entries()]
    .filter(([key]) => { const [from, to] = key.split('\u0000'); return from !== to; })
    .map(([key, count]) => { const [from, to] = key.split('\u0000'); return { from, to, count }; })
    .sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to));

  const intraGroupDensity = {};
  for (const group of Object.keys(directoryGroups)) {
    let internalEdges = 0;
    let totalEdges = 0;
    for (const edge of importEdges) {
      const from = groupById.get(edge.source);
      const to = groupById.get(edge.target);
      if (from === group || to === group) totalEdges += 1;
      if (from === group && to === group) internalEdges += 1;
    }
    intraGroupDensity[group] = { internalEdges, totalEdges, density: totalEdges ? internalEdges / totalEdges : 0 };
  }

  const crossCounts = new Map();
  const nonCodeConnections = [];
  for (const edge of allEdges) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) continue;
    const key = `${source.type}\u0000${target.type}\u0000${edge.type}`;
    crossCounts.set(key, (crossCounts.get(key) || 0) + 1);
    if (source.type !== 'file' || target.type !== 'file') {
      nonCodeConnections.push({ source: edge.source, target: edge.target, type: edge.type });
    }
  }
  const crossCategoryEdges = [...crossCounts.entries()].map(([key, count]) => {
    const [fromType, toType, edgeType] = key.split('\u0000');
    return { fromType, toType, edgeType, count };
  }).sort((a, b) => a.fromType.localeCompare(b.fromType) || a.toType.localeCompare(b.toType) || a.edgeType.localeCompare(b.edgeType));

  const patterns = [
    [/^(routes|api|controllers|endpoints|handlers|serializers|routers|blueprints)$/i, 'api'],
    [/^(services|core|lib|domain|logic|internal|composables|mailers|jobs|channels|signals)$/i, 'service'],
    [/^(models|db|data|persistence|repository|entities|entity|migrations|sql|database|schema)$/i, 'data'],
    [/^(components|views|pages|ui|layouts|screens)$/i, 'ui'],
    [/^(middleware|plugins|interceptors|guards)$/i, 'middleware'],
    [/^(utils|helpers|common|shared|tools|pkg|templatetags)$/i, 'utility'],
    [/^(config|constants|env|settings|management|commands)$/i, 'config'],
    [/^(__tests__|test|tests|spec|specs|src\/test\/java)$/i, 'test'],
    [/^(types|interfaces|schemas|contracts|dtos|dto|request|response)$/i, 'types'],
    [/^hooks$/i, 'hooks'], [/^(store|state|reducers|actions|slices)$/i, 'state'],
    [/^(assets|static|public)$/i, 'assets'], [/^(cmd|bin)$/i, 'entry'],
    [/^(docs|documentation|wiki|guides)$/i, 'documentation'],
    [/^(deploy|deployment|infra|infrastructure|k8s|kubernetes|helm|charts|terraform|tf|docker)$/i, 'infrastructure'],
    [/^(\.github|\.gitlab|\.circleci)$/i, 'ci-cd'],
  ];
  const patternMatches = {};
  for (const group of Object.keys(directoryGroups)) {
    const matched = patterns.find(([regex]) => regex.test(group));
    if (matched) patternMatches[group] = matched[1];
  }

  function fileRole(filePath) {
    const lower = filePath.toLowerCase();
    const base = path.posix.basename(lower);
    if (/\/(test_|[^/]+\.(test|spec)\.)/.test(`/${lower}`) || /^test_.*\.py$/.test(base) || /_test\.go$/.test(base)) return 'test';
    if (base.endsWith('.d.ts') || /\.(graphql|gql|proto)$/.test(base)) return 'types';
    if (base === '__init__.py' || /(^|\/)index\.(ts|js)$/.test(lower) || base === 'manage.py' || /(^|\/)cmd\/[^/]+\/main\.go$/.test(lower) || /(^|\/)src\/(main|lib)\.rs$/.test(lower) || /application\.java$/.test(base) || base === 'program.cs' || base === 'config.ru') return 'entry';
    if (base === 'wsgi.py' || base === 'asgi.py' || ['cargo.toml','go.mod','gemfile','pom.xml','build.gradle','composer.json','pyproject.toml'].includes(base)) return 'config';
    if (base === 'dockerfile' || /^docker-compose\./.test(base) || /\.(tf|tfvars)$/.test(base) || base === 'makefile') return 'infrastructure';
    if (/^\.github\/workflows\/.+\.ya?ml$/.test(lower) || base === '.gitlab-ci.yml' || base === 'jenkinsfile') return 'ci-cd';
    if (base.endsWith('.sql')) return 'data';
    if (/\.(md|rst)$/.test(base)) return 'documentation';
    return null;
  }
  const filePatternMatches = Object.fromEntries(fileNodes.map((node) => [node.id, fileRole(node.filePath || '')]).filter(([, role]) => role));

  const lowerPaths = paths.map((p) => p.toLowerCase());
  const infraFiles = fileNodes.filter((node) => ['infrastructure', 'ci-cd'].includes(fileRole(node.filePath || '')) || ['service','resource','pipeline'].includes(node.type)).map((node) => node.filePath);
  const deploymentTopology = {
    hasDockerfile: lowerPaths.some((p) => path.posix.basename(p) === 'dockerfile'),
    hasCompose: lowerPaths.some((p) => /^docker-compose\./.test(path.posix.basename(p))),
    hasK8s: lowerPaths.some((p) => /(^|\/)(k8s|kubernetes|helm|charts)(\/|$)/.test(p)),
    hasTerraform: lowerPaths.some((p) => /\.(tf|tfvars)$/.test(p) || /(^|\/)terraform(\/|$)/.test(p)),
    hasCI: lowerPaths.some((p) => /^\.github\/workflows\//.test(p) || p === '.gitlab-ci.yml' || path.posix.basename(p) === 'jenkinsfile'),
    infraFiles,
  };

  const dataPipeline = {
    schemaFiles: fileNodes.filter((n) => n.type === 'schema' || /\.(sql|graphql|gql|proto|prisma)$/.test((n.filePath || '').toLowerCase())).map((n) => n.filePath),
    migrationFiles: fileNodes.filter((n) => /(^|\/)migrations?(\/|$)/i.test(n.filePath || '')).map((n) => n.filePath),
    dataModelFiles: fileNodes.filter((n) => /(^|\/)(models?|entities|schemas?)(\/|\.|$)/i.test(n.filePath || '') || (n.tags || []).some((tag) => /data-model|type-definition/.test(tag))).map((n) => n.filePath),
    apiHandlerFiles: fileNodes.filter((n) => n.type === 'endpoint' || /(^|\/)(api|routes?|routers?|controllers?|handlers?)(\/|\.|$)/i.test(n.filePath || '') || (n.tags || []).includes('api-handler')).map((n) => n.filePath),
  };

  const docNodes = fileNodes.filter((n) => n.type === 'document' || /\.(md|rst)$/i.test(n.filePath || ''));
  const groupsWithDocs = new Set();
  for (const doc of docNodes) {
    const ownGroup = groupById.get(doc.id);
    if (ownGroup) groupsWithDocs.add(ownGroup);
    const text = `${doc.summary || ''} ${(doc.tags || []).join(' ')}`.toLowerCase();
    for (const group of Object.keys(directoryGroups)) if (text.includes(group.toLowerCase())) groupsWithDocs.add(group);
  }
  for (const edge of allEdges.filter((e) => e.type === 'documents')) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (source?.type === 'document' && target) groupsWithDocs.add(groupById.get(target.id));
    if (target?.type === 'document' && source) groupsWithDocs.add(groupById.get(source.id));
  }
  const allGroups = Object.keys(directoryGroups);
  const docCoverage = {
    groupsWithDocs: groupsWithDocs.size,
    totalGroups: allGroups.length,
    coverageRatio: allGroups.length ? groupsWithDocs.size / allGroups.length : 0,
    undocumentedGroups: allGroups.filter((group) => !groupsWithDocs.has(group)),
  };

  const dependencyDirection = [];
  const pairs = new Set(interGroupImports.map(({ from, to }) => [from, to].sort().join('\u0000')));
  for (const pair of pairs) {
    const [a, b] = pair.split('\u0000');
    const ab = importCounts.get(`${a}\u0000${b}`) || 0;
    const ba = importCounts.get(`${b}\u0000${a}`) || 0;
    if (ab > ba) dependencyDirection.push({ dependent: a, dependsOn: b });
    else if (ba > ab) dependencyDirection.push({ dependent: b, dependsOn: a });
  }

  const output = {
    scriptCompleted: true,
    commonPathPrefix: common.length ? `${common.join('/')}/` : '',
    directoryGroups,
    nodeTypeGroups,
    importAdjacency: adjacency,
    groupConnections,
    crossCategoryEdges,
    nonCodeConnections,
    interGroupImports,
    intraGroupDensity,
    patternMatches,
    filePatternMatches,
    deploymentTopology,
    dataPipeline,
    docCoverage,
    dependencyDirection,
    fileStats: {
      totalFileNodes: fileNodes.length,
      filesPerGroup: Object.fromEntries(Object.entries(directoryGroups).map(([group, ids]) => [group, ids.length])),
      nodeTypeCounts: Object.fromEntries(Object.entries(nodeTypeGroups).map(([type, ids]) => [type, ids.length])),
    },
    fileFanIn,
    fileFanOut,
  };
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
} catch (error) {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
}
