from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    jsonify,
)
import sqlite3
import os
from flask_cors import CORS

app = Flask(__name__)
DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "litenote.db")
UPLOAD_IMAGE_FOLDER = os.path.join(DATA_DIR, "images")
UPLOAD_VIDEO_FOLDER = os.path.join(DATA_DIR, "videos")

# 配置上传文件夹
app.config["UPLOAD_IMAGE_FOLDER"] = UPLOAD_IMAGE_FOLDER
app.config["UPLOAD_VIDEO_FOLDER"] = UPLOAD_VIDEO_FOLDER

# 跨域配置
CORS(app, resources={r"/upload_image": {"origins": "*"}, r"/upload_video": {"origins": "*"}})

# 创建文件夹
for folder in [UPLOAD_IMAGE_FOLDER, UPLOAD_VIDEO_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)


# 初始化数据库
def init_db():
    if os.path.exists(DB_FILE):
        return
    # 数据库不存在，全新创建
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # 创建文件夹表
        c.execute("""
            CREATE TABLE folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        # 插入默认文件夹
        c.execute("INSERT INTO folders (name) VALUES ('我的笔记本')")
        folder_id = c.lastrowid

        # 创建笔记表
        c.execute("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE,
                filename TEXT,
                folder_id INTEGER,
                subtitle TEXT,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        """)

        # 创建默认笔记
        title = "欢迎使用litenote"
        filename = f"{title}.md"
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("欢迎使用litenote！这是你的第一条笔记！")
        c.execute(
            "INSERT INTO notes (title, filename, folder_id, subtitle) VALUES (?, ?, ?, ?)",
            (title, filename, folder_id, "")
        )
        conn.commit()


init_db()


# 首页
@app.route("/")
def index():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM folders")
        folders = c.fetchall()
        # 默认加载第一个文件夹的笔记
        first_folder_id = folders[0][0] if folders else None
        c.execute(
            "SELECT id, title FROM notes WHERE folder_id = ?" if first_folder_id else "SELECT id, title FROM notes",
            (first_folder_id,) if first_folder_id else ())
        notes = c.fetchall()
    return render_template("index.html", notes=notes, folders=folders)


# 文件夹操作
@app.route("/add_folder", methods=["POST"])
def add_folder():
    name = request.form["name"].strip()
    if not name:
        return jsonify({"success": False, "error": "文件夹名称不能为空"}), 400
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO folders (name) VALUES (?)", (name,))
            conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "文件夹名称已存在"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/edit_folder/<int:folder_id>", methods=["GET", "POST"])
def edit_folder(folder_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if request.method == "POST":
            new_name = request.form["name"].strip()
            if not new_name:
                return jsonify({"success": False, "error": "文件夹名称不能为空"}), 400
            try:
                c.execute("UPDATE folders SET name = ? WHERE id = ?", (new_name, folder_id))
                conn.commit()
                return jsonify({"success": True})
            except sqlite3.IntegrityError:
                return jsonify({"success": False, "error": "文件夹名称已存在"}), 400
        else:
            c.execute("SELECT name FROM folders WHERE id = ?", (folder_id,))
            folder = c.fetchone()
    return render_template("edit_folder.html", folder=folder, folder_id=folder_id)


@app.route("/get_folders", methods=["GET"])
def get_folders():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM folders")
        folders = [{"id": row[0], "name": row[1]} for row in c.fetchall()]
    return jsonify(folders)


@app.route("/delete_folder/<int:folder_id>", methods=["POST"])
def delete_folder(folder_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # 获取该文件夹下所有笔记的文件名
        c.execute("SELECT filename FROM notes WHERE folder_id = ?", (folder_id,))
        rows = c.fetchall()
        for row in rows:
            filepath = os.path.join(DATA_DIR, row[0])
            if os.path.exists(filepath):
                os.remove(filepath)
        # 删除文件夹（由于外键级联，笔记记录会自动删除）
        c.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        conn.commit()
    return redirect(url_for("index"))


# 笔记操作
@app.route("/add", methods=["POST"])
def add_note():
    data = request.get_json() if request.is_json else request.form
    title = data.get("title")
    folder_id = data.get("folder_id")
    if not title or not folder_id:
        return jsonify({"success": False, "error": "标题或文件夹ID不能为空"}), 400

    filename = f"{title}.md"
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w") as f:
        f.write("")  # 初始为空

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO notes (title, filename, folder_id, subtitle) VALUES (?, ?, ?, ?)",
                (title, filename, folder_id, data.get("subtitle", "")),
            )
            conn.commit()
        return jsonify({"success": True}) if request.is_json else redirect(url_for("index"))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT filename FROM notes WHERE id=?", (note_id,))
        row = c.fetchone()
        if row:
            path = os.path.join(DATA_DIR, row[0])
            if os.path.exists(path):
                os.remove(path)
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))
            conn.commit()
    return redirect(url_for("index"))


