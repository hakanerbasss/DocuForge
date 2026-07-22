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
    MANUAL_VIDEO_EXTENSIONS = (".mp4",)
    MANUAL_MEDIA_EXTENSIONS = MANUAL_IMAGE_EXTENSIONS + MANUAL_VIDEO_EXTENSIONS
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
        image_prompt_items_by_scene = self._load_image_prompt_items_by_scene(
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
                    prompt_items_by_scene=image_prompt_items_by_scene,
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
                        prompt_items_by_scene=image_prompt_items_by_scene,
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
        """Return the hand-uploaded image or video for a scene, if one exists.

        The upload endpoint saves to `<scene_dir>/manual.<ext>`; we accept
        any of the common image/video extensions and require a non-empty
        file.
        """

        for extension in self.MANUAL_MEDIA_EXTENSIONS:
            candidate = scene_dir / f"manual{extension}"

            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate

        return None

    def current_scene_asset(self, scene_dir: Path) -> Path | None:
        """Whichever file RenderService.render() would actually use for
        this scene right now: newest-modified video, else newest-modified
        image -- mirrors that method's own picker exactly so a review UI
        always shows what the next render will really use.

        Newest-mtime (not alphabetical) is the tie-breaker: a scene
        directory should only ever hold one current file since every
        replace path clears the old one first, but if a stale file ever
        ends up sitting alongside a fresh replacement for any reason,
        alphabetical order has no relationship to which one is actually
        current (e.g. "image.jpg" always sorts before "manual.jpg"
        regardless of which was placed there most recently) -- mtime
        does.
        """

        videos = self._newest_first(
            scene_dir.glob("*.mp4") if scene_dir.exists() else []
        )

        if videos:
            return videos[0]

        images = self._newest_first(
            file_path
            for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp")
            for file_path in (scene_dir.glob(pattern) if scene_dir.exists() else [])
        )

        return images[0] if images else None

    def _newest_first(self, paths: Any) -> list[Path]:
        return sorted(
            paths,
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def clear_scene_media(self, scene_dir: Path) -> None:
        """Remove every acquired media file for one scene before replacing
        it -- otherwise a stale leftover file (e.g. the old auto-picked
        video) could still win RenderService's glob-based picker over the
        intentional replacement.
        """

        for pattern in ("*.mp4", "*.jpg", "*.jpeg", "*.png", "*.webp"):
            for file_path in scene_dir.glob(pattern):
                file_path.unlink()

    def regenerate_scene(
        self,
        project_path: str,
        scene_number: int,
    ) -> tuple[MediaAsset, Path]:
        """Re-acquire ONE scene's media through the normal provider flow,
        clearing whatever is there now first.

        Used by the per-scene "Yeniden Üret" fix flow so a single
        mismatched scene (e.g. a stock search returning an irrelevant
        clip) can be retried without rebuilding every other scene's
        media. When the current pick came from a stock search, the
        previous asset_id is excluded from the retry so a repeat click
        doesn't just download the identical top result again.
        """

        project_dir = Path(project_path)
        storyboard = self._load_storyboard(
            project_dir / "storyboard.json"
        )
        scene = self._find_scene(storyboard, scene_number)

        if scene is None:
            raise ValueError(
                f"Scene {scene_number} not found in storyboard."
            )

        project_data = self._load_project_data(project_dir)
        media_mode = str(project_data.get("media_mode", "mixed")).lower()
        image_provider_key = str(
            project_data.get("image_provider", "pexels")
        )
        video_provider_key = str(
            project_data.get("video_provider", "pexels")
        )

        register_default_providers()

        scene_dir = project_dir / "media" / f"scene_{scene_number:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        previous_asset_id = self._read_manifest_asset_id(
            project_dir, scene_number
        )
        search_query = self._build_query(scene)
        image_prompts_by_scene = self._load_image_prompts_by_scene(
            project_dir
        )
        image_prompt_items_by_scene = self._load_image_prompt_items_by_scene(
            project_dir
        )
        video_prompts_by_scene = self._load_video_prompts_by_scene(
            project_dir
        )

        video_provider = self._create_provider(
            "video", video_provider_key, tolerant=True
        ) if media_mode != "image" else None

        image_provider = self._create_provider(
            "image", image_provider_key, tolerant=True
        ) if media_mode != "video" else None

        self.clear_scene_media(scene_dir)

        result = None

        if media_mode == "image":
            result = self._acquire_image(
                image_provider, scene_number, scene_dir, search_query,
                image_prompts_by_scene, avoid_asset_id=previous_asset_id,
                prompt_items_by_scene=image_prompt_items_by_scene,
            )
        elif media_mode == "video":
            result = self._acquire_video(
                video_provider, scene_number, scene_dir, search_query,
                video_prompts_by_scene, avoid_asset_id=previous_asset_id,
            )
        else:
            result = self._acquire_video(
                video_provider, scene_number, scene_dir, search_query,
                video_prompts_by_scene, avoid_asset_id=previous_asset_id,
            )
            if result is None:
                result = self._acquire_image(
                    image_provider, scene_number, scene_dir, search_query,
                    image_prompts_by_scene, avoid_asset_id=previous_asset_id,
                    prompt_items_by_scene=image_prompt_items_by_scene,
                )

        if result is None:
            raise RuntimeError(
                "Bu sahne için yeni bir medya bulunamadı/üretilemedi."
            )

        asset, local_path = result
        self._update_manifest_scene(
            project_dir, scene_number, asset, local_path, search_query
        )

        return asset, local_path

    def save_manual_scene_media(
        self,
        project_path: str,
        scene_number: int,
        data: bytes,
        extension: str,
    ) -> tuple[MediaAsset, Path]:
        """Save a hand-supplied image/video as one scene's canonical
        asset, replacing whatever is currently there -- the "kendi
        görsel/video yükle" action in the per-scene fix flow.
        """

        project_dir = Path(project_path)
        scene_dir = project_dir / "media" / f"scene_{scene_number:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        self.clear_scene_media(scene_dir)

        destination = scene_dir / f"manual{extension}"
        destination.write_bytes(data)

        asset, local_path = self._manual_result(destination)
        self._update_manifest_scene(
            project_dir, scene_number, asset, local_path, search_query=""
        )

        return asset, local_path

    def search_scene_alternatives(
        self,
        project_path: str,
        scene_number: int,
        media_type: str,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """List alternate stock candidates for one scene so the user can
        browse and pick a different result than the one that's currently
        used, instead of the provider's top search hit.

        Only meaningful for search-based stock providers (Pexels/Pixabay/
        Unsplash) -- AI generation providers don't have a "browse many"
        concept the same way, since each call is its own fresh generation
        (that's what "Otomatik Başka Dene" is for instead).
        """

        if media_type not in ("image", "video"):
            raise ValueError("media_type must be 'image' or 'video'.")

        project_dir = Path(project_path)
        storyboard = self._load_storyboard(
            project_dir / "storyboard.json"
        )
        scene = self._find_scene(storyboard, scene_number)

        if scene is None:
            raise ValueError(
                f"Scene {scene_number} not found in storyboard."
            )

        project_data = self._load_project_data(project_dir)
        provider_key = str(
            project_data.get(
                "video_provider" if media_type == "video" else "image_provider",
                "pexels",
            )
        )

        register_default_providers()
        provider = ProviderRegistry.create(
            category=media_type, key=provider_key
        )

        if not hasattr(provider, "search"):
            raise ValueError(
                "Bu sağlayıcı stok arama desteklemiyor (AI üretim "
                "sağlayıcısı) -- bunun yerine \"Otomatik Başka Dene\" "
                "kullan."
            )

        search_query = self._build_query(scene)
        search_kwargs: dict[str, Any] = {
            "limit": limit,
            "orientation": "landscape",
        }

        if media_type == "video":
            search_kwargs["min_width"] = 1280

        assets = provider.search(search_query, **search_kwargs)

        return [
            {
                "asset_id": asset.asset_id,
                "provider": asset.provider,
                "media_type": asset.media_type,
                "download_url": asset.download_url,
                "preview_url": asset.preview_url or asset.download_url,
                "page_url": asset.page_url,
                "author": asset.author,
                "license": asset.license_name,
                "width": asset.width,
                "height": asset.height,
                "duration": asset.duration,
            }
            for asset in assets
        ]

    def select_scene_alternative(
        self,
        project_path: str,
        scene_number: int,
        asset_info: dict[str, Any],
    ) -> tuple[MediaAsset, Path]:
        """Download a candidate the user picked from search_scene_
        alternatives() and make it this scene's canonical asset."""

        project_dir = Path(project_path)
        scene_dir = project_dir / "media" / f"scene_{scene_number:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        media_type = str(asset_info.get("media_type") or "image")
        download_url = str(asset_info.get("download_url") or "")

        if not download_url:
            raise ValueError("Seçilen medyanın indirme adresi eksik.")

        self.clear_scene_media(scene_dir)
        destination = scene_dir / (
            "scene.mp4" if media_type == "video" else "image.jpg"
        )

        MediaDownloader.download(download_url, destination)

        def positive_or_none(value: Any) -> Any:
            return value if isinstance(value, (int, float)) and value > 0 else None

        asset = MediaAsset(
            asset_id=str(asset_info.get("asset_id") or destination.stem),
            provider=str(asset_info.get("provider") or "unknown"),
            media_type="video" if media_type == "video" else "image",
            download_url=download_url,
            page_url=asset_info.get("page_url"),
            preview_url=asset_info.get("preview_url"),
            author=asset_info.get("author"),
            license_name=asset_info.get("license"),
            width=positive_or_none(asset_info.get("width")),
            height=positive_or_none(asset_info.get("height")),
            duration=positive_or_none(asset_info.get("duration")),
        )

        self._update_manifest_scene(
            project_dir, scene_number, asset, destination, search_query=""
        )

        return asset, destination

    def _find_scene(
        self,
        storyboard: dict[str, Any],
        scene_number: int,
    ) -> dict[str, Any] | None:
        for index, scene in enumerate(storyboard.get("scenes", []), start=1):
            number = (
                scene.get("scene", index)
                if isinstance(scene, dict)
                else index
            )

            if number == scene_number:
                return scene

        return None

    def _load_project_data(self, project_dir: Path) -> dict[str, Any]:
        path = project_dir / "project.json"

        if not path.exists():
            return {}

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _read_manifest_asset_id(
        self,
        project_dir: Path,
        scene_number: int,
    ) -> str | None:
        manifest_path = project_dir / "media" / "manifest.json"

        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        for item in data.get("scenes", []) or []:
            if isinstance(item, dict) and item.get("scene") == scene_number:
                asset_id = item.get("asset_id")
                return str(asset_id) if asset_id else None

        return None

    def _update_manifest_scene(
        self,
        project_dir: Path,
        scene_number: int,
        asset: MediaAsset,
        local_path: Path,
        search_query: str,
    ) -> None:
        """Keep media/manifest.json's per-scene entry in sync after a
        post-hoc fix (upload/regenerate/select) -- manifest.json is the
        informational record the scene-media review UI reads; the render
        step itself always reads scene_dir's files directly, so this
        can't desync what actually gets rendered.
        """

        manifest_path = project_dir / "media" / "manifest.json"
        data: dict[str, Any] = {}

        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}

        scenes = data.get("scenes")

        if not isinstance(scenes, list):
            scenes = []

        new_item = {
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

        replaced = False

        for index, item in enumerate(scenes):
            if isinstance(item, dict) and item.get("scene") == scene_number:
                scenes[index] = new_item
                replaced = True
                break

        if not replaced:
            scenes.append(new_item)

        data["scenes"] = scenes
        data["project"] = str(project_dir)
        data["scene_count"] = len(scenes)
        data["completed_count"] = sum(
            1 for item in scenes if item.get("status") == "completed"
        )
        data["failed_count"] = sum(
            1 for item in scenes if item.get("status") == "failed"
        )

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
        """Wrap a hand-uploaded image or video as a completed media result."""

        media_type = (
            "video"
            if uploaded.suffix.lower() in self.MANUAL_VIDEO_EXTENSIONS
            else "image"
        )

        asset = MediaAsset(
            asset_id=uploaded.stem,
            provider="manual",
            media_type=media_type,
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

    def _pick_asset(
        self,
        assets: list[MediaAsset],
        avoid_asset_id: str | None,
    ) -> MediaAsset:
        """Pick a search result, preferring one that isn't the asset a
        retry is trying to move away from -- falls back to the top
        result if every candidate matches (e.g. only one result exists).
        """

        if avoid_asset_id:
            for candidate in assets:
                if str(candidate.asset_id) != str(avoid_asset_id):
                    return candidate

        return assets[0]

    def _acquire_video(
        self,
        provider: Any,
        scene_number: int,
        scene_dir: Path,
        search_query: str,
        video_prompts_by_scene: dict[int, str],
        avoid_asset_id: str | None = None,
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

        asset = self._pick_asset(assets, avoid_asset_id)
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
        avoid_asset_id: str | None = None,
        prompt_items_by_scene: dict[int, dict[str, Any]] | None = None,
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
                prompt_items_by_scene,
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

        asset = self._pick_asset(assets, avoid_asset_id)
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
        prompt_items_by_scene: dict[int, dict[str, Any]] | None = None,
    ) -> tuple[MediaAsset, Path] | None:
        prompt_item = (
            (prompt_items_by_scene or {}).get(scene_number)
        )

        if prompt_item is not None:
            # Full story-aware prompt (visual_summary/generation_goal/
            # recommended_source-appropriate style/authenticity notes),
            # not just the bare visual description -- see
            # compose_full_image_prompt()'s docstring for why a
            # context-free prompt can't make story-consistent choices.
            prompt = self.compose_full_image_prompt(prompt_item)
        else:
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

    def _load_image_prompt_items_by_scene(
        self,
        project_dir: Path,
    ) -> dict[int, dict[str, Any]]:
        """Like _load_image_prompts_by_scene, but keyed to each scene's
        FULL guidance dict (visual_summary/generation_goal/
        recommended_source/authenticity_note/sensitive/...), not just
        the bare prompt string -- lets callers compose a story-aware
        prompt via compose_full_image_prompt() instead of sending an AI
        generator a context-free visual description it has no way to
        make story-consistent choices from.
        """

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

        result: dict[int, dict[str, Any]] = {}

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
                result[scene] = item

        return result

    # Style guidance appended when composing the full prompt, keyed by
    # recommended_source -- ONLY affects the AI-generation path
    # (_generate_image), never stock search, since these are
    # instructions for a generative model, not search keywords.
    SOURCE_STYLE_DIRECTIVES: dict[str, str] = {
        "generated": (
            "Bu görsel temsili/sembolik bir canlandırmadır -- belirli, "
            "gerçek bir olayı ya da kişiyi birebir belgeliyormuş gibi "
            "gösterme; atmosferi ve fikri yansıtan, açıkça yorumlanmış "
            "bir sahne oluştur."
        ),
        "infographic": (
            "Bu sahne için fotogerçekçi bir görüntü yerine temiz bir "
            "bilgi grafiği/diyagram/şablon tarzı kullan -- ikonlar, "
            "etiketler, basit şekiller ve düzenli bir kompozisyonla "
            "bilgiyi görselleştir; gerçek bir fotoğraf gibi görünmeye "
            "çalışma."
        ),
        "archive": (
            "Gerçek arşiv görüntüsü bulunamadığı için bu görsel onun "
            "yerine geçecek -- fotogerçekçi taklit ÜRETME (gerçek bir "
            "belge/fotoğraf gibi görünmemeli); bunun yerine temsili/"
            "sembolik bir canlandırma ya da bilgi grafiği tarzı bir "
            "alternatif oluştur."
        ),
    }

    def compose_full_image_prompt(self, item: dict[str, Any]) -> str:
        """Fold a scene's full narrative context into ONE prompt.

        The bare "prompt" field alone only describes what should be in
        frame -- it carries none of the "why" (generation_goal), the
        surrounding story beat (visual_summary), or how source-
        appropriate a real photograph would even be (recommended_source/
        authenticity_note/sensitive). Sent as-is to an AI image
        generator (or pasted alone into another chat), none of that
        context survives, so the result can't make story-consistent
        choices -- e.g. attempting photorealism for a scene explicitly
        marked as needing a representative/symbolic or infographic
        treatment instead. This composes everything into one prompt so
        whichever model reads it (ours automatically, or another AI a
        user pastes it into) gets the whole picture in one shot.

        Used for both the actual AI generation call (_generate_image)
        and the "Promptu Kopyala" button in the web UI -- same
        composition either way, since the need (context, not a bare
        description) is identical in both cases.

        Deliberately does NOT ask the model to "leave clean space at
        the bottom for a caption": _image_to_clip() runs every still
        image through a Ken Burns zoompan (slow zoom-in over the
        scene's duration), so whatever the model left empty in the
        static image doesn't stay put -- it drifts/gets cropped as the
        zoom progresses, making a reserved "safe zone" unreliable for a
        moving clip.

        DOES explicitly ask the model to bake a small purpose caption
        at the top and "Fotoğraf Temsilidir." at the bottom directly
        into the generated image -- a deliberate choice by the user,
        who reviews/regenerates by hand (via ChatGPT's own chat, not
        DocuForge's paid API) rather than relying on this automatically.
        Baked-in text is subject to the exact same zoompan drift/crop
        risk noted above for scene images specifically (thumbnails
        aren't run through _image_to_clip, so this concern doesn't
        apply there) -- the manual review step is the safety net for
        that, not a guarantee this function can make on its own.
        """

        prompt = str(item.get("prompt") or "").strip()
        parts = [prompt] if prompt else []

        goal = str(item.get("generation_goal") or "").strip()
        if goal:
            parts.append(f"Bu görselle şu anlatılmalı: {goal}.")

        summary = str(item.get("visual_summary") or "").strip()
        if summary:
            parts.append(f"Sahnenin bağlamı: {summary}.")

        source = str(
            item.get("recommended_source") or "stock"
        ).strip().lower()
        directive = self.SOURCE_STYLE_DIRECTIVES.get(source)
        if directive:
            parts.append(directive)

        if bool(item.get("sensitive")):
            reason = str(item.get("sensitive_reason") or "").strip()
            parts.append(
                "Dikkat: bu sahne telif/gerçeklik açısından hassas"
                + (f" ({reason})" if reason else "")
                + " -- gerçek bir kişi/olayı birebir taklit etme."
            )

        parts.append(
            "Bu görsel 16:9 en-boy oranında bir YouTube belgesel "
            "videosu sahnesi için üretiliyor. Fotoğrafın üst kısmına "
            "bu görselin hangi amaçla kullanıldığını belirten küçük "
            "bir başlık, alt kısmına ise \"Fotoğraf Temsilidir.\" "
            "yazısını ekle."
        )

        return " ".join(parts)

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
