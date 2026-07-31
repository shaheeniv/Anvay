"""
Anvay — story & video log + family tree + contribution feed +
time capsule letters

A small local website (Flask + SQLite) for recording video interviews with
grandparents (transcript + translation), keeping a living family tree
(people, their parents/children/spouses), a contribution feed where any
family member can add a memory, photo, story, tradition, or note, and
time capsule letters sealed until a future date.

Run it with: python3 app.py   (or double-click "Open Anvay.command")
Then open: http://127.0.0.1:5000
"""

import os
import secrets
import sqlite3
import uuid
from collections import defaultdict
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent

# Where the database and uploaded photos live — on a normal local run
# this is just BASE_DIR, but a hosted deployment sets DATA_DIR to a
# persistent disk mount so this data survives redeploys (a container's
# own filesystem is wiped on every redeploy). Uploads are served through
# a dedicated /uploads/<filename> route (below) rather than Flask's
# static folder, since the static folder must live alongside the code
# while DATA_DIR may point somewhere else entirely.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE = DATA_DIR / "archive.db"
SCHEMA = BASE_DIR / "schema.sql"
UPLOAD_DIR = DATA_DIR / "uploads"
VIDEO_DIR = DATA_DIR / "videos"
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "avi", "webm"}

CONTRIBUTION_KINDS = [
    ("memory", "Memory"),
    ("photo", "Photo"),
    ("story", "Story"),
    ("tradition", "Tradition"),
]
CONTRIBUTION_KIND_LABELS = dict(CONTRIBUTION_KINDS)

# This app is built for one family, not as a multi-tenant product — every
# person just belongs to family row 1, seeded by schema.sql. See families
# table in schema.sql for why this column exists at all.
DEFAULT_FAMILY_ID = 1


def _load_or_create_secret_key():
    """A stable secret key, so logging in doesn't get everyone signed out
    every time the server restarts. In production set SECRET_KEY as a real
    environment variable; for local dev, generate one once and cache it in
    a gitignored file so it survives across `python3 app.py` restarts."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_path = BASE_DIR / "instance" / "secret_key.txt"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_text().strip()
    new_key = secrets.token_hex(32)
    key_path.write_text(new_key)
    return new_key


app = Flask(__name__)
app.secret_key = _load_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB per upload — covers full video files


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(SCHEMA.read_text())
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Login / accounts
# ---------------------------------------------------------------------------
#
# Plain Flask session (not Flask-Login) — this whole app is hand-rolled
# with no extensions, and a signed session cookie holding just a person_id
# is all real per-person login needs here. A single before_request gate
# covers every existing route in one place instead of decorating each one.

PUBLIC_ENDPOINTS = {"login", "static"}


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
        return None
    if "person_id" not in session:
        return redirect(url_for("login"))
    return None


def current_person():
    """The logged-in person's row, joined with their account — or None."""
    if "person_id" not in session:
        return None
    db = get_db()
    return db.execute(
        """
        SELECT people.*, accounts.username, accounts.is_admin
        FROM people
        JOIN accounts ON accounts.person_id = people.id
        WHERE people.id = ?
        """,
        (session["person_id"],),
    ).fetchone()


@app.context_processor
def inject_current_person():
    return {"current_person": current_person()}


def require_admin(view):
    """Route decorator for the handful of admin-only actions (creating
    accounts, resetting passwords) — separate from the blanket login gate
    above, since most routes just need someone logged in, not an admin."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        person = current_person()
        if person is None or not person["is_admin"]:
            return "Not authorized.", 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    db = get_db()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    account = db.execute(
        "SELECT * FROM accounts WHERE username = ?", (username,)
    ).fetchone()

    if account is None or not check_password_hash(account["password_hash"], password):
        flash("Incorrect username or password.")
        return render_template("login.html"), 401

    session.clear()
    session["person_id"] = account["person_id"]
    return redirect(url_for("home"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serves contribution photos from UPLOAD_DIR (under DATA_DIR) —
    not Flask's static folder, since DATA_DIR may live on a separate
    persistent disk rather than alongside the code. Still behind the
    login gate like every other route (not in PUBLIC_ENDPOINTS)."""
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/videos/<path:filename>")
def uploaded_video(filename):
    """Serves uploaded video files from VIDEO_DIR. send_from_directory
    supports HTTP Range requests out of the box, which is what lets a
    browser's <video> player seek/scrub instead of downloading the
    whole file up front."""
    return send_from_directory(VIDEO_DIR, filename)


@app.route("/")
def home():
    """The site's front door: a choice between the ongoing Family Portal
    (the dashboard below, at /dashboard) and the Legacy Books index
    (which lists every book project — there will be more than one over
    time, one per family branch, so this links to the index rather than
    listing each one here directly). Lives at "/" so returning visitors
    with an existing session land here too, not straight into either
    product."""
    return render_template("home.html")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    db = get_db()
    visible_ids = current_visible_person_ids()
    contrib_ids = visible_contribution_ids(visible_ids)
    capsule_ids = visible_capsule_ids(visible_ids)

    people_count = (
        db.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
        if visible_ids is None else len(visible_ids)
    )
    videos_count = (
        db.execute("SELECT COUNT(*) AS c FROM video_entries").fetchone()["c"]
        if visible_ids is None else
        sum(1 for r in db.execute("SELECT person_id FROM video_entries") if r["person_id"] in visible_ids)
    )
    contributions_count = (
        db.execute("SELECT COUNT(*) AS c FROM contributions").fetchone()["c"]
        if visible_ids is None else len(contrib_ids)
    )

    stats = {
        "people": people_count,
        "videos": videos_count,
        "contributions": contributions_count,
        "capsules_sealed": 0,
        "capsules_unlocked": 0,
    }
    for row in db.execute("SELECT id, unlock_date FROM time_capsules"):
        if visible_ids is not None and row["id"] not in capsule_ids:
            continue
        if is_unlocked(row["unlock_date"]):
            stats["capsules_unlocked"] += 1
        else:
            stats["capsules_sealed"] += 1

    activity = []

    for row in db.execute(
        """
        SELECT video_entries.id, video_entries.topic, video_entries.created_at,
               video_entries.person_id, people.name AS person_name
        FROM video_entries
        JOIN people ON people.id = video_entries.person_id
        ORDER BY video_entries.created_at DESC LIMIT 8
        """
    ):
        if visible_ids is not None and row["person_id"] not in visible_ids:
            continue
        activity.append({
            "created_at": row["created_at"],
            "badge_label": "Video",
            "badge_class": "kind-badge",
            "text": row["person_name"] + (f" — {row['topic']}" if row["topic"] else " — new recording"),
            "url": url_for("show_entry", entry_id=row["id"]),
        })

    for row in db.execute(
        "SELECT id, kind, title, created_at FROM contributions ORDER BY created_at DESC LIMIT 8"
    ):
        if visible_ids is not None and row["id"] not in contrib_ids:
            continue
        activity.append({
            "created_at": row["created_at"],
            "badge_label": CONTRIBUTION_KIND_LABELS[row["kind"]],
            "badge_class": f"kind-badge kind-{row['kind']}",
            "text": row["title"],
            "url": url_for("show_contribution", contribution_id=row["id"]),
        })

    for row in db.execute(
        """
        SELECT time_capsules.id, time_capsules.title, time_capsules.unlock_date,
               time_capsules.created_at, people.name AS recipient_name
        FROM time_capsules
        JOIN people ON people.id = time_capsules.recipient_id
        ORDER BY time_capsules.created_at DESC LIMIT 8
        """
    ):
        if visible_ids is not None and row["id"] not in capsule_ids:
            continue
        unlocked = is_unlocked(row["unlock_date"])
        activity.append({
            "created_at": row["created_at"],
            "badge_label": "Unlocked" if unlocked else "Sealed",
            "badge_class": "kind-badge kind-unlocked" if unlocked else "kind-badge kind-sealed",
            "text": row["title"] if unlocked else f"A letter for {row['recipient_name']}",
            "url": url_for("show_capsule", capsule_id=row["id"]),
        })

    for row in db.execute("SELECT id, name, created_at FROM people ORDER BY created_at DESC LIMIT 8"):
        if visible_ids is not None and row["id"] not in visible_ids:
            continue
        activity.append({
            "created_at": row["created_at"],
            "badge_label": "New person",
            "badge_class": "kind-badge",
            "text": f"{row['name']} joined the family tree",
            "url": url_for("show_person", person_id=row["id"]),
        })

    activity.sort(key=lambda a: a["created_at"], reverse=True)
    activity = activity[:12]

    recent_photos = [
        row for row in db.execute(
            """
            SELECT id, title, photo_filename FROM contributions
            WHERE kind = 'photo' AND photo_filename IS NOT NULL
            ORDER BY created_at DESC LIMIT 12
            """
        )
        if visible_ids is None or row["id"] in contrib_ids
    ][:6]

    family_roots, _, _ = build_family_forest()
    if visible_ids is not None:
        allowed_roots = get_branch_membership().get(session["person_id"], set())
        family_roots = [r for r in family_roots if r["id"] in allowed_roots]

    return render_template(
        "dashboard.html", stats=stats, activity=activity, recent_photos=recent_photos,
        family_roots=family_roots,
    )


