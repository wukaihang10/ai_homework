from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

from .face_engine import FaceEngine, iter_image_files, normalize


@dataclass
class IdentityInfo:
    identity_id: str
    name: str
    field: str = ""
    image_paths: List[str] | None = None


class IdentityRegistry:
    """身份库。

    mean_embeddings 用于识别时快速比对；
    sample_embeddings 保留每张注册图的 embedding，方便写报告时说明建库细节，
    也方便后续做失败样例分析。
    """

    def __init__(
        self,
        identities: List[IdentityInfo],
        mean_embeddings: np.ndarray,
        sample_embeddings: np.ndarray,
        sample_identity_indices: np.ndarray,
        sample_paths: List[str],
    ) -> None:
        self.identities = identities
        self.mean_embeddings = mean_embeddings.astype(np.float32)
        self.sample_embeddings = sample_embeddings.astype(np.float32)
        self.sample_identity_indices = sample_identity_indices.astype(np.int32)
        self.sample_paths = sample_paths

    @property
    def identity_ids(self) -> List[str]:
        return [item.identity_id for item in self.identities]

    @property
    def names(self) -> List[str]:
        return [item.name for item in self.identities]

    def save(self, output_path: Path | str) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        np.savez_compressed(
            output_path,
            mean_embeddings=self.mean_embeddings,
            sample_embeddings=self.sample_embeddings,
            sample_identity_indices=self.sample_identity_indices,
            identity_ids=np.asarray(self.identity_ids),
            names=np.asarray(self.names),
            sample_paths=np.asarray(self.sample_paths),
        )

        metadata_path = output_path.with_suffix(".json")
        metadata = {
            "identities": [
                {
                    "identity_id": item.identity_id,
                    "name": item.name,
                    "field": item.field,
                    "image_paths": item.image_paths or [],
                }
                for item in self.identities
            ],
            "sample_count": len(self.sample_paths),
            "embedding_dim": int(self.mean_embeddings.shape[1])
            if self.mean_embeddings.size
            else 0,
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, registry_path: Path | str) -> "IdentityRegistry":
        registry_path = Path(registry_path)
        data = np.load(registry_path, allow_pickle=False)

        metadata_path = registry_path.with_suffix(".json")
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            identities = [
                IdentityInfo(
                    identity_id=item["identity_id"],
                    name=item.get("name", item["identity_id"]),
                    field=item.get("field", ""),
                    image_paths=item.get("image_paths", []),
                )
                for item in metadata["identities"]
            ]
        else:
            identity_ids = [str(item) for item in data["identity_ids"].tolist()]
            names = [str(item) for item in data["names"].tolist()]
            identities = [
                IdentityInfo(identity_id=identity_id, name=name)
                for identity_id, name in zip(identity_ids, names)
            ]

        return cls(
            identities=identities,
            mean_embeddings=data["mean_embeddings"],
            sample_embeddings=data["sample_embeddings"],
            sample_identity_indices=data["sample_identity_indices"],
            sample_paths=[str(item) for item in data["sample_paths"].tolist()],
        )


def load_identity_csv(csv_path: Path | str | None) -> Dict[str, IdentityInfo]:
    """读取 identities.csv；CelebA 这种无姓名数据集可以不传。"""

    if csv_path is None:
        return {}

    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {}

    result: Dict[str, IdentityInfo] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            identity_id = (row.get("identity_id") or "").strip()
            if not identity_id:
                continue
            result[identity_id] = IdentityInfo(
                identity_id=identity_id,
                name=(row.get("name") or identity_id).strip(),
                field=(row.get("field") or "").strip(),
            )
    return result


def build_registry(
    register_dir: Path | str,
    engine: FaceEngine,
    identity_csv: Path | str | None = None,
    output_path: Path | str | None = None,
) -> IdentityRegistry:
    """从注册集建立身份库。

    register_dir 期望形如：
    - dataset/registered/p01/*.jpg
    - celeba_100_identities_3reg_3test/register/identity_xxxxx/*.jpg

    每张注册图通常只有一个主要人物。若检测出多张脸，取面积最大的脸作为该图的注册人脸。
    """

    register_dir = Path(register_dir)
    if not register_dir.exists():
        raise FileNotFoundError(f"注册集目录不存在：{register_dir}")

    identity_map = load_identity_csv(identity_csv)
    identities: List[IdentityInfo] = []
    mean_embeddings: List[np.ndarray] = []
    sample_embeddings: List[np.ndarray] = []
    sample_identity_indices: List[int] = []
    sample_paths: List[str] = []

    for identity_dir in sorted(path for path in register_dir.iterdir() if path.is_dir()):
        identity_id = identity_dir.name
        image_paths = list(iter_image_files(identity_dir))
        if not image_paths:
            continue

        current_embeddings: List[np.ndarray] = []
        current_paths: List[str] = []
        for image_path in image_paths:
            face = engine.largest_face(image_path)
            if face is None:
                print(f"[WARN] 注册图未检测到人脸，已跳过：{image_path}")
                continue
            current_embeddings.append(face.embedding)
            current_paths.append(str(image_path))

        if not current_embeddings:
            print(f"[WARN] 身份 {identity_id} 没有可用注册图，已跳过。")
            continue

        info = identity_map.get(
            identity_id,
            IdentityInfo(identity_id=identity_id, name=identity_id),
        )
        info.image_paths = current_paths
        identity_index = len(identities)
        identities.append(info)

        stacked = np.vstack(current_embeddings).astype(np.float32)
        mean_embeddings.append(normalize(stacked.mean(axis=0)))
        sample_embeddings.extend(current_embeddings)
        sample_identity_indices.extend([identity_index] * len(current_embeddings))
        sample_paths.extend(current_paths)

    if not identities:
        raise RuntimeError(f"没有从 {register_dir} 建立任何身份，请检查图片和目录结构。")

    registry = IdentityRegistry(
        identities=identities,
        mean_embeddings=np.vstack(mean_embeddings).astype(np.float32),
        sample_embeddings=np.vstack(sample_embeddings).astype(np.float32),
        sample_identity_indices=np.asarray(sample_identity_indices, dtype=np.int32),
        sample_paths=sample_paths,
    )
    if output_path is not None:
        registry.save(output_path)
    return registry
