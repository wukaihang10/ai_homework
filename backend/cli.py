from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .config import DEFAULT_ANNOTATIONS_PATH, DEFAULT_REGISTRY_PATH, FaceSystemConfig
from .datasets import (
    evaluate_annotations_jsonl,
    evaluate_identity_folders,
    generate_annotations_jsonl,
)
from .face_engine import FaceEngine
from .recognizer import FaceRecognizer, draw_recognition_result
from .registry import build_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="人脸识别后端命令行工具")
    _add_common_model_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_short_parser = subparsers.add_parser("build", help="按数据集预设建立身份库")
    build_short_parser.add_argument("dataset", choices=["self", "celeba"])

    annotate_short_parser = subparsers.add_parser("annotate", help="为自收集数据集生成 annotations.jsonl")
    annotate_short_parser.add_argument("dataset", choices=["self"], nargs="?", default="self")
    annotate_short_parser.add_argument("--threshold", type=float, default=None)

    eval_short_parser = subparsers.add_parser("eval", help="按数据集预设评测")
    eval_short_parser.add_argument("dataset", choices=["self", "celeba"])
    eval_short_parser.add_argument("--threshold", type=float, default=None)
    infer_short_parser = subparsers.add_parser("infer", help="按数据集预设识别单张图片")
    infer_short_parser.add_argument("dataset", choices=["self", "celeba"])
    infer_short_parser.add_argument("image", type=Path)
    infer_short_parser.add_argument("--threshold", type=float, default=None)
    infer_short_parser.add_argument("--output-image", type=Path, default=None)
    infer_short_parser.add_argument("--no-draw", action="store_true", help="只输出 JSON，不保存画框图")

    build_parser = subparsers.add_parser("build-registry", help="根据注册集建立身份库")
    build_parser.add_argument("--register-dir", required=True, type=Path)
    build_parser.add_argument("--identity-csv", type=Path, default=None)
    build_parser.add_argument("--output", type=Path, default=DEFAULT_REGISTRY_PATH)

    anno_parser = subparsers.add_parser("generate-annotations", help="生成 annotations.jsonl 草稿")
    anno_parser.add_argument("--test-images-dir", type=Path, default=Path("dataset/test/images"))
    anno_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    anno_parser.add_argument("--output", type=Path, default=DEFAULT_ANNOTATIONS_PATH)
    anno_parser.add_argument("--threshold", type=float, default=None)

    recog_parser = subparsers.add_parser("recognize", help="识别单张图片并可输出画框结果图")
    recog_parser.add_argument("--image", required=True, type=Path)
    recog_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    recog_parser.add_argument("--output-image", type=Path, default=None)
    recog_parser.add_argument("--threshold", type=float, default=None)
    recog_parser.add_argument("--closed-set", action="store_true")

    celeb_parser = subparsers.add_parser("eval-celeba", help="评测 CelebA 100 类数据集")
    celeb_parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("celeba_100_identities_3reg_3test"),
    )
    celeb_parser.add_argument("--registry", type=Path, default=Path("outputs/celeba_registry.npz"))
    celeb_parser.add_argument("--rebuild", action="store_true", help="重新建库后再评测")

    self_parser = subparsers.add_parser("eval-annotations", help="按 annotations.jsonl 评测自收集数据集")
    self_parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    self_parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS_PATH)
    self_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    self_parser.add_argument("--threshold", type=float, default=None)

    api_parser = subparsers.add_parser("api", help="启动 FastAPI 后端服务")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    config = _config_from_args(args)

    if args.command == "api":
        _run_api(args.host, args.port, config)
        return

    engine = FaceEngine(config)

    if args.command == "build":
        preset = _dataset_preset(args.dataset)
        registry = build_registry(
            preset["register_dir"],
            engine,
            preset.get("identity_csv"),
            preset["registry"],
        )
        print(f"身份库已保存：{preset['registry']}")
        print(f"身份数量：{len(registry.identities)}，注册图数量：{len(registry.sample_paths)}")

    elif args.command == "annotate":
        preset = _dataset_preset(args.dataset)
        if not preset["registry"].exists():
            raise FileNotFoundError(
                f"身份库不存在：{preset['registry']}。请先运行：python -m backend.cli build {args.dataset}"
            )
        recognizer = FaceRecognizer.from_registry_file(
            preset["registry"],
            engine=engine,
            threshold=args.threshold,
        )
        output = generate_annotations_jsonl(
            preset["test_images_dir"],
            recognizer,
            preset["annotations"],
        )
        print(f"标注文件已保存：{output}")
        print("提示：已对每张检测到的人脸逐一识别，提交前仍建议人工快速核对。")

    elif args.command == "eval":
        preset = _dataset_preset(args.dataset)
        if not preset["registry"].exists():
            raise FileNotFoundError(
                f"身份库不存在：{preset['registry']}。请先运行：python -m backend.cli build {args.dataset}"
            )
        recognizer = FaceRecognizer.from_registry_file(
            preset["registry"],
            engine=engine,
            threshold=args.threshold,
        )
        if args.dataset == "self":
            summary = evaluate_annotations_jsonl(
                preset["annotations"],
                recognizer,
                dataset_root=preset["dataset_root"],
                closed_set=False,
            )
        else:
            summary = evaluate_identity_folders(
                preset["test_dir"],
                recognizer,
                closed_set=True,
            )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "infer":
        preset = _dataset_preset(args.dataset)
        if not preset["registry"].exists():
            raise FileNotFoundError(
                f"身份库不存在：{preset['registry']}。请先运行：python -m backend.cli build {args.dataset}"
            )
        recognizer = FaceRecognizer.from_registry_file(
            preset["registry"],
            engine=engine,
            threshold=args.threshold,
        )
        result = recognizer.recognize_image(
            args.image,
            threshold=args.threshold,
            closed_set=(args.dataset == "celeba"),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        if not args.no_draw:
            output_image = args.output_image or _default_result_image(args.image, args.dataset)
            draw_recognition_result(result, output_image)
            print(f"结果图已保存：{output_image}")

    elif args.command == "build-registry":
        registry = build_registry(args.register_dir, engine, args.identity_csv, args.output)
        print(f"身份库已保存：{args.output}")
        print(f"身份数量：{len(registry.identities)}，注册图数量：{len(registry.sample_paths)}")

    elif args.command == "generate-annotations":
        if not args.registry.exists():
            raise FileNotFoundError(
                f"身份库不存在：{args.registry}。请先手动运行 build-registry。"
            )
        recognizer = FaceRecognizer.from_registry_file(
            args.registry,
            engine=engine,
            threshold=args.threshold,
        )
        output = generate_annotations_jsonl(args.test_images_dir, recognizer, args.output)
        print(f"标注草稿已保存：{output}")
        print("提示：已对每张检测到的人脸逐一识别，提交前仍建议人工快速核对。")

    elif args.command == "recognize":
        recognizer = FaceRecognizer.from_registry_file(
            args.registry,
            engine=engine,
            threshold=args.threshold,
        )
        result = recognizer.recognize_image(
            args.image,
            threshold=args.threshold,
            closed_set=args.closed_set,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        if args.output_image:
            draw_recognition_result(result, args.output_image)
            print(f"结果图已保存：{args.output_image}")

    elif args.command == "eval-celeba":
        register_dir = args.dataset_dir / "register"
        test_dir = args.dataset_dir / "test"
        if args.rebuild:
            build_registry(register_dir, engine, output_path=args.registry)
            print(f"CelebA 身份库已保存：{args.registry}")
        elif not args.registry.exists():
            raise FileNotFoundError(
                f"CelebA 身份库不存在：{args.registry}。"
                "请先手动运行 build-registry，或本次评测显式添加 --rebuild。"
            )
        recognizer = FaceRecognizer.from_registry_file(args.registry, engine=engine)
        summary = evaluate_identity_folders(test_dir, recognizer, closed_set=True)
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))

    elif args.command == "eval-annotations":
        recognizer = FaceRecognizer.from_registry_file(
            args.registry,
            engine=engine,
            threshold=args.threshold,
        )
        summary = evaluate_annotations_jsonl(
            args.annotations,
            recognizer,
            dataset_root=args.dataset_root,
            closed_set=False,
        )
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


