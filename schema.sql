-- Anvay database schema
-- SQLite: the whole archive lives in one file (archive.db) you can copy,
-- back up, or open with any standard SQLite tool if you ever want to move
-- the data somewhere else.

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- however they're known in the family (e.g. "Dada", "Nani", "Raj")
    surname TEXT,                       -- optional, e.g. "Vekaria"
    birth_date TEXT,                    -- YYYY-MM-DD, optional
    birth_place TEXT,                   -- optional, e.g. "Nairobi, Kenya"
    three_words TEXT,                   -- optional, comma-separated e.g. "Kind, Funny, Determined"
    notes TEXT,                         -- anything else worth noting about them
    family_name TEXT,                   -- optional — names this person's family tree branch
                                         -- (only meaningful when they have no recorded parents,
                                         -- i.e. they're the eldest known ancestor of a branch)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per parent/child link. A child can have more than one row
-- (e.g. two parents), and a parent can have many children.
CREATE TABLE IF NOT EXISTS parent_child (
    parent_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    child_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (parent_id, child_id)
);

-- One row per spouse/partner pair. Order doesn't matter.
CREATE TABLE IF NOT EXISTS spouses (
    person_a_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    person_b_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (person_a_id, person_b_id)
);

CREATE TABLE IF NOT EXISTS video_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    date_recorded TEXT NOT NULL,        -- stored as YYYY-MM-DD
    topic TEXT,                         -- short topic/summary
    gujarati_transcript TEXT,           -- primary source, never overwritten
    english_translation TEXT,           -- lives alongside the original
    video_link TEXT,                    -- cloud link to the actual video file
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The contribution feed: memories, photos, stories, traditions, and notes
-- that any family member can add.
CREATE TABLE IF NOT EXISTS contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                 -- memory, photo, story, tradition, note
    title TEXT NOT NULL,
    body TEXT,                          -- the story/context/why behind it
    photo_filename TEXT,                -- optional, stored under static/uploads/
    author_id INTEGER REFERENCES people(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which family members a contribution is tagged/linked to (beyond the author).
CREATE TABLE IF NOT EXISTS contribution_people (
    contribution_id INTEGER NOT NULL REFERENCES contributions(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (contribution_id, person_id)
);

-- Letters written now, addressed to someone, hidden until unlock_date passes.
-- The seal is an honor-system convention (this app has no login/encryption) —
-- the point is to not casually stumble on it, not to defeat a determined look.
CREATE TABLE IF NOT EXISTS time_capsules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL REFERENCES people(id),
    author_id INTEGER REFERENCES people(id),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    unlock_date TEXT NOT NULL,          -- YYYY-MM-DD; sealed until this date passes
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
