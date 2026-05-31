from __future__ import annotations

import os
import site
from pathlib import Path
from typing import Iterable, List

import numpy as np
from PIL import Image

from .config import FaceSystemConfig, IMAGE_EXTENSIONS
from .models import DetectedFace


class FaceEngine:
    """InsightFace 推理封装。

    InsightFace 的 FaceAnalysis 会同时完成：
    1. 人脸检测，输出 bbox 和关键点；
    2. 基于关键点的人脸对齐；
    3. ArcFace 等识别模型的 embedding 提取。

    本类把第三方对象转换成项目内部统一的 DetectedFace，后续建库、
    识别、标注和 API 都只依赖这个稳定的数据结构。
    """

    def __init__(self, config: FaceSystemConfig | None = None) -> None:
        self.config = config or FaceSystemConfig()
        self._app = None

    @property
    def app(self):
        if self._app is None:
            try:
                from insightface.app import FaceAnalysis
            except ImportError as exc:
                raise RuntimeError(
                    "未安装 insightface。请先运行：pip install -r requirements.txt"
                ) from exc

            self.config.model_root.mkdir(parents=True, exist_ok=True)
            providers = _execution_providers(self.config.ctx_id)
            self._app = FaceAnalysis(
                name=self.config.model_name,
                root=str(self.config.model_root),
                providers=providers,
            )
            self._app.prepare(ctx_id=self.config.ctx_id, det_size=self.config.det_size)
        return self._app

    def detect_file(self, image_path: Path | str) -> List[DetectedFace]:
        image_path = Path(image_path)
        image_bgr = self._read_image_as_bgr(image_path)
        return self.detect_array(image_bgr)

    def detect_array(self, image_bgr: np.ndarray) -> List[DetectedFace]:
        raw_faces = self.app.get(image_bgr)
        faces = [self._convert_face(face) for face in raw_faces]
        return sorted(faces, key=lambda face: (face.bbox_xywh[0], face.bbox_xywh[1]))

    def largest_face(self, image_path: Path | str) -> DetectedFace | None:
        faces = self.detect_file(image_path)
        if not faces:
            return None
        return max(faces, key=lambda face: face.area)

    @staticmethod
    def _read_image_as_bgr(image_path: Path) -> np.ndarray:
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片格式：{image_path}")

        # PIL 对中文路径更稳定；InsightFace 期望 BGR 顺序，因此这里手动翻转通道。
        rgb = np.asarray(Image.open(image_path).convert("RGB"))
        return np.ascontiguousarray(rgb[:, :, ::-1])

    @staticmethod
    def _convert_face(face) -> DetectedFace:
        bbox_xyxy = np.asarray(face.bbox, dtype=np.float32)
        x1, y1, x2, y2 = bbox_xyxy.tolist()
        x = int(round(max(0.0, x1)))
        y = int(round(max(0.0, y1)))
        w = int(round(max(0.0, x2 - x1)))
        h = int(round(max(0.0, y2 - y1)))

        embedding = getattr(face, "normed_embedding", None)
        if embedding is None:
            embedding = getattr(face, "embedding", None)
        if embedding is None:
            raise RuntimeError("InsightFace 没有返回 embedding，请检查模型包是否完整。")

        embedding = normalize(np.asarray(embedding, dtype=np.float32))
        landmarks = getattr(face, "kps", None)
        if landmarks is not None:
            landmarks = np.asarray(landmarks, dtype=np.float32)

        return DetectedFace(
            bbox_xyxy=bbox_xyxy,
            bbox_xywh=[x, y, w, h],
            embedding=embedding,
            det_score=float(getattr(face, "det_score", 0.0)),
            landmarks=landmarks,
        )


def normalize(vector: np.ndarray) -> np.ndarray:
    """L2 归一化后，点积就等价于余弦相似度。"""

    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector.astype(np.float32)
    return (vector / norm).astype(np.float32)


def iter_image_files(root: Path | str) -> Iterable[Path]:
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _execution_providers(ctx_id: int) -> List[str]:
    """根据 ctx_id 明确选择 ONNX Runtime provider。

    ctx_id < 0 时只启用 CPU，避免安装了 onnxruntime-gpu 后仍反复尝试加载
    CUDA DLL；ctx_id >= 0 时预加载 pip 安装的 CUDA/cuDNN DLL 并优先使用 GPU。
    """

    if ctx_id < 0:
        return ["CPUExecutionProvider"]

    _add_nvidia_dll_dirs()
    try:
        import onnxruntime as ort

        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
    except Exception as exc:
        print(f"[WARN] 预加载 CUDA/cuDNN DLL 失败，将尝试继续初始化 GPU：{exc}")

    return ["CUDAExecutionProvider", "CPUExecutionProvider"]


_DLL_DIR_HANDLES = []


def _add_nvidia_dll_dirs() -> None:
    """把 pip 安装的 NVIDIA CUDA/cuDNN DLL 目录加入 Windows 搜索路径。"""

    if os.name != "nt":
        return

    suffixes = [
        Path("nvidia") / "cudnn" / "bin",
        Path("nvidia") / "cublas" / "bin",
        Path("nvidia") / "cufft" / "bin",
        Path("nvidia") / "cuda_runtime" / "bin",
        Path("nvidia") / "cuda_nvrtc" / "bin",
        Path("nvidia") / "nvjitlink" / "bin",
    ]
    roots = [Path(item) for item in site.getsitepackages()]
    paths = [root / suffix for root in roots for suffix in suffixes]

    for dll_dir in paths:
        if not dll_dir.exists():
            continue
        dll_dir_text = str(dll_dir)
        if dll_dir_text not in os.environ.get("PATH", ""):
            os.environ["PATH"] = dll_dir_text + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                _DLL_DIR_HANDLES.append(os.add_dll_directory(dll_dir_text))
            except OSError:
                pass



