import math
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("analytics_parser")

@dataclass
class ParsedFact:
    """Единый контракт извлечённого факта для всех адаптеров (по требованию Архитектора)."""
    source_document_id: str
    source_content_version: str
    engine: str
    engine_version: str
    
    page_or_layout: str
    entity_handle_or_path_id: str
    block_instance_path: Optional[str]
    layer: Optional[str]
    
    quantity_type: str            # 'area', 'length', 'count', 'text'
    raw_value: float
    raw_units: str                # 'mm2', 'pts2', 'mm', 'pts'
    normalized_value: Optional[float]
    normalized_units: Optional[str] # 'm2', 'm'
    
    measurement_method: str
    calibration: Optional[Dict[str, Any]]
    warnings: List[str]
    review_status: str            # 'pending_calibration', 'ready', 'rejected'
    
    metadata: Dict[str, Any]

class BaseAdapter:
    def parse(self, file_path: str, document_id: str, content_version: str) -> List[ParsedFact]:
        raise NotImplementedError()

class PdfVectorAdapter(BaseAdapter):
    """
    Адаптер для извлечения векторной геометрии из PDF.
    PyMuPDF возвращает координаты в пунктах (pts). Для перевода в метры требуется калибровка.
    """
    def __init__(self, calibration_k: Optional[float] = None):
        # Коэффициент k = (реальные метры) / (PDF пункты).
        # Площадь будет умножаться на k^2.
        self.k = calibration_k

    def _polygon_area(self, points: List[Tuple[float, float]]) -> float:
        if len(points) < 3: return 0.0
        area = 0.0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += points[i][0] * points[j][1] - points[j][0] * points[i][1]
        return abs(area) / 2.0

    def parse(self, file_path: str, document_id: str, content_version: str) -> List[ParsedFact]:
        import fitz
        doc = fitz.open(file_path)
        facts = []
        
        for page_num, page in enumerate(doc):
            drawings = page.get_drawings()
            for draw_idx, draw in enumerate(drawings):
                points = []
                for item in draw["items"]:
                    if item[0] == "l": points.extend([item[1], item[2]])
                    elif item[0] == "re": 
                        r = item[1]
                        points.extend([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
                
                # Простейшее замыкание контура
                poly = []
                for p in points:
                    if not poly or poly[-1] != p: poly.append(p)
                
                if len(poly) > 2:
                    raw_area_pts2 = self._polygon_area(poly)
                    is_filled = draw.get("fill") is not None
                    
                    if raw_area_pts2 > 10.0: # Игнорируем пиксельный мусор
                        warnings = []
                        norm_val = None
                        status = "pending_calibration"
                        
                        if self.k is not None:
                            norm_val = raw_area_pts2 * (self.k ** 2)
                            status = "ready"
                        else:
                            warnings.append("No scale calibration provided. Area is in pts^2.")
                            
                        facts.append(ParsedFact(
                            source_document_id=document_id,
                            source_content_version=content_version,
                            engine="PdfVectorAdapter_PyMuPDF",
                            engine_version="1.0",
                            page_or_layout=f"Page {page_num+1}",
                            entity_handle_or_path_id=f"path_{draw_idx}",
                            block_instance_path=None,
                            layer=None, # PDF обычно не сохраняет CAD слои в drawings
                            quantity_type="area",
                            raw_value=raw_area_pts2,
                            raw_units="pts2",
                            normalized_value=norm_val,
                            normalized_units="m2" if self.k else None,
                            measurement_method="shoelace_polygon",
                            calibration={"k_factor": self.k} if self.k else None,
                            warnings=warnings,
                            review_status=status,
                            metadata={"fill": draw.get("fill"), "color": draw.get("color")}
                        ))
        doc.close()
        return facts

class AutoCadNativeAdapter(BaseAdapter):
    """
    Прямой адаптер к AutoCAD через COM (ActiveX).
    Извлекает HATCH, закрытые Polylines, Blocks и Text.
    Работает в отдельном процессе.
    """
    def parse(self, file_path: str, document_id: str, content_version: str) -> List[ParsedFact]:
        try:
            import win32com.client
            import pythoncom
        except ImportError:
            raise ImportError("win32com is missing. Run 'pip install pywin32'.")
            
        facts = []
        pythoncom.CoInitialize() # Важно для фонового потока
        try:
            try:
                acad = win32com.client.Dispatch("ZWCAD.Application")
            except Exception:
                acad = win32com.client.Dispatch("AutoCAD.Application")
                
            acad.Visible = False
            doc = acad.Documents.Open(str(Path(file_path).resolve()), True)
            
            try:
                msp = doc.ModelSpace
                for i in range(msp.Count):
                    entity = msp.Item(i)
                    ent_name = entity.EntityName
                    handle = entity.Handle
                    layer = entity.Layer
                    
                    if ent_name == "AcDbHatch":
                        raw_area_mm2 = entity.Area
                        norm_area_m2 = raw_area_mm2 / 1_000_000.0
                        facts.append(self._build_fact(
                            document_id, content_version, "ModelSpace", handle, layer,
                            "area", raw_area_mm2, "mm2", norm_area_m2, "m2",
                            "AutoCAD_Hatch_Area", {"pattern": entity.PatternName}
                        ))
                        
                    elif ent_name == "AcDbPolyline" and entity.Closed:
                        raw_area_mm2 = entity.Area
                        norm_area_m2 = raw_area_mm2 / 1_000_000.0
                        facts.append(self._build_fact(
                            document_id, content_version, "ModelSpace", handle, layer,
                            "area", raw_area_mm2, "mm2", norm_area_m2, "m2",
                            "AutoCAD_Polyline_Area", {}
                        ))
                        
                    elif ent_name == "AcDbBlockReference":
                        # Block attributes
                        attrs = {}
                        if entity.HasAttributes:
                            for attr in entity.GetAttributes():
                                attrs[attr.TagString] = attr.TextString
                        
                        facts.append(self._build_fact(
                            document_id, content_version, "ModelSpace", handle, layer,
                            "count", 1.0, "pcs", 1.0, "pcs",
                            "AutoCAD_BlockRef", {"block_name": entity.Name, "attributes": attrs}
                        ))
                        
                    elif ent_name in ("AcDbText", "AcDbMText"):
                        facts.append(self._build_fact(
                            document_id, content_version, "ModelSpace", handle, layer,
                            "text", 0.0, "none", None, None,
                            "AutoCAD_Text", {"text": entity.TextString}
                        ))
            finally:
                doc.Close(False)
        except Exception as e:
            logger.error(f"AutoCAD COM Error: {e}")
            raise
        finally:
            pythoncom.CoUninitialize()
            
        return facts

    def _build_fact(self, doc_id, rev, layout, handle, layer, q_type, raw_val, raw_unit, norm_val, norm_unit, method, meta):
        return ParsedFact(
            source_document_id=doc_id,
            source_content_version=rev,
            engine="AutoCadNativeAdapter_COM",
            engine_version="1.0",
            page_or_layout=layout,
            entity_handle_or_path_id=handle,
            block_instance_path=None,
            layer=layer,
            quantity_type=q_type,
            raw_value=raw_val,
            raw_units=raw_unit,
            normalized_value=norm_val,
            normalized_units=norm_unit,
            measurement_method=method,
            calibration=None, # CAD обычно в масштабе 1:1 в mm
            warnings=[],
            review_status="ready",
            metadata=meta
        )

class DxfAdapter(BaseAdapter):
    """
    Альтернативный адаптер через ezdxf.
    Реализация отложена до проведения сравнительных тестов прямого CAD-адаптера.
    """
    def parse(self, file_path: str, document_id: str, content_version: str) -> List[ParsedFact]:
        raise NotImplementedError("DXF parsing logic pending implementation.")
