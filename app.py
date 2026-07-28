# -*- coding: utf-8 -*-
"""
CU აუდიტორიების აღჭურვილობის მართვის სისტემა
----------------------------------------------
ლოკალური Flask აპლიკაცია + SQLite ბაზა.
გაშვება: python app.py  ->  http://127.0.0.1:8000
ნაგულისხმევი ანგარიში: admin / admin123
"""

import os
import sqlite3
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for, render_template,
    g, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

from seed_data import SEED_ROOMS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "audit.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cu-audit-local-secret-key-change-me")

FIELD_LABELS = {
    "floor": "სართული",
    "code": "აუდიტორია",
    "access_point": "აქსეს პოინტი",
    "projector": "პროექტორი",
    "smartboard": "სმარტბორდი",
    "computer": "კომპიუტერი",
    "monitor": "მონიტორი",
    "camera": "კამერა",
    "speaker": "დინამიკი",
    "comment": "კომენტარი",
}
EDITABLE_FIELDS = [
    "floor", "code", "access_point", "projector", "smartboard",
    "computer", "monitor", "camera", "speaker", "comment",
]


# ---------------------------------------------------------------- DB helpers
def get_db():
    if "db" not in g:
        os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    first_run = not os.path.exists(DB_PATH)
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    # ნაგულისხმევი ადმინი
    cur = db.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )

    # საწყისი მონაცემების ჩატვირთვა
    cur = db.execute("SELECT COUNT(*) AS c FROM rooms")
    if cur.fetchone()["c"] == 0:
        for row in SEED_ROOMS:
            db.execute(
                """INSERT INTO rooms
                   (floor, code, access_point, projector, smartboard,
                    computer, monitor, camera, speaker, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row,
            )
            room_id = db.execute(
                "SELECT id FROM rooms WHERE code = ?", (row[1],)
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO history (room_id, room_code, action, changed_by)
                   VALUES (?, ?, 'created', 'seed')""",
                (room_id, row[1]),
            )
    db.commit()
    db.close()
    return first_run


# ---------------------------------------------------------------- auth
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "მომხმარებელი ან პაროლი არასწორია"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    error = None
    success = None
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if not check_password_hash(user["password_hash"], current):
            error = "მიმდინარე პაროლი არასწორია"
        elif len(new) < 4:
            error = "ახალი პაროლი უნდა იყოს მინიმუმ 4 სიმბოლო"
        elif new != confirm:
            error = "ახალი პაროლები არ ემთხვევა"
        else:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new), user["id"]),
            )
            db.commit()
            success = "პაროლი წარმატებით შეიცვალა"
    return render_template("account.html", error=error, success=success)


# ---------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    floor = request.args.get("floor", "").strip()
    device_type = request.args.get("device_type", "").strip()
    q = request.args.get("q", "").strip()

    query = "SELECT * FROM rooms WHERE 1=1"
    params = []
    
    if floor:
        query += " AND floor = ?"
        params.append(floor)

    if device_type:
        if device_type == "smartboard":
            query += " AND smartboard != 'არა' AND smartboard != '' AND smartboard IS NOT NULL"
        elif device_type == "projector":
            query += " AND projector != 'არა' AND projector != '' AND projector IS NOT NULL"
        elif device_type == "camera":
            query += " AND camera != 'არა' AND camera != '' AND camera IS NOT NULL"
        elif device_type == "access_point":
            query += " AND access_point != 'არა' AND access_point != '' AND access_point IS NOT NULL"
        elif device_type == "computer":
            query += " AND computer != 'არა' AND computer != '' AND computer IS NOT NULL"
        elif device_type == "speaker":
            query += " AND speaker != 'არა' AND speaker != '' AND speaker IS NOT NULL"

    if q:
        like = f"%{q}%"
        query += """ AND (
            code LIKE ? OR access_point LIKE ? OR projector LIKE ? OR
            smartboard LIKE ? OR computer LIKE ? OR monitor LIKE ? OR
            camera LIKE ? OR speaker LIKE ? OR comment LIKE ?
        )"""
        params.extend([like] * 9)
        
    query += " ORDER BY floor, code"

    rooms = db.execute(query, params).fetchall()
    floors = [r["floor"] for r in db.execute(
        "SELECT DISTINCT floor FROM rooms ORDER BY floor"
    ).fetchall()]

    stats = {
        "total": db.execute("SELECT COUNT(*) c FROM rooms").fetchone()["c"],
        "no_access_point": db.execute(
            "SELECT COUNT(*) c FROM rooms WHERE access_point = 'არა' OR access_point = '' OR access_point IS NULL"
        ).fetchone()["c"],
        "no_projector": db.execute(
            "SELECT COUNT(*) c FROM rooms WHERE projector = 'არა' OR projector = '' OR projector IS NULL"
        ).fetchone()["c"],
    }

    return render_template(
        "dashboard.html", rooms=rooms, floors=floors,
        current_floor=floor, device_type=device_type, q=q, stats=stats,
    )


