# Backend API

后端使用 FastAPI，默认地址：

```text
http://127.0.0.1:8000
```

启动后端：

```powershell
python -m backend.cli api --host 127.0.0.1 --port 8000
```

GPU 启动：

```powershell
python -m backend.cli --ctx-id 0 api --host 127.0.0.1 --port 8000
```

后端支持两个身份库：

```text
self   -> outputs/identity_registry.npz
celeba -> outputs/celeba_registry.npz
```

## 1. 健康检查

```http
GET /health
```

返回示例：

```json
{
  "status": "ok",
  "default_dataset": "self",
  "datasets": ["self", "celeba"],
  "registries": {
    "self": {
      "path": "outputs/identity_registry.npz",
      "exists": true
    },
    "celeba": {
      "path": "outputs/celeba_registry.npz",
      "exists": true
    }
  }
}
```

前端可用它检查后端是否启动、两个身份库是否存在，并据此启用/禁用身份库切换选项。

## 2. 单张图片识别

```http
POST /recognize
```

请求类型：`multipart/form-data`

字段：

```text
file: 图片文件，必填
dataset: 使用哪个身份库，可选，self 或 celeba，默认 self
draw: 是否返回画框图，可选，默认 true
```

返回示例：

```json
{
  "dataset": "self",
  "image": "outputs/uploads/xxx.jpg",
  "face_count": 2,
  "faces": [
    {
      "identity_id": "p01",
      "name": "成龙",
      "score": 0.7234,
      "is_unknown": false,
      "bbox": [120, 45, 140, 185],
      "det_score": 0.9651
    },
    {
      "identity_id": "unknown",
      "name": "unknown",
      "score": 0.4123,
      "is_unknown": true,
      "bbox": [360, 70, 110, 150],
      "det_score": 0.9422
    }
  ],
  "annotated_image": "data:image/jpeg;base64,...",
  "annotated_image_path": "outputs/results/xxx_self_result.jpg"
}
```

字段说明：

```text
dataset: 本次识别使用的身份库
face_count: 检测到的人脸数量
faces: 每张人脸的识别结果
identity_id: 身份编号，如 p01；陌生人是 unknown；CelebA 是 identity_xxxxx
name: 姓名；CelebA 默认与 identity_id 相同；陌生人是 unknown
score: 人脸识别相似度，越高越像
is_unknown: 是否被判定为陌生人。self 是开放集；celeba 是闭集，通常不会返回 unknown
bbox: 人脸框，[x, y, width, height]，单位是像素
det_score: 人脸检测置信度
annotated_image: base64 结果图，可直接作为 img src
annotated_image_path: 后端本地保存的结果图路径
```

前端 fetch 示例：

```js
async function recognizeImage(file, dataset = 'self') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('dataset', dataset);

  const response = await fetch('http://127.0.0.1:8000/recognize', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Recognize failed: ${response.status}`);
  }

  return await response.json();
}
```

显示结果图：

```js
const result = await recognizeImage(file, 'self');
imageElement.src = result.annotated_image;
```

## 3. 重新加载身份库

```http
POST /reload-registry
```

可选字段/查询参数：

```text
dataset: self 或 celeba。不传则清空并重载全部缓存。
```

当后端服务已经启动，但你重新运行了 `build self` 或 `build celeba` 覆盖身份库时，可以调用这个接口让 API 重新读取最新身份库，不用重启服务。

返回示例：

```json
{
  "status": "reloaded",
  "dataset": "self"
}
```

如果前端不需要管理身份库，可以不使用这个接口。
