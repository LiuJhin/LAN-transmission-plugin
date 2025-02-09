# 局域网文件传输工具

一个基于 Flask 的局域网文件传输工具，支持多文件上传、断点续传、实时进度显示和文件管理功能。

## 特性

- 🚀 支持大文件上传（最大 2GB）
- 💨 分片上传和断点续传
- 📊 实时上传进度显示
- 🔔 新文件上传通知
- 📱 响应式设计，支持移动端
- 🎯 拖拽上传
- 🔄 自动刷新文件列表
- 🎨 美观的用户界面
- 🛡️ 文件完整性校验

## 支持的文件类型

- 文档：txt, pdf, doc, docx, xls, xlsx, ppt, pptx
- 图片：png, jpg, jpeg, gif, bmp, webp
- 视频：mp4, avi, mov, wmv, flv, mkv
- 音频：mp3, wav, flac, aac
- 压缩包：zip, rar, 7z, tar, gz

## 安装要求

- Python 3.7+
- Flask
- 现代浏览器（支持 ES6+）

## 快速开始

1. 克隆仓库：

```bash
git clone [repository-url]
cd lan-file-transfer
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行服务器：

```bash
python server.py
```

4. 访问地址：
