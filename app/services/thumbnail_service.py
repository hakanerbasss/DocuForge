import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageStat,
)

from app.core.config import settings


class ThumbnailService:
    """Generate high-CTR YouTube thumbnails from project media.

    Always produces 4 variants (thumbnail_1..4.png), each a genuinely
    different visual composition -- not the same layout with the text
    moved around. Background art comes from the DALL-E image provider
    when OPENAI_API_KEY is configured; otherwise (or if generation
    fails) it falls back to the strongest real scene frame, composited
    through the same 4 templates so the free path still looks designed.
    On-image text is a short SEO-generated hook, never the full video
    title, always drawn locally with Pillow (stroke + shadow) so
    Turkish diacritics never get mangled by an image model.
    """

    WIDTH = 1280
    HEIGHT = 720
    VERTICAL_WIDTH = 1080
    VERTICAL_HEIGHT = 1920

    MAX_FRAME_CANDIDATES = 8

    FONT_BOLD_CANDIDATES = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    )

    # 1..N in this order -- matches the brief's A/B/C/D/E template spec.
    TEMPLATE_ORDER: tuple[str, ...] = (
        "split_contrast",
        "mystery_focus",
        "documentary_cinematic",
        "breaking_discovery",
        "headline_highlight",
    )

    DEFAULT_TEMPLATE_BY_CONTENT_TYPE: dict[str, str] = {
        "news": "breaking_discovery",
        "shorts": "breaking_discovery",
        "documentary": "documentary_cinematic",
        "informational": "split_contrast",
    }

    THUMBNAIL_SOURCES = {"auto", "ai", "pexels", "scene"}
    VARIANT_NAMES = tuple(
        f"thumbnail_{i}.png" for i in range(1, len(TEMPLATE_ORDER) + 1)
    )

    def generate(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        project_data = self._load_json(project_dir / "project.json")
        seo_data = self._load_json(project_dir / "seo.json")

        brief = self._build_brief(project_data, seo_data)
        best_frame = self._select_best_frame(project_dir)

        content_type = brief["content_type"]
        default_key = self.DEFAULT_TEMPLATE_BY_CONTENT_TYPE.get(
            content_type, "documentary_cinematic"
        )

        requested_source = str(
            project_data.get("thumbnail_source", "auto")
        ).strip().lower()
        source = self._resolve_source(requested_source)

        # "ai" costs a real API call per template -- generate only the one
        # variant that would become canonical anyway. Free sources
        # (pexels stock search / real scene frame) still get all 4.
        if source == "ai":
            keys_to_generate = [default_key]
        else:
            keys_to_generate = list(self.TEMPLATE_ORDER)

        self._clear_variant_files(project_dir)

        ai_tmp_dir = project_dir / "thumbnail_ai_tmp"
        raw_backgrounds: dict[str, Image.Image] = {}

        try:
            for key in keys_to_generate:
                raw_backgrounds[key] = self._obtain_background(
                    source, key, brief, best_frame, ai_tmp_dir
                )

            for key in keys_to_generate:
                index = self.TEMPLATE_ORDER.index(key) + 1
                fitted = self._cover_fit(
                    raw_backgrounds[key], self.WIDTH, self.HEIGHT
                )
                composer = getattr(self, f"_compose_{key}")
                image = composer(fitted, brief, self.WIDTH, self.HEIGHT)
                image = self._apply_channel_logo(
                    image, self.WIDTH, self.HEIGHT
                )
                image.convert("RGB").save(
                    project_dir / f"thumbnail_{index}.png",
                    format="PNG",
                )

            canonical_key = keys_to_generate[0]
            canonical_index = self.TEMPLATE_ORDER.index(canonical_key) + 1

            canonical = project_dir / "thumbnail.jpg"
            with Image.open(
                project_dir / f"thumbnail_{canonical_index}.png"
            ) as selected:
                selected.convert("RGB").save(
                    canonical, format="JPEG", quality=92
                )

            resolution = str(
                project_data.get("resolution", "")
            ).strip().lower()

            if resolution == "vertical" or content_type == "shorts":
                fitted_vertical = self._cover_fit(
                    raw_backgrounds[canonical_key],
                    self.VERTICAL_WIDTH,
                    self.VERTICAL_HEIGHT,
                )
                composer = getattr(self, f"_compose_{canonical_key}")
                vertical_image = composer(
                    fitted_vertical,
                    brief,
                    self.VERTICAL_WIDTH,
                    self.VERTICAL_HEIGHT,
                )
                vertical_image = self._apply_channel_logo(
                    vertical_image, self.VERTICAL_WIDTH, self.VERTICAL_HEIGHT
                )
                vertical_image.convert("RGB").save(
                    project_dir / "thumbnail_vertical.jpg",
                    format="JPEG",
                    quality=92,
                )

            self._record_selected_thumbnail(
                project_dir, f"thumbnail_{canonical_index}.png"
            )
        finally:
            shutil.rmtree(ai_tmp_dir, ignore_errors=True)
            for image in raw_backgrounds.values():
                image.close()

        return canonical

    def _resolve_source(self, requested: str) -> str:
        if requested in ("ai", "pexels", "scene"):
            return requested

        # "auto": prefer whichever source is actually configured, in a
        # cost-conscious order -- paid AI only if that's genuinely the
        # only thing set up, otherwise stay free.
        if settings.pexels_api_key:
            return "pexels"

        if settings.openai_api_key:
            return "ai"

        return "scene"

    def _clear_variant_files(self, project_dir: Path) -> None:
        """Remove leftover variants from a previous generate() call so a
        source-mode switch (e.g. pexels's 4 variants -> ai's 1) never
        leaves stale, mismatched files in the gallery.
        """

        for name in self.VARIANT_NAMES:
            path = project_dir / name
            if path.exists():
                path.unlink()

    # ------------------------------------------------------------------
    # Creative brief (SEO fields -> thumbnail text/prompt inputs)
    # ------------------------------------------------------------------

    def _build_brief(
        self,
        project_data: dict[str, Any],
        seo_data: dict[str, Any],
    ) -> dict[str, str]:
        title = str(project_data.get("title", "")).strip() or "DocuForge"

        titles = seo_data.get("titles")
        primary_title = title
        if isinstance(titles, list):
            for candidate in titles:
                if isinstance(candidate, str) and candidate.strip():
                    primary_title = candidate.strip()
                    break

        def seo_str(key: str) -> str:
            value = seo_data.get(key)
            return value.strip() if isinstance(value, str) and value.strip() else ""

        hook_override = str(
            project_data.get("thumbnail_hook_override", "")
        ).strip()

        hook = hook_override or seo_str("thumbnail_hook") or self._shorten_words(
            primary_title, max_words=5
        )

        return {
            "main_subject": seo_str("main_subject") or title,
            "hook": hook,
            "text_overlay": seo_str("text_overlay") or hook,
            "emotional_trigger": seo_str("emotional_trigger") or "merak",
            "visual_contrast": seo_str("visual_contrast"),
            "avoid_elements": seo_str("avoid_elements")
            or "text, watermark, logo, subtitles, collage",
            "content_type": str(
                project_data.get("content_type", "")
            ).strip().lower() or "documentary",
        }

    def _shorten_words(self, text: str, max_words: int) -> str:
        return " ".join(text.split()[:max_words])

    def _turkish_upper(self, text: str) -> str:
        """`str.upper()` turns 'i' into 'I', losing the Turkish dotted
        capital 'İ'. Map the two Turkish i's before the generic upper().
        """

        return text.replace("i", "İ").replace("ı", "I").upper()

    # ------------------------------------------------------------------
    # Background sourcing: paid AI / free stock search / real scene frame
    # ------------------------------------------------------------------

    def _obtain_background(
        self,
        source: str,
        template_key: str,
        brief: dict[str, str],
        best_frame: Path,
        ai_tmp_dir: Path,
    ) -> Image.Image:
        if source == "ai":
            try:
                from app.providers.defaults import register_default_providers
                from app.providers.registry import ProviderRegistry

                register_default_providers()
                provider = ProviderRegistry.create("image", "dalle")
                prompt = self._build_ai_prompt(template_key, brief)

                paths = provider.get_images(
                    prompt,
                    ai_tmp_dir,
                    limit=1,
                    orientation="landscape",
                    quality="medium",
                )
                return Image.open(paths[0]).convert("RGB")
            except Exception as error:
                print(
                    f"[ThumbnailService] AI arka plan üretilemedi "
                    f"({template_key}): {error} -- gerçek sahne "
                    "karesine düşülüyor."
                )
        elif source == "pexels":
            try:
                from app.providers.defaults import register_default_providers
                from app.providers.registry import ProviderRegistry

                register_default_providers()
                provider = ProviderRegistry.create("image", "pexels")
                query = self._build_pexels_query(template_key, brief)

                paths = provider.get_images(
                    query,
                    ai_tmp_dir,
                    limit=1,
                    orientation="landscape",
                )
                return Image.open(paths[0]).convert("RGB")
            except Exception as error:
                print(
                    f"[ThumbnailService] Pexels stok görseli bulunamadı "
                    f"({template_key}): {error} -- gerçek sahne "
                    "karesine düşülüyor."
                )

        return Image.open(best_frame).convert("RGB")

    def _build_pexels_query(
        self,
        template_key: str,
        brief: dict[str, str],
    ) -> str:
        """Pexels is keyword search, not a generative prompt -- a short
        phrase works far better than the descriptive AI prompt.
        """

        mood_by_template = {
            "split_contrast": "contrast",
            "mystery_focus": "dark moody",
            "documentary_cinematic": "cinematic",
            "breaking_discovery": "dramatic",
        }
        mood = mood_by_template.get(template_key, "")
        subject = brief["main_subject"]

        return f"{subject} {mood}".strip()

    def _build_ai_prompt(
        self,
        template_key: str,
        brief: dict[str, str],
    ) -> str:
        content_type = brief["content_type"]
        main_subject = brief["main_subject"]

        if template_key == "split_contrast":
            contrast = brief["visual_contrast"] or "a dramatic before/after difference"
            body = (
                f"Split-screen photorealistic composition divided by a bold "
                f"vertical line. Main subject: {main_subject}. The left half "
                f"and right half show a stark visual contrast: {contrast}. "
                "Cool desaturated tones on the left half, warm saturated "
                "tones on the right half. Leave clean negative space in the "
                "upper third for a short title."
            )
        elif template_key == "mystery_focus":
            body = (
                f"Single dominant subject ({main_subject}) centered, filling "
                "about 45% of the frame, in sharp focus, with the "
                "background darker and softly out of focus. Dramatic rim "
                f"lighting around the subject evoking "
                f"{brief['emotional_trigger'] or 'curiosity'}. Moody, "
                "mysterious atmosphere. Leave clean negative space around "
                "the subject for a short title."
            )
        elif template_key == "documentary_cinematic":
            body = (
                f"Wide cinematic establishing shot of {main_subject} in its "
                "natural environment. Epic documentary photography, "
                "dramatic golden-hour lighting, strong foreground-"
                "background separation. Leave clean negative space in the "
                "upper third for a short title. No bottom banner or frame."
            )
        else:
            body = (
                f"Dynamic diagonal composition with {main_subject} as the "
                "dramatic focal point. High energy, urgent breaking-news "
                "photography style, saturated dramatic contrast, slight "
                "dutch angle. Leave clean negative space for a bold "
                "headline."
            )

        return (
            f"Create a high-CTR YouTube {content_type} thumbnail "
            f"background. {body} No text, no letters, no numbers, no "
            f"watermark, no logo, no subtitles, no collage. Avoid: "
            f"{brief['avoid_elements']}. 16:9 landscape composition, "
            "photorealistic, high detail."
        )

    # ------------------------------------------------------------------
    # Best real-frame selection (fallback source + fallback-only path)
    # ------------------------------------------------------------------

    def _select_best_frame(self, project_dir: Path) -> Path:
        media_dir = project_dir / "media"

        scene_dirs = sorted(
            path
            for path in media_dir.iterdir()
            if path.is_dir() and path.name.startswith("scene_")
        ) if media_dir.exists() else []

        candidates: list[Path] = []

        for scene_dir in scene_dirs:
            images = sorted(
                file_path
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp")
                for file_path in scene_dir.glob(pattern)
            )

            if images:
                candidates.append(images[0])
            else:
                videos = sorted(scene_dir.glob("*.mp4"))

                if videos:
                    frame_path = (
                        project_dir
                        / f"thumbnail_source_{scene_dir.name}.jpg"
                    )
                    self._extract_video_frame(videos[0], frame_path)

                    if frame_path.exists() and frame_path.stat().st_size > 0:
                        candidates.append(frame_path)

            if len(candidates) >= self.MAX_FRAME_CANDIDATES:
                break

        if not candidates:
            raise FileNotFoundError(
                "No scene image or video found to build a thumbnail from."
            )

        scored = [(self._score_frame(path), path) for path in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        return scored[0][1]

    def _score_frame(self, path: Path) -> float:
        """Cheap 'how strong is this frame' heuristic: sharper edges and
        higher contrast tend to mean a clearer, more prominent subject.
        No ML/CV dependency -- just Pillow edge detection + stddev.
        """

        try:
            with Image.open(path) as source:
                grayscale = source.convert("L")
                target_height = max(
                    1, int(320 * grayscale.height / grayscale.width)
                )
                sample = grayscale.resize((320, target_height))

                edges = sample.filter(ImageFilter.FIND_EDGES)
                edge_score = ImageStat.Stat(edges).mean[0]
                contrast_score = ImageStat.Stat(sample).stddev[0]

                return edge_score + contrast_score
        except Exception:
            return 0.0

    def _extract_video_frame(
        self,
        video_path: Path,
        output_path: Path,
    ) -> None:
        self._run([
            "ffmpeg",
            "-y",
            "-ss",
            "0.5",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ])

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def _cover_fit(
        self,
        img: Image.Image,
        width: int,
        height: int,
    ) -> Image.Image:
        src_w, src_h = img.size
        scale = max(width / src_w, height / src_h)
        new_w, new_h = int(src_w * scale) + 1, int(src_h * scale) + 1

        resized = img.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - width) // 2
        top = (new_h - height) // 2

        return resized.crop((left, top, left + width, top + height))

    def _center_crop_exact(
        self,
        img: Image.Image,
        width: int,
        height: int,
    ) -> Image.Image:
        """Crop the centered width x height box with no rescale -- unlike
        _cover_fit, which would rescale (and so zoom back into) an
        intentionally oversampled canvas.
        """

        src_w, src_h = img.size
        left = max(0, (src_w - width) // 2)
        top = max(0, (src_h - height) // 2)

        return img.crop((left, top, left + width, top + height))

    def _find_font_path(self) -> Path | None:
        for candidate in self.FONT_BOLD_CANDIDATES:
            if candidate.exists():
                return candidate

        return None

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        path = self._find_font_path()

        if path is not None:
            return ImageFont.truetype(str(path), size=max(8, size))

        return ImageFont.load_default()

    def _wrap_by_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> list[str]:
        """Word-wrap to fit max_width. Returns as many lines as needed --
        callers that care about a line cap should shrink the font via
        _fit_text_lines instead of truncating words off the end.
        """

        words = [word for word in text.split() if word]
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)

            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        return lines if lines else [text]

    def _fit_text_lines(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        max_lines: int,
        base_size: int,
        min_size: int | None = None,
    ) -> tuple[ImageFont.FreeTypeFont, list[str]]:
        """Word-wrap text to at most max_lines by shrinking the font
        size instead of dropping words -- a hook that doesn't fit at
        the ideal size should get smaller, never truncated mid-phrase.
        """

        min_size = min_size or max(14, int(base_size * 0.45))
        size = base_size

        font = self._font(size)
        lines = self._wrap_by_width(draw, text, font, max_width)

        while len(lines) > max_lines and size > min_size:
            size = max(min_size, int(size * 0.88))
            font = self._font(size)
            lines = self._wrap_by_width(draw, text, font, max_width)

        return font, lines[:max_lines]

    def _draw_text_block(
        self,
        canvas: Image.Image,
        lines: list[str],
        font: ImageFont.FreeTypeFont,
        fill: tuple[int, int, int],
        stroke_fill: tuple[int, int, int],
        stroke_width: int,
        anchor_xy: tuple[int, int],
        align: str = "center",
        line_spacing: float = 1.18,
        highlight_alpha: int = 0,
    ) -> int:
        """Draw a wrapped text block with a drop shadow + outline stroke,
        both scaled to font size so bigger hooks stay proportionally
        bold instead of looking thin. When highlight_alpha > 0, a
        translucent dark bar is composited behind the whole block first
        -- for templates whose background isn't already darkened
        (gradient/vignette), this is what keeps text legible over a
        busy or light real-scene photo.
        """

        draw = ImageDraw.Draw(canvas)
        x_anchor, y = anchor_xy
        font_size = getattr(font, "size", 40)
        shadow_offset = max(3, font_size // 16)

        placements: list[tuple[str, int, int, int]] = []
        cursor_y = y
        left_bound = x_anchor
        right_bound = x_anchor

        for line in lines:
            bbox = draw.textbbox(
                (0, 0), line, font=font, stroke_width=stroke_width
            )
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]

            x = x_anchor - line_w // 2 if align == "center" else x_anchor

            placements.append((line, x, cursor_y, line_h))
            left_bound = min(left_bound, x)
            right_bound = max(right_bound, x + line_w)
            cursor_y += int(line_h * line_spacing)

        if highlight_alpha > 0 and placements:
            pad_x = int(font_size * 0.35)
            pad_y = int(font_size * 0.25)
            box = (
                left_bound - pad_x,
                y - pad_y,
                right_bound + pad_x,
                cursor_y - int(placements[-1][3] * (line_spacing - 1)) + pad_y,
            )
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(overlay).rectangle(box, fill=(0, 0, 0, highlight_alpha))
            blended = Image.alpha_composite(
                canvas.convert("RGBA"), overlay
            ).convert("RGB")
            canvas.paste(blended, (0, 0))
            draw = ImageDraw.Draw(canvas)

        for line, x, line_y, _line_h in placements:
            draw.text(
                (x + shadow_offset, line_y + shadow_offset),
                line, font=font, fill=(0, 0, 0),
            )
            draw.text(
                (x, line_y),
                line,
                font=font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )

        return cursor_y

    def _apply_top_gradient(
        self,
        img: Image.Image,
        height_fraction: float = 0.45,
        max_alpha: int = 190,
    ) -> Image.Image:
        width, height = img.size
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        band_h = int(height * height_fraction)

        for y in range(band_h):
            alpha = int(max_alpha * (1 - y / band_h))
            odraw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

        return Image.alpha_composite(
            img.convert("RGBA"), overlay
        ).convert("RGB")

    # ------------------------------------------------------------------
    # Templates -- each produces a genuinely different composition
    # ------------------------------------------------------------------

    def _compose_split_contrast(
        self,
        bg: Image.Image,
        brief: dict[str, str],
        width: int,
        height: int,
    ) -> Image.Image:
        left = bg.crop((0, 0, width // 2, height))
        right = bg.crop((width // 2, 0, width, height))

        left = ImageEnhance.Color(left).enhance(0.35)
        left = ImageEnhance.Brightness(left).enhance(0.85)
        left = Image.blend(left, Image.new("RGB", left.size, (15, 30, 70)), 0.22)

        right = ImageEnhance.Color(right).enhance(1.4)
        right = ImageEnhance.Contrast(right).enhance(1.15)
        right = Image.blend(right, Image.new("RGB", right.size, (200, 90, 15)), 0.15)

        canvas = Image.new("RGB", (width, height))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (width // 2, 0))

        draw = ImageDraw.Draw(canvas)
        divider_w = max(4, width // 160)
        draw.rectangle(
            [
                width // 2 - divider_w // 2,
                0,
                width // 2 + divider_w // 2,
                height,
            ],
            fill=(255, 255, 255),
        )

        hook = self._turkish_upper(brief["hook"])
        font, lines = self._fit_text_lines(
            draw, hook, max_width=int(width * 0.85), max_lines=2,
            base_size=int(height * 0.11),
        )

        self._draw_text_block(
            canvas,
            lines,
            font,
            fill=(255, 220, 60),
            stroke_fill=(0, 0, 0),
            stroke_width=max(4, int(height * 0.013)),
            anchor_xy=(width // 2, int(height * 0.06)),
            align="center",
            highlight_alpha=90,
        )

        return canvas

    def _compose_mystery_focus(
        self,
        bg: Image.Image,
        brief: dict[str, str],
        width: int,
        height: int,
    ) -> Image.Image:
        blurred = bg.filter(ImageFilter.GaussianBlur(radius=max(6, width // 120)))
        darker = ImageEnhance.Brightness(blurred).enhance(0.55)
        darker = ImageEnhance.Color(darker).enhance(0.7)

        cx, cy = width // 2, int(height * 0.42)
        max_r = int(min(width, height) * 0.42)

        mask = Image.new("L", (width, height), 0)
        mdraw = ImageDraw.Draw(mask)
        for r in range(max_r, 0, -2):
            alpha = int(255 * (1 - r / max_r) ** 1.6)
            mdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, max_r // 4)))

        sharp_center = ImageEnhance.Contrast(bg).enhance(1.1)
        canvas = Image.composite(sharp_center, darker, mask)

        vignette = Image.new("L", (width, height), 0)
        vdraw = ImageDraw.Draw(vignette)
        vdraw.ellipse(
            [-width * 0.2, -height * 0.2, width * 1.2, height * 1.2],
            fill=255,
        )
        vignette = vignette.filter(
            ImageFilter.GaussianBlur(radius=max(1, width // 8))
        )
        black = Image.new("RGB", (width, height), (0, 0, 0))
        canvas = Image.composite(canvas, black, vignette)

        draw = ImageDraw.Draw(canvas)
        hook = self._turkish_upper(brief["hook"])
        font, lines = self._fit_text_lines(
            draw, hook, max_width=int(width * 0.6), max_lines=2,
            base_size=int(height * 0.095),
        )

        self._draw_text_block(
            canvas,
            lines,
            font,
            fill=(255, 255, 255),
            stroke_fill=(0, 0, 0),
            stroke_width=max(4, int(height * 0.012)),
            anchor_xy=(int(width * 0.08), int(height * 0.73)),
            align="left",
            highlight_alpha=130,
        )

        return canvas

    def _compose_documentary_cinematic(
        self,
        bg: Image.Image,
        brief: dict[str, str],
        width: int,
        height: int,
    ) -> Image.Image:
        canvas = ImageEnhance.Contrast(bg).enhance(1.08)
        canvas = ImageEnhance.Color(canvas).enhance(1.05)
        canvas = self._apply_top_gradient(
            canvas, height_fraction=0.46, max_alpha=205
        )

        draw = ImageDraw.Draw(canvas)
        hook = self._turkish_upper(brief["hook"])
        font, lines = self._fit_text_lines(
            draw, hook, max_width=int(width * 0.75), max_lines=2,
            base_size=int(height * 0.105),
        )

        self._draw_text_block(
            canvas,
            lines,
            font,
            fill=(255, 255, 255),
            stroke_fill=(0, 0, 0),
            stroke_width=max(4, int(height * 0.012)),
            anchor_xy=(int(width * 0.06), int(height * 0.07)),
            align="left",
        )

        return canvas

    def _compose_breaking_discovery(
        self,
        bg: Image.Image,
        brief: dict[str, str],
        width: int,
        height: int,
    ) -> Image.Image:
        # Oversample generously before rotating (expand=True), then take
        # a pure center CROP (no rescale) of the rotated canvas. Growing
        # the source keeps the black corners the rotation introduces
        # proportionally further from center, while the fixed-size crop
        # window stays put -- rescaling back down here (e.g. via
        # _cover_fit) would zoom back into those corners and defeat the
        # whole point of oversampling.
        oversized = self._cover_fit(bg, int(width * 1.6), int(height * 1.6))
        rotated = oversized.rotate(-4, resample=Image.BICUBIC, expand=True)
        canvas = self._center_crop_exact(rotated, width, height)

        canvas = ImageEnhance.Color(canvas).enhance(1.25)
        canvas = ImageEnhance.Contrast(canvas).enhance(1.2)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.polygon(
            [
                (0, height),
                (0, int(height * 0.35)),
                (int(width * 0.65), height),
            ],
            fill=(10, 5, 5, 150),
        )
        canvas = Image.alpha_composite(
            canvas.convert("RGBA"), overlay
        ).convert("RGB")

        draw = ImageDraw.Draw(canvas)

        tag_text = self._turkish_upper(brief["emotional_trigger"] or "şok")
        tag_font = self._font(int(height * 0.05))
        tag_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0] + int(width * 0.06)
        tag_h = int(height * 0.09)
        tag_x0 = width - tag_w - int(width * 0.03)
        tag_y0 = int(height * 0.05)

        draw.rectangle(
            [tag_x0, tag_y0, tag_x0 + tag_w, tag_y0 + tag_h],
            fill=(210, 20, 20),
        )
        draw.text(
            (tag_x0 + int(width * 0.03), tag_y0 + tag_h // 2),
            tag_text,
            font=tag_font,
            fill=(255, 255, 255),
            anchor="lm",
        )

        hook_words = self._turkish_upper(brief["hook"]).split()
        number_word = next(
            (word for word in hook_words if any(ch.isdigit() for ch in word)),
            None,
        )

        y_anchor = int(height * 0.62)

        if number_word:
            big_font = self._font(int(height * 0.24))
            draw.text(
                (int(width * 0.06), int(height * 0.31)),
                number_word,
                font=big_font,
                fill=(255, 210, 40),
                stroke_width=max(5, int(height * 0.014)),
                stroke_fill=(0, 0, 0),
            )
            remaining_words = [
                word for word in hook_words if word != number_word
            ]
            hook_text = " ".join(remaining_words)
        else:
            hook_text = " ".join(hook_words)

        if hook_text:
            font, lines = self._fit_text_lines(
                draw, hook_text, max_width=int(width * 0.75), max_lines=2,
                base_size=int(height * 0.13),
            )
            self._draw_text_block(
                canvas,
                lines,
                font,
                fill=(255, 255, 255),
                stroke_fill=(0, 0, 0),
                stroke_width=max(4, int(height * 0.012)),
                anchor_xy=(int(width * 0.06), y_anchor),
                align="left",
            )

        return canvas

    def _compose_headline_highlight(
        self,
        bg: Image.Image,
        brief: dict[str, str],
        width: int,
        height: int,
    ) -> Image.Image:
        """Plain full-bleed photo, bold white headline lines, and the
        LAST wrapped line punched out on a solid color bar -- a
        creator-thumbnail convention (bold statement capped by one
        high-contrast highlighted phrase) that reads clearly regardless
        of the background photo's own contrast.
        """

        canvas = ImageEnhance.Contrast(bg).enhance(1.05)
        draw = ImageDraw.Draw(canvas)

        hook = self._turkish_upper(brief["hook"])
        font, lines = self._fit_text_lines(
            draw, hook, max_width=int(width * 0.82), max_lines=3,
            base_size=int(height * 0.125),
        )

        if not lines:
            return canvas

        lead_lines, punch_line = lines[:-1], lines[-1]

        x = int(width * 0.055)
        y = int(height * 0.08)
        stroke_width = max(4, int(height * 0.013))
        shadow_offset = max(3, font.size // 16)
        line_spacing = 1.16

        for line in lead_lines:
            draw.text(
                (x + shadow_offset, y + shadow_offset),
                line, font=font, fill=(0, 0, 0),
            )
            draw.text(
                (x, y), line, font=font, fill=(255, 255, 255),
                stroke_width=stroke_width, stroke_fill=(0, 0, 0),
            )
            bbox = draw.textbbox(
                (0, 0), line, font=font, stroke_width=stroke_width
            )
            y += int((bbox[3] - bbox[1]) * line_spacing)

        bbox = draw.textbbox((0, 0), punch_line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        pad_x = int(font.size * 0.32)
        pad_y = int(font.size * 0.24)

        box = (
            x - pad_x,
            y - pad_y,
            x + line_w + pad_x,
            y + line_h + pad_y,
        )
        draw.rectangle(box, fill=(255, 205, 0))
        draw.text(
            (x, y), punch_line, font=font, fill=(20, 16, 0),
        )

        return canvas

    def _apply_channel_logo(
        self,
        canvas: Image.Image,
        width: int,
        height: int,
    ) -> Image.Image:
        """Paste the configured channel logo (Settings) onto the bottom-
        right corner of a composed thumbnail, if the feature is enabled.
        Bottom-right is the one corner every template leaves clear --
        the others are where each composer puts its own headline text
        or (breaking_discovery's) emotional-trigger tag. Uploaded as-is,
        so a transparent PNG blends in while a plain square just shows
        as a square -- no automatic circular masking. Any read/decode/
        paste failure falls back to the plain thumbnail rather than
        failing the whole render over a cosmetic extra.
        """

        try:
            if not settings.is_configured("channel_logo_enabled"):
                return canvas

            if not settings.is_configured("channel_logo"):
                return canvas

            logo_path = Path(settings.channel_logo)

            if not logo_path.exists() or logo_path.stat().st_size == 0:
                return canvas

            with Image.open(logo_path) as raw_logo:
                logo = raw_logo.convert("RGBA")

            target = int(min(width, height) * 0.16)
            scale = target / max(logo.width, logo.height)
            logo = logo.resize(
                (
                    max(1, int(logo.width * scale)),
                    max(1, int(logo.height * scale)),
                ),
                Image.LANCZOS,
            )

            margin = int(min(width, height) * 0.035)
            x = width - logo.width - margin
            y = height - logo.height - margin

            result = canvas.convert("RGBA")
            result.paste(logo, (x, y), logo)
            return result.convert("RGB")
        except Exception as error:
            print(
                f"  ⚠ Kanal logosu eklenemedi, logosuz devam ediliyor: "
                f"{error}"
            )
            return canvas

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _record_selected_thumbnail(
        self,
        project_dir: Path,
        variant_filename: str,
    ) -> None:
        """Note which variant is currently canonical (thumbnail.jpg) so
        the project page can highlight it. Best-effort: a missing or
        unreadable project.json just skips this, since it's a display
        hint, not a required field.
        """

        project_json_path = project_dir / "project.json"
        data = self._load_json(project_json_path)

        if not data:
            return

        data["thumbnail_selected"] = variant_filename

        try:
            project_json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def _run(self, command: list[str]) -> None:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "FFmpeg is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"FFmpeg failed:\n{error.stderr}"
            ) from error
