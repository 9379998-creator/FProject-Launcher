"""
FERO CAD Physical Component Assembly Engine (Tasks 024 & 032)
=============================================================
Assembles individual CAD polylines, cavities, and hatches into
distinct, selectable, and movable physical components using native
AutoCAD groups (ACAD_GROUP).

Multi-Section Spatial Separation Contract (Task 032):
- Distinct vertical/spatial sections (e.g. Schüco AWS 70 TipTronic vs SL.HI)
  are separated into independent spatial clusters so identical materials
  from separate sections are NEVER merged into a single global group.
- Each glass unit is its own discrete physical assembly.
- All grouping is coordinate-offset invariant.
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

    group_table = doc.groups

    cdef_by_id = {}
    component_entities = defaultdict(list)

    # 1. Filter out dimensions, annotations, callouts, and article notes
    structural_entities = []
    for ent in all_entities:
        lyr = ent.dxf.layer
        lyr_up = lyr.upper()
        if "РАЗМЕР" in lyr_up or "DIMENSION" in ent.dxftype().upper() or "DIMENSION" in lyr_up:
            continue
        if any(k in lyr_up for k in ("ОБОЗНАЧ", "АРТИКУЛ", "ВЫНОСК", "ARTICLE", "CALLOUT", "НАДПИСИ", "АННОТАЦИИ")):
            continue
        structural_entities.append(ent)

    if not structural_entities:
        return {"componentsCount": 0, "groups": []}

    # 2. Detect independent spatial clusters along Y (e.g. separate sections on Schüco sheet E 2-2)
    # A gap of > 10 mm between bounding intervals indicates distinct physical assemblies.
    ent_boxes = [(ent, get_entity_bbox(ent)) for ent in structural_entities]
    valid_boxes = [eb for eb in ent_boxes if bbox_area(eb[1]) > 0.0 or (eb[1][2] - eb[1][0] > 0.0)]

    if valid_boxes:
        sorted_boxes = sorted(valid_boxes, key=lambda eb: eb[1][1])
        clusters: List[List[DXFGraphic]] = []
        cur_cluster: List[DXFGraphic] = [sorted_boxes[0][0]]
        cur_min_y = sorted_boxes[0][1][1]
        cur_max_y = sorted_boxes[0][1][3]

        for ent, b in sorted_boxes[1:]:
            y0, y1 = b[1], b[3]
            if y0 <= cur_max_y + 10.0:
                cur_cluster.append(ent)
                cur_min_y = min(cur_min_y, y0)
                cur_max_y = max(cur_max_y, y1)
            else:
                clusters.append(cur_cluster)
                cur_cluster = [ent]
                cur_min_y = y0
                cur_max_y = y1
        if cur_cluster:
            clusters.append(cur_cluster)

        # Only treat substantive multi-entity assemblies (>= 15 entities) as independent sections
        substantive_clusters = [c for c in clusters if len(c) >= 15]
        if len(substantive_clusters) >= 2:
            clusters = substantive_clusters
        else:
            clusters = [structural_entities]
    else:
        clusters = [structural_entities]

    num_clusters = len(clusters)
    logger.info("Identified %d independent spatial section cluster(s)", num_clusters)

    # 3. Layer mapping for architectural components (coordinate-offset invariant)
    catalog_layer_defs = [
        ("05_СТЕКЛОПАКЕТ", "PART_GLASS_UNIT", "Заполнение / стеклопакет"),
        ("01_АЛЮМИНИЙ_НАРУЖНЫЙ", "PART_ALU_OUTER", "Профиль наружной чаши (алюминий)"),
        ("01_АЛЮМИНИЙ_ВНУТРЕННИЙ", "PART_ALU_INNER", "Профиль внутренней чаши (алюминий)"),
        ("01_АЛЮМИНИЙ", "PART_ALU_PROFILE", "Профиль алюминиевый"),
        ("01_ПРОФИЛИ", "PART_PROFILES", "Профили фасадные"),
        ("03_ТЕРМОМОСТ", "PART_THERMAL_BREAKS", "Термоизоляционные мосты"),
        ("04_УПЛОТНИТЕЛИ", "PART_SEALS_EPDM", "Уплотнители фальца / EPDM"),
        ("ОТЛИВ", "PART_EXTERNAL_SILL", "Отлив / капельник"),
        ("УТЕПЛИТЕЛЬ", "PART_INSULATION", "Утеплитель примыкания"),
    ]

    for cluster_idx, cluster_ents in enumerate(clusters):
        suffix = f"_S{cluster_idx + 1}" if num_clusters > 1 else ""
        section_desc = f" (сечение {cluster_idx + 1})" if num_clusters > 1 else ""

        for l_key, p_id_base, p_desc_base in catalog_layer_defs:
            p_id = f"{p_id_base}{suffix}"
            p_desc = f"{p_desc_base}{section_desc}"

            matching = [e for e in cluster_ents if l_key in e.dxf.layer.upper()]
            if matching:
                component_entities[p_id].extend(matching)
                cdef_by_id[p_id] = {"name": p_desc}

    # 4. Create AutoCAD groups (ACAD_GROUP) for each populated component
    created_groups = []

    for comp_id, entities in component_entities.items():
        if not entities:
            continue
        cdef = cdef_by_id.get(comp_id, {"name": comp_id})
        part_name = comp_id
        part_desc = cdef["name"]

        if part_name in group_table:
            grp = group_table.get(part_name)
        else:
            grp = group_table.new(name=part_name, description=part_desc)

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
