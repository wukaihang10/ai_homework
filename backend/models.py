from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class DetectedFace:
    """InsightFace 单张人脸的标准化输出。"""

    bbox_xyxy: np.ndarray
    bbox_xywh: List[int]
    embedding: np.ndarray
    det_score: float
    landmarks: Optional[np.ndarray] = None

    @property
    def area(self) -> int:
        return int(max(0, self.bbox_xywh[2]) * max(0, self.bbox_xywh[3]))


@dataclass
class MatchResult:
    identity_id: str
    name: str
    score: float
    is_unknown: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "score": round(float(self.score), 4),
            "is_unknown": self.is_unknown,
        }


@dataclass
class RecognizedFace:
    bbox: List[int]
    det_score: float
    match: MatchResult

    def to_dict(self) -> Dict[str, Any]:
        data = self.match.to_dict()
        data.update(
            {
                "bbox": self.bbox,
                "det_score": round(float(self.det_score), 4),
            }
        )
        return data


@dataclass
class RecognitionResult:
    image_path: Path
    faces: List[RecognizedFace]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": str(self.image_path),
            "face_count": len(self.faces),
            "faces": [face.to_dict() for face in self.faces],
        }
