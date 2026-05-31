# 后端 README

本目录是项目的后端模块，负责完成人脸检测、人脸特征提取、身份库构建、单图识别、数据集评测以及给前端提供 API 服务。

后端基于 InsightFace 完成人脸检测、对齐和 embedding 提取，使用余弦相似度把待识别人脸与身份库中的注册人脸进行匹配。自采集数据集按开放集处理，低于阈值时可判定为 `unknown`；CelebA 100 类数据集按闭集评测。

## 目录说明

```text
backend/
  api.py          FastAPI 服务，提供前端调用接口
  cli.py          命令行入口，支持建库、标注、评测、推理和启动 API
  config.py       模型、路径和运行参数配置
  datasets.py     数据集标注和评测逻辑
  face_engine.py  InsightFace 封装
  models.py       识别结果等数据结构
  recognizer.py   人脸匹配与结果画框
  registry.py     身份库构建、保存和读取
```

## 环境安装

建议使用 Python 3.12 或 3.13：

```powershell
conda create -n face-ai python=3.13
conda activate face-ai
pip install -r requirements.txt
```

首次运行时，InsightFace 会把模型下载到 `models/insightface/`，之后推理会直接使用本地模型。

默认使用 CPU。若有 NVIDIA 显卡，可在命令中加入 `--ctx-id 0` 使用 GPU。注意 `--ctx-id 0` 是全局参数，需要放在子命令前面。

## 构建身份库

自采集 20 人身份库：

```powershell
python -m backend.cli build self
```

CelebA 100 类身份库：

```powershell
python -m backend.cli build celeba
```

GPU 示例：

```powershell
python -m backend.cli --ctx-id 0 build self
python -m backend.cli --ctx-id 0 build celeba
```

默认输出：

```text
outputs/identity_registry.npz
outputs/celeba_registry.npz
```

注册集不变时，不需要重复建库。

## 生成自采集数据集标注

```powershell
python -m backend.cli annotate self
```

输出文件：

```text
dataset/test/annotations.jsonl
```

该文件用于自采集 20 人数据集评测。生成后建议人工检查并修正明显错误。

## 命令行评测

```powershell
python -m backend.cli eval self
python -m backend.cli eval celeba
```

自采集数据集会读取 `dataset/test/annotations.jsonl`；CelebA 数据集会使用 `test/identity_xxxxx/` 文件夹名作为真实身份。

## 单张图片推理

```powershell
python -m backend.cli infer self dataset/test/images/p01_t01.jpg
python -m backend.cli infer celeba celeba_100_identities_3reg_3test/test/identity_00070/008180.jpg
```

命令会输出 JSON，并默认把带人脸框和姓名的结果图保存到 `outputs/results/`。如果只需要 JSON，可添加 `--no-draw`。

## 启动 API 服务

```powershell
python -m backend.cli api --host 127.0.0.1 --port 8000
```

GPU 示例：

```powershell
python -m backend.cli --ctx-id 0 api --host 127.0.0.1 --port 8000
```

主要接口：

```text
GET  /health              检查后端状态和身份库是否存在
POST /recognize           上传单张图片并返回识别结果
POST /recognize-path      识别后端本地测试集图片
GET  /evaluation/images   获取评测图片列表
POST /evaluation/run      运行评测
POST /reload-registry     重新加载身份库缓存
```

前端默认调用：

```text
http://127.0.0.1:8000
```

如果重新构建了身份库，可以调用 `/reload-registry` 或点击前端的“重新加载身份库”按钮，无需重启后端。
