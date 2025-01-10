# app.py
from flask import Flask, render_template, request, session, send_from_directory
from flask_socketio import SocketIO, emit
import secrets
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'uploads'
# 增加最大文件大小到50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

# 定义文件大小限制（以字节为单位）
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# 确保上传目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

socketio = SocketIO(app)
online_users = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(file):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


@app.route('/')
def index():
    if 'username' not in session:
        return render_template('login.html')
    return render_template('chat.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    if username:
        session['username'] = username
    return render_template('chat.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return {'error': 'No file part'}, 400

    file = request.files['file']
    if file.filename == '':
        return {'error': '没有选择文件'}, 400

    # 检查文件大小
    file_size = get_file_size(file)
    if file_size > MAX_FILE_SIZE:
        return {'error': f'文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）'}, 413

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            # 添加时间戳或随机字符串以确保文件名唯一
            unique_filename = f"{secrets.token_hex(8)}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)

            # 获取文件类型
            file_ext = filename.rsplit('.', 1)[1].lower()
            is_image = file_ext in {'png', 'jpg', 'jpeg', 'gif'}

            # 通过WebSocket广播文件消息
            username = session.get('username', 'Anonymous')
            socketio.emit('message', {
                'user': username,
                'msg': f'分享了一个文件: {filename}',
                'file': {
                    'name': filename,
                    'path': unique_filename,
                    'is_image': is_image
                }
            }, include_self=True)

            return {'success': True, 'filename': unique_filename}
        except Exception as e:
            return {'error': f'文件上传失败: {str(e)}'}, 500

    return {'error': '不支持的文件类型'}, 400


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@socketio.on('connect')
def handle_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        emit('user_list', list(online_users.keys()), broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        del online_users[session['username']]
        emit('user_list', list(online_users.keys()), broadcast=True)


@socketio.on('message')
def handle_message(message):
    username = session.get('username', 'Anonymous')
    emit('message', {'user': username, 'msg': message}, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)