import json
from pathlib import Path
from typing import Any

from app.providers.defaults import register_default_providers
from app.providers.registry import ProviderRegistry
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.models import MediaAsset


class MediaBuilder:
    """Download suitable media for every storyboard scene."""

    def build(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        storyboard_path = project_dir / "storyboard.json"

        if not storyboard_path.exists():
            raise FileNotFoundError(
                f"storyboard.json not found: {storyboard_path}"
            )

        storyboard = self._load_storyboard(storyboard_path)
        media_dir = project_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        register_default_providers()

        video_provider = ProviderRegistry.create(
            category="video",
            key="pexels",
        )
        image_provider = ProviderRegistry.create(
            category="image",
            key="pexels",
        )

        manifest_items: list[dict[str, Any]] = []

        for index, scene in enumerate(
            storyboard["scenes"],
            start=1,
        ):
            scene_number = scene.get("scene", index)
            scene_dir = media_dir / f"scene_{scene_number:03d}"
            scene_dir.mkdir(parents=True, exist_ok=True)

            query = self._build_query(scene)

            print(
                f"[{index}/{len(storyboard['scenes'])}] "
                f"Scene {scene_number}: {query}"
            )

            result = self._acquire_video(
                provider=video_provider,
                query=query,
                scene_dir=scene_dir,
            )

            if result is None:
                result = self._acquire_image(
                    provider=image_provider,
                    query=query,
                    scene_dir=scene_dir,
                )

            if result is None:
                manifest_item = {
                    "scene": scene_number,
                    "status": "failed",
                    "query": query,
                    "error": "No suitable Pexels video or image found.",
                }

                self._write_scene_asset(
                    scene_dir,
                    manifest_item,
                )

                manifest_items.append(manifest_item)
                continue

            asset, local_path = result

            manifest_item = {
                "scene": scene_number,
                "status": "completed",
                "query": query,
                "media_type": asset.media_type,
                "provider": asset.provider,
                "asset_id": asset.asset_id,
                "local_path": str(local_path),
                "download_url": asset.download_url,
                "page_url": asset.page_url,
                "preview_url": asset.preview_url,
                "author": asset.author,
                "license": asset.license_name,
                "width": asset.width,
                "height": asset.height,
                "duration": asset.duration,
                "metadata": asset.metadata,
            }

            self._write_scene_asset(
                scene_dir,
                manifest_item,
            )

            manifest_items.append(manifest_item)

        manifest_path = media_dir / "manifest.json"

        manifest_path.write_text(
            json.dumps(
                {
                    "project": str(project_dir),
                    "scene_count": len(storyboard["scenes"]),
                    "completed_count": sum(
                        item["status"] == "completed"
                        for item in manifest_items
                    ),
                    "failed_count": sum(
                        item["status"] == "failed"
                        for item in manifest_items
                    ),
                    "scenes": manifest_items,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return manifest_path

    def _acquire_video(
        self,
        provider: Any,
        query: str,
        scene_dir: Path,
    ) -> tuple[MediaAsset, Path] | None:
        try:
            assets = provider.search(
                query,
                limit=5,
                orientation="landscape",
                min_width=1280,
            )
        except Exception as error:
            print(f"  ⚠ Video search failed: {error}")
            return None

        if not assets:
            print("  ⚠ No video found, trying image.")
            return None

        asset = assets[0]
        destination = scene_dir / "scene.mp4"

        try:
            MediaDownloader.download(
                asset.download_url,
                destination,
            )
        except Exception as error:
            print(f"  ⚠ Video download failed: {error}")
            return None

        print(f"  ✅ Video downloaded: {destination}")

        return asset, destination

    def _acquire_image(
        self,
        provider: Any,
        query: str,
        scene_dir: Path,
    ) -> tuple[MediaAsset, Path] | None:
        try:
            assets = provider.search(
                query,
                limit=5,
                orientation="landscape",
            )
        except Exception as error:
            print(f"  ⚠ Image search failed: {error}")
            return None

        if not assets:
            print("  ❌ No image found.")
            return None

        asset = assets[0]
        destination = scene_dir / "image.jpg"

        try:
            MediaDownloader.download(
                asset.download_url,
                destination,
            )
        except Exception as error:
            print(f"  ❌ Image download failed: {error}")
            return None

        print(f"  ✅ Image downloaded: {destination}")

        return asset, destination

    def _load_storyboard(
        self,
        storyboard_path: Path,
    ) -> dict[str, Any]:
        try:
            data = json.loads(
                storyboard_path.read_text(
                    encoding="utf-8",
                )
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"storyboard.json is invalid: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Storyboard root must be a JSON object."
            )

        scenes = data.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Storyboard must contain a non-empty scenes list."
            )

        return data

    def _build_query(self, scene: dict[str, Any]) -> str:
        visual = scene.get("visual")
        title = scene.get("title")

        if isinstance(visual, str) and visual.strip():
            query = visual.strip()
        elif isinstance(title, str) and title.strip():
            query = title.strip()
        else:
            query = "documentary cinematic scene"

        # Pexels aramasında çok uzun yapay zekâ promptları verimsiz olabilir.
        words = query.replace("\n", " ").split()

        return " ".join(words[:12])

    def _write_scene_asset(
        self,
        scene_dir: Path,
        data: dict[str, Any],
    ) -> None:
        asset_path = scene_dir / "asset.json"

        asset_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
