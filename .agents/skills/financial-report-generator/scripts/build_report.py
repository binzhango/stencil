#!/usr/bin/env python3
"""Build a deterministic monthly management report from canonical JSON."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, select_autoescape
from markupsafe import Markup

INCOME_FIELDS = (
    "revenue",
    "cost_of_revenue",
    "operating_expenses",
    "interest_expense",
    "tax_expense",
)
BALANCE_FIELDS = (
    "cash",
    "accounts_receivable",
    "inventory",
    "other_current_assets",
    "property_plant_equipment",
    "other_assets",
    "accounts_payable",
    "short_term_debt",
    "other_current_liabilities",
    "long_term_debt",
    "other_liabilities",
    "equity",
)
CASH_FIELDS = (
    "opening_cash",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "closing_cash",
)
REQUIRED_META = (
    "company_name",
    "report_title",
    "current_period",
    "current_period_end",
    "prior_period",
    "prior_period_end",
    "currency",
    "scale",
    "page_size",
    "tolerance",
)
SCALE_LABELS = {"units": "units", "thousands": "000s", "millions": "millions"}
PAGE_SIZES = {"A4", "Letter"}
PAGE_HEIGHTS = {"A4": "270mm", "Letter": "252mm"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path: Path, value: str) -> None:
    """Atomically replace a UTF-8 text artifact without exposing partial output."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def dec(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None or value == "":
        raise ValueError(f"{field}: expected a decimal value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"{field}: value must be finite")
    return result


def derive(period: dict[str, Any], prefix: str) -> dict[str, dict[str, Decimal]]:
    income = {key: dec(period["income"][key], f"{prefix}.income.{key}") for key in INCOME_FIELDS}
    balance = {
        key: dec(period["balance"][key], f"{prefix}.balance.{key}") for key in BALANCE_FIELDS
    }
    cash = {key: dec(period["cash_flow"][key], f"{prefix}.cash_flow.{key}") for key in CASH_FIELDS}
    income["gross_profit"] = income["revenue"] - income["cost_of_revenue"]
    income["operating_income"] = income["gross_profit"] - income["operating_expenses"]
    income["pretax_income"] = income["operating_income"] - income["interest_expense"]
    income["net_income"] = income["pretax_income"] - income["tax_expense"]
    income["gross_margin"] = (
        income["gross_profit"] / income["revenue"] if income["revenue"] else Decimal(0)
    )
    income["operating_margin"] = (
        income["operating_income"] / income["revenue"] if income["revenue"] else Decimal(0)
    )
    income["net_margin"] = (
        income["net_income"] / income["revenue"] if income["revenue"] else Decimal(0)
    )
    balance["total_current_assets"] = sum(
        (balance[k] for k in ("cash", "accounts_receivable", "inventory", "other_current_assets")),
        Decimal(0),
    )
    balance["total_assets"] = (
        balance["total_current_assets"]
        + balance["property_plant_equipment"]
        + balance["other_assets"]
    )
    balance["total_current_liabilities"] = sum(
        (balance[k] for k in ("accounts_payable", "short_term_debt", "other_current_liabilities")),
        Decimal(0),
    )
    balance["total_liabilities"] = (
        balance["total_current_liabilities"]
        + balance["long_term_debt"]
        + balance["other_liabilities"]
    )
    balance["liabilities_and_equity"] = balance["total_liabilities"] + balance["equity"]
    cash["net_change"] = (
        cash["operating_cash_flow"] + cash["investing_cash_flow"] + cash["financing_cash_flow"]
    )
    cash["calculated_closing_cash"] = cash["opening_cash"] + cash["net_change"]
    return {"income": income, "balance": balance, "cash_flow": cash}


def add_gate(
    gates: list[dict[str, Any]], name: str, passed: bool, detail: str, severity: str = "hard"
) -> None:
    gates.append(
        {
            "name": name,
            "status": "PASS" if passed else ("WARN" if severity == "warning" else "FAIL"),
            "severity": severity,
            "detail": detail,
        }
    )


def validate(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    gates: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    meta = data.get("metadata")
    missing = [key for key in REQUIRED_META if not isinstance(meta, dict) or key not in meta]
    if missing:
        errors.append("missing metadata fields: " + ", ".join(missing))
        add_gate(gates, "data-contract", False, errors[-1])
        return {}, gates, errors
    if meta["scale"] not in SCALE_LABELS:
        errors.append("metadata.scale must be units, thousands, or millions")
    if meta["page_size"] not in PAGE_SIZES:
        errors.append("metadata.page_size must be A4 or Letter")
    if meta["current_period"] == meta["prior_period"]:
        errors.append("current and prior periods must be distinct")
    parsed_dates: dict[str, Any] = {}
    for when in ("current_period_end", "prior_period_end"):
        try:
            parsed_dates[when] = datetime.fromisoformat(str(meta[when])).date()
        except ValueError:
            errors.append(f"metadata.{when} must be an ISO date")
    periods = data.get("periods", {})
    try:
        current = derive(periods["current"], "current")
        prior = derive(periods["prior"], "prior")
        tolerance = abs(dec(meta["tolerance"], "metadata.tolerance"))
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(str(exc))
        add_gate(gates, "data-contract", False, "; ".join(errors))
        return {}, gates, errors
    add_gate(
        gates,
        "data-contract",
        not errors,
        "canonical fields and decimal values are valid" if not errors else "; ".join(errors),
    )
    for name, values in (("current", current), ("prior", prior)):
        bdiff = values["balance"]["total_assets"] - values["balance"]["liabilities_and_equity"]
        add_gate(
            gates,
            f"balance-sheet-{name}",
            abs(bdiff) <= tolerance,
            f"difference={bdiff}; tolerance={tolerance}",
        )
        cdiff = values["cash_flow"]["calculated_closing_cash"] - values["cash_flow"]["closing_cash"]
        add_gate(
            gates,
            f"cash-rollforward-{name}",
            abs(cdiff) <= tolerance,
            f"difference={cdiff}; tolerance={tolerance}",
        )
        bridge = values["cash_flow"]["closing_cash"] - values["balance"]["cash"]
        add_gate(
            gates,
            f"cash-to-balance-{name}",
            abs(bridge) <= tolerance,
            f"difference={bridge}; tolerance={tolerance}",
        )
        for field in INCOME_FIELDS:
            if values["income"][field] < 0:
                warning = f"{name}.income.{field} is negative under a positive-magnitude convention"
                warnings.append(warning)
                add_gate(gates, f"sign-{name}-income-{field}", False, warning, "warning")
        if values["balance"]["equity"] < 0:
            warning = f"{name}.balance.equity is negative"
            warnings.append(warning)
            add_gate(gates, f"negative-equity-{name}", False, warning, "warning")
    sources = data.get("sources")
    source_ok = (
        isinstance(sources, list)
        and bool(sources)
        and all(
            isinstance(s, dict) and s.get("id") and s.get("label") and s.get("as_of")
            for s in sources
        )
    )
    if source_ok and len({str(s["id"]) for s in sources}) != len(sources):
        source_ok = False
    add_gate(
        gates,
        "source-inventory",
        source_ok,
        "source identifiers, labels, and dates are present"
        if source_ok
        else "at least one complete source is required",
    )
    if not source_ok:
        errors.append("invalid or missing source inventory")
    else:
        period_end = parsed_dates.get("current_period_end")
        for index, source in enumerate(sources):
            try:
                source_date = datetime.fromisoformat(str(source["as_of"])).date()
                if period_end and source_date > period_end:
                    warning = f"sources[{index}].as_of is later than the reporting-period end"
                    warnings.append(warning)
                    add_gate(gates, f"source-date-{index}", False, warning, "warning")
            except ValueError:
                errors.append(f"sources[{index}].as_of must be an ISO date")
                add_gate(gates, f"source-date-{index}", False, errors[-1])
            if not source.get("sha256"):
                warning = f"sources[{index}] has no verified snapshot hash"
                warnings.append(warning)
                add_gate(gates, f"source-hash-{index}", False, warning, "warning")
    all_refs = {
        f"{section}.{key}"
        for section in ("income", "balance", "cash_flow")
        for key in current[section]
    }
    unresolved: list[str] = []
    for index, item in enumerate(data.get("commentary", [])):
        refs = item.get("source_refs", []) if isinstance(item, dict) else []
        unresolved.extend(f"commentary[{index}]:{ref}" for ref in refs if ref not in all_refs)
        if isinstance(item, dict) and re.search(r"\d", str(item.get("text", ""))) and not refs:
            warning = f"commentary[{index}] contains numbers without source_refs"
            warnings.append(warning)
            add_gate(gates, f"numeric-commentary-{index}", False, warning, "warning")
        if isinstance(item, dict) and item.get("kind") not in {
            "data observation",
            "management explanation",
            "forecast or judgment",
        }:
            errors.append(f"commentary[{index}].kind is unsupported")
            add_gate(gates, f"commentary-kind-{index}", False, errors[-1])
    add_gate(
        gates,
        "commentary-references",
        not unresolved,
        "all commentary references resolve" if not unresolved else ", ".join(unresolved),
    )
    if unresolved:
        errors.append("unresolved commentary references")
    for index, item in enumerate(data.get("kpis", [])):
        if (
            not isinstance(item, dict)
            or not item.get("label")
            or item.get("format") not in {"number", "percent", "money"}
        ):
            errors.append(f"kpis[{index}] is incomplete or has an unsupported format")
            add_gate(gates, f"kpi-contract-{index}", False, errors[-1])
            continue
        try:
            dec(item.get("current"), f"kpis[{index}].current")
            dec(item.get("prior"), f"kpis[{index}].prior")
        except ValueError as exc:
            errors.append(str(exc))
            add_gate(gates, f"kpi-contract-{index}", False, errors[-1])
    hard_failed = [g for g in gates if g["severity"] == "hard" and g["status"] == "FAIL"]
    if hard_failed and "one or more hard gates failed" not in errors:
        errors.append("one or more hard gates failed")
    return {"current": current, "prior": prior, "tolerance": tolerance}, gates, errors


def money(value: Decimal, currency: str) -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥"}
    sign = "-" if value < 0 else ""
    symbol = symbols.get(currency.upper(), currency.upper() + " ")
    return f"{sign}{symbol}{abs(value):,.0f}"


def pct(value: Decimal) -> str:
    return f"{value * 100:.1f}%"


def delta(current: Decimal, prior: Decimal, percent: bool = False) -> dict[str, str]:
    change = current - prior
    direction = "up" if change >= 0 else "down"
    shown = pct(abs(change)) if percent else f"{abs(change):,.0f}"
    arrow = "▲" if change >= 0 else "▼"
    return {"class_name": direction, "text": f"{arrow} {shown} vs prior"}


def metric_card(label: str, value: str, change: dict[str, str]) -> dict[str, Any]:
    return {"label": label, "value": value, "delta": change}


def statement_rows(
    rows: list[tuple[str, Decimal, Decimal, str]], currency: str
) -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "current": money(current, currency),
            "prior": money(prior, currency),
            "change": money(current - prior, currency),
            "class_name": class_name,
        }
        for label, current, prior, class_name in rows
    ]


