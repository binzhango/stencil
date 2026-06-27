"""PPTX rendering engine."""

from __future__ import annotations

import posixpath
import re
import zipfile
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

from jinja2 import Environment, StrictUndefined, TemplateError

from .errors import RenderError

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
)

FOR_TAG_RE = re.compile(
    r"^\s*\{%\s*for\s+(?P<variable>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+"
    r"(?P<expression>.*?)\s*%\}\s*$",
    re.DOTALL,
)
END_FOR_TAG_RE = re.compile(r"^\s*\{%\s*endfor\s*%\}\s*$", re.DOTALL)
SLIDE_NUMBER_RE = re.compile(r"^ppt/slides/slide(?P<number>\d+)\.xml$")

ElementTree.register_namespace("a", A_NS)
ElementTree.register_namespace("p", P_NS)
ElementTree.register_namespace("r", R_NS)


def render_pptx(template_path: str | Path, data: Mapping[str, Any]) -> bytes:
    """Render a PPTX template with Jinja-compatible data."""

    path = Path(template_path)

    if not path.exists():
        raise RenderError("Template file does not exist", template_path=path, stage="load")
    if not path.is_file():
        raise RenderError("Template path is not a file", template_path=path, stage="load")

    environment = Environment(undefined=StrictUndefined, autoescape=False)
    context = dict(data)

    try:
        with zipfile.ZipFile(path) as archive:
            package = {name: archive.read(name) for name in archive.namelist()}
    except Exception as exc:
        raise RenderError("Failed to load PPTX template", template_path=path, stage="load") from exc

    try:
        slide_refs = _read_slide_refs(package)
        render_plan = _build_render_plan(package, slide_refs, context, environment)
        _render_planned_slides(package, render_plan, environment)
        _rewrite_presentation(package, slide_refs, render_plan)
    except TemplateError as exc:
        raise RenderError(
            f"Failed to render PPTX template: {exc}",
            template_path=path,
            stage="render",
        ) from exc
    except Exception as exc:
        raise RenderError(
            "Failed to render PPTX template", template_path=path, stage="render"
        ) from exc

    buffer = BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in package.items():
                archive.writestr(name, content)
    except Exception as exc:
        raise RenderError(
            "Failed to serialize rendered PPTX", template_path=path, stage="save"
        ) from exc

    return buffer.getvalue()


def _read_slide_refs(package: Mapping[str, bytes]) -> list[dict[str, str]]:
    presentation = ElementTree.fromstring(package["ppt/presentation.xml"])
    rels = ElementTree.fromstring(package["ppt/_rels/presentation.xml.rels"])
    targets = {
        relationship.attrib["Id"]: _presentation_target_to_part(relationship.attrib["Target"])
        for relationship in rels
        if relationship.attrib.get("Target")
    }

    refs: list[dict[str, str]] = []
    for slide_id in presentation.findall(f".//{{{P_NS}}}sldId"):
        relationship_id = slide_id.attrib[f"{{{R_NS}}}id"]
        refs.append(
            {
                "id": slide_id.attrib["id"],
                "r_id": relationship_id,
                "path": targets[relationship_id],
            }
        )
    return refs


def _build_render_plan(
    package: dict[str, bytes],
    slide_refs: Sequence[dict[str, str]],
    context: Mapping[str, Any],
    environment: Environment,
) -> list[dict[str, Any]]:
    blocks = _find_slide_loop_blocks(package, slide_refs)
    if not blocks:
        return [{"path": ref["path"], "context": context, "source": ref} for ref in slide_refs]

    block_by_start = {block[0]: block for block in blocks}
    covered = {
        index
        for start, end, _, _ in blocks
        for index in range(start, end + 1)
    }
    plan: list[dict[str, Any]] = []
    max_slide_number = _max_slide_number(package)

    index = 0
    while index < len(slide_refs):
        if index in block_by_start:
            start, end, variable, expression = block_by_start[index]
            items = _evaluate_iterable(expression, context, environment)
            body_refs = slide_refs[start + 1 : end]
            for item in items:
                loop_context = dict(context)
                loop_context[variable] = item
                for source_ref in body_refs:
                    max_slide_number += 1
                    target_path = f"ppt/slides/slide{max_slide_number}.xml"
                    _clone_slide_part(package, source_ref["path"], target_path)
                    plan.append({"path": target_path, "context": loop_context, "source": None})
            index = end + 1
            continue

        if index not in covered:
            ref = slide_refs[index]
            plan.append({"path": ref["path"], "context": context, "source": ref})
        index += 1

    return plan


