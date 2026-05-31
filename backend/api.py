from __future__ import annotations

import base64
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from .config import DEFAULT_ANNOTATIONS_PATH, DEFAULT_REGISTRY_PATH, FaceSystemConfig
from .face_engine import FaceEngine, iter_image_files
from .recognizer import FaceRecognizer, draw_recognition_result

try:
    from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - 运行 API 前会明确提示依赖
    raise RuntimeError("未安装 FastAPI。请先运行：pip install -r requirements.txt") from exc


app = FastAPI(title="AI Lab Face Recognition Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

REGISTRY_PRESETS = {
    "self": DEFAULT_REGISTRY_PATH,
    "celeba": Path("outputs/celeba_registry.npz"),
}


def _config_from_env() -> FaceSystemConfig:
    det_size_text = os.getenv("FACE_DET_SIZE", "640,640")
    det_width, det_height = [int(item.strip()) for item in det_size_text.split(",", 1)]
    return FaceSystemConfig(
        model_name=os.getenv("FACE_MODEL_NAME", "buffalo_l"),
        model_root=Path(os.getenv("FACE_MODEL_ROOT", "models/insightface")),
        ctx_id=int(os.getenv("FACE_CTX_ID", "-1")),
        det_size=(det_width, det_height),
    )


_engine = FaceEngine(_config_from_env())
_recognizers: dict[str, FaceRecognizer] = {}


def get_recognizer(dataset: str = "self") -> FaceRecognizer:
    dataset = _normalize_dataset(dataset)
    if dataset not in _recognizers:
        registry_path = _registry_path(dataset)
        if not registry_path.exists():
            raise HTTPException(
                status_code=503,
                detail=f"身份库不存在：{registry_path}。请先运行 python -m backend.cli build {dataset}。",
            )
        _recognizers[dataset] = FaceRecognizer.from_registry_file(
            registry_path,
            engine=_engine,
        )
    return _recognizers[dataset]


@app.get("/health")
def health() -> dict:
    registries = {}
    for dataset in REGISTRY_PRESETS:
        path = _registry_path(dataset)
        registries[dataset] = {
            "path": str(path),
            "exists": path.exists(),
        }
    return {
        "status": "ok",
        "default_dataset": "self",
        "datasets": list(REGISTRY_PRESETS.keys()),
        "registries": registries,
    }


@app.post("/recognize")
def recognize(
    file: UploadFile = File(...),
    dataset: str = Form("self"),
    draw: bool = Form(True),
) -> dict:
    """前端上传单张图片时调用的接口。"""

    dataset = _normalize_dataset(dataset)
    recognizer = get_recognizer(dataset)
    upload_dir = Path("outputs/uploads")
    result_dir = Path("outputs/results")
    upload_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    image_path = upload_dir / f"{uuid4().hex}{suffix}"
    with image_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    return _recognize_path_payload(image_path, dataset, recognizer, draw)


@app.post("/recognize-path")
def recognize_path(
    image: str = Form(...),
    dataset: str = Form("self"),
    draw: bool = Form(True),
    highlight_errors: bool = Form(False),
) -> dict:
    """识别后端本地测试集图片，供评测页按需展示错误样例。"""

    dataset = _normalize_dataset(dataset)
    image_path = _safe_eval_image_path(dataset, image)
    recognizer = get_recognizer(dataset)
    return _recognize_path_payload(image_path, dataset, recognizer, draw, highlight_errors)


@app.get("/evaluation/images")
def evaluation_images(dataset: str = Query("self")) -> dict:
    dataset = _normalize_dataset(dataset)
    return {
        "dataset": dataset,
        "images": _list_evaluation_images(dataset),
    }


@app.post("/evaluation/run")
def run_evaluation(dataset: str = Form("self")) -> dict:
    dataset = _normalize_dataset(dataset)
    recognizer = get_recognizer(dataset)
    if dataset == "self":
        items, total, correct, no_face, image_total, image_correct = _evaluate_self(recognizer)
    else:
        items, total, correct, no_face, image_total, image_correct = _evaluate_celeba(recognizer)

    return {
        "dataset": dataset,
        "total": total,
        "correct": correct,
        "no_face": no_face,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "image_total": image_total,
        "image_correct": image_correct,
        "image_accuracy": round(image_correct / image_total, 4) if image_total else 0.0,
        "items": items,
    }


def _recognize_path_payload(
    image_path: Path,
    dataset: str,
    recognizer: FaceRecognizer,
    draw: bool,
    highlight_errors: bool = False,
) -> dict:
    result = recognizer.recognize_image(
        image_path,
        closed_set=(dataset == "celeba"),
    )
    payload = result.to_dict()
    payload["dataset"] = dataset

    if draw:
        result_dir = Path("outputs/results")
        result_dir.mkdir(parents=True, exist_ok=True)
        output_path = result_dir / f"{image_path.stem}_{dataset}_result.jpg"
        wrong_face_indices = _wrong_face_indices(dataset, image_path, result) if highlight_errors else set()
        draw_recognition_result(result, output_path, wrong_face_indices=wrong_face_indices)
        payload["annotated_image"] = _image_to_base64(output_path)
        payload["annotated_image_path"] = str(output_path)

    return payload


@app.post("/reload-registry")
def reload_registry(
    dataset: str | None = Form(None),
    dataset_query: str | None = Query(None, alias="dataset"),
) -> dict:
    """重建身份库后，可不重启服务直接刷新内存中的 registry。"""

    dataset = dataset or dataset_query
    if dataset is None:
        _recognizers.clear()
        return {"status": "reloaded", "dataset": "all"}

    dataset = _normalize_dataset(dataset)
    _recognizers.pop(dataset, None)
    get_recognizer(dataset)
    return {"status": "reloaded", "dataset": dataset}


def _list_evaluation_images(dataset: str) -> list[dict]:
    if dataset == "self":
        annotations_path = DEFAULT_ANNOTATIONS_PATH
        if not annotations_path.exists():
            raise HTTPException(
                status_code=503,
                detail=f"标注文件不存在：{annotations_path}。请先运行 python -m backend.cli annotate self。",
            )

        images = []
        for line in annotations_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            image_path = Path("dataset") / item["image"]
            expected = [face["identity_id"] for face in item.get("faces", [])]
            images.append(
                {
                    "image": str(image_path),
                    "name": image_path.name,
                    "expected": ", ".join(expected) if expected else "no labels",
                }
            )
        return images

    test_dir = Path("celeba_100_identities_3reg_3test/test")
    if not test_dir.exists():
        raise HTTPException(status_code=503, detail=f"测试集不存在：{test_dir}")

    return [
        {
            "image": str(image_path),
            "name": image_path.name,
            "expected": image_path.parent.name,
        }
        for image_path in iter_image_files(test_dir)
    ]


def _evaluate_self(recognizer: FaceRecognizer) -> tuple[list[dict], int, int, int, int, int]:
    annotations_path = DEFAULT_ANNOTATIONS_PATH
    if not annotations_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"标注文件不存在：{annotations_path}。请先运行 python -m backend.cli annotate self。",
        )

    total = correct = no_face = image_total = image_correct = 0
    items = []
    for line in annotations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        image_total += 1
        image_path = Path("dataset") / item["image"]
        result = recognizer.recognize_image(image_path, closed_set=False)
        predicted_faces = result.faces
        if not predicted_faces:
            no_face += len(item.get("faces", []))

        faces = []
        image_ok = True
        for gt_face in item.get("faces", []):
            total += 1
            expected = gt_face["identity_id"]
            matched = _best_iou_face(gt_face["bbox"], predicted_faces)
            predicted = matched.match.identity_id if matched else "no_face"
            score = float(matched.match.score) if matched else 0.0
            ok = predicted == expected
            if ok:
                correct += 1
            else:
                image_ok = False
            faces.append(
                {
                    "expected": expected,
                    "predicted": predicted,
                    "score": round(score, 4),
                    "ok": ok,
                    "bbox": gt_face["bbox"],
                    "iou": round(_iou(gt_face["bbox"], matched.bbox), 4) if matched else 0.0,
                }
            )

        items.append(
            {
                "image": str(image_path),
                "name": image_path.name,
                "expected": ", ".join(face["expected"] for face in faces) if faces else "no labels",
                "predicted": ", ".join(face["predicted"] for face in faces) if faces else "no prediction",
                "score": max((face["score"] for face in faces), default=0.0),
                "ok": image_ok,
                "faces": faces,
            }
        )
        if image_ok:
            image_correct += 1

    return items, total, correct, no_face, image_total, image_correct


