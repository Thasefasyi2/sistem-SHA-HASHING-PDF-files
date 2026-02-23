"""
PDF Verification System
Sistem verifikasi akses file PDF menggunakan Flask, PostgreSQL, dan SHA256
"""

import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import qrcode
from PIL import Image
import io
import base64

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'storage/pdf'
QR_CODE_FOLDER = 'static/qrcodes'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'pdf_verification'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_CODE_FOLDER, exist_ok=True)


def get_db_connection():
    """Create and return database connection"""
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create pdf_files table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pdf_files (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255) NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            bodyteks VARCHAR(255) NOT NULL,
            sha_key TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully!")


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def calculate_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_sha_key(secret_key, bodyteks, file_hash):
    """Generate SHA key from secret key, bodyteks, and file hash"""
    combined = f"{secret_key}{bodyteks}{file_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()


def generate_qr_code(data):
    """Generate QR code from data and return as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str


def save_qr_code(data, filename):
    """Save QR code to file and return path"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to file
    qr_path = os.path.join(QR_CODE_FOLDER, f"qr_{filename}.png")
    img.save(qr_path)
    
    return qr_path


def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Akses ditolak. Hanya admin yang boleh mengakses.', 'danger')
            return redirect(url_for('user_panel'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Redirect to appropriate panel based on role"""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_panel'))
        else:
            return redirect(url_for('user_panel'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email dan password wajib diisi', 'danger')
            return render_template('login.html')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and verify_password(password, user['password_hash']):
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['role'] = user['role']
            flash(f'Selamat datang, {user["email"]}!', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('user_panel'))
        else:
            flash('Email atau password salah', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Anda telah logout', 'info')
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def admin_panel():
    """Admin panel - Manage PDFs"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT p.*, u.email as creator_email 
        FROM pdf_files p 
        LEFT JOIN users u ON p.created_by = u.id 
        ORDER BY p.created_at DESC
    ''')
    pdfs = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('admin.html', pdfs=pdfs)


@app.route('/admin/upload', methods=['POST'])
@admin_required
def upload_pdf():
    """Handle PDF upload from admin"""
    if 'pdf_file' not in request.files:
        flash('Tidak ada file yang dipilih', 'danger')
        return redirect(url_for('admin_panel'))
    
    file = request.files['pdf_file']
    bodyteks = request.form.get('bodyteks', '').strip().upper()
    
    if file.filename == '':
        flash('Tidak ada file yang dipilih', 'danger')
        return redirect(url_for('admin_panel'))
    
    if not bodyteks:
        flash('Bodyteks (kode akses) wajib diisi', 'danger')
        return redirect(url_for('admin_panel'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Add timestamp to filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Calculate file hash
        file_hash = calculate_file_hash(file_path)
        
        # Generate SHA key
        secret_key = os.getenv('SECRET_KEY', 'default-secret')
        sha_key = generate_sha_key(secret_key, bodyteks, file_hash)
        
        # Save to database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO pdf_files (file_name, file_path, file_hash, bodyteks, sha_key, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (filename, file_path, file_hash, bodyteks, sha_key, session['user_id']))
        pdf_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Generate QR code
        qr_base64 = generate_qr_code(bodyteks)
        qr_path = save_qr_code(bodyteks, filename)
        
        flash(f'PDF berhasil diupload! ID: {pdf_id}', 'success')
        return render_template('admin.html', qr_code=qr_base64, bodyteks=bodyteks, 
                             qr_path=qr_path, show_qr=True)
    
    flash('File tidak valid. Hanya file PDF yang diperbolehkan.', 'danger')
    return redirect(url_for('admin_panel'))


@app.route('/admin/qr/<int:pdf_id>')
@admin_required
def get_qr_code(pdf_id):
    """Get QR code for specific PDF"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()
    
    if not pdf:
        flash('PDF tidak ditemukan', 'danger')
        return redirect(url_for('admin_panel'))
    
    # Note: We need to store bodyteks or regenerate it somehow
    # For now, we'll just show a message that bodyteks should be kept
    return jsonify({
        'message': 'QR Code dapat dibuat dari bodyteks yang telah disimpan'
    })


@app.route('/admin/delete/<int:pdf_id>', methods=['POST'])
@admin_required
def delete_pdf(pdf_id):
    """Delete PDF file"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    
    if pdf:
        # Delete file from storage
        try:
            if os.path.exists(pdf['file_path']):
                os.remove(pdf['file_path'])
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        # Delete QR code if exists
        qr_path = os.path.join(QR_CODE_FOLDER, f"qr_{pdf['file_name']}.png")
        try:
            if os.path.exists(qr_path):
                os.remove(qr_path)
        except Exception as e:
            print(f"Error deleting QR: {e}")
        
        # Delete from database
        cur.execute('DELETE FROM pdf_files WHERE id = %s', (pdf_id,))
        conn.commit()
        flash('PDF berhasil dihapus', 'success')
    else:
        flash('PDF tidak ditemukan', 'danger')
    
    cur.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/view-qr/<int:pdf_id>')
@admin_required
def view_qr(pdf_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()

    if not pdf:
        flash('PDF tidak ditemukan', 'danger')
        return redirect(url_for('admin_panel'))

    # Generate ulang QR dari bodyteks yang tersimpan
    qr_base64 = generate_qr_code(pdf['bodyteks'])

    return render_template(
        'view_qr.html',
        pdf=pdf,
        qr_code=qr_base64
    )

@app.route('/user')
@login_required
def user_panel():
    """User panel - Gallery of PDFs"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT id, file_name, created_at, created_by 
        FROM pdf_files 
        ORDER BY created_at DESC
    ''')
    pdfs = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('user.html', pdfs=pdfs)


@app.route('/user/verify', methods=['POST'])
@login_required
def verify_access():
    """Verify bodyteks and grant access to PDF"""
    pdf_id = request.form.get('pdf_id')
    bodyteks = request.form.get('bodyteks', '').strip().upper()
    
    if not pdf_id or not bodyteks:
        return jsonify({'success': False, 'message': 'PDF ID dan bodyteks wajib diisi'})
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()
    
    if not pdf:
        return jsonify({'success': False, 'message': 'PDF tidak ditemukan'})
    
    # Generate SHA key from input
    secret_key = os.getenv('SECRET_KEY', 'default-secret')
    generated_sha = generate_sha_key(secret_key, bodyteks, pdf['file_hash'])
    
    # Verify
    if generated_sha == pdf['sha_key']:
        return jsonify({
            'success': True,
            'pdf_id': pdf_id,
            'file_name': pdf['file_name'],
            'file_path': pdf['file_path'],
            'download_url': url_for('download_pdf', pdf_id=pdf_id, _external=True),
            'preview_url': url_for('preview_pdf', pdf_id=pdf_id, _external=True)
        })
    else:
        return jsonify({'success': False, 'message': 'Kode akses salah. Silakan coba lagi.'})


@app.route('/preview/<int:pdf_id>')
@login_required
def preview_pdf(pdf_id):
    """Preview PDF file (requires verification first via AJAX)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()
    
    if not pdf:
        flash('PDF tidak ditemukan', 'danger')
        return redirect(url_for('user_panel'))
    
    if os.path.exists(pdf['file_path']):
        return send_file(pdf['file_path'], mimetype='application/pdf')
    else:
        flash('File PDF tidak ditemukan di server', 'danger')
        return redirect(url_for('user_panel'))


@app.route('/download/<int:pdf_id>')
@login_required
def download_pdf(pdf_id):
    """Download PDF file (requires verification first via AJAX)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()
    
    if not pdf:
        flash('PDF tidak ditemukan', 'danger')
        return redirect(url_for('user_panel'))
    
    if os.path.exists(pdf['file_path']):
        return send_file(pdf['file_path'], as_attachment=True, download_name=pdf['file_name'])
    else:
        flash('File PDF tidak ditemukan di server', 'danger')
        return redirect(url_for('user_panel'))


@app.route('/api/scan-qr', methods=['POST'])
@login_required
def scan_qr():
    """API endpoint for QR code scanning"""
    data = request.get_json()
    bodyteks = data.get('bodyteks', '').strip().upper()
    pdf_id = data.get('pdf_id')
    
    if not bodyteks or not pdf_id:
        return jsonify({'success': False, 'message': 'Data tidak lengkap'})
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM pdf_files WHERE id = %s', (pdf_id,))
    pdf = cur.fetchone()
    cur.close()
    conn.close()
    
    if not pdf:
        return jsonify({'success': False, 'message': 'PDF tidak ditemukan'})
    
    # Generate SHA key from input
    secret_key = os.getenv('SECRET_KEY', 'default-secret')
    generated_sha = generate_sha_key(secret_key, bodyteks, pdf['file_hash'])
    
    # Verify
    if generated_sha == pdf['sha_key']:
        return jsonify({
            'success': True,
            'pdf_id': pdf_id,
            'file_name': pdf['file_name'],
            'download_url': url_for('download_pdf', pdf_id=pdf_id, _external=True),
            'preview_url': url_for('preview_pdf', pdf_id=pdf_id, _external=True)
        })
    else:
        return jsonify({'success': False, 'message': 'Kode QR tidak valid untuk PDF ini'})


# ==================== CLI COMMANDS ====================

@app.cli.command('init-db')
def init_db_command():
    """Initialize database tables"""
    init_db()
    print('Database initialized!')


@app.cli.command('create-admin')
def create_admin():
    """Create admin user"""
    import click
    email = click.prompt('Email admin')
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    password_hash = hash_password(password)
    
    try:
        cur.execute('''
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s)
        ''', (email, password_hash, 'admin'))
        conn.commit()
        print(f'Admin user {email} created successfully!')
    except psycopg2.IntegrityError:
        print(f'User with email {email} already exists!')
    finally:
        cur.close()
        conn.close()


@app.cli.command('create-user')
def create_user():
    """Create regular user"""
    import click
    email = click.prompt('Email user')
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    password_hash = hash_password(password)
    
    try:
        cur.execute('''
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s)
        ''', (email, password_hash, 'user'))
        conn.commit()
        print(f'User {email} created successfully!')
    except psycopg2.IntegrityError:
        print(f'User with email {email} already exists!')
    finally:
        cur.close()
        conn.close()


# ==================== MAIN ====================

if __name__ == '__main__':
    # Initialize database on first run
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization error: {e}")
        print("Pastikan PostgreSQL sudah berjalan dan konfigurasi .env benar.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