def _find_slide_loop_blocks(
    package: Mapping[str, bytes],
    slide_refs: Sequence[dict[str, str]],
) -> list[tuple[int, int, str, str]]:
    stack: list[tuple[int, str, str]] = []
    blocks: list[tuple[int, int, str, str]] = []

    for index, ref in enumerate(slide_refs):
        for text in _slide_paragraph_texts(package[ref["path"]]):
            for_match = FOR_TAG_RE.match(text)
            if for_match:
                stack.append(
                    (
                        index,
                        for_match.group("variable"),
                        for_match.group("expression").strip(),
                    )
                )
                continue

            if END_FOR_TAG_RE.match(text):
                if not stack:
                    raise ValueError("Found PPTX endfor slide without matching for slide")
                start, variable, expression = stack.pop()
                if start >= index - 1:
                    raise ValueError("PPTX slide loop must contain at least one body slide")
                blocks.append((start, index, variable, expression))

    if stack:
        start, _, _ = stack[-1]
        raise ValueError(f"Found PPTX for slide without matching endfor at slide {start + 1}")

    return blocks


def _slide_paragraph_texts(slide_xml: bytes) -> list[str]:
    root = ElementTree.fromstring(slide_xml)
    texts: list[str] = []
    for paragraph in root.iter(f"{{{A_NS}}}p"):
        parts = [
            node.text or ""
            for node in paragraph.iter(f"{{{A_NS}}}t")
        ]
        if parts:
            texts.append("".join(parts).strip())
    return texts


def _render_planned_slides(
    package: dict[str, bytes],
    render_plan: Sequence[dict[str, Any]],
    environment: Environment,
) -> None:
    for entry in render_plan:
        package[entry["path"]] = _render_slide_xml(
            package[entry["path"]],
            context=entry["context"],
            environment=environment,
        )


def _render_slide_xml(
    slide_xml: bytes,
    *,
    context: Mapping[str, Any],
    environment: Environment,
) -> bytes:
    root = ElementTree.fromstring(slide_xml)
    for paragraph in root.iter(f"{{{A_NS}}}p"):
        text_nodes = list(paragraph.iter(f"{{{A_NS}}}t"))
        if not text_nodes:
            continue

        template = "".join(node.text or "" for node in text_nodes)
        if "{{" not in template and "{%" not in template:
            continue

        rendered = environment.from_string(template).render(dict(context))
        text_nodes[0].text = rendered
        for node in text_nodes[1:]:
            node.text = ""

    return cast(bytes, ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))