def bar_chart(
    items: list[tuple[str, Decimal, Decimal]], current_label: str, prior_label: str
) -> str:
    maximum = max((abs(v) for _, a, b in items for v in (a, b)), default=Decimal(1)) or Decimal(1)
    parts = [
        '<svg viewBox="0 0 620 240" role="img" '
        'aria-label="Current and prior period performance comparison">'
    ]
    parts.append(
        "<style>.a{fill:#174f66}.b{fill:#9bb4bf}"
        ".t{font:12px Arial;fill:#667085}"
        ".v{font:bold 11px Arial;fill:#172033}</style>"
    )
    for i, (label, cur, prior) in enumerate(items):
        y = 25 + i * 68
        cw = float(abs(cur) / maximum) * 380
        pw = float(abs(prior) / maximum) * 380
        parts.append(
            f'<text class="t" x="0" y="{y + 13}">{html.escape(label)}</text>'
            f'<rect class="a" x="125" y="{y}" width="{cw:.1f}" '
            'height="18" rx="3"/>'
            f'<rect class="b" x="125" y="{y + 24}" width="{pw:.1f}" '
            'height="18" rx="3"/>'
            f'<text class="v" x="{min(585, 130 + cw):.1f}" '
            f'y="{y + 13}">{cur:,.0f}</text>'
            f'<text class="v" x="{min(585, 130 + pw):.1f}" '
            f'y="{y + 37}">{prior:,.0f}</text>'
        )
    parts.append(
        f'<text class="t" x="125" y="232">■ {html.escape(current_label)}   '
        f"▪ {html.escape(prior_label)}</text></svg>"
    )
    return "".join(parts)


