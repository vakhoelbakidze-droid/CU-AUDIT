-- Caucasus University -- აუდიტორიების აღჭურვილობის ბაზა

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    floor TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    access_point TEXT DEFAULT '',
    projector TEXT DEFAULT '',
    smartboard TEXT DEFAULT '',
    computer TEXT DEFAULT '',
    monitor TEXT DEFAULT '',
    camera TEXT DEFAULT '',
    speaker TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER,
    room_code TEXT NOT NULL,
    action TEXT NOT NULL,           -- created / updated / deleted
    field_name TEXT DEFAULT '',
    old_value TEXT DEFAULT '',
    new_value TEXT DEFAULT '',
    changed_by TEXT DEFAULT '',
    changed_at TEXT DEFAULT (datetime('now', 'localtime'))
);