def _evaluate_celeba(recognizer: FaceRecognizer) -> tuple[list[dict], int, int, int, int, int]:
    test_dir = Path("celeba_100_identities_3reg_3test/test")
    if not test_dir.exists():
        raise HTTPException(status_code=503, detail=f"测试集不存在：{test_dir}")

    total = correct = no_face = image_total = image_correct = 0
    items = []
    for image_path in iter_image_files(test_dir):
        total += 1
        image_total += 1
        expected = image_path.parent.name
        result = recognizer.recognize_image(image_path, closed_set=True)
        if not result.faces:
            no_face += 1
            predicted = "no_face"
            score = 0.0
        else:
            face = max(result.faces, key=lambda item: item.bbox[2] * item.bbox[3])
            predicted = face.match.identity_id
            score = float(face.match.score)
            if predicted == expected:
                correct += 1
                image_correct += 1

        items.append(
            {
                "image": str(image_path),
                "name": f"{expected}/{image_path.name}",
                "expected": expected,
                "predicted": predicted,
                "score": round(score, 4),
                "ok": predicted == expected,
            }
        )

    return items, total, correct, no_face, image_total, image_correct


def _safe_eval_image_path(dataset: str, image: str) -> Path:
    image_path = Path(image)
    allowed_roots = [Path("dataset/test"), Path("dataset/test/images")] if dataset == "self" else [
        Path("celeba_100_identities_3reg_3test/test")
    ]
    try:
        resolved = image_path.resolve()
        allowed = [root.resolve() for root in allowed_roots]
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"无效图片路径：{image}") from exc

    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail=f"图片不存在：{image}")

    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise HTTPException(status_code=400, detail="只能识别测试集目录中的图片")
    return image_path


