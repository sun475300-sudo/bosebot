"""API Gateway with versioning, pagination, and sorting support."""

import math
from datetime import datetime


class APIGateway:
    """Manages API version lifecycle including registration and deprecation."""

    def __init__(self):
        self._versions = {}

    def register_version(self, version, status="active"):
        """Register an API version with a given status."""
        self._versions[version] = {
            "version": version,
            "status": status,
            "registered_at": datetime.utcnow().isoformat(),
            "sunset_date": None,
        }

    def get_active_versions(self):
        """Return list of all versions with their status."""
        return [
            {"version": v, "status": info["status"]}
            for v, info in self._versions.items()
        ]

    def deprecate_version(self, version, sunset_date):
        """Mark a version as deprecated with a sunset date."""
        if version not in self._versions:
            raise ValueError(f"Version '{version}' is not registered.")
        self._versions[version]["status"] = "deprecated"
        self._versions[version]["sunset_date"] = sunset_date

    def is_deprecated(self, version):
        """Check if a version is deprecated."""
        if version not in self._versions:
            return False
        return self._versions[version]["status"] == "deprecated"

    def add_deprecation_headers(self, response, version):
        """Add Sunset and Deprecation headers to a response if version is deprecated."""
        if version in self._versions and self._versions[version]["status"] == "deprecated":
            info = self._versions[version]
            if info["sunset_date"]:
                response.headers["Sunset"] = info["sunset_date"]
            response.headers["Deprecation"] = "true"
        return response


class PaginationHelper:
    """Provides pagination for lists of items."""

    @staticmethod
    def paginate(items, page=1, per_page=20):
        """Return a paginated result dict with metadata.

        Args:
            items: The full list of items.
            page: 1-based page number.
            per_page: Number of items per page.

        Returns:
            dict with keys: items, page, per_page, total, pages
        """
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 1

        total = len(items)
        pages = max(1, math.ceil(total / per_page))

        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = items[start:end]

        return {
            "items": paginated_items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        }


class SortHelper:
    """Provides sorting for lists of dicts."""

    @staticmethod
    def sort_items(items, sort_by, order="asc"):
        """Sort a list of dicts by a given key.

        Args:
            items: List of dicts to sort.
            sort_by: The dict key to sort by.
            order: 'asc' for ascending, 'desc' for descending.

        Returns:
            A new sorted list.
        """
        reverse = order.lower() == "desc"
        return sorted(items, key=lambda x: x.get(sort_by, ""), reverse=reverse)
