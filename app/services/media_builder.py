import json
from pathlib import Path
from typing import Any

from app.pipeline.exceptions import PipelineAwaitingUpload
from app.providers.defaults import register_default_providers
from app.providers.registry import ProviderRegistry
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.models import MediaAsset


class MediaBuilder:
    """Download or generate suitable media for every storyboard scene."""

    MANUAL_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
    MANUAL_READY_MARKER = "manual_ready.json"

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

        # Read project settings
        project_json = project_dir / "project.json"
        project_data: dict[str, Any] = {}
        if project_json.exists():
            import json as _json
            try:
                project_data = _json.loads(
                    project_json.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        media_mode = str(project_data.get("media_mode", "mixed")).lower()
        image_provider_key = str(project_data.get("image_provider", "pexels"))
        video_provider_key = str(project_data.get("video_provider", "pexels"))

        # Optional manual-upload layer: when enabled, the user may hand-supply
        # any scene's image (e.g. generated in ChatGPT from the per-scene
        # prompt). It is NOT mandatory -- scenes left without an upload fall
        # back to the normal provider flow below. On the first media run we
        # pause once (marker absent) to give the user the chance to upload;
        # "Devam Et" writes the marker and resumes.
        manual_enabled = bool(project_data.get("manual_upload_enabled"))
        manual_marker = media_dir / self.MANUAL_READY_MARKER

        if manual_enabled and not manual_marker.exists():
            missing = self._scenes_without_upload(media_dir, storyboard)
            raise PipelineAwaitingUpload(missing)

        # When manual upload is enabled the providers are only a fallback for
        # scenes the user left empty, so a missing API key must not hard-fail
        # the whole build -- an empty scene simply gets no provider media
        # (the render step then drops in a placeholder). Without manual
        # upload, a provider that can't be created is still a real error.
        video_provider = self._create_provider(
            "video",
            video_provider_key,
            tolerant=manual_enabled,
        ) if media_mode != "image" else None

        image_provider = self._create_provider(
            "image",
            image_provider_key,
            tolerant=manual_enabled,
        ) if media_mode != "video" else None

        image_prompts_by_scene = self._load_image_prompts_by_scene(
            project_dir
        )
        video_prompts_by_scene = self._load_video_prompts_by_scene(
            project_dir
        )

        manifest_items: list[dict[str, Any]] = []

        for index, scene in enumerate(
            storyboard["scenes"],
            start=1,
        ):
            scene_number = scene.get("scene", index)
            scene_dir = media_dir / f"scene_{scene_number:03d}"
            scene_dir.mkdir(parents=True, exist_ok=True)

            search_query = self._build_query(scene)

            print(
                f"[{index}/{len(storyboard['scenes'])}] "
                f"Scene {scene_number}: {search_query} [{media_mode}]"
            )

            result = None

            manual_upload = (
                self.find_manual_upload(scene_dir)
                if manual_enabled
                else None
            )

            if manual_upload is not None:
                # Hand-supplied image wins over any provider/video for this
                # scene (works in every media_mode); empty scenes fall
                # through to the normal acquisition below.
                print(f"  🖼 Elle yüklenen görsel kullanılıyor: {manual_upload.name}")
                result = self._manual_result(manual_upload)
            elif media_mode == "image":
                # Only images
                result = self._acquire_image(
                    provider=image_provider,
                    scene_number=scene_number,
                    scene_dir=scene_dir,
                    search_query=search_query,
                    image_prompts_by_scene=image_prompts_by_scene,
                )
            elif media_mode == "video":
                # Only videos, no image fallback
                result = self._acquire_video(
                    provider=video_provider,
                    scene_number=scene_number,
                    scene_dir=scene_dir,
                    search_query=search_query,
                    video_prompts_by_scene=video_prompts_by_scene,
                )
            else:
                # mixed: try video first, fall back to image
                result = self._acquire_video(
                    provider=video_provider,
                    scene_number=scene_number,
                    scene_dir=scene_dir,
                    search_query=search_query,
                    video_prompts_by_scene=video_prompts_by_scene,
                )
                if result is None:
                    result = self._acquire_image(
                        provider=image_provider,
                        scene_number=scene_number,
                        scene_dir=scene_dir,
                        search_query=search_query,
                        image_prompts_by_scene=image_prompts_by_scene,
                    )

            if result is None:
                manifest_item = {
                    "scene": scene_number,
                    "status": "failed",
                    "query": search_query,
                    "error": "No suitable media found or generated.",
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
                "query": search_query,
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

    def find_manual_upload(self, scene_dir: Path) -> Path | None:
        """Return the hand-uploaded image for a scene, if one exists.

        The upload endpoint saves to `<scene_dir>/manual.<ext>`; we accept
        any of the common image extensions and require a non-empty file.
        """

        for extension in self.MANUAL_IMAGE_EXTENSIONS:
            candidate = scene_dir / f"manual{extension}"

            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate

        return None

    def _create_provider(
        self,
        category: str,
        key: str,
        tolerant: bool,
    ) -> Any:
        try:
            return ProviderRegistry.create(category=category, key=key)
        except Exception as error:
            if tolerant:
                print(
                    f"  ⚠ {category}/{key} sağlayıcısı hazırlanamadı "
                    f"({error}); elle yüklenmeyen sahneler boş kalabilir."
                )
                return None
            raise

    def _scenes_without_upload(
        self,
        media_dir: Path,
        storyboard: dict[str, Any],
    ) -> list[int]:
        """List scene numbers that still lack a hand-uploaded image.

        Purely informational (uploads are optional): it tells the pause UI
        which scenes are still empty. Also ensures each scene dir exists so
        an upload can land there.
        """

        missing: list[int] = []

        for index, scene in enumerate(storyboard["scenes"], start=1):
            scene_number = (
                scene.get("scene", index)
                if isinstance(scene, dict)
                else index
            )
            scene_dir = media_dir / f"scene_{scene_number:03d}"
            scene_dir.mkdir(parents=True, exist_ok=True)

            if self.find_manual_upload(scene_dir) is None:
                missing.append(scene_number)

        return missing

    def _manual_result(
        self,
        uploaded: Path,
    ) -> tuple[MediaAsset, Path]:
        """Wrap a hand-uploaded image as a completed media result."""

        asset = MediaAsset(
            asset_id=uploaded.stem,
            provider="manual",
            media_type="image",
            download_url=str(uploaded),
            metadata={"manual_upload": True},
        )

        return asset, uploaded

    def _is_generation_provider(self, provider: Any) -> bool:
        """Distinguish AI generation providers from search-based stock providers.

        Stock providers (Pexels/Pixabay/Unsplash) expose .search() in
        addition to the ImageProvider/VideoProvider interface; generation
        providers (DALL-E/Imagen/Veo/fal) only implement get_images()/
        get_videos(), treating the query as a generation prompt.
        """

        return not hasattr(provider, "search")

    def _acquire_video(
        self,
        provider: Any,
        scene_number: int,
        scene_dir: Path,
        search_query: str,
        video_prompts_by_scene: dict[int, str],
    ) -> tuple[MediaAsset, Path] | None:
        if provider is None:
            return None

        if self._is_generation_provider(provider):
            return self._generate_video(
                provider,
                scene_number,
                scene_dir,
                search_query,
                video_prompts_by_scene,
            )

        try:
            assets = provider.search(
                search_query,
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

    def _generate_video(
        self,
        provider: Any,
        scene_number: int,
        scene_dir: Path,
        search_query: str,
        video_prompts_by_scene: dict[int, str],
    ) -> tuple[MediaAsset, Path] | None:
        prompt = video_prompts_by_scene.get(scene_number, search_query)

        try:
            paths = provider.get_videos(
                prompt,
                scene_dir,
                limit=1,
                orientation="landscape",
            )
        except Exception as error:
            print(
                f"  ⚠ Video generation failed "
                f"({provider.provider_key}): {error}"
            )
            return None

        if not paths:
            print("  ⚠ No video generated.")
            return None

        destination = paths[0]

        asset = MediaAsset(
            asset_id=destination.stem,
            provider=provider.provider_key,
            media_type="video",
            download_url=str(destination),
            query=prompt,
            metadata={"generated": True, "prompt": prompt},
        )

        print(f"  ✅ Video generated: {destination}")

        return asset, destination

    def _acquire_image(
        self,
        provider: Any,
        scene_number: int,
        scene_dir: Path,
        search_query: str,
        image_prompts_by_scene: dict[int, str],
    ) -> tuple[MediaAsset, Path] | None:
        if provider is None:
            return None

        if self._is_generation_provider(provider):
            return self._generate_image(
                provider,
                scene_number,
                scene_dir,
                search_query,
                image_prompts_by_scene,
            )

        try:
            assets = provider.search(
                search_query,
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

    def _generate_image(
        self,
        provider: Any,
        scene_number: int,
        scene_dir: Path,
        search_query: str,
        image_prompts_by_scene: dict[int, str],
    ) -> tuple[MediaAsset, Path] | None:
        prompt = image_prompts_by_scene.get(scene_number, search_query)

        try:
            paths = provider.get_images(
                prompt,
                scene_dir,
                limit=1,
                orientation="landscape",
            )
        except Exception as error:
            print(
                f"  ❌ Image generation failed "
                f"({provider.provider_key}): {error}"
            )
            return None

        if not paths:
            print("  ❌ No image generated.")
            return None

        destination = paths[0]

        asset = MediaAsset(
            asset_id=destination.stem,
            provider=provider.provider_key,
            media_type="image",
            download_url=str(destination),
            query=prompt,
            metadata={"generated": True, "prompt": prompt},
        )

        print(f"  ✅ Image generated: {destination}")

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

    def _load_image_prompts_by_scene(
        self,
        project_dir: Path,
    ) -> dict[int, str]:
        """Load ImagePromptAgent's richer per-scene prompts, if present."""

        path = project_dir / "image_prompts.json"

        if not path.exists():
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        images = data.get("images")

        if not isinstance(images, list):
            return {}

        result: dict[int, str] = {}

        for item in images:
            if not isinstance(item, dict):
                continue

            scene = item.get("scene")
            prompt = item.get("prompt")

            if (
                isinstance(scene, int)
                and isinstance(prompt, str)
                and prompt.strip()
            ):
                result[scene] = prompt.strip()

        return result

    def _load_video_prompts_by_scene(
        self,
        project_dir: Path,
    ) -> dict[int, str]:
        """Load VideoPromptAgent's richer per-scene prompts, if present.

        Combines "prompt" with "camera_motion" since both are meaningful
        generation guidance that a stock search query never carried.
        """

        path = project_dir / "video_prompts.json"

        if not path.exists():
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        videos = data.get("videos")

        if not isinstance(videos, list):
            return {}

        result: dict[int, str] = {}

        for item in videos:
            if not isinstance(item, dict):
                continue

            scene = item.get("scene")
            prompt = item.get("prompt")
            camera_motion = item.get("camera_motion")

            if not (
                isinstance(scene, int)
                and isinstance(prompt, str)
                and prompt.strip()
            ):
                continue

            combined = prompt.strip()

            if isinstance(camera_motion, str) and camera_motion.strip():
                combined = (
                    f"{combined}. Camera motion: "
                    f"{camera_motion.strip()}."
                )

            result[scene] = combined

        return result

    def _build_query(self, scene: dict[str, Any]) -> str:
        visual = scene.get("visual")
        title = scene.get("title")

        if isinstance(visual, str) and visual.strip():
            query = visual.strip()
        elif isinstance(title, str) and title.strip():
            query = title.strip()
        else:
            query = "documentary cinematic scene"

        # Stock search APIs are less effective with long AI-style prompts.
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
