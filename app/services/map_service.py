from pathlib import Path

import requests


class MapService:
    """Geocode a place name and render a static map image.

    Uses only free, no-API-key services: OpenStreetMap's Nominatim for
    geocoding and public OSM tile servers (via the `staticmap` package)
    for rendering -- no Google Maps/Mapbox key required.
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "DocuForge/1.0 (+https://github.com/hakanerbasss/DocuForge)"
    REQUEST_TIMEOUT_SECONDS = 10
    DEFAULT_ZOOM = 6
    MARKER_COLOR = "#e63946"
    MARKER_WIDTH = 18

    def geocode(self, place_name: str) -> tuple[float, float] | None:
        query = place_name.strip()

        if not query:
            return None

        try:
            response = requests.get(
                self.NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json()
        except Exception:
            return None

        if not isinstance(results, list) or not results:
            return None

        try:
            latitude = float(results[0]["lat"])
            longitude = float(results[0]["lon"])
        except (KeyError, TypeError, ValueError):
            return None

        return latitude, longitude

    def render_map(
        self,
        latitude: float,
        longitude: float,
        output_path: Path,
        width: int = 1280,
        height: int = 720,
        zoom: int = DEFAULT_ZOOM,
    ) -> Path:
        from staticmap import CircleMarker, StaticMap

        map_renderer = StaticMap(width, height)
        map_renderer.add_marker(
            CircleMarker(
                (longitude, latitude),
                self.MARKER_COLOR,
                self.MARKER_WIDTH,
            )
        )
        image = map_renderer.render(zoom=zoom)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = image.convert("RGB")
        image.save(output_path)

        return output_path
