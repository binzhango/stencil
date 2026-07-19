const fs = require('fs');
const path = require('path');

try {
  const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const nodes = input.fileNodes || [];
  const imports = input.importEdges || [];
  const allEdges = input.allEdges || [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const paths = nodes.map((node) => node.filePath || node.id.split(':').slice(1).join(':'));
  const split = paths.map((p) => p.split('/'));
  let common = [];
  if (split.length) {
    for (let i = 0; i < Math.min(...split.map((p) => p.length - 1)); i++) {
      if (split.every((p) => p[i] === split[0][i])) common.push(split[0][i]);
      else break;
    }
  }
  const groupOfPath = (p) => {
    const parts = p.split('/').slice(common.length);
    if (parts.length > 1) return parts[0];
    if (p.includes('/')) return p.split('/')[0];
    if (/^(test_.*|.*\.(test|spec)\.)/.test(p)) return 'test';
    if (/\.(json|ya?ml|toml)$/.test(p)) return 'config';
    return 'root';
  };
  const groupOf = (id) => groupOfPath((byId.get(id) || {}).filePath || id);
  const directoryGroups = {}, nodeTypeGroups = {};
  for (const node of nodes) {
    const group = groupOf(node.id);
    (directoryGroups[group] ||= []).push(node.id);
    (nodeTypeGroups[node.type] ||= []).push(node.id);
  }
  const fanIn = Object.fromEntries(nodes.map((node) => [node.id, 0]));
  const fanOut = Object.fromEntries(nodes.map((node) => [node.id, 0]));
  const pairCounts = new Map();
  const involved = Object.fromEntries(Object.keys(directoryGroups).map((g) => [g, 0]));
  const internal = Object.fromEntries(Object.keys(directoryGroups).map((g) => [g, 0]));
  for (const edge of imports) {
    fanOut[edge.source] = (fanOut[edge.source] || 0) + 1;
    fanIn[edge.target] = (fanIn[edge.target] || 0) + 1;
    const from = groupOf(edge.source), to = groupOf(edge.target);
    involved[from]++; involved[to]++;
    if (from === to) internal[from]++;
    else pairCounts.set(`${from}\0${to}`, (pairCounts.get(`${from}\0${to}`) || 0) + 1);
  }
  const interGroupImports = [...pairCounts].map(([key, count]) => {
    const [from, to] = key.split('\0'); return { from, to, count };
  });
  const dependencyDirection = [];
  const seenPairs = new Set();
  for (const edge of interGroupImports) {
    const pair = [edge.from, edge.to].sort().join('\0');
    if (seenPairs.has(pair)) continue;
    seenPairs.add(pair);
    const forward = pairCounts.get(`${edge.from}\0${edge.to}`) || 0;
    const reverse = pairCounts.get(`${edge.to}\0${edge.from}`) || 0;
    if (forward !== reverse) dependencyDirection.push(forward > reverse
      ? { dependent: edge.from, dependsOn: edge.to }
      : { dependent: edge.to, dependsOn: edge.from });
  }
  const patternMap = {
    routes: 'api', api: 'api', controllers: 'api', endpoints: 'api', handlers: 'api',
    services: 'service', core: 'service', lib: 'service', domain: 'service', logic: 'service',
    models: 'data', db: 'data', data: 'data', persistence: 'data', repository: 'data', entities: 'data',
    utils: 'utility', helpers: 'utility', common: 'utility', shared: 'utility', tools: 'utility',
    config: 'config', constants: 'config', env: 'config', settings: 'config',
    tests: 'test', test: 'test', specs: 'test', types: 'types', schemas: 'types', contracts: 'types',
    docs: 'documentation', documentation: 'documentation', guides: 'documentation',
    '.github': 'ci-cd', deploy: 'infrastructure', deployment: 'infrastructure', infra: 'infrastructure',
    examples: 'examples'
  };
  const patternMatches = {};
  for (const group of Object.keys(directoryGroups)) patternMatches[group] = patternMap[group.toLowerCase()] || null;
  const cross = new Map();
  const nonCodeConnections = [];
  for (const edge of allEdges) {
    const from = byId.get(edge.source), to = byId.get(edge.target);
    if (!from || !to) continue;
    const key = `${from.type}\0${to.type}\0${edge.type}`;
    cross.set(key, (cross.get(key) || 0) + 1);
    if (from.type !== 'file' || to.type !== 'file') nonCodeConnections.push(edge);
  }
  const crossCategoryEdges = [...cross].map(([key, count]) => {
    const [fromType, toType, edgeType] = key.split('\0'); return { fromType, toType, edgeType, count };
  });
  const infraFiles = paths.filter((p) => /(^|\/)(Dockerfile|docker-compose|k8s|kubernetes|terraform)|\.tf(vars)?$|^\.github\/workflows\//i.test(p));
  const schemaFiles = paths.filter((p) => /\.(sql|graphql|gql|proto|prisma)$/i.test(p));
  const migrationFiles = paths.filter((p) => /(^|\/)migrations?\//i.test(p));
  const dataModelFiles = paths.filter((p) => /(^|\/)(models?|database|db)\.py$/i.test(p));
  const apiHandlerFiles = paths.filter((p) => /(^|\/)(routes?|routers?|api|handlers?|endpoints?)\//i.test(p) || /(^|\/)(api|app|main)\.py$/i.test(p));
  const docPaths = paths.filter((p) => /\.(md|rst)$/i.test(p));
  const documented = new Set(docPaths.map(groupOfPath));
  const groups = Object.keys(directoryGroups);
  const output = {
    scriptCompleted: true,
    commonPathPrefix: common.join('/'),
    directoryGroups,
    nodeTypeGroups,
    importAdjacency: Object.fromEntries(nodes.map((node) => [node.id, imports.filter((e) => e.source === node.id).map((e) => e.target)])),
    crossCategoryEdges,
    nonCodeConnections,
    interGroupImports,
    intraGroupDensity: Object.fromEntries(groups.map((g) => [g, { internalEdges: internal[g], totalEdges: involved[g], density: involved[g] ? internal[g] / involved[g] : 0 }])),
    patternMatches,
    deploymentTopology: {
      hasDockerfile: paths.some((p) => /(^|\/)Dockerfile/.test(p)),
      hasCompose: paths.some((p) => /docker-compose/i.test(p)),
      hasK8s: paths.some((p) => /(^|\/)(k8s|kubernetes)\//i.test(p)),
      hasTerraform: paths.some((p) => /\.tf(vars)?$/i.test(p)),
      hasCI: paths.some((p) => /^\.github\/workflows\//.test(p)),
      infraFiles
    },
    dataPipeline: { schemaFiles, migrationFiles, dataModelFiles, apiHandlerFiles },
    docCoverage: {
      groupsWithDocs: documented.size,
      totalGroups: groups.length,
      coverageRatio: groups.length ? documented.size / groups.length : 0,
      undocumentedGroups: groups.filter((g) => !documented.has(g))
    },
    dependencyDirection,
    fileStats: {
      totalFileNodes: nodes.length,
      filesPerGroup: Object.fromEntries(groups.map((g) => [g, directoryGroups[g].length])),
      nodeTypeCounts: Object.fromEntries(Object.entries(nodeTypeGroups).map(([type, ids]) => [type, ids.length]))
    },
    fileFanIn: fanIn,
    fileFanOut: fanOut
  };
  fs.writeFileSync(process.argv[3], JSON.stringify(output, null, 2));
} catch (error) {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exit(1);
}
