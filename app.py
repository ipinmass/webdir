import os
import secrets
from pathlib import Path
from functools import wraps
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    send_from_directory, abort, session, flash
)
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


@app.template_filter("timestampformat")
def timestampformat(value):
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

USERNAME = os.environ.get("FS_USER", "admin")
PASSWORD = os.environ.get("FS_PASS", "changeme")
PORT = int(os.environ.get("FS_PORT", 6969))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == USERNAME and request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    rel_path = request.args.get("path", "")
    current_dir = (STORAGE_DIR / rel_path).resolve()

    if not str(current_dir).startswith(str(STORAGE_DIR.resolve())):
        abort(403)

    if not current_dir.exists():
        abort(404)

    items = []
    if current_dir != STORAGE_DIR.resolve():
        items.append({
            "name": "..",
            "is_dir": True,
            "is_parent": True,
            "path": str(Path(rel_path).parent) if rel_path else "",
        })

    for idx, entry in enumerate(sorted(current_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())), start=1):
        stat = entry.stat()
        items.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "is_image": entry.suffix.lower() in IMAGE_EXTS,
            "size": stat.st_size if entry.is_file() else None,
            "mtime": stat.st_mtime,
            "num": idx,
            "path": str(Path(rel_path) / entry.name) if rel_path else entry.name,
        })

    return render_template("index.html", items=items, current_path=rel_path)


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    rel_path = request.form.get("path", "")
    current_dir = (STORAGE_DIR / rel_path).resolve()

    if not str(current_dir).startswith(str(STORAGE_DIR.resolve())):
        abort(403)

    files = request.files.getlist("files")
    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            f.save(current_dir / filename)

    return redirect(url_for("index", path=rel_path))


@app.route("/download/<path:filepath>")
@login_required
def download(filepath):
    file_path = (STORAGE_DIR / filepath).resolve()
    if not str(file_path).startswith(str(STORAGE_DIR.resolve())):
        abort(403)
    if not file_path.exists():
        abort(404)
    return send_from_directory(file_path.parent, file_path.name, as_attachment=True)


@app.route("/view/<path:filepath>")
@login_required
def view(filepath):
    file_path = (STORAGE_DIR / filepath).resolve()
    if not str(file_path).startswith(str(STORAGE_DIR.resolve())):
        abort(403)
    if not file_path.exists():
        abort(404)
    return send_from_directory(file_path.parent, file_path.name, max_age=86400 * 7)


@app.route("/delete", methods=["POST"])
@login_required
def delete():
    filepath = request.form.get("path", "")
    file_path = (STORAGE_DIR / filepath).resolve()
    if not str(file_path).startswith(str(STORAGE_DIR.resolve())):
        abort(403)
    if not file_path.exists():
        abort(404)

    if file_path.is_dir():
        file_path.rmdir()
    else:
        file_path.unlink()

    parent = str(Path(filepath).parent) if Path(filepath).parent != Path(".") else ""
    return redirect(url_for("index", path=parent))


@app.route("/mkdir", methods=["POST"])
@login_required
def mkdir():
    rel_path = request.form.get("path", "")
    folder_name = request.form.get("name", "")
    if folder_name:
        target = (STORAGE_DIR / rel_path / secure_filename(folder_name)).resolve()
        if str(target).startswith(str(STORAGE_DIR.resolve())):
            target.mkdir(exist_ok=True)
    return redirect(url_for("index", path=rel_path))


@app.route("/rename", methods=["POST"])
@login_required
def rename():
    old_path = request.form.get("path", "")
    new_name = request.form.get("new_name", "")
    if not new_name:
        return redirect(url_for("index", path=str(Path(old_path).parent) if Path(old_path).parent != Path(".") else ""))

    old_file = (STORAGE_DIR / old_path).resolve()
    if not str(old_file).startswith(str(STORAGE_DIR.resolve())):
        abort(403)
    if not old_file.exists():
        abort(404)

    new_file = (old_file.parent / secure_filename(new_name)).resolve()
    if not str(new_file).startswith(str(STORAGE_DIR.resolve())):
        abort(403)

    old_file.rename(new_file)
    parent = str(Path(old_path).parent) if Path(old_path).parent != Path(".") else ""
    return redirect(url_for("index", path=parent))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