def _wrong_face_indices(dataset: str, image_path: Path, result) -> set[int]:
    if dataset == "celeba":
        expected = image_path.parent.name
        return {
            index
            for index, face in enumerate(result.faces)
            if face.match.identity_id != expected
        }

    annotation = _annotation_for_image(image_path)
    if not annotation:
        return set()

    wrong_indices = set()
    for gt_face in annotation.get("faces", []):
        index = _best_iou_face_index(gt_face["bbox"], result.faces)
        if index is None:
            continue
        if result.faces[index].match.identity_id != gt_face["identity_id"]:
            wrong_indices.add(index)
    return wrong_indices


def _annotation_for_image(image_path: Path) -> dict | None:
    annotations_path = DEFAULT_ANNOTATIONS_PATH
    if not annotations_path.exists():
        return None

    image_path = image_path.resolve()
    for line in annotations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        annotated_path = (Path("dataset") / item["image"]).resolve()
        if annotated_path == image_path:
            return item
    return None


def _best_iou_face(gt_bbox: list[int], predicted_faces) -> object | None:
    if not predicted_faces:
        return None
    return max(predicted_faces, key=lambda face: _iou(gt_bbox, face.bbox))


def _best_iou_face_index(gt_bbox: list[int], predicted_faces) -> int | None:
    if not predicted_faces:
        return None
    return max(range(len(predicted_faces)), key=lambda index: _iou(gt_bbox, predicted_faces[index].bbox))


def _iou(a: list[int], b: list[int]) -> float:
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


def _normalize_dataset(dataset: str) -> str:
    dataset = dataset.lower().strip()
    if dataset not in REGISTRY_PRESETS:
        allowed = ", ".join(REGISTRY_PRESETS)
        raise HTTPException(status_code=400, detail=f"未知数据集：{dataset}。可选：{allowed}")
    return dataset


def _registry_path(dataset: str) -> Path:
    env_name = f"FACE_{dataset.upper()}_REGISTRY"
    if os.getenv(env_name):
        return Path(os.environ[env_name])
    return REGISTRY_PRESETS[dataset]


def _image_to_base64(image_path: Path) -> str:
    data = image_path.read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


