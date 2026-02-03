"""UI Geometry-based reachability checks for Playwright outputs.

Parses ui_facts.json containing bounding boxes, occlusion data, and
click target information to verify UI elements are actually reachable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BoundingBox:
    """Bounding box with position and dimensions."""
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        """Calculate the area of the bounding box."""
        return self.width * self.height

    @property
    def center_x(self) -> float:
        """Calculate the x-coordinate of the box center."""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        """Calculate the y-coordinate of the box center."""
        return self.y + self.height / 2

    def intersects(self, other: BoundingBox) -> bool:
        """Check if this box intersects with another.

        Args:
            other: Another bounding box to check intersection with.

        Returns:
            True if the boxes intersect, False otherwise.
        """
        return not (
            self.x + self.width < other.x or
            other.x + other.width < self.x or
            self.y + self.height < other.y or
            other.y + other.height < self.y
        )

    def intersection_area(self, other: BoundingBox) -> float:
        """Calculate intersection area with another box."""
        if not self.intersects(other):
            return 0.0

        left = max(self.x, other.x)
        right = min(self.x + self.width, other.x + other.width)
        top = max(self.y, other.y)
        bottom = min(self.y + self.height, other.y + other.height)

        return max(0, right - left) * max(0, bottom - top)


@dataclass
class UIElement:
    """UI element with geometry and metadata."""
    id: str
    selector: str
    tag: str
    bbox: BoundingBox
    visible: bool = True
    clickable: bool = False
    occluded_by: list[str] = field(default_factory=list)
    z_index: int = 0
    viewport: str = "desktop"  # desktop, mobile, tablet

    def to_dict(self) -> dict[str, Any]:
        """Convert UI element to dictionary representation."""
        return {
            "id": self.id,
            "selector": self.selector,
            "tag": self.tag,
            "bbox": {
                "x": self.bbox.x,
                "y": self.bbox.y,
                "width": self.bbox.width,
                "height": self.bbox.height,
            },
            "visible": self.visible,
            "clickable": self.clickable,
            "occluded_by": self.occluded_by,
            "z_index": self.z_index,
            "viewport": self.viewport,
        }


@dataclass
class Viewport:
    """Viewport dimensions."""
    width: int
    height: int
    name: str


class UIGeometryParser:
    """Parser for UI geometry facts from Playwright."""

    def __init__(self, facts_path: Path) -> None:
        """Initialize with path to ui_facts.json."""
        self.facts_path = facts_path
        self.elements: list[UIElement] = []
        self.viewports: list[Viewport] = []
        self._parse()

    def _parse(self) -> None:
        """Parse the ui_facts.json file."""
        if not self.facts_path.exists():
            return

        with open(self.facts_path, encoding="utf-8") as f:
            data = json.load(f)

        # Parse viewports
        for vp_data in data.get("viewports", []):
            self.viewports.append(Viewport(
                width=vp_data.get("width", 0),
                height=vp_data.get("height", 0),
                name=vp_data.get("name", "unknown"),
            ))

        # Parse elements
        for elem_data in data.get("elements", []):
            bbox_data = elem_data.get("boundingBox", {})
            bbox = BoundingBox(
                x=bbox_data.get("x", 0),
                y=bbox_data.get("y", 0),
                width=bbox_data.get("width", 0),
                height=bbox_data.get("height", 0),
            )

            self.elements.append(UIElement(
                id=elem_data.get("id", ""),
                selector=elem_data.get("selector", ""),
                tag=elem_data.get("tag", ""),
                bbox=bbox,
                visible=elem_data.get("visible", True),
                clickable=elem_data.get("clickable", False),
                occluded_by=elem_data.get("occludedBy", []),
                z_index=elem_data.get("zIndex", 0),
                viewport=elem_data.get("viewport", "desktop"),
            ))

    def get_element(self, selector: str) -> UIElement | None:
        """Get element by selector."""
        for elem in self.elements:
            if elem.selector == selector or elem.id == selector:
                return elem
        return None

    def get_clickable_elements(self, viewport: str | None = None) -> list[UIElement]:
        """Get all clickable elements, optionally filtered by viewport."""
        elements = [e for e in self.elements if e.clickable and e.visible]
        if viewport:
            elements = [e for e in elements if e.viewport == viewport]
        return elements

    def get_occluded_elements(self) -> list[UIElement]:
        """Get elements that are occluded by others."""
        return [e for e in self.elements if e.occluded_by]


class UIReachabilityChecker:
    """Check UI element reachability based on geometry."""

    def __init__(self, parser: UIGeometryParser) -> None:
        self.parser = parser

    def check_cta_clickable(
        self,
        cta_selector: str,
        viewports: list[str] | None = None,
    ) -> dict[str, Any]:
        """Check if CTA is clickable across viewports.

        Returns:
            Result dict with pass/fail and details
        """
        if viewports is None:
            viewports = ["desktop", "mobile"]

        results = {}
        all_passed = True

        for viewport in viewports:
            elem = None
            for e in self.parser.elements:
                if e.selector == cta_selector and e.viewport == viewport:
                    elem = e
                    break

            if elem is None:
                results[viewport] = {
                    "passed": False,
                    "reason": f"CTA not found in {viewport}",
                }
                all_passed = False
                continue

            # Check if clickable and not occluded
            if not elem.clickable:
                results[viewport] = {
                    "passed": False,
                    "reason": "Element not clickable",
                    "element": elem.to_dict(),
                }
                all_passed = False
            elif elem.occluded_by:
                results[viewport] = {
                    "passed": False,
                    "reason": f"Element occluded by: {elem.occluded_by}",
                    "element": elem.to_dict(),
                }
                all_passed = False
            else:
                results[viewport] = {
                    "passed": True,
                    "element": elem.to_dict(),
                }

        return {
            "passed": all_passed,
            "selector": cta_selector,
            "viewports": results,
        }

    def check_sticky_overlap(
        self,
        sticky_selector: str,
        content_selectors: list[str],
    ) -> dict[str, Any]:
        """Check if sticky element overlaps primary content.

        Returns:
            Result dict with overlap information
        """
        sticky = self.parser.get_element(sticky_selector)
        if sticky is None:
            return {
                "passed": False,
                "reason": f"Sticky element not found: {sticky_selector}",
            }

        overlaps = []

        for content_selector in content_selectors:
            content = self.parser.get_element(content_selector)
            if content is None:
                continue

            # Check for intersection
            if sticky.bbox.intersects(content.bbox):
                overlap_area = sticky.bbox.intersection_area(content.bbox)
                overlap_pct = overlap_area / content.bbox.area if content.bbox.area > 0 else 0

                if overlap_pct > 0.1:  # More than 10% overlap
                    overlaps.append({
                        "element": content_selector,
                        "overlap_area": overlap_area,
                        "overlap_percent": overlap_pct,
                    })

        return {
            "passed": len(overlaps) == 0,
            "sticky_element": sticky.to_dict(),
            "overlaps": overlaps,
        }

    def check_viewport_coverage(
        self,
        required_elements: list[str],
        viewport: str,
    ) -> dict[str, Any]:
        """Check if all required elements are visible in viewport."""
        missing = []
        found = []

        for selector in required_elements:
            elem = None
            for e in self.parser.elements:
                if e.selector == selector and e.viewport == viewport:
                    elem = e
                    break

            if elem is None or not elem.visible:
                missing.append(selector)
            else:
                found.append(elem.to_dict())

        return {
            "passed": len(missing) == 0,
            "viewport": viewport,
            "missing": missing,
            "found": found,
        }

    def run_all_checks(self) -> list[dict[str, Any]]:
        """Run all standard UI reachability checks."""
        checks = []

        # Check common CTAs
        cta_selectors = [
            "button[type='submit']",
            ".cta-button",
            "[data-testid='primary-cta']",
        ]

        for cta in cta_selectors:
            result = self.check_cta_clickable(cta)
            if any(v.get("element") for v in result["viewports"].values()):
                checks.append({
                    "type": "cta_clickable",
                    "result": result,
                })

        # Check sticky overlaps
        sticky_selectors = [
            ".sticky-header",
            ".fixed-navbar",
        ]

        for sticky in sticky_selectors:
            if self.parser.get_element(sticky):
                result = self.check_sticky_overlap(
                    sticky,
                    [".main-content", "[data-testid='content']"],
                )
                checks.append({
                    "type": "sticky_overlap",
                    "result": result,
                })

        return checks
