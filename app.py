import os
import json
import shutil
import datetime
import hashlib
import logging
import re
import socket
from logging.handlers import RotatingFileHandler
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, abort, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 适配 Nginx 反向代理
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- 日志系统配置 ---
file_handler = RotatingFileHandler('server.log', maxBytes=1*1024*1024, backupCount=10, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
file_handler.setLevel(logging.INFO)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Load config
CONFIG_FILE = 'config.json'

def load_config():
    config = {"password": "admin", "port": 5000, "root_dir": "./files_root"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            try:
                config.update(json.load(f))
            except json.JSONDecodeError:
                pass
    
    if 'secret_key' not in config:
        config['secret_key'] = os.urandom(24).hex()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    
    pwd = config.get('password', 'admin')
    
    if not pwd.startswith('sha256:'):
        print("Hashing plain text password in config...")
        salt = os.urandom(8).hex()
        hashed_pwd = hashlib.sha256((salt + pwd).encode()).hexdigest()
        config['password'] = f"sha256:{salt}${hashed_pwd}"
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
            
    return config

def check_password(stored_password, provided_password):
    if stored_password.startswith('sha256:'):
        try:
            _, rest = stored_password.split(':', 1)
            salt, hash_val = rest.split('$', 1)
            calculated_hash = hashlib.sha256((salt + provided_password).encode()).hexdigest()
            return calculated_hash == hash_val
        except ValueError:
            return False
    return False

config = load_config()
app.secret_key = config.get('secret_key') 

ROOT_DIR = os.path.abspath(config.get('root_dir', './files_root'))
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)

# --- CSRF Protection ---
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = os.urandom(16).hex()
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('_csrf_token')
        if not token or token != request.form.get('_csrf_token'):
            # AJAX requests might send token in headers
            if token != request.headers.get('X-CSRF-Token'):
                 abort(403)

@app.after_request
def log_request(response):
    app.logger.info(f"[{request.remote_addr}] ACCESS {request.method} {request.path} {response.status_code}")
    return response

# Improved safe path check
def is_safe_path(path):
    abs_path = os.path.abspath(path)
    root = os.path.abspath(ROOT_DIR)
    return os.path.normcase(abs_path).startswith(os.path.normcase(root))

# Filename validation
def is_valid_name(name):
    # Disallow path separators and control characters
    if not name or name == '.' or name == '..': return False
    # Check for invalid characters on Windows/Linux
    return not re.search(r'[\\/:\*\?"<>\|]', name)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('index', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def format_size(size):
    if size == "-":
        return "-"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def get_file_info(path):
    full_path = os.path.join(ROOT_DIR, path)
    if not is_safe_path(full_path):
        return None
    
    items = []
    try:
        with os.scandir(full_path) as entries:
            for entry in entries:
                stats = entry.stat()
                size = "-" if entry.is_dir() else stats.st_size
                mtime = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                items.append({
                    'name': entry.name,
                    'is_dir': entry.is_dir(),
                    'size': size,
                    'formatted_size': format_size(size) if size != "-" else "-",
                    'mtime': mtime,
                    'mtime_ts': stats.st_mtime
                })
    except PermissionError:
        pass
    except FileNotFoundError:
        pass
        
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return items

@app.route('/')
@app.route('/browse/')
@app.route('/browse/<path:req_path>')
def index(req_path=''):
    if req_path:
        abs_path = os.path.abspath(os.path.join(ROOT_DIR, req_path))
    else:
        abs_path = ROOT_DIR

    if not is_safe_path(abs_path):
        abort(403)
        
    if not os.path.exists(abs_path):
        abort(404)
    
    if os.path.isfile(abs_path):
        app.logger.info(f"[{request.remote_addr}] DOWNLOAD FILE: {req_path}")
        return send_from_directory(os.path.dirname(abs_path), os.path.basename(abs_path))
        
    files = get_file_info(req_path)
    
    parent_path = None
    if req_path:
        parent_path = os.path.dirname(req_path)
        
    return render_template('index.html', files=files, current_path=req_path, parent_path=parent_path, logged_in=session.get('logged_in'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password_candidate = request.form.get('password')
        current_config = load_config()
        stored_password = current_config.get('password')
        
        next_url = request.args.get('next') or request.referrer or url_for('index')
        
        if '/login' in next_url:
             next_url = url_for('index')

        if check_password(stored_password, password_candidate):
            session['logged_in'] = True
            app.logger.info(f"[{request.remote_addr}] LOGIN SUCCESS")
            return redirect(next_url)
        else:
            flash('Invalid password')
            app.logger.warning(f"[{request.remote_addr}] LOGIN FAILED")
            return redirect(next_url)
            
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    app.logger.info(f"[{request.remote_addr}] LOGOUT")
    return redirect(request.referrer or url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    # Handle folder upload or multi-file upload
    path = request.form.get('path', '')
    
    # We use request.files.getlist to handle multiple files
    files = request.files.getlist('file')
    
    if not files:
        return jsonify({"error": "No files received"}), 400
        
    uploaded_count = 0
    skipped_files = []
    
    # Check if this is a folder upload (webkitRelativePath is sent as file.filename usually includes paths)
    # Flask/Werkzeug 0.15+ handles paths in filename if configured, but secure_filename strips them.
    # We need to trust the paths for folder structure reconstruction, but validate them.
    
    for file in files:
        if file.filename == '':
            continue
            
        # file.filename contains relative path for folder uploads (e.g. "myfolder/file.txt")
        # For regular uploads, it's just "file.txt"
        
        # Validate all parts of the path
        parts = file.filename.replace('\\', '/').split('/')
        is_valid = True
        for part in parts:
            if not is_valid_name(part):
                is_valid = False
                break
        
        if not is_valid:
            skipped_files.append(file.filename)
            app.logger.warning(f"[{request.remote_addr}] SKIP invalid name: {file.filename}")
            continue
            
        # Construct full save path
        # join ROOT_DIR, current browsed path, and the relative file path
        full_save_path = os.path.join(ROOT_DIR, path, *parts)
        
        # Security check: must be inside ROOT_DIR
        if not is_safe_path(full_save_path):
            skipped_files.append(file.filename)
            app.logger.error(f"[{request.remote_addr}] UNSAFE PATH attempted: {full_save_path}")
            continue
            
        # Create directories if needed
        os.makedirs(os.path.dirname(full_save_path), exist_ok=True)
        
        try:
            file.save(full_save_path)
            uploaded_count += 1
        except Exception as e:
            app.logger.error(f"Upload error: {e}")
            skipped_files.append(file.filename)

    app.logger.info(f"[{request.remote_addr}] UPLOAD BATCH: {uploaded_count} files to {path}")
    
    return jsonify({
        "message": f"Upload complete. {uploaded_count} files uploaded.",
        "skipped_files": skipped_files,
        "count": uploaded_count
    })

@app.route('/mkdir', methods=['POST'])
@login_required
def mkdir():
    path = request.form.get('path', '')
    dirname = request.form.get('dirname')
    if dirname and is_valid_name(dirname):
        new_dir_path = os.path.join(ROOT_DIR, path, dirname)
        if not is_safe_path(new_dir_path):
             abort(403)
        os.makedirs(new_dir_path, exist_ok=True)
        app.logger.info(f"[{request.remote_addr}] CREATE DIR: {dirname} in {path}")
    else:
        # For non-ajax, flash message. For ajax future proofing, maybe return json.
        # But mkdir is currently simple form post.
        flash("Invalid folder name.")
    return redirect(url_for('index', req_path=path))

@app.route('/delete', methods=['POST'])
@login_required
def delete():
    path = request.form.get('path', '')
    name = request.form.get('name')
    
    if not name:
        flash('Invalid request')
        return redirect(url_for('index', req_path=path))
        
    full_path = os.path.join(ROOT_DIR, path, name)
    
    if not is_safe_path(full_path):
         abort(403)
         
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
            app.logger.info(f"[{request.remote_addr}] DELETE DIR: {name} from {path}")
        else:
            os.remove(full_path)
            app.logger.info(f"[{request.remote_addr}] DELETE FILE: {name} from {path}")
            
    return redirect(url_for('index', req_path=path))

@app.route('/rename', methods=['POST'])
@login_required
def rename():
    path = request.form.get('path', '')
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name')
    
    if not old_name or not new_name or not is_valid_name(new_name):
        flash('Invalid request or new name.')
        return redirect(url_for('index', req_path=path))
    
    old_path = os.path.join(ROOT_DIR, path, old_name)
    new_path = os.path.join(ROOT_DIR, path, new_name)
    
    if not is_safe_path(old_path) or \
       not is_safe_path(new_path):
         abort(403)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        app.logger.info(f"[{request.remote_addr}] RENAME: {old_name} -> {new_name} in {path}")
        
    return redirect(url_for('index', req_path=path))

if __name__ == '__main__':
    # Get port from config, but don't auto-increment it.
    # The auto-increment logic is flawed in debug mode because the reloader 
    # starts a second process, which finds the port busy and switches to the next one,
    # causing a loop or constant port switching.
    # It's better to just fail if port is busy, or let user configure it.
    # Or, if we really want auto-switching, we should do it only if NOT in debug mode reloader.
    
    port = config.get('port', 5000)
    
    # Check if we are in the main process (not the reloader child) to avoid double checking
    # But simpler is to just run. If port is busy, Flask will throw error.
    # The user's issue "switching to 5001" is because my previous code added this logic.
    # I should remove the auto-switching logic to fix the "bug" of changing ports unexpectedly
    # and updating config.json which causes reloads.
    
    print(f"Server starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
