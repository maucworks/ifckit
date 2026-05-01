"""
ifckit.json_build
=================

JSON to IFC building functions.

Moved here to avoid import issues with 'ifckit.schema' being treated
as a module vs package in some environments.
"""

import json
from typing import Any, Dict, List, Optional

from ifckit.model import IfcModel
from ifckit.schema import IfcSchema, LengthUnit
from ifckit.validator import validate, ValidationResult as JsonValidationResult
from ifckit.elements.registry import ElementRegistry


def validate_json(data: Dict[str, Any]) -> JsonValidationResult:
    """Validate a JSON dict against the ifckit JSON schema."""
    errors: List[str] = []
    warnings: List[str] = []

    if "ifc_version" in data:
        if data["ifc_version"] not in ("IFC4", "IFC4X3"):
            errors.append(f"ifc_version must be 'IFC4' or 'IFC4X3', got {data['ifc_version']}")
    else:
        errors.append("Missing required field: ifc_version")

    if "project" in data:
        if not isinstance(data["project"], dict):
            errors.append("project must be a dict")
        elif "name" not in data["project"]:
            errors.append("project.name is required")
    else:
        errors.append("Missing required field: project")

    if "unit" in data:
        if data["unit"] not in ("METRE", "MILLIMETRE"):
            errors.append(f"unit must be METRE or MILLIMETRE, got {data['unit']}")
    else:
        errors.append("Missing required field: unit")

    if "buildings" in data:
        for i, bldg in enumerate(data.get("buildings", [])):
            if "name" not in bldg:
                errors.append(f"buildings[{i}] missing name")
            for j, storey in enumerate(bldg.get("storeys", [])):
                if "name" not in storey:
                    errors.append(f"buildings[{i}].storeys[{j}] missing name")

    return JsonValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def build(data: Dict[str, Any], output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON dict."""
    json_result = validate_json(data)
    if not json_result.ok:
        raise ValueError(f"Invalid JSON: {'; '.join(json_result.errors)}")

    schema_str = data.get("ifc_version", "IFC4")
    schema = IfcSchema.IFC4 if schema_str == "IFC4" else IfcSchema.IFC4X3

    project_name = data.get("project", {}).get("name", "Unnamed Project")
    author = data.get("project", {}).get("author", "")
    unit_str = data.get("unit", "METRE")
    unit = LengthUnit.MILLIMETRE if unit_str == "MILLIMETRE" else LengthUnit.METRE

    model = IfcModel(name=project_name, schema=schema, author=author, unit=unit)
    site_data = data.get("site") or {}
    site = model.add_site(site_data.get("name", "Site"))

    for bldg_data in data.get("buildings", []):
        building = site.add_building(bldg_data.get("name", "Building"))
        
        for storey_data in bldg_data.get("storeys", []):
            storey = building.add_storey(
                storey_data.get("name", "Storey"),
                elevation=storey_data.get("elevation", 0.0)
            )
            
            for elem_data in storey_data.get("elements", []):
                elem_type = elem_data.get("type")
                # Support both formats: {"type": "...", "data": {...}} or {"type": "...", ...}
                elem_dict = elem_data.get("data") if "data" in elem_data else elem_data
                
                try:
                    cls = ElementRegistry.get(elem_type)
                except KeyError:
                    raise KeyError(
                        f"Unknown element type {elem_type!r} in "
                        f"building '{bldg_data.get('name')}' / "
                        f"storey '{storey_data.get('name')}'. "
                        f"Available: {list(ElementRegistry.types().keys())}"
                    )
                pending = cls.from_dict(elem_dict)
                
                result = validate(pending)
                if not result.ok:
                    raise ValueError(f"Validation failed: {result.errors}")
                
                storey.add(pending)

    if output_path:
        model.save(output_path)

    return model


def build_from_json(json_str: str, output_path: Optional[str] = None) -> IfcModel:
    """Build an IfcModel from a JSON string."""
    return build(json.loads(json_str), output_path)