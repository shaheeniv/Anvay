# Anvay

A private, local website for recording the family's stories, keeping a
living family tree, collecting memories/photos/traditions from everyone,
and writing time capsule letters — starting with video interviews with
grandparents (Gujarati transcript + English translation side by side).

Everything lives on this computer. Nothing is uploaded anywhere. The
data is stored in a single file, `archive.db`, which you can back up
just by copying it.

## How to run it

Open Terminal, then run these commands (only needed once per computer
restart — you don't need to repeat the setup steps below every time):

```bash
cd "/Users/arun/Desktop/Anvay"
source venv/bin/activate
python3 app.py
```

Then open your browser to:

```
http://127.0.0.1:5000
```

To stop the site, go back to Terminal and press `Control + C`.

## Home dashboard

Opening the site (or clicking the logo/"Home") shows the Anvay logo
and tagline centered up top, followed by a "Your Family" / "Your
Families" box — one large clickable card per named family branch,
taking you straight to that branch on the Family Tree page. Below
that: how many people are in the tree, how many stories/contributions/
letters exist, a strip of recent photos, quick "+" buttons to jump
straight to adding something, and a combined "recent activity" list
across everything that's been added — new people, videos,
contributions, and letters (sealed letters show up without revealing
their contents). The story list itself lives at "Stories" in the nav
/ `/stories`.

## What each part is, in plain terms

- `app.py` — the actual program: what happens when you click things.
- `schema.sql` — describes what an "entry" is made of (person, date,
  transcript, translation, video link) and how people relate to each
  other (parent/child, spouse).
- `archive.db` — the database file itself. This is created the first
  time you run the app. **This is the file to back up.**
- `templates/` — the HTML pages (what things look like).
- `static/style.css` — the styling (colors, fonts, layout).
- `venv/` — a self-contained folder holding the exact tools this
  project needs, so it doesn't interfere with anything else on your
  computer.

## Adding a video entry

Video files themselves are too large to store in the database, so for
each entry you paste in a **cloud link** (e.g. a Google Drive or iCloud
share link) to where the actual video file lives. The archive stores
that link plus: person, date recorded, topic, the original Gujarati
transcript, and the English translation.

The Gujarati transcript is always treated as the primary record — the
English translation lives alongside it, never in place of it.

## Family tree

Click "Family Tree" in the top nav to see a traditional branching
tree diagram — couples shown together with a connecting line down to
their children, generation by generation. Unlike other pages, this
one uses the full width of your window rather than a narrow reading
column, since a wide family spreads out horizontally. Click "+ Add a
person" to add someone standalone, or go to an existing person's
profile page to add their parents, spouse, or children directly — you
can either link to someone already in the tree or type a new name to
create them on the spot.

If the family has more than one distinct branch with no common
ancestor recorded (e.g. your mum's side and your dad's side, before
they married each other), pill buttons appear above the tree so you
can switch between viewing each side. Once a branch's tree reaches a
point where it converges with another branch (like a marriage), the
shared descendants are only drawn once, on whichever side got there
first — the other side shows a small "see their family above" note
instead of repeating everyone.

Each branch can have its own name — e.g. "Mavji Vekaria Family" or
"Bhudia Family" — set on the eldest known ancestor's profile page
(the "Family tree name" field only does anything when that person has
no recorded parents, since that's what makes them the root of a
branch). Without a name set, a branch just falls back to showing the
root couple's names. These names are also what the homepage's family
box uses.

Each person's profile lists any story/video entries linked to them
(with a shortcut to log a new one), and now also has room for a
surname, where they were born, and three words to describe them —
edit any of that from their profile's "Edit" button.

## Contribution feed

Click "Contributions" in the top nav to see the shared feed — anyone
in the family can add a memory, photo, story, tradition, or note. Each
entry has a title, an optional longer write-up, an optional photo
(stored in `static/uploads/`, unlike videos these are small enough to
keep locally), who added it, and which family member(s) it's about.
Filter the feed by type using the pills at the top — the "Photo"
filter shows a proper gallery grid instead of a list. Anything tagged
to a person also shows up on their profile page.

## Time capsule letters

Click "Time Capsules" to write a letter now, addressed to someone,
sealed until a future date (e.g. a child's 18th birthday). Until that
date, the letter's title and contents stay hidden — the feed and the
recipient's profile only show who it's for and roughly how long until
it unlocks. A sealed letter also can't be edited (delete and rewrite
it if you need to change something before it opens).

Worth knowing: the seal is an honor-system convention, not encryption
— this app has no login, so anyone with access to the computer (or
the `archive.db` file) could technically look. It's there to stop
casual peeking, not a determined one.

## Backing up / exporting your data

Because everything is in one SQLite file (`archive.db`), you can:
- Copy that single file anywhere as a backup.
- Open it with any free SQLite viewer if you ever want to look at the
  raw data outside this app.
- Export it to CSV or another format later — nothing here locks the
  data into this particular website.

Uploaded photos live in `static/uploads/` — back that folder up
alongside `archive.db` (the database only stores the filenames, not
the image data itself).

## Yearly almanac

Click "Almanac" to see everything added in a given year in one place:
new people in the family tree, stories/videos recorded, contributions
added, and any time capsule letters that unlocked that year (still
sealed ones don't show up until they actually open). Use the arrows
to move between years.

Click "Print / Save as PDF" to get a clean, printable version — it
hides the navigation and buttons and uses your browser's own
print/PDF feature, so no extra software is needed to turn a year into
something you could put in a printed book.

## What's next

All the planned features are in place: story archive, family tree,
contribution feed, time capsule letters, and the yearly almanac. From
here it's about adding real family data — people, stories, memories —
rather than new features, unless something new comes up.