# ---------------------------------------------------------------------------
# Story & video entries
# ---------------------------------------------------------------------------

ENTRY_QUERY = """
    SELECT video_entries.*, people.name AS person_name
    FROM video_entries
    JOIN people ON people.id = video_entries.person_id
"""


def save_video_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        flash(f"Video not saved — \"{file_storage.filename}\" isn't a supported video type.")
        return None
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    file_storage.save(VIDEO_DIR / filename)
    return filename


@app.route("/stories")
def stories():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        like = f"%{q}%"
        entries = db.execute(
            ENTRY_QUERY
            + """
            WHERE people.name LIKE ?
               OR video_entries.topic LIKE ?
               OR video_entries.english_translation LIKE ?
               OR video_entries.gujarati_transcript LIKE ?
            ORDER BY video_entries.date_recorded DESC, video_entries.id DESC
            """,
            (like, like, like, like),
        ).fetchall()
    else:
        entries = db.execute(
            ENTRY_QUERY + " ORDER BY video_entries.date_recorded DESC, video_entries.id DESC"
        ).fetchall()

    visible_ids = current_visible_person_ids()
    if visible_ids is not None:
        entries = [e for e in entries if e["person_id"] in visible_ids]

    return render_template("stories.html", entries=entries, q=q)


@app.route("/entries/new")
def new_entry():
    people = visible_people()
    preselect_person_id = request.args.get("person_id", type=int)
    return render_template("form.html", entry=None, people=people, preselect_person_id=preselect_person_id)


