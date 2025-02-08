from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
from datetime import datetime

# 创建应用
app = Flask(__name__)

# 基础配置
app.config.update(
    UPLOAD_FOLDER='uploads',
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 50MB
    MAX_FILES=10,
    ALLOWED_EXTENSIONS={'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
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

@app.route('/')
def index():
    files = []
    file_info = load_file_info()
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    current_files = os.listdir(app.config['UPLOAD_FOLDER'])
    remaining_slots = app.config['MAX_FILES'] - len(current_files)
    
    for filename in current_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        info = file_info.get(filename, {})
        
        if not info:
            info = {
                'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'share_by': get_host_info()
            }
            file_info[filename] = info
            save_file_info(file_info)
        
        file_size = os.path.getsize(file_path)
        
        files.append({
            'name': filename,
            'share_time': info.get('share_time', '未知'),
            'share_by': info.get('share_by', '未知'),
            'size': file_size
        })
    
    return render_template('index.html', 
                         files=files,
                         max_size=app.config['MAX_CONTENT_LENGTH'],
                         max_files=app.config['MAX_FILES'],
                         remaining_slots=remaining_slots,
                         allowed_extensions=list(app.config['ALLOWED_EXTENSIONS']))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件被上传'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    if file:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # 更新文件信息
        file_info = load_file_info()
        file_info[filename] = {
            'share_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'share_by': get_host_info()
        }
        save_file_info(file_info)
        
        return jsonify({'success': True})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 