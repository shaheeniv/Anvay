-- Anvay database schema
-- SQLite: the whole archive lives in one file (archive.db) you can copy,
-- back up, or open with any standard SQLite tool if you ever want to move
-- the data somewhere else.

-- One row per family using this archive. Today there's only ever one row —
-- this app is built for a single family, not as a public multi-tenant
-- product — but shaping the data this way now means that door isn't
-- expensive to open later: every other table already reaches a family
-- transitively by joining through people.family_id, so nothing else needs
-- its own family_id column.
CREATE TABLE IF NOT EXISTS families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO families (id, name) VALUES (1, 'The Vekaria-Bhudia Family');

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
    family_id INTEGER NOT NULL REFERENCES families(id),
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
    video_link TEXT,                    -- optional cloud link, when no file is uploaded
    video_filename TEXT,                -- optional, stored under videos/ — the actual video file
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
    video_filename TEXT,                -- optional, stored under DATA_DIR/videos/ (mutually exclusive with photo_filename)
    event_month INTEGER,                -- 1-12, when the photo/video was actually taken (not when it was uploaded)
    event_year INTEGER,
    location TEXT,                      -- optional, e.g. "Nairobi, Kenya"
    author_id INTEGER REFERENCES people(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Which family members a contribution is tagged/linked to (beyond the author).
CREATE TABLE IF NOT EXISTS contribution_people (
    contribution_id INTEGER NOT NULL REFERENCES contributions(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (contribution_id, person_id)
);

-- Login credentials. A separate table (not columns on people) because not
-- everyone needs an account — young kids in the tree, for instance — and
-- it mirrors the existing pattern of small single-purpose tables (spouses,
-- contribution_people) rather than overloading people.
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL UNIQUE REFERENCES people(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    email TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Email is the login identifier now (usernames are gone) but the column
-- stays nullable at the DB level -- some accounts predate this change and
-- a hard NOT NULL migration risks breaking them. A partial unique index
-- (skipping NULLs) still enforces "no two accounts share an email"
-- without that risk. Enforcing "every new account has one" is done in
-- the application layer instead (new_account()), not here.
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_email ON accounts(email) WHERE email IS NOT NULL;

-- A single-use, expiring link emailed to someone to either set their
-- initial password (a brand-new account has an unusable random
-- placeholder password_hash until this completes) or reset a forgotten
-- one -- both are the same underlying action, so one table covers both.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT
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

-- "Legacy Book" projects: a time-boxed biography for one person or a couple.
-- The subject's own video_entries form the spine; everyone else answers
-- targeted questions instead, grouped by their relationship to the subject.
CREATE TABLE IF NOT EXISTS book_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,                        -- e.g. "The Life of Mavji & Radha"
    status TEXT NOT NULL DEFAULT 'collecting',  -- collecting, compiling, ready
    created_by INTEGER REFERENCES people(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 1 row = a single subject, 2 rows = a couple. Its own table (not nullable
-- columns on book_projects) so "one person or a couple" is just "1 or 2
-- rows," not a special case.
CREATE TABLE IF NOT EXISTS book_subjects (
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id),
    PRIMARY KEY (book_project_id, person_id)
);

-- Question bank. Rows with book_project_id = NULL are the starting
-- template, cloned into a book's own rows (book_project_id set) when
-- that book is created — so each book's questions can be edited
-- independently afterward (e.g. one family's migration story mentions
-- Uganda, another's mentions Kenya) without affecting any other book or
-- the shared template new books clone from. target_relationship is one
-- of: child, child_in_law, grandchild, great_grandchild, any (a catch-all
-- for anyone else, e.g. a grandchild's spouse, close family friends).
CREATE TABLE IF NOT EXISTS book_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    target_relationship TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    book_project_id INTEGER REFERENCES book_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES book_questions(id),
    person_id INTEGER NOT NULL REFERENCES people(id),
    answer_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(book_project_id, question_id, person_id)
);

-- Marks one person's answers for one book as final. book_answers rows
-- stay freely editable (save-as-you-go drafts) right up until a row
-- exists here -- after that, submit_book_answers() refuses further
-- edits. An admin can delete this row to unlock someone's answers again
-- if they submitted by mistake.
CREATE TABLE IF NOT EXISTS book_submissions (
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (book_project_id, person_id)
);

-- Which existing Contributions-feed photos (kind='photo') are relevant to
-- a given Legacy Book. Photos are only ever added in one place — the
-- Contributions feed — a book just marks which ones apply to it, for use
-- when it's eventually compiled.
CREATE TABLE IF NOT EXISTS book_contribution_photos (
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    contribution_id INTEGER NOT NULL REFERENCES contributions(id) ON DELETE CASCADE,
    PRIMARY KEY (book_project_id, contribution_id)
);

-- A named, admin-issued invite link for someone outside the family tree
-- (no person row, no account) to contribute memories to one specific book.
-- The token itself is the credential — knowing it is what grants access to
-- the public /contribute/<token> page, so it must be long and random.
-- revoked_at lets an admin kill a link without deleting the record (and
-- without deleting anything that person already contributed).
CREATE TABLE IF NOT EXISTS book_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    contributor_name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_by INTEGER REFERENCES people(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT
);

-- What an outside contributor submits through their invite link. Starts as
-- 'pending' and is invisible to the family until an admin approves it —
-- the link could be forwarded further than intended, so nothing outside
-- contributors write goes into the book unreviewed.
CREATE TABLE IF NOT EXISTS book_guest_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_project_id INTEGER NOT NULL REFERENCES book_projects(id) ON DELETE CASCADE,
    invite_id INTEGER NOT NULL REFERENCES book_invites(id) ON DELETE CASCADE,
    memory_text TEXT,
    photo_filename TEXT,
    video_filename TEXT,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, approved, rejected
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewed_by INTEGER REFERENCES people(id)
);

-- Seed the default question bank (only runs once — INSERT OR IGNORE against
-- fixed ids means re-running schema.sql on an existing database is safe).
-- "child" is deliberately the longest and most structured section (Uganda →
-- Oldham → who they were as parents), since it's the spine of the book.
INSERT OR IGNORE INTO book_questions (id, text, target_relationship, sort_order) VALUES
    (1, 'What do you remember about life in Uganda before you left?', 'child', 1),
    (2, 'What do you know about how and why the family left Uganda for Oldham — what was that journey like?', 'child', 2),
    (3, 'What was it like arriving in Oldham and starting over?', 'child', 3),
    (4, 'What was your childhood like growing up in Oldham?', 'child', 4),
    (5, 'What did your parents tell you about their own upbringing, before you were born?', 'child', 5),
    (6, 'What''s your earliest memory of your parents?', 'child', 6),
    (7, 'What values or sayings do you most associate with them?', 'child', 7),
    (8, 'How did they show love or care day-to-day?', 'child', 8),
    (9, 'What''s a hard time in your life they helped you through?', 'child', 9),
    (10, 'What''s a story about them you find yourself retelling?', 'child', 10),
    (11, 'What do you think they were proudest of?', 'child', 11),
    (12, 'What do you wish more people knew about them?', 'child', 12),

    (13, 'How did they welcome you into the family?', 'child_in_law', 1),
    (14, 'What''s your favorite memory with them since joining the family?', 'child_in_law', 2),
    (15, 'What have you come to admire about them?', 'child_in_law', 3),
    (16, 'Did your spouse (their child) ever tell you something about them that changed how you saw them?', 'child_in_law', 4),
    (17, 'What do you wish more people knew about them?', 'child_in_law', 5),

    (18, 'What''s your favorite memory with them?', 'grandchild', 1),
    (19, 'What do they always say or do that makes you smile?', 'grandchild', 2),
    (20, 'What have they taught you — a skill, a recipe, a value?', 'grandchild', 3),
    (21, 'What''s something about their life before you were born that surprises you?', 'grandchild', 4),
    (22, 'If you could ask them one more question, what would it be?', 'grandchild', 5),

    (23, 'What''s your favorite memory with them, if you have one?', 'great_grandchild', 1),
    (24, 'What''s one thing you know about them that you''d want to remember when you''re older?', 'great_grandchild', 2),
    (25, 'What would you want to ask them if you could?', 'great_grandchild', 3),

    (26, 'How did you come to know them?', 'any', 1),
    (27, 'What''s a memory or story about them that''s stayed with you?', 'any', 2),
    (28, 'What would you want future generations to know about them?', 'any', 3);
