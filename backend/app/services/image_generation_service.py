from __future__ import annotations

import asyncio
import base64
import binascii
import io
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.db_models import Attachment, GeneratedImage, Message, Thread
from app.services.chat_service import ChatService
from app.services.file_storage_service import FileStorageService
from app.services.message_service import MessageService
from app.services.thread_service import ThreadService


class ImageGenerationError(Exception):
    pass


class PromptValidationError(ImageGenerationError):
    pass


class ImageRateLimitError(ImageGenerationError):
    pass


@dataclass(frozen=True)
class GeneratedImagePayload:
    image_bytes: bytes
    mime_type: str


class ImageGenerationService:
    _image_intent_pattern = re.compile(
        r"\b(generate|create|draw|design|render|make)\b.{0,60}\b(image|picture|photo|logo|art|illustration)\b",
        re.IGNORECASE,
    )
    _blocked_prompt_pattern = re.compile(
        r"\b(child sexual|csam|bestiality|rape|exploit child|incest|gore killing|terror attack)\b",
        re.IGNORECASE,
    )
    _modification_pattern = re.compile(
        r"\b(change|modify|update|alter|make it|turn it|color it|make the|add|remove|replace)\b",
        re.IGNORECASE,
    )
    _color_names: tuple[str, ...] = (
        "red",
        "green",
        "blue",
        "yellow",
        "orange",
        "purple",
        "pink",
        "black",
        "white",
        "gray",
        "grey",
        "silver",
        "gold",
        "brown",
    )
    _target_hues: dict[str, int] = {
        "red": 0,
        "orange": 20,
        "yellow": 30,
        "green": 80,
        "blue": 145,
        "purple": 190,
        "pink": 235,
        "brown": 18,
        "gold": 25,
        "silver": 0,
        "gray": 0,
        "grey": 0,
        "black": 0,
        "white": 0,
    }
    _requests_by_user: dict[uuid.UUID, deque[float]] = defaultdict(deque)
    _rate_lock = asyncio.Lock()

    def __init__(self, db: AsyncSession, storage: FileStorageService | None = None) -> None:
        self._db = db
        self._storage = storage or FileStorageService()
        self._thread_service = ThreadService(db)
        self._message_service = MessageService(db)

    @classmethod
    def is_image_intent(cls, text: str) -> bool:
        return bool(cls._image_intent_pattern.search(text.strip()))

    async def generate_for_chat(
        self,
        user_id: uuid.UUID,
        prompt: str,
        thread_id: uuid.UUID | None,
        message: str | None,
    ) -> tuple[Thread, Message, Message, GeneratedImage]:
        normalized_prompt = self._validate_prompt(prompt)
        user_visible_prompt = normalized_prompt
        effective_prompt = normalized_prompt

        thread = await self._resolve_thread(user_id=user_id, thread_id=thread_id)

        # If this is an edit request, anchor it to the most recent image in the same thread.
        is_edit_request = self._is_modification_request(effective_prompt)
        last_image: GeneratedImage | None = None
        if is_edit_request:
            last_image = await self._get_last_generated_image_in_thread(thread.id)
            if last_image:
                effective_prompt = self._merge_prompts(last_image.prompt, effective_prompt)

        await self._enforce_rate_limit(user_id)

        cached_image = await self._find_generated_image_by_prompt(user_id=user_id, prompt=effective_prompt)
        if cached_image:
            attachment = Attachment(
                thread_id=thread.id,
                file_name=f"generated_image_cached.png",
                mime_type="image/png",
                file_path=cached_image.image_url,
            )
            self._db.add(attachment)

            user_text = self._build_user_message_text(message=message, prompt=user_visible_prompt)
            user_message = await self._message_service.save_message(
                thread_id=thread.id,
                user_id=user_id,
                role="user",
                content=user_text,
            )

            assistant_text = "Using previously generated image."
            assistant_message = await self._message_service.save_message(
                thread_id=thread.id,
                user_id=user_id,
                role="assistant",
                content=assistant_text,
            )
            attachment.message_id = assistant_message.id
            await self._db.commit()
            await self._db.refresh(assistant_message)
            return thread, user_message, assistant_message, cached_image

        used_reference_edit = False
        if is_edit_request and last_image is not None:
            local_edit = await self._try_local_color_edit(
                prompt=effective_prompt,
                base_image_path=last_image.image_url,
            )
            if local_edit is not None:
                payload = local_edit
                used_reference_edit = True
            else:
                payload = await self._edit_or_generate_image_payload(
                    prompt=effective_prompt,
                    base_image=last_image,
                )
                used_reference_edit = True
        else:
            payload = await self._generate_image_payload(effective_prompt)
        stored = await self._storage.save_generated_image(
            thread_id=thread.id,
            image_bytes=payload.image_bytes,
            mime_type=payload.mime_type,
        )

        user_text = self._build_user_message_text(message=message, prompt=user_visible_prompt)
        user_message = await self._message_service.save_message(
            thread_id=thread.id,
            user_id=user_id,
            role="user",
            content=user_text,
        )

        assistant_text = (
            "Edited previous image based on your instruction."
            if used_reference_edit
            else "Generated image based on your prompt."
        )
        assistant_message = await self._message_service.save_message(
            thread_id=thread.id,
            user_id=user_id,
            role="assistant",
            content=assistant_text,
        )

        attachment = Attachment(
            thread_id=thread.id,
            message_id=assistant_message.id,
            file_name=stored.file_name,
            mime_type=stored.mime_type,
            file_path=stored.file_path,
        )
        self._db.add(attachment)

        generated = GeneratedImage(
            user_id=user_id,
            thread_id=thread.id,
            prompt=effective_prompt,
            image_url=stored.file_path,
        )
        self._db.add(generated)

        should_update_name = thread.name.strip().lower() == "new chat"
        if should_update_name:
            try:
                name_source = message.strip() if message and message.strip() else user_visible_prompt
                name = await ChatService().generate_thread_name(name_source)
                await self._thread_service.update_thread(thread.id, user_id, name)
            except Exception:
                pass

        await self._db.commit()

        await self._db.refresh(assistant_message)
        await self._db.refresh(generated)
        return thread, user_message, assistant_message, generated

    async def _find_generated_image_by_prompt(
        self,
        user_id: uuid.UUID,
        prompt: str,
    ) -> GeneratedImage | None:
        stmt = (
            select(GeneratedImage)
            .where(GeneratedImage.user_id == user_id, GeneratedImage.prompt == prompt)
            .order_by(GeneratedImage.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_last_generated_image_in_thread(self, thread_id: uuid.UUID) -> GeneratedImage | None:
        """Get the most recently generated image in a thread."""
        stmt = (
            select(GeneratedImage)
            .where(GeneratedImage.thread_id == thread_id)
            .order_by(GeneratedImage.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    def _is_modification_request(cls, prompt: str) -> bool:
        """Check if prompt is a modification request on a previous image."""
        return bool(cls._modification_pattern.search(prompt.strip()))

    @staticmethod
    def _merge_prompts(original_prompt: str, modification: str) -> str:
        """Merge edit request with strict instructions to preserve scene continuity."""
        base_prompt = ImageGenerationService._extract_base_prompt(original_prompt)
        cleaned = re.sub(
            r"^(change it|change|make it|update it|modify it|alter it|turn it|color it|make the)\s+",
            "",
            modification,
            flags=re.IGNORECASE,
        ).strip()

        return (
            f"Original image description: {base_prompt}. "
            f"Edit instruction: {cleaned}. "
            "Keep the same subject, camera angle, composition, background, lighting, and style. "
            "Only apply the requested edit and do not change anything else."
        )

    @staticmethod
    def _extract_base_prompt(original_prompt: str) -> str:
        marker = "Original image description:"
        edit_marker = ". Edit instruction:"
        if original_prompt.startswith(marker) and edit_marker in original_prompt:
            content = original_prompt[len(marker) :]
            return content.split(edit_marker, 1)[0].strip()
        return original_prompt.strip()

    async def _edit_or_generate_image_payload(
        self,
        prompt: str,
        base_image: GeneratedImage,
    ) -> GeneratedImagePayload:
        """Attempt image-edit endpoint first, then fall back to text-to-image generation."""
        try:
            return await self._edit_image_payload(prompt=prompt, base_image_path=base_image.image_url)
        except ImageGenerationError:
            return await self._generate_image_payload(prompt)

    async def _edit_image_payload(self, prompt: str, base_image_path: str) -> GeneratedImagePayload:
        if not settings.litellm_virtual_key:
            raise ImageGenerationError("Missing LITELLM_VIRTUAL_KEY environment variable.")

        source_path = self._storage.resolve_path(base_image_path)
        if not source_path.exists() or not source_path.is_file():
            raise ImageGenerationError("Base image for edit was not found.")

        image_bytes = await asyncio.to_thread(Path(source_path).read_bytes)
        mime_type = "image/png"

        url = f"{settings.litellm_proxy_url}/v1/images/edits"
        headers = {
            "Authorization": f"Bearer {settings.litellm_virtual_key}",
            "x-litellm-user": settings.litellm_user_id,
            "x-litellm-department": settings.litellm_department,
            "x-litellm-environment": settings.litellm_environment,
        }
        files = {
            "image": ("base_image.png", image_bytes, mime_type),
        }
        form_data = {
            "model": settings.imagen_model,
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "b64_json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, data=form_data, files=files, headers=headers)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ImageGenerationError(f"Image edit failed: {detail}") from exc
        except Exception as exc:
            raise ImageGenerationError("Failed to call image edit API.") from exc

        return await self._parse_image_response(body)

    async def _try_local_color_edit(self, prompt: str, base_image_path: str) -> GeneratedImagePayload | None:
        """Apply deterministic local recolor for target-specific edits to preserve composition."""
        lowered = prompt.lower()
        edit_target = self._extract_edit_target(lowered)
        if edit_target is None:
            return None

        target_color = self._extract_target_color(lowered)
        if target_color is None:
            return None

        source_path = self._storage.resolve_path(base_image_path)
        if not source_path.exists() or not source_path.is_file():
            return None

        try:
            image_bytes = await asyncio.to_thread(Path(source_path).read_bytes)
            edited = await asyncio.to_thread(self._recolor_target_region, image_bytes, edit_target, target_color)
            return GeneratedImagePayload(image_bytes=edited, mime_type="image/png")
        except Exception:
            return None

    @staticmethod
    def _extract_edit_target(prompt: str) -> str | None:
        if re.search(r"\b(grass|lawn)\b", prompt):
            return "grass"
        if re.search(r"\b(sky|cloud)\b", prompt):
            return "sky"
        if re.search(r"\b(car|vehicle|truck|bike|motorcycle)\b", prompt):
            return "vehicle"
        return None

    def _extract_target_color(self, prompt: str) -> str | None:
        for name in self._color_names:
            if re.search(rf"\b{name}\b", prompt):
                return name
        return None

    def _recolor_target_region(self, image_bytes: bytes, target: str, target_color: str) -> bytes:
        with Image.open(io.BytesIO(image_bytes)) as img:
            rgb = img.convert("RGB")
            hsv = rgb.convert("HSV")
            w, h = hsv.size
            px = hsv.load()
            target_hue = self._target_hues.get(target_color, 0)

            if target == "grass":
                mask = self._build_grass_mask(px, w, h)
            elif target == "sky":
                mask = self._build_sky_mask(px, w, h)
            else:
                mask = self._build_vehicle_mask(px, w, h)

            for y in range(h):
                for x in range(w):
                    if not mask[y][x]:
                        continue
                    hue, sat, val = px[x, y]
                    new_hue = int((0.8 * target_hue) + (0.2 * hue)) % 256
                    px[x, y] = (new_hue, max(sat, 95), val)

            out = io.BytesIO()
            hsv.convert("RGB").save(out, format="PNG")
            return out.getvalue()

    @staticmethod
    def _build_grass_mask(px: Any, w: int, h: int) -> list[list[bool]]:
        mask = [[False for _ in range(w)] for _ in range(h)]
        for y in range(int(h * 0.45), h):
            for x in range(w):
                hue, sat, val = px[x, y]
                if 45 <= hue <= 110 and sat >= 35 and val >= 25:
                    mask[y][x] = True
        return mask

    @staticmethod
    def _build_sky_mask(px: Any, w: int, h: int) -> list[list[bool]]:
        mask = [[False for _ in range(w)] for _ in range(h)]
        for y in range(0, int(h * 0.55)):
            for x in range(w):
                hue, sat, val = px[x, y]
                if (120 <= hue <= 210 and sat >= 20 and val >= 50) or (sat <= 25 and val >= 120):
                    mask[y][x] = True
        return mask

    @staticmethod
    def _build_vehicle_mask(px: Any, w: int, h: int) -> list[list[bool]]:
        mask = [[False for _ in range(w)] for _ in range(h)]
        x0, x1 = int(w * 0.2), int(w * 0.8)
        y0, y1 = int(h * 0.35), int(h * 0.92)

        hue_hist = [0] * 256
        for y in range(y0, y1):
            for x in range(x0, x1):
                hue, sat, val = px[x, y]
                if sat > 65 and val > 35:
                    hue_hist[hue] += 1

        dominant_hue = max(range(256), key=lambda idx: hue_hist[idx])
        for y in range(y0, y1):
            for x in range(x0, x1):
                hue, sat, val = px[x, y]
                dist = min((hue - dominant_hue) % 256, (dominant_hue - hue) % 256)
                if sat > 45 and val > 25 and dist <= 18:
                    mask[y][x] = True
        return mask

    async def _resolve_thread(self, user_id: uuid.UUID, thread_id: uuid.UUID | None) -> Thread:
        if thread_id is None:
            return await self._thread_service.create_thread(user_id=user_id, name="New Chat")

        thread = await self._thread_service.get_thread(thread_id=thread_id, user_id=user_id)
        if thread is None:
            raise PromptValidationError("Thread not found.")
        return thread

    def _validate_prompt(self, prompt: str) -> str:
        normalized = prompt.strip()
        if not normalized:
            raise PromptValidationError("Prompt is required.")
        if len(normalized) > settings.max_image_prompt_chars:
            raise PromptValidationError(
                f"Prompt exceeds maximum length of {settings.max_image_prompt_chars} characters."
            )
        if self._blocked_prompt_pattern.search(normalized):
            raise PromptValidationError("Prompt violates safety policy.")
        return normalized

    async def _enforce_rate_limit(self, user_id: uuid.UUID) -> None:
        window = settings.image_generation_rate_limit_window_seconds
        max_requests = settings.image_generation_rate_limit_count
        now = time.monotonic()

        async with self._rate_lock:
            bucket = self._requests_by_user[user_id]
            while bucket and now - bucket[0] > window:
                bucket.popleft()

            if len(bucket) >= max_requests:
                raise ImageRateLimitError("Image generation rate limit exceeded. Try again shortly.")

            bucket.append(now)

    async def _generate_image_payload(self, prompt: str) -> GeneratedImagePayload:
        if not settings.litellm_virtual_key:
            raise ImageGenerationError("Missing LITELLM_VIRTUAL_KEY environment variable.")

        url = f"{settings.litellm_proxy_url}/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.litellm_virtual_key}",
            "Content-Type": "application/json",
            "x-litellm-user": settings.litellm_user_id,
            "x-litellm-department": settings.litellm_department,
            "x-litellm-environment": settings.litellm_environment,
        }
        payload: dict[str, Any] = {
            "model": settings.imagen_model,
            "prompt": prompt,
            "size": "1024x1024",
            "response_format": "b64_json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ImageGenerationError(f"Image generation failed: {detail}") from exc
        except Exception as exc:
            raise ImageGenerationError("Failed to call image generation API.") from exc

        return await self._parse_image_response(body)

    async def _parse_image_response(self, body: Any) -> GeneratedImagePayload:
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or not data:
            raise ImageGenerationError("Image API returned an invalid response payload.")

        first = data[0] if isinstance(data[0], dict) else {}
        b64_data = first.get("b64_json")
        if isinstance(b64_data, str) and b64_data:
            try:
                image_bytes = base64.b64decode(b64_data)
            except (ValueError, binascii.Error) as exc:
                raise ImageGenerationError("Generated image payload is not valid base64.") from exc
            return GeneratedImagePayload(image_bytes=image_bytes, mime_type="image/png")

        image_url = first.get("url")
        if isinstance(image_url, str) and image_url:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    image_response = await client.get(image_url)
                image_response.raise_for_status()
                mime_type = image_response.headers.get("content-type", "image/png").split(";")[0].strip()
                return GeneratedImagePayload(image_bytes=image_response.content, mime_type=mime_type)
            except Exception as exc:
                raise ImageGenerationError("Failed to fetch generated image from provider URL.") from exc

        raise ImageGenerationError("Image API response did not include image data.")

    @staticmethod
    def _build_user_message_text(message: str | None, prompt: str) -> str:
        if message and message.strip():
            return f"{message.strip()}\n\n[Image prompt]\n{prompt}"
        return f"Generate an image: {prompt}"
