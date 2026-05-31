# 图片批量转 JPG

这个脚本用于把 `dataset/` 里的图片批量转成 JPG，并输出到 `dataset_new/`，保持原目录结构不变。

## 快速使用

在项目根目录运行：

```
python scripts/convert_to_jpg.py
```

默认行为：
- 扫描 `dataset/`
- 输出到 `dataset_new/`
- **不删除**原图
- 转换格式：`webp/png/jpeg/jpg/bmp/gif`

## 常用参数

- 指定输入目录：
```
python scripts/convert_to_jpg.py --root dataset
```

- 指定输出目录：
```
python scripts/convert_to_jpg.py --output-root dataset_new
```

- 转换后删除原图（谨慎使用）：
```
python scripts/convert_to_jpg.py --delete-original
```

- 只转换部分格式：
```
python scripts/convert_to_jpg.py --formats webp,png
```

## 输出结构示例

```
dataset/registered/p01/abc.webp
-> dataset_new/registered/p01/abc.jpg
```

如果有问题，可以继续找我帮你改。
