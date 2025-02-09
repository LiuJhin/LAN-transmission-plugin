from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import os
import json
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename
from hashlib import md5
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

# 创建应用
app = Flask(__name__)

# 基础配置
app.config.update(
    UPLOAD_FOLDER='uploads',
    MAX_CONTENT_LENGTH=2 * 1024 * 1024 * 1024,  # 2GB 单文件上限
    MAX_STORAGE_SIZE=50 * 1024 * 1024 * 1024,   # 50GB 总存储上限
    MAX_FILES=100,  # 增加文件数量限制
    CHUNK_SIZE=1024 * 1024,  # 1MB 分片大小
    ALLOWED_EXTENSIONS={
        # 文档
        'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        # 图片
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp',
        # 视频
        'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv',
        # 音频
        'mp3', 'wav', 'flac', 'aac',
        # 压缩文件
        'zip', 'rar', '7z', 'tar', 'gz'
    },
    MAX_WORKERS=4,  # 并行上传的最大线程数
    CHUNK_RETRY=3,  # 分片上传重试次数
    UPLOAD_TIMEOUT=3600,  # 上传会话超时时间（秒）
)

# 首先定义所有过滤器
def file_icon_filter(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    icons = {
        'pdf': 'fa-file-pdf file-icon-pdf',
        'doc': 'fa-file-word file-icon-doc',
        'docx': 'fa-file-word file-icon-doc',
        'xls': 'fa-file-excel file-icon-doc',
        'xlsx': 'fa-file-excel file-icon-doc',
        'zip': 'fa-file-archive file-icon-zip',
        'rar': 'fa-file-archive file-icon-zip',
        '7z': 'fa-file-archive file-icon-zip',
        'png': 'fa-file-image file-icon-image',
        'jpg': 'fa-file-image file-icon-image',
        'jpeg': 'fa-file-image file-icon-image',
        'gif': 'fa-file-image file-icon-image',
        'mp3': 'fa-file-audio file-icon-audio',
        'wav': 'fa-file-audio file-icon-audio',
        'mp4': 'fa-file-video file-icon-video',
        'avi': 'fa-file-video file-icon-video',
        'mov': 'fa-file-video file-icon-video',
        'txt': 'fa-file-alt'
    }
    return icons.get(ext, 'fa-file')

def file_size_filter(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def time_filter(time_str):
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return time_str

# 注册过滤器
app.jinja_env.filters['get_file_icon'] = file_icon_filter
app.jinja_env.filters['format_file_size'] = file_size_filter
app.jinja_env.filters['format_time'] = time_filter

def get_host_info():
    return request.remote_addr

def load_file_info():
    if os.path.exists('file_info.json'):
        with open('file_info.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_file_info(file_info):
    with open('file_info.json', 'w', encoding='utf-8') as f:
        json.dump(file_info, f, ensure_ascii=False, indent=2)

# 添加存储空间检查函数
def check_storage_space():
    total_size = 0
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
        total_size += sum(os.path.getsize(os.path.join(root, name)) for name in files)
    return total_size < app.config['MAX_STORAGE_SIZE']

# 添加上传会话管理
upload_sessions = {}
upload_locks = {}

# 添加全局消息队列
message_queues = []

def send_update_notification(message):
    # 向所有连接的客户端发送更新
    for q in message_queues[:]:  # 使用切片复制防止迭代时修改
        try:
            q.put(message)
        except:
            message_queues.remove(q)

class UploadSession:
    def __init__(self, filename, total_chunks, file_hash=None):
        self.filename = filename
        self.total_chunks = total_chunks
        self.received_chunks = set()
        self.file_hash = file_hash
        self.start_time = time.time()
        self.last_update = time.time()
        self.total_bytes = 0
        self.chunk_hashes = {}

    def add_chunk(self, chunk_number, chunk_hash, chunk_size):
        self.received_chunks.add(chunk_number)
        self.chunk_hashes[chunk_number] = chunk_hash
        self.total_bytes += chunk_size
        self.last_update = time.time()

    def is_complete(self):
        return len(self.received_chunks) == self.total_chunks

    def is_expired(self):
        return time.time() - self.last_update > app.config['UPLOAD_TIMEOUT']

    def get_missing_chunks(self):
        return set(range(self.total_chunks)) - self.received_chunks

def calculate_md5(data):
    return md5(data).hexdigest()

@app.route('/')
def index():
    files = []
    file_info = load_file_info()
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    current_files = os.listdir(app.config['UPLOAD_FOLDER'])
    remaining_slots = app.config['MAX_FILES'] - len(current_files)
    
    for filename in current_files:
        if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            file_stat = os.stat(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            info = file_info.get(filename, {})
            files.append({
                'name': filename,
                'size': file_stat.st_size,
                'share_time': info.get('share_time', '未知'),
                'share_by': info.get('share_by', '未知'),
                'md5': info.get('md5', '')
            })
    
    return render_template('index.html', 
                         files=files,
                         max_files=app.config['MAX_FILES'],
                         remaining_slots=remaining_slots,
                         allowed_extensions=list(app.config['ALLOWED_EXTENSIONS']),
                         chunk_size=app.config['CHUNK_SIZE'])

@app.route('/upload/init', methods=['POST'])
def init_upload():
    filename = secure_filename(request.form['filename'])
    total_chunks = int(request.form['chunks'])
    file_hash = request.form.get('file_hash')
    
    session_id = f"{filename}_{int(time.time())}"
    upload_sessions[session_id] = UploadSession(filename, total_chunks, file_hash)
    upload_locks[session_id] = threading.Lock()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'missing_chunks': list(range(total_chunks))
    })

@app.route('/upload/status/<session_id>', methods=['GET'])
def upload_status(session_id):
    if session_id not in upload_sessions:
        return jsonify({'success': False, 'message': '上传会话不存在'})
    
    session = upload_sessions[session_id]
    missing_chunks = session.get_missing_chunks()
    
    return jsonify({
        'success': True,
        'missing_chunks': list(missing_chunks),
        'total_bytes': session.total_bytes,
        'elapsed_time': time.time() - session.start_time
    })

@app.route('/upload/chunk/<session_id>', methods=['POST'])
def upload_chunk(session_id):
    if session_id not in upload_sessions:
        return jsonify({'success': False, 'message': '上传会话不存在'})
    
    session = upload_sessions[session_id]
    chunk_number = int(request.form['chunk'])
    chunk_data = request.files['file'].read()
    chunk_hash = calculate_md5(chunk_data)
    
    with upload_locks[session_id]:
        # 保存分片
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', session_id)
        os.makedirs(temp_dir, exist_ok=True)
        chunk_path = os.path.join(temp_dir, f'chunk_{chunk_number}')
        
        with open(chunk_path, 'wb') as f:
            f.write(chunk_data)
        
        session.add_chunk(chunk_number, chunk_hash, len(chunk_data))
        
        # 检查是否所有分片都已上传
        if session.is_complete():
            try:
                # 合并文件
                final_path = os.path.join(app.config['UPLOAD_FOLDER'], session.filename)
                with open(final_path, 'wb') as f:
                    for i in range(session.total_chunks):
                        chunk_path = os.path.join(temp_dir, f'chunk_{i}')
                        with open(chunk_path, 'rb') as chunk:
                            f.write(chunk.read())
                
                # 验证文件完整性
                if session.file_hash:
                    with open(final_path, 'rb') as f:
                        final_hash = calculate_md5(f.read())
                        if final_hash != session.file_hash:
                            raise ValueError('文件校验失败')
                
                # 清理临时文件
                shutil.rmtree(temp_dir)
                del upload_sessions[session_id]
                del upload_locks[session_id]
                
                # 更新文件信息
                file_info = load_file_info()
                file_info[session.filename] = {
                    'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'share_by': get_host_info(),
                    'md5': session.file_hash
                }
                save_file_info(file_info)
                
                # 发送更新通知
                send_update_notification({
                    'type': 'new_file',
                    'filename': session.filename,
                    'size': os.path.getsize(final_path),
                    'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'share_by': get_host_info()
                })
                
                return jsonify({
                    'success': True,
                    'message': '文件上传完成',
                    'speed': session.total_bytes / (time.time() - session.start_time)
                })
                
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
    
    return jsonify({'success': True, 'message': '分片上传成功'})

@app.route('/download/<filename>')
def download_file(filename):
    # 添加大文件支持
    return send_from_directory(app.config['UPLOAD_FOLDER'], 
                             filename,
                             as_attachment=True,
                             max_age=0)  # 禁用缓存，确保大文件正确下载

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # 更新文件信息
            file_info = load_file_info()
            if filename in file_info:
                del file_info[filename]
                save_file_info(file_info)
            
            return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# 添加定期清理过期会话的任务
def cleanup_sessions():
    while True:
        time.sleep(300)  # 每5分钟检查一次
        expired_sessions = []
        for session_id, session in upload_sessions.items():
            if session.is_expired():
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', session_id)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            del upload_sessions[session_id]
            del upload_locks[session_id]

# 启动清理任务
cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
cleanup_thread.start()

@app.route('/events')
def events():
    def event_stream():
        q = queue.Queue()
        message_queues.append(q)
        try:
            while True:
                message = q.get()  # 阻塞等待直到有新消息
                yield f"data: {json.dumps(message)}\n\n"
        except:
            message_queues.remove(q)
    
    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 