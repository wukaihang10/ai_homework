from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import FaceSystemConfig
from .face_engine import FaceEngine
from .models import MatchResult, RecognizedFace, RecognitionResult
from .registry import IdentityRegistry


class FaceRecognizer:
    """人脸识别主流程：检测 -> embedding -> 相似度比对 -> 返回身份。"""

    def __init__(
        self,
        registry: IdentityRegistry,
        engine: FaceEngine,
        threshold: Optional[float] = None,
    ) -> None:
        self.registry = registry
        self.engine = engine
        self.threshold = (
            threshold
            if threshold is not None
            else FaceSystemConfig().similarity_threshold
        )

    @classmethod
    def from_registry_file(
        cls,
        registry_path: Path | str,
        engine: FaceEngine | None = None,
        threshold: Optional[float] = None,
    ) -> "FaceRecognizer":
        return cls(
            registry=IdentityRegistry.load(registry_path),
            engine=engine or FaceEngine(),
            threshold=threshold,
        )

    def recognize_image(
        self,
        image_path: Path | str,
        threshold: Optional[float] = None,
        closed_set: bool = False,
    ) -> RecognitionResult:
        image_path = Path(image_path)
        faces = self.engine.detect_file(image_path)
        recognized = [
            RecognizedFace(
                bbox=face.bbox_xywh,
                det_score=face.det_score,
                match=self.match(face.embedding, threshold=threshold, closed_set=closed_set),
            )
            for face in faces
        ]
        return RecognitionResult(image_path=image_path, faces=recognized)

    def match(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None,
        closed_set: bool = False,
    ) -> MatchResult:
        # 多模板匹配：测试 embedding 与每张注册图 embedding 分别计算余弦相似度，
        # 再把同一身份下的最高相似度作为该身份分数。相比简单平均 embedding，
        # 这种方式对年龄、角度、妆容差异更宽容。
        sample_scores = self.registry.sample_embeddings @ embedding.astype(np.float32)
        identity_scores = np.full(len(self.registry.identities), -1.0, dtype=np.float32)
        np.maximum.at(
            identity_scores,
            self.registry.sample_identity_indices,
            sample_scores,
        )
        best_index = int(np.argmax(identity_scores))
        best_score = float(identity_scores[best_index])

        active_threshold = self.threshold if threshold is None else threshold
        is_unknown = (not closed_set) and best_score < active_threshold
        if is_unknown:
            return MatchResult(
                identity_id="unknown",
                name="unknown",
                score=best_score,
                is_unknown=True,
            )

        identity = self.registry.identities[best_index]
        return MatchResult(
            identity_id=identity.identity_id,
            name=identity.name,
            score=best_score,
            is_unknown=False,
        )


def draw_recognition_result(
    result: RecognitionResult,
    output_path: Path | str,
    wrong_face_indices: set[int] | None = None,
) -> Path:
    """在原图上画人脸框、身份编号、姓名和相似度。"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrong_face_indices = wrong_face_indices or set()

    image = Image.open(result.image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = _load_font(size=max(16, image.width // 45))

    for index, face in enumerate(result.faces):
        x, y, w, h = face.bbox
        x2, y2 = x + w, y + h
        label = _format_label(face.match)
        color = (255, 64, 64) if index in wrong_face_indices or face.match.is_unknown else (0, 190, 80)

        draw.rectangle([x, y, x2, y2], outline=color, width=max(2, image.width // 400))

        text_box = draw.textbbox((x, y), label, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        text_y = max(0, y - text_h - 6)
        draw.rectangle([x, text_y, x + text_w + 8, text_y + text_h + 6], fill=color)
        draw.text((x + 4, text_y + 2), label, fill=(255, 255, 255), font=font)

    image.save(output_path)
    return output_path


def _format_label(match: MatchResult) -> str:
    if match.identity_id == match.name:
        return match.identity_id
    return f"{match.identity_id} {match.name}"


def _load_font(size: int) -> ImageFont.ImageFont:
    # Windows 常见中文字体；找不到时退回默认字体，英文/编号仍可正常显示。
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()

