# 📄 PDF Verification System

Sistem verifikasi akses file PDF menggunakan Python, Flask, dan PostgreSQL. File PDF yang diupload oleh admin akan terkunci dan hanya dapat diakses oleh user yang memiliki kode akses (bodyteks) yang valid.

---

## ✨ Fitur Utama

- **🔐 Keamanan SHA256**: Verifikasi integritas file dengan hashing SHA256
- **🔑 Secret Key**: Kunci rahasia disimpan di server (.env)
- **📱 QR Code**: Generate dan scan QR Code untuk akses cepat
- **👥 Role-based Access**: Admin dan User dengan hak akses berbeda
- **🔒 Password Hashing**: Menggunakan bcrypt untuk keamanan password
- **📂 Local Storage**: Penyimpanan file PDF di folder lokal

---

## 🏗️ Arsitektur Sistem

```
Internet
   ↓
Cloudflare Tunnel (opsional)
   ↓
Flask (localhost:5000)
   ↓
PostgreSQL (localhost:5432)
   ↓
storage/pdf/
```

---

## 📋 Prasyarat (Yang Harus Diinstall)

### 1. Python 3.8+
Download dan install dari: https://www.python.org/downloads/

### 2. PostgreSQL
Download dan install dari: https://www.postgresql.org/download/

**Catatan untuk Windows:**
- Download installer dari PostgreSQL official
- Ingat password yang Anda buat saat instalasi
- Default port: 5432

### 3. pip (Python Package Manager)
Biasanya sudah terinstall bersama Python.

---

## 🚀 Instalasi dan Setup

### Step 1: Clone/Download Project
```bash
cd pdf_verification_system
```

### Step 2: Buat Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Setup Database PostgreSQL

1. **Buka pgAdmin** atau **psql** (command line PostgreSQL)

2. **Buat Database Baru:**
```sql
CREATE DATABASE pdf_verification;
```

3. **Verifikasi database sudah dibuat**

### Step 5: Konfigurasi Environment Variables

1. **Buka file `.env`**

2. **Edit konfigurasi sesuai setup Anda:**
```env
# Secret Key (WAJIB GANTI!)
SECRET_KEY=supersecret123changemeinproduction

# Database Configuration
DB_NAME=pdf_verification
DB_USER=postgres
DB_PASSWORD=password_anda_disini
DB_HOST=localhost
DB_PORT=5432
```

**PENTING:**
- Ganti `SECRET_KEY` dengan string acak panjang untuk production
- Sesuaikan `DB_PASSWORD` dengan password PostgreSQL Anda

### Step 6: Inisialisasi Database

```bash
# Set environment variable Flask
set FLASK_APP=app.py  (Windows)
export FLASK_APP=app.py  (Linux/Mac)

# Inisialisasi tabel database
flask init-db
```

### Step 7: Buat User Admin

```bash
flask create-admin
```

Ikuti prompt untuk memasukkan email dan password admin.

### Step 8: (Opsional) Buat User Biasa

```bash
flask create-user
```

---

## ▶️ Menjalankan Aplikasi

### Development Mode
```bash
python app.py
```

Atau dengan Flask CLI:
```bash
flask run
```

Aplikasi akan berjalan di: **http://localhost:5000**

### Production Mode (dengan Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 📖 Cara Penggunaan

### Untuk Admin:

1. **Login** ke `/login` dengan akun admin
2. **Upload PDF** di Admin Panel:
   - Pilih file PDF
   - Masukkan bodyteks (kode akses), contoh: `GRATISONGKIR2026`
   - Klik Upload
3. **QR Code** akan digenerate otomatis
4. **Download/Print** QR Code untuk diberikan ke user
5. **Manage PDF**: Lihat daftar PDF dan hapus jika perlu

### Untuk User:

1. **Login** ke `/login` dengan akun user
2. **Lihat Gallery** PDF yang tersedia
3. **Verifikasi Akses** dengan cara:
   - Masukkan bodyteks manual, atau
   - Scan QR Code (masukkan hasil scan)
4. **Akses PDF**: Preview atau Download setelah terverifikasi