def _add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-name", default="buffalo_l")
    parser.add_argument("--model-root", type=Path, default=Path("models/insightface"))
    parser.add_argument("--ctx-id", type=int, default=-1, help="-1 使用 CPU，0 使用第一张 GPU")
    parser.add_argument("--det-size", type=int, nargs=2, default=(640, 640))


def _config_from_args(args: argparse.Namespace) -> FaceSystemConfig:
    return FaceSystemConfig(
        model_name=args.model_name,
        model_root=args.model_root,
        ctx_id=args.ctx_id,
        det_size=tuple(args.det_size),
    )


def _default_result_image(image_path: Path | str, dataset: str) -> Path:
    image_path = Path(image_path)
    return Path("outputs/results") / f"{image_path.stem}_{dataset}_result.jpg"

def _dataset_preset(dataset: str) -> dict:
    if dataset == "self":
        identity_csv = Path("dataset/identities.csv")
        if not identity_csv.exists() and Path("identities.csv").exists():
            identity_csv = Path("identities.csv")
        return {
            "dataset_root": Path("dataset"),
            "register_dir": Path("dataset/registered"),
            "identity_csv": identity_csv,
            "test_images_dir": Path("dataset/test/images"),
            "annotations": DEFAULT_ANNOTATIONS_PATH,
            "registry": DEFAULT_REGISTRY_PATH,
        }
    if dataset == "celeba":
        dataset_root = Path("celeba_100_identities_3reg_3test")
        return {
            "dataset_root": dataset_root,
            "register_dir": dataset_root / "register",
            "identity_csv": None,
            "test_dir": dataset_root / "test",
            "registry": Path("outputs/celeba_registry.npz"),
        }
    raise ValueError(f"未知数据集：{dataset}")


def _run_api(host: str, port: int, config: FaceSystemConfig) -> None:
    os.environ["FACE_MODEL_NAME"] = config.model_name
    os.environ["FACE_MODEL_ROOT"] = str(config.model_root)
    os.environ["FACE_CTX_ID"] = str(config.ctx_id)
    os.environ["FACE_DET_SIZE"] = f"{config.det_size[0]},{config.det_size[1]}"
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("未安装 uvicorn。请先运行：pip install -r requirements.txt") from exc
    uvicorn.run("backend.api:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()


