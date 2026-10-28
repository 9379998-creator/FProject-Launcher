"""
FERO CAD Physical Component Assembly Engine (Task 024)
======================================================
Assembles individual CAD polylines, cavities, and hatches into
distinct, selectable, and movable physical components using native
AutoCAD groups (ACAD_GROUP).

Duality Contract:
- Level 1: Every contour and cavity remains an independent, closed LWPOLYLINE.
- Level 2: The physical component binds outer perimeter, cavities, and hatch
  into a native AutoCAD group, enabling 1-click selection and movement in CAD.
"""

import math
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import LWPolyline, DXFGraphic

logger = logging.getLogger(__name__)


def get_entity_bbox(entity: DXFGraphic) -> Tuple[float, float, float, float]:
    """Calculate 2D bounding box (min_x, min_y, max_x, max_y) of a DXF entity."""
    if entity.dxftype() == "LWPOLYLINE":
        pts = list(entity.get_points())
        if not pts:
            return 0.0, 0.0, 0.0, 0.0
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    elif entity.dxftype() == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        return min(start.x, end.x), min(start.y, end.y), max(start.x, end.x), max(start.y, end.y)
    return 0.0, 0.0, 0.0, 0.0


def bbox_area(b: Tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def bbox_contains(outer_b: Tuple[float, float, float, float],
                  inner_b: Tuple[float, float, float, float],
                  tol: float = 0.5) -> bool:
    return (outer_b[0] - tol <= inner_b[0] and
            outer_b[1] - tol <= inner_b[1] and
            outer_b[2] + tol >= inner_b[2] and
            outer_b[3] + tol >= inner_b[3])


def assemble_physical_components(doc: Drawing) -> Dict[str, Any]:
    """
    Classify modelspace entities into physical components and bind them into
    native AutoCAD groups (ACAD_GROUP).
    """
    msp = doc.modelspace()
    all_entities = list(msp)
    if not all_entities:
        return {"componentsCount": 0, "groups": []}

    # Group table in ezdxf
    group_table = doc.groups

    # Target physical component taxonomy (Task 024 Component Map)
    component_defs = [
        # 1. Glass unit assembly
        {
            "id": "PART_01_GLASS_UNIT",
            "name": "Стеклопакет двухкамерный",
            "layer_filter": lambda lyr: "СТЕКЛОПАКЕТ" in lyr,
            "bbox_filter": lambda b: 350.0 <= b[0] <= 445.0 and 390.0 <= b[1] <= 450.0,
        },
        # 2. Exterior glass seal
        {
            "id": "PART_02_SEAL_GLASS_EXT",
            "name": "Наружный EPDM уплотнитель стеклопакета",
            "layer_filter": lambda lyr: "КОМПЛЕКТУЮЩИЕ" in lyr or "ГЕРМЕТИК" in lyr,
            "bbox_filter": lambda b: 350.0 <= b[0] <= 365.0 and 395.0 <= b[1] <= 412.0,
        },
        # 3. Interior glazing bead seal
        {
            "id": "PART_03_SEAL_GLASS_INT",
            "name": "Внутренний уплотнитель штапика",
            "layer_filter": lambda lyr: "КОМПЛЕКТУЮЩИЕ" in lyr or "ГЕРМЕТИК" in lyr,
            "bbox_filter": lambda b: 410.0 <= b[0] <= 430.0 and 395.0 <= b[1] <= 415.0,
        },
        # 4. Glazing bridge & setting blocks
        {
            "id": "PART_04_GLAZING_BRIDGE_SHIM",
            "name": "Опорная подкладка стеклопакета и фальцевый вкладыш",
            "layer_filter": lambda lyr: "КОМПЛЕКТУЮЩИЕ" in lyr,
            "bbox_filter": lambda b: 365.0 <= b[0] <= 410.0 and 385.0 <= b[1] <= 405.0,
        },
        # 5. Glazing bead (штапик)
        {
            "id": "PART_05_GLAZING_BEAD",
            "name": "Штапик алюминиевый прижимной",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 400.0 <= b[0] <= 435.0 and 350.0 <= b[1] <= 395.0,
        },
        # 6. Sash: outer aluminium shell
        {
            "id": "PART_06_SASH_OUTER_ALU",
            "name": "Наружная чаша створки (алюминий)",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 350.0 <= b[0] <= 372.0 and 335.0 <= b[1] <= 365.0,
        },
        # 7. Sash: inner aluminium shell
        {
            "id": "PART_07_SASH_INNER_ALU",
            "name": "Внутренняя чаша створки (алюминий)",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 405.0 <= b[0] <= 435.0 and 335.0 <= b[1] <= 365.0,
        },
        # 8. Sash thermal break assembly
        {
            "id": "PART_08_SASH_THERMAL_BREAK",
            "name": "Полиамидные термомосты створки",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr or "ТЕРМОМОСТ" in lyr,
            "bbox_filter": lambda b: 368.0 <= b[0] <= 408.0 and 342.0 <= b[1] <= 360.0,
        },
        # 9. Central weather / acoustic seal
        {
            "id": "PART_09_SEAL_CENTRAL",
            "name": "Средний лепестковый уплотнитель притвора",
            "layer_filter": lambda lyr: "КОМПЛЕКТУЮЩИЕ" in lyr or "ТЕРМОМОСТ" in lyr,
            "bbox_filter": lambda b: 368.0 <= b[0] <= 385.0 and 330.0 <= b[1] <= 345.0,
        },
        # 10. Frame: outer aluminium shell
        {
            "id": "PART_10_FRAME_OUTER_ALU",
            "name": "Наружная чаша рамы (алюминий)",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 350.0 <= b[0] <= 375.0 and 305.0 <= b[1] <= 335.0,
        },
        # 11. Frame: inner aluminium shell
        {
            "id": "PART_11_FRAME_INNER_ALU",
            "name": "Внутренняя чаша рамы (алюминий)",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 405.0 <= b[0] <= 440.0 and 305.0 <= b[1] <= 335.0,
        },
        # 12. Frame thermal break assembly
        {
            "id": "PART_12_FRAME_THERMAL_BREAK",
            "name": "Полиамидные термомосты рамы",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr or "ТЕРМОМОСТ" in lyr,
            "bbox_filter": lambda b: 368.0 <= b[0] <= 408.0 and 365.0 <= b[1] <= 385.0,
        },
        # 13. Subframe base profile
        {
            "id": "PART_13_SUBFRAME_PROFILE",
            "name": "Подставочный базовый профиль под рамой",
            "layer_filter": lambda lyr: "ПРОФИЛИ" in lyr,
            "bbox_filter": lambda b: 365.0 <= b[0] <= 410.0 and 305.0 <= b[1] <= 330.0,
        },
        # 14. Exterior sill / flashing
        {
            "id": "PART_14_EXTERNAL_SILL_ALU",
            "name": "Наружный металлический отлив / капельник",
            "layer_filter": lambda lyr: "ОТЛИВ" in lyr,
            "bbox_filter": lambda b: True,
        },
        # 15. Wall insulation wave
        {
            "id": "PART_15_MINERAL_WOOL_WAVE",
            "name": "Минераловатный утеплитель примыкания (волна)",
            "layer_filter": lambda lyr: "УТЕПЛИТЕЛЬ_ВОЛНА" in lyr,
            "bbox_filter": lambda b: True,
        },
        # 16. Polyurethane foam insulation
        {
            "id": "PART_16_FOAM_INSULATION",
            "name": "Монтажная пена теплоизоляционного шва",
            "layer_filter": lambda lyr: "ШТРИХОВКА_УТЕПЛИТЕЛЬ" in lyr or "ШТРИХОВКА_ОБЩАЯ" in lyr,
            "bbox_filter": lambda b: True,
        },
        # 17. Masonry / wall reveal substrate
        {
            "id": "PART_17_WALL_SUBSTRATE",
            "name": "Стеновое основание (четверть проёма)",
            "layer_filter": lambda lyr: "ШТРИХОВКА_СТЕНЫ" in lyr,
            "bbox_filter": lambda b: True,
        },
    ]

    # Target physical component taxonomy (Task 024 Component Map)
    cdef_by_id = {c["id"]: c for c in component_defs}

    # Assign entities to components
    component_entities = defaultdict(list)
    assigned_handles = set()

    # Pass 1: Assign structural and accessory entities matching component definitions
    for ent in all_entities:
        lyr = ent.dxf.layer
        lyr_up = lyr.upper()
        # Never group DIMENSION entities or witness lines into parts
        if "РАЗМЕР" in lyr_up or "DIMENSION" in ent.dxftype().upper() or "DIMENSION" in lyr_up:
            continue
        # Never group general annotations / callouts / articles into parts
        if "ВЫНОСКИ" in lyr_up or "НАДПИСИ" in lyr_up or "АРТИКУЛ" in lyr_up or "ARTICLE" in lyr_up or "АННОТАЦИИ" in lyr_up or "ОБОЗНАЧЕНИЯ" in lyr_up:
            continue

        b = get_entity_bbox(ent)
        for cdef in component_defs:
            if cdef["layer_filter"](lyr) and cdef["bbox_filter"](b):
                component_entities[cdef["id"]].append(ent)
                assigned_handles.add(ent.dxf.handle)
                break

    # Pass 1b: Catalog mode fallback for extruded products
    if not component_entities:
        catalog_layer_map = {
            "01_АЛЮМИНИЙ_НАРУЖНЫЙ": ("PART_ALU_SASH_OUTER", "Наружная чаша профиля створки (алюминий)"),
            "01_АЛЮМИНИЙ_ВНУТРЕННИЙ": ("PART_ALU_SASH_INNER", "Внутренняя чаша профиля створки (алюминий)"),
            "03_ТЕРМОМОСТ": ("PART_THERMAL_BREAKS", "Полиамидные термомосты"),
            "04_УПЛОТНИТЕЛИ": ("PART_SEALS_EPDM", "Уплотнители резиновые / EPDM"),
            "05_СТЕКЛОПАКЕТ": ("PART_GLASS_UNIT", "Стеклопакет и дистанционные рамки"),
        }
        for ent in all_entities:
            lyr = ent.dxf.layer
            lyr_up = lyr.upper()
            if "РАЗМЕР" in lyr_up or "DIMENSION" in ent.dxftype().upper() or "DIMENSION" in lyr_up:
                continue
            if "ВЫНОСКИ" in lyr_up or "НАДПИСИ" in lyr_up or "АРТИКУЛ" in lyr_up or "ARTICLE" in lyr_up or "АННОТАЦИИ" in lyr_up or "ОБОЗНАЧЕНИЯ" in lyr_up:
                continue
            if lyr in catalog_layer_map:
                p_id, p_name = catalog_layer_map[lyr]
                component_entities[p_id].append(ent)
                if p_id not in cdef_by_id:
                    cdef_by_id[p_id] = {"name": p_name}

    # Pass 2: Create AutoCAD groups (ACAD_GROUP) for each populated component
    created_groups = []

    for comp_id, entities in component_entities.items():
        if not entities:
            continue
        cdef = cdef_by_id.get(comp_id, {"name": comp_id})
        part_name = comp_id
        part_desc = cdef["name"]

        # Check if group name already exists
        if part_name in group_table:
            grp = group_table.get(part_name)
        else:
            grp = group_table.new(name=part_name, description=part_desc)

        # Extend group with entities
        grp.extend(entities)
        created_groups.append({
            "id": comp_id,
            "name": part_desc,
            "entitiesCount": len(entities),
        })

    logger.info("Successfully assembled %d physical components into AutoCAD groups", len(created_groups))
    return {
        "componentsCount": len(created_groups),
        "groups": created_groups,
    }