---

## 🔐 Konsep Keamanan

### Proses Upload (Admin)

```
1. Upload PDF → Simpan ke storage/
2. Hitung file_hash = SHA256(file_pdf)
3. Admin input bodyteks (contoh: GRATISONGKIR2026)
4. Generate sha_key = SHA256(secret_key + bodyteks + file_hash)
5. Simpan metadata ke PostgreSQL
6. Generate QR Code (isi: bodyteks saja)
```

### Proses Verifikasi (User)

```
1. User input bodyteks
2. Ambil file_hash dari database
3. Generate ulang: test_sha = SHA256(secret_key + input_bodyteks + file_hash)
4. Bandingkan: test_sha == stored_sha_key
5. Jika cocok → Akses diberikan
6. Jika tidak → Akses ditolak
```

---

## 📁 Struktur Folder

```
pdf_verification_system/
│
├── app.py                  # Main Flask application
├── .env                    # Environment variables
├── requirements.txt        # Python dependencies
├── README.md              # Dokumentasi ini
│
├── database/              # (Opsional) SQLite backup
│   └── pdf_verification.db
│
├── storage/               # Folder penyimpanan PDF
│   └── pdf/
│       ├── file1.pdf
│       └── file2.pdf
│
├── templates/             # HTML Templates
│   ├── login.html
│   ├── admin.html
│   └── user.html
│
└── static/               # Static files
    ├── css/
    ├── js/
    └── qrcodes/          # Generated QR codes
```

---

## 🛠️ Troubleshooting

### Error: "Database does not exist"
**Solusi:** Pastikan database `pdf_verification` sudah dibuat di PostgreSQL

### Error: "Password authentication failed"
**Solusi:** Periksa `DB_PASSWORD` di file `.env` sesuai dengan password PostgreSQL Anda

### Error: "Module not found"
**Solusi:** Jalankan `pip install -r requirements.txt` lagi

### Error: "Port 5000 already in use"
**Solusi:** Ganti port dengan:
```bash
flask run -p 5001
```

---

## 🔧 Konfigurasi Cloudflare Tunnel (Opsional)

Untuk expose aplikasi ke internet dengan aman:

1. **Install cloudflared:**
   Download dari: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

2. **Login dan buat tunnel:**
```bash
cloudflared tunnel login
cloudflared tunnel create pdf-verification
```

3. **Config file** (`~/.cloudflared/config.yml`):
```yaml
tunnel: <tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: pdf-verification.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404
```

4. **Jalankan tunnel:**
```bash
cloudflared tunnel run pdf-verification
```

---

## 📝 Daftar Lengkap Dependensi

| Package | Version | Kegunaan |
|---------|---------|----------|
| Flask | 3.0.0 | Web framework |
| psycopg2-binary | 2.9.9 | PostgreSQL driver |
| bcrypt | 4.1.2 | Password hashing |
| qrcode | 7.4.2 | QR Code generation |
| Pillow | 10.1.0 | Image processing |
| python-dotenv | 1.0.0 | Environment variables |
| gunicorn | 21.2.0 | WSGI server |
| Werkzeug | 3.0.1 | WSGI utilities |

---

## 🔒 Security Best Practices

1. **Ganti SECRET_KEY** sebelum deploy ke production
2. **Gunakan HTTPS** untuk komunikasi aman
3. **Jangan expose PostgreSQL** ke internet (localhost only)
4. **Gunakan password kuat** untuk admin dan user
5. **Backup database** secara berkala
6. **Batasi ukuran file** upload (default: 16MB)
7. **Validasi file type** (hanya PDF yang diizinkan)

---

## 📞 Support

Jika ada masalah atau pertanyaan, silakan:
1. Periksa bagian Troubleshooting di atas
2. Cek log error di terminal
3. Verifikasi konfigurasi `.env`
4. Pastikan PostgreSQL berjalan

---

## 📄 Lisensi

Project ini dibuat untuk keperluan verifikasi dokumen PDF dengan sistem keamanan SHA256.

---

**Selamat menggunakan PDF Verification System! 🎉**