def build_view_model(
    data: dict[str, Any],
    derived: dict[str, Any],
    input_hash: str,
    template_hash: str,
    generated: str,
    gates: list[dict[str, Any]],
) -> dict[str, Any]:
    meta = data["metadata"]
    cur, prior = derived["current"], derived["prior"]
    summary_metrics = [
        metric_card(
            "Revenue",
            money(cur["income"]["revenue"], meta["currency"]),
            delta(cur["income"]["revenue"], prior["income"]["revenue"]),
        ),
        metric_card(
            "Gross margin",
            pct(cur["income"]["gross_margin"]),
            delta(cur["income"]["gross_margin"], prior["income"]["gross_margin"], True),
        ),
        metric_card(
            "Operating income",
            money(cur["income"]["operating_income"], meta["currency"]),
            delta(cur["income"]["operating_income"], prior["income"]["operating_income"]),
        ),
        metric_card(
            "Closing cash",
            money(cur["balance"]["cash"], meta["currency"]),
            delta(cur["balance"]["cash"], prior["balance"]["cash"]),
        ),
    ]
    kpi_cards = []
    for index, item in enumerate(data.get("kpis", [])):
        current = dec(item["current"], f"kpis[{index}].current")
        prior_value = dec(item["prior"], f"kpis[{index}].prior")
        fmt = item.get("format", "number")
        shown = (
            pct(current)
            if fmt == "percent"
            else money(current, meta["currency"])
            if fmt == "money"
            else f"{current:,.0f}"
        )
        kpi_cards.append(
            metric_card(str(item["label"]), shown, delta(current, prior_value, fmt == "percent"))
        )
    income_rows = [
        ("Revenue", cur["income"]["revenue"], prior["income"]["revenue"], ""),
        (
            "Cost of revenue",
            cur["income"]["cost_of_revenue"],
            prior["income"]["cost_of_revenue"],
            "",
        ),
        (
            "Gross profit",
            cur["income"]["gross_profit"],
            prior["income"]["gross_profit"],
            "subtotal",
        ),
        (
            "Operating expenses",
            cur["income"]["operating_expenses"],
            prior["income"]["operating_expenses"],
            "",
        ),
        (
            "Operating income",
            cur["income"]["operating_income"],
            prior["income"]["operating_income"],
            "subtotal",
        ),
        (
            "Interest expense",
            cur["income"]["interest_expense"],
            prior["income"]["interest_expense"],
            "",
        ),
        (
            "Pretax income",
            cur["income"]["pretax_income"],
            prior["income"]["pretax_income"],
            "subtotal",
        ),
        ("Tax expense", cur["income"]["tax_expense"], prior["income"]["tax_expense"], ""),
        ("Net income", cur["income"]["net_income"], prior["income"]["net_income"], "total"),
    ]
    balance_rows = [
        ("Cash", cur["balance"]["cash"], prior["balance"]["cash"], ""),
        (
            "Accounts receivable",
            cur["balance"]["accounts_receivable"],
            prior["balance"]["accounts_receivable"],
            "",
        ),
        ("Inventory", cur["balance"]["inventory"], prior["balance"]["inventory"], ""),
        (
            "Other current assets",
            cur["balance"]["other_current_assets"],
            prior["balance"]["other_current_assets"],
            "",
        ),
        (
            "Total current assets",
            cur["balance"]["total_current_assets"],
            prior["balance"]["total_current_assets"],
            "subtotal",
        ),
        (
            "Property, plant and equipment",
            cur["balance"]["property_plant_equipment"],
            prior["balance"]["property_plant_equipment"],
            "",
        ),
        ("Other assets", cur["balance"]["other_assets"], prior["balance"]["other_assets"], ""),
        ("Total assets", cur["balance"]["total_assets"], prior["balance"]["total_assets"], "total"),
        (
            "Accounts payable",
            cur["balance"]["accounts_payable"],
            prior["balance"]["accounts_payable"],
            "",
        ),
        (
            "Short-term debt",
            cur["balance"]["short_term_debt"],
            prior["balance"]["short_term_debt"],
            "",
        ),
        (
            "Other current liabilities",
            cur["balance"]["other_current_liabilities"],
            prior["balance"]["other_current_liabilities"],
            "",
        ),
        (
            "Total current liabilities",
            cur["balance"]["total_current_liabilities"],
            prior["balance"]["total_current_liabilities"],
            "subtotal",
        ),
        (
            "Long-term debt",
            cur["balance"]["long_term_debt"],
            prior["balance"]["long_term_debt"],
            "",
        ),
        (
            "Other liabilities",
            cur["balance"]["other_liabilities"],
            prior["balance"]["other_liabilities"],
            "",
        ),
        (
            "Total liabilities",
            cur["balance"]["total_liabilities"],
            prior["balance"]["total_liabilities"],
            "subtotal",
        ),
        ("Equity", cur["balance"]["equity"], prior["balance"]["equity"], ""),
        (
            "Liabilities and equity",
            cur["balance"]["liabilities_and_equity"],
            prior["balance"]["liabilities_and_equity"],
            "total",
        ),
    ]
    cash_rows = [
        ("Opening cash", cur["cash_flow"]["opening_cash"], prior["cash_flow"]["opening_cash"], ""),
        (
            "Operating cash flow",
            cur["cash_flow"]["operating_cash_flow"],
            prior["cash_flow"]["operating_cash_flow"],
            "",
        ),
        (
            "Investing cash flow",
            cur["cash_flow"]["investing_cash_flow"],
            prior["cash_flow"]["investing_cash_flow"],
            "",
        ),
        (
            "Financing cash flow",
            cur["cash_flow"]["financing_cash_flow"],
            prior["cash_flow"]["financing_cash_flow"],
            "",
        ),
        (
            "Net change in cash",
            cur["cash_flow"]["net_change"],
            prior["cash_flow"]["net_change"],
            "subtotal",
        ),
        (
            "Closing cash",
            cur["cash_flow"]["closing_cash"],
            prior["cash_flow"]["closing_cash"],
            "total",
        ),
    ]
    controls = [gate for gate in gates if gate["severity"] == "hard"]
    warnings = [gate for gate in gates if gate["status"] == "WARN"]
    return {
        "document_title": f"{meta['company_name']} - {meta['report_title']}",
        "meta": {**meta, "scale_label": SCALE_LABELS[meta["scale"]]},
        "page_height": PAGE_HEIGHTS[meta["page_size"]],
        "generated_at": generated,
        "generated_date": generated[:10],
        "summary_metrics": summary_metrics,
        "performance_chart": Markup(
            bar_chart(
                [
                    ("Revenue", cur["income"]["revenue"], prior["income"]["revenue"]),
                    (
                        "Gross profit",
                        cur["income"]["gross_profit"],
                        prior["income"]["gross_profit"],
                    ),
                    ("Net income", cur["income"]["net_income"], prior["income"]["net_income"]),
                ],
                meta["current_period"],
                meta["prior_period"],
            )
        ),
        "commentary": data.get("commentary", []),
        "kpi_cards": kpi_cards,
        "income_rows": statement_rows(income_rows, meta["currency"]),
        "balance_rows": statement_rows(balance_rows, meta["currency"]),
        "cash_flow_rows": statement_rows(cash_rows, meta["currency"]),
        "cash_chart": Markup(
            bar_chart(
                [
                    (
                        "Operating",
                        cur["cash_flow"]["operating_cash_flow"],
                        prior["cash_flow"]["operating_cash_flow"],
                    ),
                    (
                        "Investing",
                        cur["cash_flow"]["investing_cash_flow"],
                        prior["cash_flow"]["investing_cash_flow"],
                    ),
                    (
                        "Financing",
                        cur["cash_flow"]["financing_cash_flow"],
                        prior["cash_flow"]["financing_cash_flow"],
                    ),
                ],
                meta["current_period"],
                meta["prior_period"],
            )
        ),
        "gross_margin_note": {
            "current": pct(cur["income"]["gross_margin"]),
            "prior": pct(prior["income"]["gross_margin"]),
        },
        "operating_margin_note": {
            "current": pct(cur["income"]["operating_margin"]),
            "prior": pct(prior["income"]["operating_margin"]),
        },
        "controls": controls,
        "warnings": warnings,
        "sources": [
            {
                **source,
                "location": source.get("path") or source.get("uri") or "location not disclosed",
            }
            for source in data["sources"]
        ],
        "input_hash": input_hash,
        "template_hash": template_hash,
    }