@app.route("/entries", methods=["POST"])
def create_entry():
    db = get_db()
    video_filename = save_video_upload(request.files.get("video_file"))
    cur = db.execute(
        """
        INSERT INTO video_entries
            (person_id, date_recorded, topic, gujarati_transcript, english_translation, video_link, video_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form["person_id"],
            request.form["date_recorded"].strip(),
            request.form.get("topic", "").strip(),
            request.form.get("gujarati_transcript", "").strip(),
            request.form.get("english_translation", "").strip(),
            request.form.get("video_link", "").strip(),
            video_filename,
        ),
    )
    db.commit()
    return redirect(url_for("stories"))


@app.route("/entries/<int:entry_id>")
def show_entry(entry_id):
    db = get_db()
    entry = db.execute(ENTRY_QUERY + " WHERE video_entries.id = ?", (entry_id,)).fetchone()
    if entry is None:
        return "Entry not found", 404
    visible_ids = current_visible_person_ids()
    if visible_ids is not None and entry["person_id"] not in visible_ids:
        return "Entry not found", 404
    return render_template("entry.html", entry=entry)


@app.route("/entries/<int:entry_id>/edit")
def edit_entry(entry_id):
    db = get_db()
    entry = db.execute(ENTRY_QUERY + " WHERE video_entries.id = ?", (entry_id,)).fetchone()
    if entry is None:
        return "Entry not found", 404
    people = visible_people()
    return render_template("form.html", entry=entry, people=people, preselect_person_id=None)


@app.route("/entries/<int:entry_id>/update", methods=["POST"])
def update_entry(entry_id):
    db = get_db()
    db.execute(
        """
        UPDATE video_entries
        SET person_id = ?, date_recorded = ?, topic = ?,
            gujarati_transcript = ?, english_translation = ?, video_link = ?
        WHERE id = ?
        """,
        (
            request.form["person_id"],
            request.form["date_recorded"].strip(),
            request.form.get("topic", "").strip(),
            request.form.get("gujarati_transcript", "").strip(),
            request.form.get("english_translation", "").strip(),
            request.form.get("video_link", "").strip(),
            entry_id,
        ),
    )
    db.commit()
    return redirect(url_for("show_entry", entry_id=entry_id))


@app.route("/entries/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM video_entries WHERE id = ?", (entry_id,))
    db.commit()
    return redirect(url_for("stories"))


# ---------------------------------------------------------------------------
# Family tree: people + relationships
# ---------------------------------------------------------------------------

def add_relationship(person_id, relation, existing_id, new_name):
    """Link person_id to another person as parent/child/spouse.
    The other person is either picked from existing_id, or created fresh
    from new_name if no existing person was chosen."""
    db = get_db()
    target_id = None
    if existing_id:
        target_id = int(existing_id)
    elif new_name and new_name.strip():
        cur = db.execute(
            "INSERT INTO people (name, family_id) VALUES (?, ?)",
            (new_name.strip(), DEFAULT_FAMILY_ID),
        )
        target_id = cur.lastrowid

    if target_id is None or target_id == person_id:
        return

    if relation == "parent":
        db.execute(
            "INSERT OR IGNORE INTO parent_child (parent_id, child_id) VALUES (?, ?)",
            (target_id, person_id),
        )
    elif relation == "child":
        db.execute(
            "INSERT OR IGNORE INTO parent_child (parent_id, child_id) VALUES (?, ?)",
            (person_id, target_id),
        )
    elif relation == "spouse":
        a, b = sorted((person_id, target_id))
        db.execute(
            "INSERT OR IGNORE INTO spouses (person_a_id, person_b_id) VALUES (?, ?)", (a, b)
        )
    db.commit()


@app.route("/people/new")
def new_person():
    return render_template(
        "person_form.html",
        person=None,
        as_child_of=request.args.get("as_child_of", type=int),
        as_parent_of=request.args.get("as_parent_of", type=int),
        as_spouse_of=request.args.get("as_spouse_of", type=int),
        people=visible_people(),
    )


@app.route("/people", methods=["POST"])
def create_person():
    db = get_db()

    as_child_of = request.form.get("as_child_of", type=int)
    as_parent_of = request.form.get("as_parent_of", type=int)
    as_spouse_of = request.form.get("as_spouse_of", type=int)
    relation_type = request.form.get("relation_type", "").strip()
    relation_person_id = request.form.get("relation_person_id", type=int)
    has_relation = as_child_of or as_parent_of or as_spouse_of or (relation_type and relation_person_id)

    # Every new person must be connected to someone already in the tree
    # (parent, child, or spouse) — a standalone, unconnected person isn't
    # allowed, except for the very first person ever added (nothing to
    # connect to yet).
    already_has_people = db.execute("SELECT 1 FROM people LIMIT 1").fetchone() is not None
    if not has_relation and already_has_people:
        flash("New people need to be connected to an existing family member — pick a parent, child, or spouse below.")
        return redirect(url_for("new_person"))

    cur = db.execute(
        """
        INSERT INTO people (name, surname, birth_date, birth_place, three_words, notes, family_name, family_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form["name"].strip(),
            request.form.get("surname", "").strip() or None,
            request.form.get("birth_date", "").strip() or None,
            request.form.get("birth_place", "").strip() or None,
            request.form.get("three_words", "").strip() or None,
            request.form.get("notes", "").strip() or None,
            request.form.get("family_name", "").strip() or None,
            DEFAULT_FAMILY_ID,
        ),
    )
    new_id = cur.lastrowid
    db.commit()

    if as_child_of:
        add_relationship(as_child_of, "child", new_id, None)
        return redirect(url_for("show_person", person_id=as_child_of))
    if as_parent_of:
        add_relationship(as_parent_of, "parent", new_id, None)
        return redirect(url_for("show_person", person_id=as_parent_of))
    if as_spouse_of:
        add_relationship(as_spouse_of, "spouse", new_id, None)
        return redirect(url_for("show_person", person_id=as_spouse_of))
    if relation_type and relation_person_id:
        # add_relationship's own convention is "existing_id becomes
        # person_id's <relation>" — e.g. relation="child" means
        # existing_id becomes new_id's child. The form is phrased the
        # other way round (from the new person's perspective, which
        # reads far less ambiguously), so translate here.
        relation_map = {"new_is_child": "parent", "new_is_parent": "child", "new_is_spouse": "spouse"}
        add_relationship(new_id, relation_map[relation_type], relation_person_id, None)

    return redirect(url_for("show_person", person_id=new_id))


