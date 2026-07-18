import fs from "node:fs";

const extraction = JSON.parse(fs.readFileSync(new URL("./ua-file-extract-results-1.json", import.meta.url), "utf8"));
const analyzerInput = JSON.parse(fs.readFileSync(new URL("./ua-file-analyzer-input-1.json", import.meta.url), "utf8"));

const fileMeta = {
  "src/stencil/api.py": ["Optional FastAPI service exposing health, metrics, and Office-template rendering endpoints for trusted internal callers, with bounded template-path resolution and in-process render telemetry.", ["api-handler", "service", "metrics", "validation"], "moderate"],
  "src/stencil/cli.py": ["Typer command-line interface that loads JSON render data, dispatches Office template rendering, and writes the resulting document with user-friendly errors.", ["entry-point", "cli", "api-handler", "validation"], "simple"],
  "src/stencil/docx.py": ["DOCX renderer that validates a template path, delegates Jinja-compatible WordprocessingML rendering to docxtpl, and returns the serialized document bytes.", ["service", "docx", "templating", "serialization"], "simple"],
  "src/stencil/errors.py": ["Defines the Stencil exception hierarchy, including unsupported-format errors and stage-aware render failures that retain template context.", ["type-definition", "error-handling", "validation", "diagnostics"], "simple"],
  "src/stencil/pptx.py": ["PPTX rendering engine that edits Open Packaging Convention parts directly, expands slide-level Jinja loops, renders text across XML runs, and rebuilds presentation relationships and content types.", ["service", "pptx", "templating", "xml-processing", "serialization"], "complex"],
  "src/stencil/render.py": ["Public format dispatcher that validates template/output combinations, routes DOCX, XLSX, and PPTX work to their renderers, and optionally converts results to PDF.", ["entry-point", "factory", "validation", "format-dispatch"], "moderate"],
  "src/stencil/xlsx.py": ["XLSX rendering engine that evaluates Jinja expressions in cells, expands row-loop blocks while preserving formatting, and translates copied formulas before serialization.", ["service", "xlsx", "templating", "formula-translation", "serialization"], "complex"],
};