@app.route("/get_notes", methods=["GET"])
def get_notes():
    folder_id = request.args.get("folder_id")
    if not folder_id:
        return jsonify({"error": "缺少folder_id参数"}), 400
    try:
        folder_id = int(folder_id)
    except ValueError:
        return jsonify({"error": "folder_id格式错误"}), 400
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, title, subtitle, folder_id FROM notes WHERE folder_id = ?", (folder_id,))
        notes = [{"id": row[0], "title": row[1], "subtitle": row[2], "folder_id": row[3]} for row in c.fetchall()]
    return jsonify(notes)


@app.route("/api/note/<int:note_id>", methods=["GET"])
def api_note_detail(note_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT title, filename, subtitle FROM notes WHERE id = ?", (note_id,))
        note = c.fetchone()
        if not note:
            return jsonify({"error": "笔记不存在"}), 404
        filepath = os.path.join(DATA_DIR, note[1])
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    return jsonify({"id": note_id, "title": note[0], "subtitle": note[2], "content": content})


@app.route("/save/<int:note_id>", methods=["POST"])
def save_note(note_id):
    data = request.json
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT filename, title, folder_id FROM notes WHERE id = ?", (note_id,))
        note = c.fetchone()
        if not note:
            return jsonify({"success": False, "error": "笔记不存在"}), 404

        filename, old_title, folder_id = note
        new_title = data.get("title")
        content = data.get("content", "")

        # 处理标题变更（文件重命名、唯一性检查）
        if new_title and new_title != old_title:
            # 检查标题是否已存在（全局唯一）
            c.execute("SELECT id FROM notes WHERE title = ? AND id != ?", (new_title, note_id))
            if c.fetchone():
                return jsonify({"success": False, "error": "笔记标题已存在"}), 400

            new_filename = f"{new_title}.md"
            old_filepath = os.path.join(DATA_DIR, filename)
            new_filepath = os.path.join(DATA_DIR, new_filename)

            # 重命名磁盘文件
            if os.path.exists(old_filepath):
                os.rename(old_filepath, new_filepath)
            else:
                # 若原文件缺失，直接创建新文件
                with open(new_filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # 更新数据库中的标题和文件名
            c.execute("UPDATE notes SET title = ?, filename = ? WHERE id = ?", (new_title, new_filename, note_id))
            # 后续写入内容使用新文件名
            filepath = new_filepath
        else:
            # 标题未变，直接使用原文件路径
            filepath = os.path.join(DATA_DIR, filename)
            # 仅更新内容时，写入文件
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            conn.commit()
            return jsonify({"success": True})

        # 写入正文（标题变更时也需要写入内容）
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        conn.commit()
        return jsonify({"success": True})


# 媒体文件上传/访问
@app.route("/upload_image", methods=["POST"])
def upload_image():
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"error": "请选择文件"}), 400
    file = request.files["file"]
    file.save(os.path.join(app.config["UPLOAD_IMAGE_FOLDER"], file.filename))
    return jsonify({"url": f"/notes/images/{file.filename}"})


@app.route("/upload_video", methods=["POST"])
def upload_video():
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"error": "请选择文件"}), 400
    file = request.files["file"]
    file.save(os.path.join(app.config["UPLOAD_VIDEO_FOLDER"], file.filename))
    return jsonify({"url": f"/notes/videos/{file.filename}"})


@app.route("/notes/images/<filename>")
def get_uploaded_image(filename):
    return send_from_directory(app.config["UPLOAD_IMAGE_FOLDER"], filename)


@app.route("/notes/videos/<filename>")
def get_uploaded_video(filename):
    return send_from_directory(app.config["UPLOAD_VIDEO_FOLDER"], filename)


# 笔记预览
@app.route("/note/<int:note_id>", methods=["GET"])
def view_note(note_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT title, filename, subtitle FROM notes WHERE id = ?", (note_id,))
        note = c.fetchone()
    if not note:
        return "笔记不存在", 404
    with open(os.path.join(DATA_DIR, note[1]), "r") as f:
        content = f.read()
    return render_template("note.html", title=note[0], subtitle=note[2], content=content, note_id=note_id)


if __name__ == "__main__":
    app.run(debug=True, port=5005)