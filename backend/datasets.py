from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .face_engine import iter_image_files
from .recognizer import FaceRecognizer


IDENTITY_RE = re.compile(r"(p\d{2}|identity_\d+)", re.IGNORECASE)


@dataclass
class EvaluationSummary:
    total: int
    correct: int
    no_face: int
    accuracy: float
    samples: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "correct": self.correct,
            "no_face": self.no_face,
            "accuracy": round(self.accuracy, 4),
            "samples": self.samples,
        }


def generate_annotations_jsonl(
    test_images_dir: Path | str,
    recognizer: FaceRecognizer,
    output_path: Path | str,
) -> Path:
    """为自收集 20 类测试集生成 annotations.jsonl。

    每张测试图会先检测出所有人脸，再逐脸与 20 人身份库做相似度匹配：
    - 相似度达到阈值：写入对应 pXX；
    - 相似度低于阈值：写入 unknown。

    因为标注文件会进入最终提交，生成后仍建议人工快速浏览一遍结果图或 JSONL。
    """

    test_images_dir = Path(test_images_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    for image_path in iter_image_files(test_images_dir):
        result = recognizer.recognize_image(image_path, closed_set=False)

        face_items = []
        for face in result.faces:
            face_items.append(
                {
                    "identity_id": face.match.identity_id,
                    "bbox": face.bbox,
                }
            )

        image_type = "single" if len(result.faces) <= 1 else "multi"
        item = {
            "image": _annotation_image_path(image_path),
            "image_type": image_type,
            "faces": face_items,
        }
        lines.append(json.dumps(item, ensure_ascii=False))

    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output_path


def evaluate_identity_folders(
    test_dir: Path | str,
    recognizer: FaceRecognizer,
    closed_set: bool = True,
    max_samples: int = 12,
) -> EvaluationSummary:
    """评测 CelebA 这类 test/identity_xxx/*.jpg 结构。"""

    total = correct = no_face = 0
    samples: List[Dict] = []

    for identity_dir in sorted(path for path in Path(test_dir).iterdir() if path.is_dir()):
        expected_id = identity_dir.name
        for image_path in iter_image_files(identity_dir):
            total += 1
            result = recognizer.recognize_image(image_path, closed_set=closed_set)
            if not result.faces:
                no_face += 1
                predicted = "no_face"
                score = 0.0
            else:
                # 已裁剪数据集中一般只有一张脸；若检测到多张，取最大框对应的人脸。
                face = max(result.faces, key=lambda item: item.bbox[2] * item.bbox[3])
                predicted = face.match.identity_id
                score = face.match.score
                if predicted == expected_id:
                    correct += 1

            if len(samples) < max_samples:
                samples.append(
                    {
                        "image": str(image_path),
                        "expected": expected_id,
                        "predicted": predicted,
                        "score": round(float(score), 4),
                        "ok": predicted == expected_id,
                    }
                )

    accuracy = correct / total if total else 0.0
    return EvaluationSummary(total, correct, no_face, accuracy, samples)


def evaluate_annotations_jsonl(
    annotations_path: Path | str,
    recognizer: FaceRecognizer,
    dataset_root: Path | str = ".",
    closed_set: bool = False,
    max_samples: int = 12,
) -> EvaluationSummary:
    """评测自收集 20 类 annotations.jsonl。

    对每个已标注人脸，找到预测框中 IoU 最大的人脸作为匹配项。
    known 和 unknown 都纳入统计，符合课堂演示“图片中所有清晰人脸”的要求。
    """

    annotations_path = Path(annotations_path)
    dataset_root = Path(dataset_root)
    total = correct = no_face = 0
    samples: List[Dict] = []

    for line in annotations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        image_path = dataset_root / item["image"]
        result = recognizer.recognize_image(image_path, closed_set=closed_set)
        predicted_faces = result.faces
        if not predicted_faces:
            no_face += len(item.get("faces", []))

        for gt_face in item.get("faces", []):
            total += 1
            expected_id = gt_face["identity_id"]
            matched = _best_iou_face(gt_face["bbox"], predicted_faces)
            predicted_id = matched.match.identity_id if matched else "no_face"
            ok = predicted_id == expected_id
            if ok:
                correct += 1

            if len(samples) < max_samples:
                samples.append(
                    {
                        "image": str(image_path),
                        "expected": expected_id,
                        "predicted": predicted_id,
                        "score": round(float(matched.match.score), 4) if matched else 0.0,
                        "ok": ok,
                        "iou": round(_iou(gt_face["bbox"], matched.bbox), 4)
                        if matched
                        else 0.0,
                    }
                )

    accuracy = correct / total if total else 0.0
    return EvaluationSummary(total, correct, no_face, accuracy, samples)


def infer_identity_from_path(path: Path | str) -> Optional[str]:
    match = IDENTITY_RE.search(Path(path).as_posix())
    return match.group(1) if match else None


def _annotation_image_path(image_path: Path) -> str:
    parts = image_path.as_posix().split("/")
    if "test" in parts:
        index = parts.index("test")
        return "/".join(parts[index:])
    return image_path.as_posix()


def _largest_face_index(faces) -> Optional[int]:
    if not faces:
        return None
    return max(range(len(faces)), key=lambda index: faces[index].area)


def _best_iou_face(gt_bbox: List[int], predicted_faces) -> Optional[object]:
    if not predicted_faces:
        return None
    return max(predicted_faces, key=lambda face: _iou(gt_bbox, face.bbox))


def _iou(a: List[int], b: List[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1, inter_y1 = max(ax, bx), max(ay, by)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    union_area = aw * ah + bw * bh - inter_area
    return inter_area / union_area if union_area else 0.0

