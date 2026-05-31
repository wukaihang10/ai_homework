# AI 实验人脸识别系统

这是一个面向人工智能课程实验的人脸识别项目，包含前端控制台、FastAPI 后端、人脸识别模型封装、身份库构建工具和数据集评测流程。

项目支持两类数据集：

- 自采集 20 人数据集：用于开放集识别，可识别已注册人员，也可将低相似度人脸判定为 `unknown`。
- CelebA 100 类数据集：用于闭集身份识别和准确率评测。

## 项目结构

```text
.
  backend/                         后端代码和命令行工具
  fronted/                         前端控制台
  dataset/                         自采集数据集
  celeba_100_identities_3reg_3test/ CelebA 100 类数据集
  models/                          InsightFace 模型缓存
  outputs/                         身份库、上传图片和识别结果输出
  scripts/                         辅助脚本
  requirements.txt                 Python 依赖
```

## 技术栈

- 后端：Python、FastAPI、Uvicorn
- 人脸识别：InsightFace、ONNX Runtime、OpenCV
- 数据处理：NumPy、Pillow
- 前端：原生 HTML、CSS、JavaScript

## 快速开始

首次在电脑使用这个程序，会网络请求下载模型，比较慢。本来想把模型上传到github，但是文件太大上传不了。

注意：requirements.txt文件内写了“onnxruntime-gpu[cuda,cudnn]>=1.26.0”来为虚拟环境安装cuda相关依赖包，但包比较大，下载比较慢；如果电脑内已装了cuda且配置好了环境变量，可以删去这一行。如果后续出现依赖问题，再加上这一行并重新执行“pip install -r requirements.txt”。

建议使用 Python 3.12 或 3.13：

```powershell
conda create -n face-ai python=3.13
conda activate face-ai
pip install -r requirements.txt
```

如果只使用 CPU，后续命令不需要加额外参数。

如果使用 NVIDIA GPU，先在终端检查显卡驱动：

```powershell
nvidia-smi
```

需要确认 `nvidia-smi` 可以正常显示显卡和 Driver Version，并且驱动版本能够支持当前环境中 ONNX Runtime GPU 所需的 CUDA 运行时（本项目使用 onnxruntime-gpu[cuda,cudnn]，对应 CUDA 12.x 运行时和 cuDNN 9.x）。如果命令不可用、驱动版本过旧，或不确定兼容性，建议先使用 CPU 版本命令完成实验。

第一次运行项目前，必须先构建身份库。如果以下文件不存在，就需要运行对应命令（在github上下载的项目身份库已经建好了；当然后续注册图改变了需要重新构建）：

```text
outputs/identity_registry.npz
outputs/celeba_registry.npz
```

CPU 版本：

```powershell
python -m backend.cli build self
python -m backend.cli build celeba
```

GPU 版本：

```powershell
python -m backend.cli --ctx-id 0 build self
python -m backend.cli --ctx-id 0 build celeba
```

如果需要在前端或命令行中评测自采集 20 人数据集，还需要准备 `dataset/test/annotations.jsonl`。如果该文件不存在，运行（在github上下载的项目已经包含此文件；当然后续测试图变了需要重新构建）：

CPU 版本：

```powershell
python -m backend.cli annotate self
```

GPU 版本：

```powershell
python -m backend.cli --ctx-id 0 annotate self
```

启动后端服务：

CPU 版本：

```powershell
python -m backend.cli api --host 127.0.0.1 --port 8000
```

GPU 版本：

```powershell
python -m backend.cli --ctx-id 0 api --host 127.0.0.1 --port 8000
```

打开前端：

```text
fronted/index.html
```

前端默认连接 `http://127.0.0.1:8000`。

## 主要流程

1. 准备注册集和测试集。
2. 运行 `build self` 或 `build celeba` 构建身份库。
3. 运行 `annotate self` 创建 `dataset/test/annotations.jsonl`
4. 启动 FastAPI 后端服务。
5. 打开前端控制台，选择身份库并上传图片识别。
6. 在评测页运行测试集评测，查看准确率和错误样例。

## 后端终端命令

以下命令是用户在终端中直接使用的后端命令。前端内部调用的 HTTP 接口不在这里展开。

全局参数需要放在子命令前面，例如：

```powershell
python -m backend.cli --ctx-id 0 build self
```

常用全局参数：

```text
--ctx-id -1              使用 CPU，默认值
--ctx-id 0               使用第 1 张 NVIDIA GPU
--model-name buffalo_l   InsightFace 模型名，默认 buffalo_l
--model-root models/insightface
                         模型缓存目录
--det-size 640 640       人脸检测输入尺寸
```

### 构建身份库

自采集 20 人数据集：

```powershell
python -m backend.cli build self
python -m backend.cli --ctx-id 0 build self
```

CelebA 100 类数据集：

```powershell
python -m backend.cli build celeba
python -m backend.cli --ctx-id 0 build celeba
```

### 生成自采集数据集标注

用于生成 `dataset/test/annotations.jsonl`。

```powershell
python -m backend.cli annotate self
python -m backend.cli --ctx-id 0 annotate self
```

可选参数：

```text
--threshold FLOAT   自定义 unknown 判定阈值
```

示例：

```powershell
python -m backend.cli annotate self --threshold 0.45
python -m backend.cli --ctx-id 0 annotate self --threshold 0.45
```

### 命令行评测

自采集 20 人数据集：

```powershell
python -m backend.cli eval self
python -m backend.cli --ctx-id 0 eval self
```

CelebA 100 类数据集：

```powershell
python -m backend.cli eval celeba
python -m backend.cli --ctx-id 0 eval celeba
```

可选参数：

```text
--threshold FLOAT   自定义 unknown 判定阈值
```

### 单张图片识别

CPU 版本：

```powershell
python -m backend.cli infer self dataset/test/images/p01_t01.jpg
```

GPU 版本：

```powershell
python -m backend.cli --ctx-id 0 infer self dataset/test/images/p01_t01.jpg
```

CelebA 示例：

```powershell
python -m backend.cli infer celeba celeba_100_identities_3reg_3test/test/identity_00070/008180.jpg
python -m backend.cli --ctx-id 0 infer celeba celeba_100_identities_3reg_3test/test/identity_00070/008180.jpg
```

可选参数：

```text
--threshold FLOAT       自定义 unknown 判定阈值
--output-image PATH     指定画框结果图保存路径
--no-draw               只输出 JSON，不保存画框结果图
```

### 启动后端服务

CPU 版本：

```powershell
python -m backend.cli api --host 127.0.0.1 --port 8000
```

GPU 版本：

```powershell
python -m backend.cli --ctx-id 0 api --host 127.0.0.1 --port 8000
```

可选参数：

```text
--host HOST   服务监听地址，默认 127.0.0.1
--port PORT   服务端口，默认 8000
```

## 输出文件

```text
outputs/identity_registry.npz      自采集 20 人身份库
outputs/celeba_registry.npz        CelebA 100 类身份库
outputs/uploads/                   前端上传图片缓存
outputs/results/                   画框后的识别结果图
dataset/test/annotations.jsonl     自采集测试集标注
```

## 更多说明

- 后端说明见 `backend/README.md`。
- 前端说明见 `fronted/README.md`。
- 辅助脚本说明见 `scripts/README.md`。