# ---------------------------------------------------------------- room CRUD
@app.route("/room/new", methods=["GET", "POST"])
@login_required
def room_new():
    if request.method == "POST":
        values = {f: request.form.get(f, "").strip() for f in EDITABLE_FIELDS}
        if not values["code"]:
            flash("აუდიტორიის კოდი სავალდებულოა", "error")
            return render_template("room_form.html", room=values, mode="new")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM rooms WHERE code = ?", (values["code"],)
        ).fetchone()
        if existing:
            flash(f"აუდიტორია '{values['code']}' უკვე არსებობს", "error")
            return render_template("room_form.html", room=values, mode="new")

        db.execute(
            """INSERT INTO rooms
               (floor, code, access_point, projector, smartboard,
                computer, monitor, camera, speaker, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(values[f] for f in EDITABLE_FIELDS),
        )
        room_id = db.execute(
            "SELECT id FROM rooms WHERE code = ?", (values["code"],)
        ).fetchone()["id"]
        db.execute(
            """INSERT INTO history (room_id, room_code, action, changed_by)
               VALUES (?, ?, 'created', ?)""",
            (room_id, values["code"], session.get("username", "")),
        )
        db.commit()
        flash(f"აუდიტორია '{values['code']}' დაემატა", "success")
        return redirect(url_for("room_detail", room_id=room_id))

    return render_template("room_form.html", room=None, mode="new")


@app.route("/room/<int:room_id>")
@login_required
def room_detail(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        flash("აუდიტორია ვერ მოიძებნა", "error")
        return redirect(url_for("dashboard"))
    history = db.execute(
        "SELECT * FROM history WHERE room_id = ? ORDER BY changed_at DESC, id DESC",
        (room_id,),
    ).fetchall()
    return render_template(
        "room_detail.html", room=room, history=history, labels=FIELD_LABELS
    )


@app.route("/room/<int:room_id>/edit", methods=["GET", "POST"])
@login_required
def room_edit(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        flash("აუდიტორია ვერ მოიძებნა", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        new_values = {f: request.form.get(f, "").strip() for f in EDITABLE_FIELDS}
        if not new_values["code"]:
            flash("აუდიტორიის კოდი სავალდებულოა", "error")
            return render_template("room_form.html", room=room, mode="edit")

        dup = db.execute(
            "SELECT id FROM rooms WHERE code = ? AND id != ?",
            (new_values["code"], room_id),
        ).fetchone()
        if dup:
            flash(f"აუდიტორია '{new_values['code']}' უკვე არსებობს", "error")
            return render_template("room_form.html", room=room, mode="edit")

        changed_fields = []
        for f in EDITABLE_FIELDS:
            old_val = room[f] or ""
            new_val = new_values[f]
            if old_val != new_val:
                changed_fields.append((f, old_val, new_val))

        if changed_fields:
            db.execute(
                f"""UPDATE rooms SET {', '.join(f + ' = ?' for f in EDITABLE_FIELDS)},
                    updated_at = datetime('now', 'localtime')
                    WHERE id = ?""",
                tuple(new_values[f] for f in EDITABLE_FIELDS) + (room_id,),
            )
            for field_name, old_val, new_val in changed_fields:
                db.execute(
                    """INSERT INTO history
                       (room_id, room_code, action, field_name, old_value, new_value, changed_by)
                       VALUES (?, ?, 'updated', ?, ?, ?, ?)""",
                    (room_id, new_values["code"], field_name, old_val, new_val,
                     session.get("username", "")),
                )
            db.commit()
            flash("ცვლილებები შენახულია", "success")
        else:
            flash("ცვლილება არ დაფიქსირებულა", "info")
        return redirect(url_for("room_detail", room_id=room_id))

    return render_template("room_form.html", room=room, mode="edit")


@app.route("/room/<int:room_id>/delete", methods=["POST"])
@login_required
def room_delete(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if room:
        db.execute(
            """INSERT INTO history (room_id, room_code, action, changed_by)
               VALUES (?, ?, 'deleted', ?)""",
            (None, room["code"], session.get("username", "")),
        )
        db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        db.commit()
        flash(f"აუდიტორია '{room['code']}' წაიშალა", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------- global history
@app.route("/history")
@login_required
def history_log():
    db = get_db()
    q = request.args.get("q", "").strip()
    query = "SELECT * FROM history WHERE 1=1"
    params = []
    if q:
        query += " AND room_code LIKE ?"
        params.append(f"%{q}%")
    query += " ORDER BY changed_at DESC, id DESC LIMIT 500"
    entries = db.execute(query, params).fetchall()
    return render_template("history.html", entries=entries, labels=FIELD_LABELS, q=q)


@app.context_processor
def inject_globals():
    return {"field_labels": FIELD_LABELS}


if __name__ == "__main__":
    first_run = init_db()
    if first_run:
        print("=" * 60)
        print("ბაზა შეიქმნა და საწყისი მონაცემები ჩაიტვირთა.")
        print("შესვლა: admin / admin123  -- გთხოვთ შეცვალოთ პაროლი!")
        print("=" * 60)
    # პორტი შეცვლილია 8000-ზე
    app.run(debug=True, host="127.0.0.1", port=8000)