const summaries = {
  "class:src/stencil/api.py:RenderMetrics": "Thread-safe in-memory counters that record render successes, failures, durations, formats, and failure stages for one API process.",
  "function:src/stencil/api.py:create_app": "Builds the optional FastAPI application, lazily imports API dependencies, and registers health, metrics, and render routes around a configurable renderer.",
  "function:src/stencil/api.py:_template_path_from_payload": "Validates the request template path and, when a template root is configured, prevents resolved paths from escaping that root.",
  "function:src/stencil/api.py:_output_format_from_payload": "Normalizes an explicit output format or derives it from the template suffix, rejecting malformed request values.",
  "function:src/stencil/api.py:_media_type_for": "Maps supported output formats to Office or PDF media types with a binary fallback.",
  "function:src/stencil/api.py:_http_exception": "Lazily constructs a FastAPI HTTPException while preserving the package's optional API dependency boundary.",
  "function:src/stencil/cli.py:main": "Defines the Typer application callback and CLI command-group entry point.",
  "function:src/stencil/cli.py:render_command": "Loads and validates a JSON object, invokes the public renderer, and writes the rendered bytes to a requested output path.",
  "function:src/stencil/docx.py:render_docx": "Validates and loads a DOCX template, renders it with docxtpl using mapping data, and serializes the result to bytes with stage-specific errors.",
  "class:src/stencil/errors.py:StencilError": "Base exception used to distinguish Stencil failures from unrelated runtime errors.",
  "class:src/stencil/errors.py:UnsupportedFormatError": "Signals unsupported template suffixes or requested output-format combinations.",
  "class:src/stencil/errors.py:RenderError": "Carries render-stage and template-path context and incorporates those diagnostics into the exception message.",
  "function:src/stencil/pptx.py:render_pptx": "Loads a PPTX ZIP package, plans and renders slide content, rewrites presentation metadata, and returns a compressed rendered package.",
  "function:src/stencil/pptx.py:_read_slide_refs": "Resolves the ordered presentation slide IDs and relationship targets into package-part references.",
  "function:src/stencil/pptx.py:_build_render_plan": "Builds the final ordered slide plan, cloning loop-body slides once per evaluated item while retaining ordinary slides.",
  "function:src/stencil/pptx.py:_find_slide_loop_blocks": "Scans slide paragraph text for balanced Jinja for/endfor markers and returns validated slide-loop boundaries.",
  "function:src/stencil/pptx.py:_slide_paragraph_texts": "Collects paragraph text from DrawingML XML while joining text split across multiple runs.",
  "function:src/stencil/pptx.py:_render_planned_slides": "Renders each slide in a prepared plan with the context assigned to that slide.",
  "function:src/stencil/pptx.py:_render_slide_xml": "Renders Jinja markup across DrawingML text runs and rewrites each affected paragraph into valid slide XML.",
  "function:src/stencil/pptx.py:_rewrite_presentation": "Reconciles slide parts, slide IDs, relationships, and content-type declarations with the rendered slide plan.",
  "function:src/stencil/pptx.py:_clone_slide_part": "Copies a slide XML part and its optional relationships part to a new package path.",
  "function:src/stencil/pptx.py:_max_slide_number": "Finds the largest numeric slide-part suffix in the PPTX package.",
  "function:src/stencil/pptx.py:_is_slide_part": "Tests whether a package member follows the canonical numbered slide-part path.",
  "function:src/stencil/pptx.py:_next_relationship_id": "Allocates the first unused sequential presentation relationship identifier.",
  "function:src/stencil/pptx.py:_slide_relationships_path": "Converts a slide-part path to its companion relationships-part path.",
  "function:src/stencil/pptx.py:_presentation_target_to_part": "Normalizes a presentation relationship target into a package-relative part path.",
  "function:src/stencil/pptx.py:_part_to_presentation_target": "Converts a package part name into a relationship target relative to the presentation part.",
  "function:src/stencil/pptx.py:_evaluate_iterable": "Evaluates a Jinja loop expression and requires a non-string sequence suitable for slide expansion.",
  "function:src/stencil/render.py:render": "Validates source and destination formats, invokes the appropriate Office renderer, and performs optional format-specific PDF conversion.",
  "function:src/stencil/xlsx.py:render_xlsx": "Loads an XLSX workbook, renders every worksheet with strict Jinja semantics, and serializes the result with stage-aware errors.",
  "function:src/stencil/xlsx.py:_render_worksheet": "Expands worksheet loop blocks in reverse order before rendering every remaining cell value.",
  "function:src/stencil/xlsx.py:_find_loop_blocks": "Discovers and validates balanced row-level Jinja loops encoded in worksheet cells.",
  "function:src/stencil/xlsx.py:_single_text_cell_value": "Returns a stripped loop-marker string only when a cell contains an entire for or endfor tag.",
  "function:src/stencil/xlsx.py:_render_loop_block": "Replaces a loop-marker region with repeated, styled row templates rendered against per-item contexts.",
  "function:src/stencil/xlsx.py:_capture_row": "Creates shallow copies of a worksheet row for later loop expansion.",
  "function:src/stencil/xlsx.py:_copy_cell": "Copies styling, formatting, hyperlinks, and comments between openpyxl cells.",
  "function:src/stencil/xlsx.py:_render_cell_value": "Evaluates standalone Jinja expressions as typed values, renders inline templates, and translates formulas when rows are copied.",
  "function:src/stencil/xlsx.py:_evaluate_iterable": "Evaluates a Jinja row-loop expression and rejects strings or non-sequence results.",
};