def _rewrite_presentation(
    package: dict[str, bytes],
    slide_refs: Sequence[dict[str, str]],
    render_plan: Sequence[dict[str, Any]],
) -> None:
    presentation = ElementTree.fromstring(package["ppt/presentation.xml"])
    rels = ElementTree.fromstring(package["ppt/_rels/presentation.xml.rels"])
    content_types = ElementTree.fromstring(package["[Content_Types].xml"])
    slide_id_list = presentation.find(f"{{{P_NS}}}sldIdLst")
    if slide_id_list is None:
        raise ValueError("PPTX presentation has no slide id list")

    planned_slide_paths = {entry["path"] for entry in render_plan}
    for name in list(package):
        if _is_slide_part(name) and name not in planned_slide_paths:
            del package[name]
            relationships_name = _slide_relationships_path(name)
            if relationships_name in package:
                del package[relationships_name]

    for child in list(slide_id_list):
        slide_id_list.remove(child)

    for relationship in list(rels):
        if relationship.attrib.get("Type", "").endswith("/slide"):
            rels.remove(relationship)

    max_slide_id = max((int(ref["id"]) for ref in slide_refs), default=255)
    used_relationship_ids = {
        relationship.attrib["Id"] for relationship in rels if "Id" in relationship.attrib
    }
    for override in list(content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
        part_name = override.attrib.get("PartName", "")
        if _is_slide_part(part_name.removeprefix("/")):
            content_types.remove(override)
    content_type_parts: set[str] = set()

    for entry in render_plan:
        source_ref = entry["source"]
        if source_ref is not None:
            slide_id = source_ref["id"]
            relationship_id = source_ref["r_id"]
            used_relationship_ids.add(relationship_id)
        else:
            max_slide_id += 1
            slide_id = str(max_slide_id)
            relationship_id = _next_relationship_id(used_relationship_ids)
            used_relationship_ids.add(relationship_id)

        ElementTree.SubElement(
            rels,
            f"{{{REL_NS}}}Relationship",
            {
                "Id": relationship_id,
                "Type": (
                    "http://schemas.openxmlformats.org/officeDocument/2006/"
                    "relationships/slide"
                ),
                "Target": _part_to_presentation_target(entry["path"]),
            },
        )

        ElementTree.SubElement(
            slide_id_list,
            f"{{{P_NS}}}sldId",
            {"id": slide_id, f"{{{R_NS}}}id": relationship_id},
        )

        part_name = f"/{entry['path']}"
        if part_name not in content_type_parts:
            ElementTree.SubElement(
                content_types,
                f"{{{CONTENT_TYPES_NS}}}Override",
                {"PartName": part_name, "ContentType": SLIDE_CONTENT_TYPE},
            )
            content_type_parts.add(part_name)

    package["ppt/presentation.xml"] = ElementTree.tostring(
        presentation, encoding="utf-8", xml_declaration=True
    )
    ElementTree.register_namespace("", REL_NS)
    package["ppt/_rels/presentation.xml.rels"] = ElementTree.tostring(
        rels, encoding="utf-8", xml_declaration=True
    )
    ElementTree.register_namespace("", CONTENT_TYPES_NS)
    package["[Content_Types].xml"] = ElementTree.tostring(
        content_types, encoding="utf-8", xml_declaration=True
    )


def _clone_slide_part(package: dict[str, bytes], source_path: str, target_path: str) -> None:
    package[target_path] = package[source_path]

    source_rels = _slide_relationships_path(source_path)
    if source_rels in package:
        package[_slide_relationships_path(target_path)] = package[source_rels]


def _max_slide_number(package: Mapping[str, bytes]) -> int:
    numbers = [
        int(match.group("number"))
        for name in package
        if (match := SLIDE_NUMBER_RE.match(name))
    ]
    return max(numbers, default=0)


def _is_slide_part(name: str) -> bool:
    return SLIDE_NUMBER_RE.match(name) is not None


def _next_relationship_id(used_relationship_ids: set[str]) -> str:
    index = 1
    while f"rId{index}" in used_relationship_ids:
        index += 1
    return f"rId{index}"


def _slide_relationships_path(slide_path: str) -> str:
    directory, filename = posixpath.split(slide_path)
    return f"{directory}/_rels/{filename}.rels"


def _presentation_target_to_part(target: str) -> str:
    if target.startswith("/"):
        return target.removeprefix("/")
    return posixpath.normpath(posixpath.join("ppt", target))


def _part_to_presentation_target(part_name: str) -> str:
    return posixpath.relpath(part_name, "ppt")


def _evaluate_iterable(
    expression: str, context: Mapping[str, Any], environment: Environment
) -> Sequence[Any]:
    value = environment.compile_expression(expression)(**context)
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"PPTX slide loop expression {expression!r} did not evaluate to a list")
    return value
