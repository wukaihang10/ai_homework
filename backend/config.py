from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class FaceSystemConfig:
    """系统级参数。

    ctx_id=-1 表示使用 CPU；如果机器有可用 CUDA，可以改成 0。
    similarity_threshold 是开放集识别阈值：低于该值时返回 unknown。
    CelebA 的 top-1 评测是闭集任务，默认不使用 unknown 阈值。
    """

    model_name: str = "buffalo_l"
    model_root: Path = Path("models/insightface")
    ctx_id: int = -1
    det_size: Tuple[int, int] = (640, 640)
    similarity_threshold: float = 0.40


DEFAULT_REGISTRY_PATH = Path("outputs/identity_registry.npz")
DEFAULT_ANNOTATIONS_PATH = Path("dataset/test/annotations.jsonl")