def render_template(template_path: Path, context: dict[str, Any]) -> str:
    environment = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(template_path.name)
    return template.render(**context)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "monthly-report.html",
    )
    parser.add_argument(
        "--generated-at",
        help="Optional ISO-8601 generation timestamp for reproducible builds",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        generated = (
            datetime.fromisoformat(args.generated_at.replace("Z", "+00:00"))
            if args.generated_at
            else datetime.now(UTC).replace(microsecond=0)
        )
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=UTC)
        generated_text = generated.astimezone(UTC).replace(microsecond=0).isoformat()
    except ValueError:
        print("ERROR: --generated-at must be an ISO-8601 timestamp", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    derived, gates, errors = validate(data)
    warnings = [g["detail"] for g in gates if g["status"] == "WARN"]
    overall = "FAIL" if errors else "PASS"
    report = {
        "overall": overall,
        "generated_at": generated_text,
        "gates": gates,
        "warnings": warnings,
        "errors": errors,
    }
    gate_path = args.out_dir / "GATE_REPORT.json"
    atomic_write_text(gate_path, json.dumps(report, indent=2) + "\n")
    if errors:
        print(f"FAIL: {len(errors)} error(s); see {gate_path}", file=sys.stderr)
        return 1
    if not args.template.is_file():
        add_gate(gates, "template-render", False, f"template not found: {args.template}")
        report.update(overall="FAIL", errors=[f"template not found: {args.template}"], gates=gates)
        atomic_write_text(gate_path, json.dumps(report, indent=2) + "\n")
        print(f"FAIL: template not found: {args.template}", file=sys.stderr)
        return 1
    input_hash, template_hash = sha256(args.input), sha256(args.template)
    try:
        context = build_view_model(
            data,
            derived,
            input_hash,
            template_hash,
            generated_text,
            gates,
        )
        output = render_template(args.template.resolve(), context)
    except (TemplateError, OSError, ValueError) as exc:
        detail = f"Jinja template render failed: {exc}"
        add_gate(gates, "template-render", False, detail)
        report.update(overall="FAIL", errors=[detail], gates=gates)
        atomic_write_text(gate_path, json.dumps(report, indent=2) + "\n")
        print(f"FAIL: {detail}; see {gate_path}", file=sys.stderr)
        return 1
    add_gate(gates, "template-render", True, "strict Jinja rendering completed")
    remote_resources = re.findall(r"(?:src|href)=[\"']https?://", output, re.I)
    add_gate(
        gates,
        "offline-resources",
        not remote_resources,
        "no remote resources" if not remote_resources else "remote resources are forbidden",
    )
    expected_sections = {
        "executive-summary",
        "income-statement",
        "balance-sheet",
        "cash-flow",
        "controls-and-provenance",
    }
    actual_sections = set(re.findall(r'<section\b[^>]*data-report-section="([^"]+)"', output, re.I))
    missing_sections = sorted(expected_sections - actual_sections)
    add_gate(
        gates,
        "required-sections",
        not missing_sections,
        "all five sections present"
        if not missing_sections
        else "missing sections: " + ", ".join(missing_sections),
    )
    final_errors = [
        gate["detail"] for gate in gates if gate["severity"] == "hard" and gate["status"] == "FAIL"
    ]
    report.update(
        overall="FAIL" if final_errors else "PASS",
        errors=final_errors,
        gates=gates,
        warnings=[gate["detail"] for gate in gates if gate["status"] == "WARN"],
    )
    atomic_write_text(gate_path, json.dumps(report, indent=2) + "\n")
    if final_errors:
        print(f"FAIL: template release gates failed; see {gate_path}", file=sys.stderr)
        return 1
    html_path = args.out_dir / "report.html"
    atomic_write_text(html_path, output)
    formulas = {
        "gross_profit": "revenue - cost_of_revenue",
        "operating_income": "gross_profit - operating_expenses",
        "pretax_income": "operating_income - interest_expense",
        "net_income": "pretax_income - tax_expense",
        "total_assets": "current assets + property_plant_equipment + other_assets",
        "total_liabilities": "current liabilities + long_term_debt + other_liabilities",
        "net_change": "operating_cash_flow + investing_cash_flow + financing_cash_flow",
    }
    manifest = {
        "generated_at": generated_text,
        "company": data["metadata"]["company_name"],
        "period_end": data["metadata"]["current_period_end"],
        "render_contract": {"engine": "jinja2", "undefined": "strict", "autoescape": True},
        "input": {"path": str(args.input), "sha256": input_hash},
        "template": {"path": str(args.template), "sha256": template_hash},
        "sources": data["sources"],
        "formulas": formulas,
    }
    atomic_write_text(args.out_dir / "DATA_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    print(f"PASS: wrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