@app.route("/people/<int:person_id>")
def show_person(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if person is None:
        return "Person not found", 404
    visible_ids = current_visible_person_ids()
    if visible_ids is not None and person_id not in visible_ids:
        return "Person not found", 404

    parents = db.execute(
        """
        SELECT people.* FROM parent_child
        JOIN people ON people.id = parent_child.parent_id
        WHERE parent_child.child_id = ?
        ORDER BY people.name
        """,
        (person_id,),
    ).fetchall()
    children = db.execute(
        """
        SELECT people.* FROM parent_child
        JOIN people ON people.id = parent_child.child_id
        WHERE parent_child.parent_id = ?
        ORDER BY people.birth_date IS NULL, people.birth_date, people.name
        """,
        (person_id,),
    ).fetchall()
    spouses = db.execute(
        """
        SELECT people.* FROM spouses
        JOIN people ON people.id = (
            CASE WHEN spouses.person_a_id = :pid THEN spouses.person_b_id
                 ELSE spouses.person_a_id END
        )
        WHERE spouses.person_a_id = :pid OR spouses.person_b_id = :pid
        ORDER BY people.name
        """,
        {"pid": person_id},
    ).fetchall()
    entries = db.execute(
        "SELECT * FROM video_entries WHERE person_id = ? ORDER BY date_recorded DESC",
        (person_id,),
    ).fetchall()
    all_people = visible_people(exclude_id=person_id)
    contributions = db.execute(
        """
        SELECT DISTINCT contributions.*, people.name AS author_name
        FROM contributions
        LEFT JOIN people ON people.id = contributions.author_id
        LEFT JOIN contribution_people ON contribution_people.contribution_id = contributions.id
        WHERE contributions.author_id = ? OR contribution_people.person_id = ?
        ORDER BY contributions.created_at DESC
        """,
        (person_id, person_id),
    ).fetchall()
    capsule_rows = db.execute(
        CAPSULE_QUERY + " WHERE time_capsules.recipient_id = ? ORDER BY time_capsules.unlock_date",
        (person_id,),
    ).fetchall()
    account = db.execute(
        "SELECT * FROM accounts WHERE person_id = ?", (person_id,)
    ).fetchone()
    book_photos_tagged = db.execute(
        """
        SELECT book_photos.*, book_projects.title AS book_title
        FROM book_photo_people
        JOIN book_photos ON book_photos.id = book_photo_people.book_photo_id
        JOIN book_projects ON book_projects.id = book_photos.book_project_id
        WHERE book_photo_people.person_id = ?
        ORDER BY book_photos.created_at DESC
        """,
        (person_id,),
    ).fetchall()

    return render_template(
        "person.html",
        person=person,
        parents=parents,
        children=children,
        spouses=spouses,
        entries=entries,
        all_people=all_people,
        contributions=contributions,
        kind_labels=CONTRIBUTION_KIND_LABELS,
        capsules=capsule_rows,
        is_unlocked=is_unlocked,
        describe_time_until=describe_time_until,
        account=account,
        book_photos_tagged=book_photos_tagged,
    )


@app.route("/people/<int:person_id>/account/new", methods=["GET", "POST"])
@require_admin
def new_account(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if person is None:
        return "Person not found", 404
    existing = db.execute("SELECT * FROM accounts WHERE person_id = ?", (person_id,)).fetchone()
    if existing is not None:
        return redirect(url_for("edit_account", person_id=person_id))

    if request.method == "GET":
        return render_template("account_form.html", person=person, account=None, error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = 1 if request.form.get("is_admin") else 0

    if not username or not password:
        return render_template(
            "account_form.html", person=person, account=None,
            error="Username and password are both required.",
        )
    if db.execute("SELECT 1 FROM accounts WHERE username = ?", (username,)).fetchone():
        return render_template(
            "account_form.html", person=person, account=None,
            error=f'The username "{username}" is already taken.',
        )

    db.execute(
        "INSERT INTO accounts (person_id, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
        (person_id, username, generate_password_hash(password, method="pbkdf2:sha256"), is_admin),
    )
    db.commit()
    flash(f"Login created for {person['name']}.")
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/people/<int:person_id>/account/edit", methods=["GET", "POST"])
@require_admin
def edit_account(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    account = db.execute("SELECT * FROM accounts WHERE person_id = ?", (person_id,)).fetchone()
    if person is None or account is None:
        return "Not found", 404

    if request.method == "GET":
        return render_template("account_form.html", person=person, account=account, error=None)

    username = request.form.get("username", "").strip()
    new_password = request.form.get("password", "")
    is_admin = 1 if request.form.get("is_admin") else 0

    if not username:
        return render_template(
            "account_form.html", person=person, account=account,
            error="Username is required.",
        )
    clash = db.execute(
        "SELECT 1 FROM accounts WHERE username = ? AND person_id != ?", (username, person_id)
    ).fetchone()
    if clash:
        return render_template(
            "account_form.html", person=person, account=account,
            error=f'The username "{username}" is already taken.',
        )

    if new_password:
        db.execute(
            "UPDATE accounts SET username = ?, password_hash = ?, is_admin = ? WHERE person_id = ?",
            (username, generate_password_hash(new_password, method="pbkdf2:sha256"), is_admin, person_id),
        )
    else:
        db.execute(
            "UPDATE accounts SET username = ?, is_admin = ? WHERE person_id = ?",
            (username, is_admin, person_id),
        )
    db.commit()
    flash(f"Login details updated for {person['name']}.")
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/people/<int:person_id>/edit")
def edit_person(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if person is None:
        return "Person not found", 404
    return render_template("person_form.html", person=person, as_child_of=None, as_parent_of=None, as_spouse_of=None)


@app.route("/people/<int:person_id>/update", methods=["POST"])
def update_person(person_id):
    db = get_db()
    db.execute(
        """
        UPDATE people
        SET name = ?, surname = ?, birth_date = ?, birth_place = ?,
            three_words = ?, notes = ?, family_name = ?
        WHERE id = ?
        """,
        (
            request.form["name"].strip(),
            request.form.get("surname", "").strip() or None,
            request.form.get("birth_date", "").strip() or None,
            request.form.get("birth_place", "").strip() or None,
            request.form.get("three_words", "").strip() or None,
            request.form.get("notes", "").strip() or None,
            request.form.get("family_name", "").strip() or None,
            person_id,
        ),
    )
    db.commit()
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/people/<int:person_id>/delete", methods=["POST"])
def delete_person(person_id):
    db = get_db()
    has_entries = db.execute(
        "SELECT COUNT(*) AS c FROM video_entries WHERE person_id = ?", (person_id,)
    ).fetchone()["c"]
    if has_entries:
        flash("Can't delete this person — they still have story entries linked to them. Delete or reassign those first.")
        return redirect(url_for("show_person", person_id=person_id))
    db.execute("DELETE FROM people WHERE id = ?", (person_id,))
    db.commit()
    return redirect(url_for("tree"))


@app.route("/people/<int:person_id>/parents", methods=["POST"])
def add_parent(person_id):
    add_relationship(person_id, "parent", request.form.get("existing_id"), request.form.get("new_name"))
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/people/<int:person_id>/children", methods=["POST"])
def add_child(person_id):
    add_relationship(person_id, "child", request.form.get("existing_id"), request.form.get("new_name"))
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/people/<int:person_id>/spouses", methods=["POST"])
def add_spouse(person_id):
    add_relationship(person_id, "spouse", request.form.get("existing_id"), request.form.get("new_name"))
    return redirect(url_for("show_person", person_id=person_id))


@app.route("/relationships/parent_child/remove", methods=["POST"])
def remove_parent_child():
    db = get_db()
    db.execute(
        "DELETE FROM parent_child WHERE parent_id = ? AND child_id = ?",
        (request.form["parent_id"], request.form["child_id"]),
    )
    db.commit()
    return redirect(url_for("show_person", person_id=request.form["return_to"]))


@app.route("/relationships/spouse/remove", methods=["POST"])
def remove_spouse():
    db = get_db()
    a, b = sorted((int(request.form["person_a_id"]), int(request.form["person_b_id"])))
    db.execute(
        "DELETE FROM spouses WHERE person_a_id = ? AND person_b_id = ?", (a, b)
    )
    db.commit()
    return redirect(url_for("show_person", person_id=request.form["return_to"]))


def build_family_forest():
    """Find every distinct family branch (one per side — e.g. Mum's side vs
    Dad's side), and build each branch's full nested tree, rooted at its
    eldest known ancestor(s). People who married into a branch (no recorded
    parents of their own) are shown as a spouse rather than a separate root.

    Returns (roots_meta, trees_by_root_id, unattached_people):
    - roots_meta: [{"id":.., "label":..}, ...] for a branch-picker UI.
    - trees_by_root_id: {root_id: nested tree node}.
    - unattached_people: people not reachable from any branch (shouldn't
      normally happen, but shown so nothing silently disappears).
    """
    db = get_db()
    people = {row["id"]: dict(row) for row in db.execute("SELECT * FROM people").fetchall()}

    parents_of = defaultdict(list)
    children_of = defaultdict(list)
    for row in db.execute("SELECT parent_id, child_id FROM parent_child"):
        parents_of[row["child_id"]].append(row["parent_id"])
        children_of[row["parent_id"]].append(row["child_id"])

    spouses_of = defaultdict(list)
    for row in db.execute("SELECT person_a_id, person_b_id FROM spouses"):
        spouses_of[row["person_a_id"]].append(row["person_b_id"])
        spouses_of[row["person_b_id"]].append(row["person_a_id"])

    def sort_key(pid):
        bd = people[pid].get("birth_date")
        return (bd is None, bd or "", people[pid]["name"])

    no_parents = [pid for pid in people if pid not in parents_of]

    def married_in(pid):
        return any(sp in parents_of for sp in spouses_of.get(pid, []))

    true_roots = [pid for pid in no_parents if not married_in(pid)]
    true_roots_set = set(true_roots)

    top_level = []
    skip = set()
    for pid in sorted(true_roots, key=sort_key):
        if pid in skip:
            continue
        top_level.append(pid)
        for sp in spouses_of.get(pid, []):
            if sp in true_roots_set:
                skip.add(sp)

    all_rendered = set()
    trees_by_root = {}
    roots_meta = []

    for root_pid in top_level:
        rendered = set()

        def build_node(pid, ancestry):
            rendered.add(pid)
            spouse_ids = spouses_of.get(pid, [])
            rendered.update(spouse_ids)
            spouses = [people[sp] for sp in sorted(spouse_ids, key=sort_key)]

            # Children may be recorded under either partner, so gather from both.
            child_id_set = set()
            for parent_id in [pid] + spouse_ids:
                child_id_set.update(children_of.get(parent_id, []))
            child_ids = sorted(child_id_set, key=sort_key)

            next_ancestry = ancestry | {pid} | set(spouse_ids)
            children_nodes = []
            for cid in child_ids:
                if cid in ancestry:
                    continue
                if cid in rendered:
                    # Rare (e.g. cousins marrying within the same branch) —
                    # already shown once above, don't duplicate the subtree.
                    children_nodes.append(
                        {"person": people[cid], "spouses": [], "children": [], "cross_ref": True}
                    )
                    continue
                children_nodes.append(build_node(cid, next_ancestry))
            return {"person": people[pid], "spouses": spouses, "children": children_nodes, "cross_ref": False}

        trees_by_root[root_pid] = build_node(root_pid, set())
        all_rendered.update(rendered)

        names = [people[root_pid]["name"]] + [
            people[sp]["name"] for sp in sorted(spouses_of.get(root_pid, []), key=sort_key)
        ]
        auto_label = " & ".join(names)

        custom_name = people[root_pid].get("family_name")
        if not custom_name:
            for sp in spouses_of.get(root_pid, []):
                if people[sp].get("family_name"):
                    custom_name = people[sp]["family_name"]
                    break

        roots_meta.append({"id": root_pid, "label": custom_name or auto_label})

    unattached = sorted(
        (p for pid, p in people.items() if pid not in all_rendered),
        key=lambda p: p["name"],
    )
    return roots_meta, trees_by_root, unattached


RELATIONSHIP_LABELS = {
    "child": "Children",
    "child_in_law": "Sons/daughters-in-law",
    "grandchild": "Grandchildren",
    "great_grandchild": "Great-grandchildren",
    "any": "Anyone else",
}


def get_book_subject_ids(book_id):
    db = get_db()
    return [
        row["person_id"]
        for row in db.execute(
            "SELECT person_id FROM book_subjects WHERE book_project_id = ?", (book_id,)
        )
    ]


def classify_relationship(subject_ids, viewer_id):
    """Classify viewer_id's relationship to a Legacy Book's subject(s) (one
    person or a couple), for picking which question set they see:
    child, child_in_law, grandchild, great_grandchild, or any (catch-all —
    e.g. a grandchild's spouse, or anyone more distantly related)."""
    db = get_db()
    children_of = defaultdict(list)
    for row in db.execute("SELECT parent_id, child_id FROM parent_child"):
        children_of[row["parent_id"]].append(row["child_id"])
    spouses_of = defaultdict(list)
    for row in db.execute("SELECT person_a_id, person_b_id FROM spouses"):
        spouses_of[row["person_a_id"]].append(row["person_b_id"])
        spouses_of[row["person_b_id"]].append(row["person_a_id"])

    children = set()
    for sid in subject_ids:
        children.update(children_of.get(sid, []))
    if viewer_id in children:
        return "child"

    children_in_law = set()
    for cid in children:
        children_in_law.update(spouses_of.get(cid, []))
    children_in_law -= children
    if viewer_id in children_in_law:
        return "child_in_law"

    grandchildren = set()
    for cid in children:
        grandchildren.update(children_of.get(cid, []))
    if viewer_id in grandchildren:
        return "grandchild"

    great_grandchildren = set()
    for gid in grandchildren:
        great_grandchildren.update(children_of.get(gid, []))
    if viewer_id in great_grandchildren:
        return "great_grandchild"

    return "any"


def get_branch_membership():
    """Maps person_id -> set of family-tree root_ids whose rendered branch
    includes them. Deliberately reuses build_family_forest()'s own render
    of each branch (not raw graph connectivity) — a distant in-law chain
    (e.g. your daughter's husband's father) can connect two branches in
    the raw parent_child/spouses graph without either side actually
    belonging to the other's branch. build_family_forest() already draws
    that line correctly (spouses attach as leaves, not as a bridge into
    their own separate branch), so membership here matches exactly what
    someone sees when they open a given branch on the Family Tree page."""
    roots_meta, trees_by_root, _ = build_family_forest()
    membership = defaultdict(set)

    def walk(node, root_id):
        membership[node["person"]["id"]].add(root_id)
        for spouse in node["spouses"]:
            membership[spouse["id"]].add(root_id)
        for child in node["children"]:
            walk(child, root_id)

    for root in roots_meta:
        walk(trees_by_root[root["id"]], root["id"])
    return membership


def get_solo_person_ids():
    """People who are the sole member of their own family-tree branch —
    no recorded parent, child, or spouse yet (build_family_forest() makes
    every such person the root of a one-person branch of their own, they
    don't show up in its "unattached" list). Treated as visible to
    everyone rather than hidden: a freshly-added standalone person isn't
    "in the wrong branch," they just aren't in anyone's branch yet.
    Otherwise, adding a new person and being redirected straight to their
    own profile page would 404 for whoever just added them."""
    roots_meta, trees_by_root, _ = build_family_forest()
    return {
        root["id"] for root in roots_meta
        if not trees_by_root[root["id"]]["children"]
        and not trees_by_root[root["id"]]["spouses"]
    }


def get_visible_person_ids(seed_ids):
    """Every person_id who shares at least one family-tree branch with
    any of seed_ids — e.g. everyone a given viewer is allowed to see, or
    everyone belonging to a Legacy Book's own subject(s). Accepts a
    single person_id or an iterable of them (a couple, say)."""
    if isinstance(seed_ids, int):
        seed_ids = {seed_ids}
    else:
        seed_ids = set(seed_ids)
    membership = get_branch_membership()
    solo_ids = get_solo_person_ids()

    seed_branches = set()
    for pid in seed_ids:
        seed_branches |= membership.get(pid, set())
    if not seed_branches:
        return seed_ids | solo_ids

    visible = {
        pid for pid, branches in membership.items()
        if branches & seed_branches
    }
    return visible | solo_ids | seed_ids


def current_visible_person_ids():
    """Per-request cached accessor. Returns None for admins (meaning: no
    restriction, see everyone) — every other route treats None as
    'skip filtering'."""
    if "visible_ids" not in g:
        person = current_person()
        if person is None:
            g.visible_ids = set()
        elif person["is_admin"]:
            g.visible_ids = None
        else:
            g.visible_ids = get_visible_person_ids(person["id"])
    return g.visible_ids


def visible_contribution_ids(visible_ids):
    """Contribution ids where the author or at least one tagged person is
    visible. None input (admin) means no restriction — returns None."""
    if visible_ids is None:
        return None
    db = get_db()
    ids = set()
    for row in db.execute("SELECT id, author_id FROM contributions"):
        if row["author_id"] in visible_ids:
            ids.add(row["id"])
    for row in db.execute("SELECT contribution_id, person_id FROM contribution_people"):
        if row["person_id"] in visible_ids:
            ids.add(row["contribution_id"])
    return ids


def visible_capsule_ids(visible_ids):
    """Time capsule ids where the recipient or author is visible. None
    input (admin) means no restriction — returns None."""
    if visible_ids is None:
        return None
    db = get_db()
    ids = set()
    for row in db.execute("SELECT id, recipient_id, author_id FROM time_capsules"):
        if row["recipient_id"] in visible_ids or row["author_id"] in visible_ids:
            ids.add(row["id"])
    return ids


def visible_people(exclude_id=None):
    """People visible to the current viewer, sorted by name — used for
    person-picker dropdowns (adding a relation, tagging a contribution,
    etc.) so a non-admin can't see or tag someone from a family branch
    they don't belong to."""
    db = get_db()
    rows = db.execute("SELECT * FROM people ORDER BY name").fetchall()
    visible_ids = current_visible_person_ids()
    if visible_ids is not None:
        rows = [r for r in rows if r["id"] in visible_ids]
    if exclude_id is not None:
        rows = [r for r in rows if r["id"] != exclude_id]
    return rows


@app.route("/tree")
def tree():
    roots_meta, trees_by_root, unattached = build_family_forest()

    person = current_person()
    if not (person and person["is_admin"]):
        allowed_roots = get_branch_membership().get(session["person_id"], set())
        roots_meta = [r for r in roots_meta if r["id"] in allowed_roots]
        visible_ids = current_visible_person_ids()
        unattached = [p for p in unattached if p["id"] in visible_ids]

    selected_root = request.args.get("root", type=int)
    if selected_root not in {r["id"] for r in roots_meta}:
        selected_root = roots_meta[0]["id"] if roots_meta else None
    return render_template(
        "tree.html",
        roots=roots_meta,
        selected_root=selected_root,
        tree=trees_by_root.get(selected_root),
        unattached=unattached,
    )


# ---------------------------------------------------------------------------
# Contribution feed
# ---------------------------------------------------------------------------

CONTRIBUTION_QUERY = """
    SELECT contributions.*, people.name AS author_name
    FROM contributions
    LEFT JOIN people ON people.id = contributions.author_id
"""


def save_photo_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        flash(f"Photo not saved — \"{file_storage.filename}\" isn't a supported image type.")
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def get_linked_people(contribution_id):
    db = get_db()
    return db.execute(
        """
        SELECT people.* FROM contribution_people
        JOIN people ON people.id = contribution_people.person_id
        WHERE contribution_people.contribution_id = ?
        ORDER BY people.name
        """,
        (contribution_id,),
    ).fetchall()


def set_linked_people(contribution_id, person_ids):
    db = get_db()
    db.execute("DELETE FROM contribution_people WHERE contribution_id = ?", (contribution_id,))
    for pid in person_ids:
        db.execute(
            "INSERT OR IGNORE INTO contribution_people (contribution_id, person_id) VALUES (?, ?)",
            (contribution_id, pid),
        )
    db.commit()


def get_book_photo_people(book_photo_id):
    db = get_db()
    return db.execute(
        """
        SELECT people.* FROM book_photo_people
        JOIN people ON people.id = book_photo_people.person_id
        WHERE book_photo_people.book_photo_id = ?
        ORDER BY people.name
        """,
        (book_photo_id,),
    ).fetchall()


def set_book_photo_people(book_photo_id, person_ids):
    db = get_db()
    db.execute("DELETE FROM book_photo_people WHERE book_photo_id = ?", (book_photo_id,))
    for pid in person_ids:
        db.execute(
            "INSERT OR IGNORE INTO book_photo_people (book_photo_id, person_id) VALUES (?, ?)",
            (book_photo_id, pid),
        )
    db.commit()


@app.route("/feed")
def feed():
    db = get_db()
    kind = request.args.get("kind", "").strip()
    query = CONTRIBUTION_QUERY
    params = ()
    if kind:
        query += " WHERE contributions.kind = ?"
        params = (kind,)
    query += " ORDER BY contributions.created_at DESC, contributions.id DESC"
    contributions = db.execute(query, params).fetchall()

    visible_ids = current_visible_person_ids()
    if visible_ids is not None:
        allowed = visible_contribution_ids(visible_ids)
        contributions = [c for c in contributions if c["id"] in allowed]

    return render_template(
        "feed.html", contributions=contributions, kinds=CONTRIBUTION_KINDS,
        kind_labels=CONTRIBUTION_KIND_LABELS, active_kind=kind,
    )


@app.route("/feed/new")
def new_contribution():
    people = visible_people()
    person_id = request.args.get("person_id", type=int)
    linked_ids = {person_id} if person_id else set()
    return render_template(
        "contribution_form.html", contribution=None, people=people,
        kinds=CONTRIBUTION_KINDS, linked_ids=linked_ids,
    )


@app.route("/feed", methods=["POST"])
def create_contribution():
    db = get_db()
    photo_filename = save_photo_upload(request.files.get("photo"))
    cur = db.execute(
        """
        INSERT INTO contributions (kind, title, body, photo_filename, author_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            request.form["kind"],
            request.form["title"].strip(),
            request.form.get("body", "").strip(),
            photo_filename,
            request.form.get("author_id") or None,
        ),
    )
    contribution_id = cur.lastrowid
    db.commit()
    person_ids = [int(pid) for pid in request.form.getlist("person_ids")]
    set_linked_people(contribution_id, person_ids)
    return redirect(url_for("show_contribution", contribution_id=contribution_id))


@app.route("/feed/<int:contribution_id>")
def show_contribution(contribution_id):
    db = get_db()
    contribution = db.execute(
        CONTRIBUTION_QUERY + " WHERE contributions.id = ?", (contribution_id,)
    ).fetchone()
    if contribution is None:
        return "Entry not found", 404
    visible_ids = current_visible_person_ids()
    if visible_ids is not None and contribution_id not in visible_contribution_ids(visible_ids):
        return "Entry not found", 404
    linked_people = get_linked_people(contribution_id)
    return render_template(
        "contribution.html", contribution=contribution, linked_people=linked_people,
        kind_labels=CONTRIBUTION_KIND_LABELS,
    )


@app.route("/feed/<int:contribution_id>/edit")
def edit_contribution(contribution_id):
    db = get_db()
    contribution = db.execute(
        CONTRIBUTION_QUERY + " WHERE contributions.id = ?", (contribution_id,)
    ).fetchone()
    if contribution is None:
        return "Entry not found", 404
    people = visible_people()
    linked_ids = {p["id"] for p in get_linked_people(contribution_id)}
    return render_template(
        "contribution_form.html", contribution=contribution, people=people,
        kinds=CONTRIBUTION_KINDS, linked_ids=linked_ids,
    )


@app.route("/feed/<int:contribution_id>/update", methods=["POST"])
def update_contribution(contribution_id):
    db = get_db()
    photo_filename = save_photo_upload(request.files.get("photo"))
    if photo_filename:
        db.execute(
            """
            UPDATE contributions
            SET kind = ?, title = ?, body = ?, photo_filename = ?, author_id = ?
            WHERE id = ?
            """,
            (
                request.form["kind"],
                request.form["title"].strip(),
                request.form.get("body", "").strip(),
                photo_filename,
                request.form.get("author_id") or None,
                contribution_id,
            ),
        )
    else:
        db.execute(
            """
            UPDATE contributions
            SET kind = ?, title = ?, body = ?, author_id = ?
            WHERE id = ?
            """,
            (
                request.form["kind"],
                request.form["title"].strip(),
                request.form.get("body", "").strip(),
                request.form.get("author_id") or None,
                contribution_id,
            ),
        )
    db.commit()
    person_ids = [int(pid) for pid in request.form.getlist("person_ids")]
    set_linked_people(contribution_id, person_ids)
    return redirect(url_for("show_contribution", contribution_id=contribution_id))


@app.route("/feed/<int:contribution_id>/delete", methods=["POST"])
def delete_contribution(contribution_id):
    db = get_db()
    db.execute("DELETE FROM contributions WHERE id = ?", (contribution_id,))
    db.commit()
    return redirect(url_for("feed"))


# ---------------------------------------------------------------------------
# Time capsule letters
# ---------------------------------------------------------------------------

CAPSULE_QUERY = """
    SELECT time_capsules.*,
           recipient.name AS recipient_name,
           author.name AS author_name
    FROM time_capsules
    JOIN people AS recipient ON recipient.id = time_capsules.recipient_id
    LEFT JOIN people AS author ON author.id = time_capsules.author_id
"""


def is_unlocked(unlock_date_str):
    return date.today().isoformat() >= unlock_date_str


def describe_time_until(unlock_date_str):
    days = (date.fromisoformat(unlock_date_str) - date.today()).days
    if days <= 0:
        return "unlocks today"
    if days >= 365:
        years = days // 365
        return f"unlocks in about {years} year{'s' if years != 1 else ''}"
    if days >= 30:
        months = days // 30
        return f"unlocks in about {months} month{'s' if months != 1 else ''}"
    return f"unlocks in {days} day{'s' if days != 1 else ''}"


@app.route("/capsules")
def capsules():
    db = get_db()
    rows = db.execute(CAPSULE_QUERY + " ORDER BY time_capsules.unlock_date").fetchall()

    visible_ids = current_visible_person_ids()
    if visible_ids is not None:
        allowed = visible_capsule_ids(visible_ids)
        rows = [r for r in rows if r["id"] in allowed]

    sealed = [r for r in rows if not is_unlocked(r["unlock_date"])]
    unlocked = sorted(
        (r for r in rows if is_unlocked(r["unlock_date"])),
        key=lambda r: r["unlock_date"],
        reverse=True,
    )
    return render_template(
        "capsules.html", sealed=sealed, unlocked=unlocked, describe_time_until=describe_time_until
    )


@app.route("/capsules/new")
def new_capsule():
    people = visible_people()
    return render_template(
        "capsule_form.html", capsule=None, people=people,
        preselect_recipient_id=request.args.get("person_id", type=int),
    )


@app.route("/capsules", methods=["POST"])
def create_capsule():
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO time_capsules (recipient_id, author_id, title, body, unlock_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            request.form["recipient_id"],
            request.form.get("author_id") or None,
            request.form["title"].strip(),
            request.form["body"].strip(),
            request.form["unlock_date"].strip(),
        ),
    )
    db.commit()
    return redirect(url_for("show_capsule", capsule_id=cur.lastrowid))


@app.route("/capsules/<int:capsule_id>")
def show_capsule(capsule_id):
    db = get_db()
    capsule = db.execute(CAPSULE_QUERY + " WHERE time_capsules.id = ?", (capsule_id,)).fetchone()
    if capsule is None:
        return "Letter not found", 404
    visible_ids = current_visible_person_ids()
    if visible_ids is not None and capsule_id not in visible_capsule_ids(visible_ids):
        return "Letter not found", 404
    unlocked = is_unlocked(capsule["unlock_date"])
    return render_template(
        "capsule.html", capsule=capsule, unlocked=unlocked,
        describe_time_until=describe_time_until,
    )


@app.route("/capsules/<int:capsule_id>/edit")
def edit_capsule(capsule_id):
    db = get_db()
    capsule = db.execute(CAPSULE_QUERY + " WHERE time_capsules.id = ?", (capsule_id,)).fetchone()
    if capsule is None:
        return "Letter not found", 404
    if not is_unlocked(capsule["unlock_date"]):
        flash("This letter is sealed and can't be edited until it unlocks — delete and rewrite it if you need to change something.")
        return redirect(url_for("show_capsule", capsule_id=capsule_id))
    people = visible_people()
    return render_template(
        "capsule_form.html", capsule=capsule, people=people, preselect_recipient_id=None
    )


@app.route("/capsules/<int:capsule_id>/update", methods=["POST"])
def update_capsule(capsule_id):
    db = get_db()
    existing = db.execute(
        "SELECT unlock_date FROM time_capsules WHERE id = ?", (capsule_id,)
    ).fetchone()
    if existing is None:
        return "Letter not found", 404
    if not is_unlocked(existing["unlock_date"]):
        flash("This letter is sealed and can't be edited until it unlocks.")
        return redirect(url_for("show_capsule", capsule_id=capsule_id))
    db.execute(
        """
        UPDATE time_capsules
        SET recipient_id = ?, author_id = ?, title = ?, body = ?, unlock_date = ?
        WHERE id = ?
        """,
        (
            request.form["recipient_id"],
            request.form.get("author_id") or None,
            request.form["title"].strip(),
            request.form["body"].strip(),
            request.form["unlock_date"].strip(),
            capsule_id,
        ),
    )
    db.commit()
    return redirect(url_for("show_capsule", capsule_id=capsule_id))


@app.route("/capsules/<int:capsule_id>/delete", methods=["POST"])
def delete_capsule(capsule_id):
    db = get_db()
    db.execute("DELETE FROM time_capsules WHERE id = ?", (capsule_id,))
    db.commit()
    return redirect(url_for("capsules"))


# ---------------------------------------------------------------------------
# Legacy Books
# ---------------------------------------------------------------------------

@app.route("/books")
def books_index():
    db = get_db()
    projects = db.execute("SELECT * FROM book_projects ORDER BY created_at DESC").fetchall()
    return render_template("books.html", projects=projects)


def clone_question_bank_for_book(book_project_id):
    """Copies the shared template (book_project_id IS NULL) into a new
    book's own rows, so its questions can be edited independently later
    without touching the template or any other book."""
    db = get_db()
    template_rows = db.execute(
        "SELECT text, target_relationship, sort_order FROM book_questions"
        " WHERE book_project_id IS NULL ORDER BY id"
    ).fetchall()
    for row in template_rows:
        db.execute(
            "INSERT INTO book_questions (text, target_relationship, sort_order, book_project_id)"
            " VALUES (?, ?, ?, ?)",
            (row["text"], row["target_relationship"], row["sort_order"], book_project_id),
        )
    db.commit()


@app.route("/books/new", methods=["GET", "POST"])
@require_admin
def new_book():
    db = get_db()
    people = db.execute("SELECT * FROM people ORDER BY name").fetchall()

    if request.method == "GET":
        return render_template("book_new.html", people=people, error=None, selected_ids=[], title="")

    subject_ids = [int(pid) for pid in request.form.getlist("subject_ids")]
    title = request.form.get("title", "").strip()

    if not subject_ids or len(subject_ids) > 2:
        return render_template(
            "book_new.html", people=people,
            error="Pick one person, or a couple (two people).",
            selected_ids=subject_ids, title=title,
        )

    if not title:
        names = [p["name"] for p in people if p["id"] in subject_ids]
        title = f"The Life of {' & '.join(names)}"

    cur = db.execute(
        "INSERT INTO book_projects (title, created_by) VALUES (?, ?)",
        (title, session["person_id"]),
    )
    book_id = cur.lastrowid
    for pid in subject_ids:
        db.execute(
            "INSERT INTO book_subjects (book_project_id, person_id) VALUES (?, ?)",
            (book_id, pid),
        )
    db.commit()
    clone_question_bank_for_book(book_id)
    return redirect(url_for("show_book", book_id=book_id))


@app.route("/books/<int:book_id>")
def show_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM book_projects WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return "Book not found", 404

    subjects = db.execute(
        """
        SELECT people.* FROM book_subjects
        JOIN people ON people.id = book_subjects.person_id
        WHERE book_subjects.book_project_id = ?
        ORDER BY people.name
        """,
        (book_id,),
    ).fetchall()
    subject_ids = [s["id"] for s in subjects]

    entries = []
    if subject_ids:
        placeholders = ",".join("?" * len(subject_ids))
        entries = db.execute(
            ENTRY_QUERY + f" WHERE video_entries.person_id IN ({placeholders})"
            " ORDER BY video_entries.date_recorded",
            subject_ids,
        ).fetchall()

    viewer_id = session["person_id"]
    relationship = classify_relationship(subject_ids, viewer_id)

    questions = db.execute(
        "SELECT * FROM book_questions WHERE book_project_id = ? AND target_relationship = ? ORDER BY sort_order",
        (book_id, relationship),
    ).fetchall()

    existing_answers = {
        row["question_id"]: row["answer_text"]
        for row in db.execute(
            "SELECT question_id, answer_text FROM book_answers WHERE book_project_id = ? AND person_id = ?",
            (book_id, viewer_id),
        )
    }

    contributor_count = db.execute(
        "SELECT COUNT(DISTINCT person_id) AS c FROM book_answers WHERE book_project_id = ?",
        (book_id,),
    ).fetchone()["c"]

    photo_count = db.execute(
        "SELECT COUNT(*) AS c FROM book_photos WHERE book_project_id = ?", (book_id,)
    ).fetchone()["c"]

    return render_template(
        "book.html",
        book=book,
        subjects=subjects,
        entries=entries,
        questions=questions,
        existing_answers=existing_answers,
        contributor_count=contributor_count,
        photo_count=photo_count,
    )


@app.route("/books/<int:book_id>/questions/edit", methods=["GET", "POST"])
@require_admin
def edit_book_questions(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM book_projects WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return "Book not found", 404

    if request.method == "POST":
        for key, value in request.form.items():
            if not key.startswith("question_"):
                continue
            question_id = int(key[len("question_"):])
            new_text = value.strip()
            if new_text:
                db.execute(
                    "UPDATE book_questions SET text = ? WHERE id = ? AND book_project_id = ?",
                    (new_text, question_id, book_id),
                )
        db.commit()
        flash("Questions updated for this book.")
        return redirect(url_for("show_book", book_id=book_id))

    questions = db.execute(
        "SELECT * FROM book_questions WHERE book_project_id = ? ORDER BY target_relationship, sort_order",
        (book_id,),
    ).fetchall()
    return render_template(
        "book_questions_edit.html", book=book, questions=questions,
        relationship_labels=RELATIONSHIP_LABELS,
    )


@app.route("/books/<int:book_id>/answers", methods=["POST"])
def submit_book_answers(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM book_projects WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return "Book not found", 404

    viewer_id = session["person_id"]
    for key, value in request.form.items():
        if not key.startswith("question_"):
            continue
        question_id = int(key[len("question_"):])
        answer_text = value.strip()
        if not answer_text:
            continue
        db.execute(
            """
            INSERT INTO book_answers (book_project_id, question_id, person_id, answer_text)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(book_project_id, question_id, person_id)
            DO UPDATE SET answer_text = excluded.answer_text
            """,
            (book_id, question_id, viewer_id, answer_text),
        )
    db.commit()
    flash("Your answers have been saved.")
    return redirect(url_for("show_book", book_id=book_id))


@app.route("/books/<int:book_id>/photos")
def book_photos(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM book_projects WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return "Book not found", 404

    photos = db.execute(
        """
        SELECT book_photos.*, people.name AS uploaded_by_name
        FROM book_photos
        LEFT JOIN people ON people.id = book_photos.uploaded_by
        WHERE book_photos.book_project_id = ?
        ORDER BY book_photos.created_at DESC
        """,
        (book_id,),
    ).fetchall()
    tagged_by_photo = {photo["id"]: get_book_photo_people(photo["id"]) for photo in photos}

    book_family_ids = get_visible_person_ids(get_book_subject_ids(book_id))
    people = [p for p in db.execute("SELECT * FROM people ORDER BY name") if p["id"] in book_family_ids]

    return render_template(
        "book_photos.html", book=book, photos=photos, tagged_by_photo=tagged_by_photo,
        people=people,
    )


@app.route("/books/<int:book_id>/photos", methods=["POST"])
def create_book_photo(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM book_projects WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        return "Book not found", 404

    photo_filename = save_photo_upload(request.files.get("photo"))
    if not photo_filename:
        return redirect(url_for("book_photos", book_id=book_id))

    cur = db.execute(
        "INSERT INTO book_photos (book_project_id, photo_filename, caption, uploaded_by) VALUES (?, ?, ?, ?)",
        (book_id, photo_filename, request.form.get("caption", "").strip() or None, session["person_id"]),
    )
    photo_id = cur.lastrowid
    db.commit()
    person_ids = [int(pid) for pid in request.form.getlist("person_ids")]
    set_book_photo_people(photo_id, person_ids)
    flash("Photo added.")
    return redirect(url_for("book_photos", book_id=book_id))


@app.route("/books/<int:book_id>/photos/<int:photo_id>/delete", methods=["POST"])
def delete_book_photo(book_id, photo_id):
    db = get_db()
    db.execute(
        "DELETE FROM book_photos WHERE id = ? AND book_project_id = ?", (photo_id, book_id)
    )
    db.commit()
    return redirect(url_for("book_photos", book_id=book_id))


if not DATABASE.exists():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