const tagsFor = (id, type) => {
  const name = id.slice(id.lastIndexOf(":") + 1);
  if (type === "class") {
    if (name.endsWith("Error")) return ["type-definition", "error-handling", "diagnostics"];
    return ["data-model", "metrics", "thread-safety"];
  }
  if (name.startsWith("render") || name === "create_app") return ["api-handler", "service", "rendering"];
  if (name.includes("loop") || name.includes("iterable")) return ["utility", "templating", "validation"];
  if (name.includes("path") || name.includes("format") || name.includes("media_type")) return ["utility", "validation", "formatting"];
  if (name.includes("slide") || name.includes("presentation")) return ["utility", "pptx", "xml-processing"];
  if (name.includes("cell") || name.includes("worksheet") || name.includes("row")) return ["utility", "xlsx", "templating"];
  if (name === "main") return ["entry-point", "cli", "command-group"];
  return ["utility", "rendering", "serialization"];
};

const nodes = [];
for (const result of extraction.results) {
  const [summary, tags, complexity] = fileMeta[result.path];
  nodes.push({
    id: `file:${result.path}`,
    type: "file",
    name: result.path.split("/").at(-1),
    filePath: result.path,
    summary,
    tags,
    complexity,
    ...(result.path.endsWith("pptx.py") ? { languageNotes: "Uses zipfile and ElementTree to manipulate Open Packaging Convention and PresentationML parts without a high-level presentation library." } : {}),
    ...(result.path.endsWith("xlsx.py") ? { languageNotes: "Uses openpyxl object copies and formula translation so expanded template rows retain workbook behavior and formatting." } : {}),
  });

  for (const classInfo of result.classes ?? []) {
    const id = `class:${result.path}:${classInfo.name}`;
    nodes.push({ id, type: "class", name: classInfo.name, filePath: result.path,
      lineRange: [classInfo.startLine, classInfo.endLine], summary: summaries[id], tags: tagsFor(id, "class"),
      complexity: classInfo.endLine - classInfo.startLine + 1 > 50 ? "moderate" : "simple" });
  }
  for (const functionInfo of result.functions ?? []) {
    const id = `function:${result.path}:${functionInfo.name}`;
    const lines = functionInfo.endLine - functionInfo.startLine + 1;
    nodes.push({ id, type: "function", name: functionInfo.name, filePath: result.path,
      lineRange: [functionInfo.startLine, functionInfo.endLine], summary: summaries[id], tags: tagsFor(id, "function"),
      complexity: lines > 75 ? "moderate" : "simple" });
  }
}

const edges = [];
const edge = (source, target, type, weight) => edges.push({ source, target, type, direction: "forward", weight });
for (const result of extraction.results) {
  for (const imported of analyzerInput.batchImportData[result.path] ?? []) edge(`file:${result.path}`, `file:${imported}`, "imports", 0.7);
  for (const node of nodes.filter((candidate) => candidate.filePath === result.path && candidate.type !== "file")) {
    edge(`file:${result.path}`, node.id, "contains", 1.0);
    edge(`file:${result.path}`, node.id, "exports", 0.8);
  }
}

edge("class:src/stencil/errors.py:UnsupportedFormatError", "class:src/stencil/errors.py:StencilError", "inherits", 0.9);
edge("class:src/stencil/errors.py:RenderError", "class:src/stencil/errors.py:StencilError", "inherits", 0.9);
edge("function:src/stencil/api.py:create_app", "class:src/stencil/api.py:RenderMetrics", "calls", 0.8);
edge("function:src/stencil/cli.py:render_command", "function:src/stencil/render.py:render", "calls", 0.8);
edge("function:src/stencil/docx.py:render_docx", "class:src/stencil/errors.py:RenderError", "calls", 0.8);
edge("function:src/stencil/pptx.py:render_pptx", "class:src/stencil/errors.py:RenderError", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/docx.py:render_docx", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/xlsx.py:render_xlsx", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/pptx.py:render_pptx", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/pdf.py:convert_docx_to_pdf", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/pdf.py:convert_xlsx_to_pdf", "calls", 0.8);
edge("function:src/stencil/render.py:render", "function:src/stencil/pdf.py:convert_pptx_to_pdf", "calls", 0.8);
edge("function:src/stencil/xlsx.py:render_xlsx", "class:src/stencil/errors.py:RenderError", "calls", 0.8);

const output = { nodes, edges };
fs.writeFileSync(new URL("../intermediate/batch-1.json", import.meta.url), JSON.stringify(output, null, 2) + "\n");
