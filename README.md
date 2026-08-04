# Anvay

A private website for recording the family's stories, keeping a living
family tree, collecting memories/photos/traditions from everyone, and
writing time capsule letters — starting with video interviews with
grandparents (Gujarati transcript + English translation side by side).

You can run it purely on this computer (see below), or put the deployed
version online so everyone in the family can log in from their own phone
or laptop (see "Deploying so the family can access it remotely"). Either
way, the data is stored in a single file, `archive.db`, which you can
back up just by copying it.

Everyone now needs a username and password to get in — see "Logging in"
below.

## How to run it locally

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

## Logging in

The site now requires a username and password — this became necessary
once family members can reach it remotely, not just from one shared
computer. There's no public sign-up: only an admin (currently just
Shaheeni) can create a login for someone else.

- **Shaheeni's own account** was created automatically when this feature
  shipped, username `shaheeni`. If you don't already have the password,
  ask whoever set this up, or reset it directly in the database (see
  "Resetting a password by hand" below).
- **To give someone else a login**: go to their profile page (Family
  Tree → click their name) and click "Set up login" — pick a username
  and enter their **email address**. They'll get an email with a link
  to set their own password — nobody has to invent or share a starting
  password. If they don't have an email (e.g. a young child), leave
  the email blank and set a starting password directly instead, the
  old way.
- **Forgot a password?** Anyone can click "Forgot your password?" on
  the login page and enter their username or email — if there's an
  email on file, they'll get a reset link themselves, no admin needed.
  An admin can also trigger this for someone from their "Edit login"
  page ("Email \[name\] a login link").
- **Sending these emails** needs a [Resend](https://resend.com) account
  (free tier) with `anvay.uk` verified as a sending domain, and its API
  key set as the `RESEND_API_KEY` environment variable on Render. Without
  that key set, login/reset emails silently fail (with a flash message
  explaining why) — the admin-sets-a-password-directly path still works
  regardless.
- **Staying logged in**: once someone logs in, their session lasts a
  year before they'd need to log in again — good for a personal phone
  or laptop that stays theirs, since nobody wants to keep re-entering a
  password just to add a photo. Logging out clears it immediately if
  needed (e.g. on a shared device).

### Resetting a password by hand

If you're ever locked out and can't get to an admin account to fix it,
this can be done directly from Terminal:

```bash
cd "/Users/arun/Desktop/Anvay"
source venv/bin/activate
python3 -c "
from werkzeug.security import generate_password_hash
print(generate_password_hash('your-new-password-here', method='pbkdf2:sha256'))
"
```

Copy the long string that prints out, then:

```bash
sqlite3 archive.db "UPDATE accounts SET password_hash = 'PASTE_THE_STRING_HERE' WHERE username = 'shaheeni';"
```

## Landing page

Visiting the site while logged out shows a public welcome page — logo,
tagline, a plain explanation of what Anvay is, and a "Log in" box (no
account details are shown here, it's just the front door). Logging in
takes you to a chooser between the two things this site does: the
**Family Portal** (everything below) and any **Legacy Books** in
progress. Click "Family Portal" to reach the dashboard. Clicking the
logo/"Home" while logged in returns here too.

## Home dashboard

The dashboard shows the Anvay logo and tagline centered up top, followed
by a "Your Family" / "Your Families" box — one large clickable card per
named family branch, taking you straight to that branch on the Family
Tree page. Below that: how many people are in the tree, how many
videos/contributions/letters exist, a strip of recent photos, quick "+"
buttons to jump straight to adding something, and a combined "recent
activity" list across everything that's been added — new people, videos,
contributions, and letters (sealed letters show up without revealing
their contents). The video list itself lives at "Videos" in the nav
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
- `requirements.txt` — the list of those tools, used both by `venv/`
  locally and by Render when it builds the hosted version.
- `Procfile` — tells Render how to actually start the site
  (`gunicorn app:app`) once it's built.
- `instance/secret_key.txt` — a random value used to keep you logged in
  between visits, generated automatically the first time the app runs
  locally. Never shared or committed to git; the hosted version uses a
  separate `SECRET_KEY` you set directly in Render instead.

## Adding a video entry

There are two ways to attach the actual video to an entry:

- **Upload the video file directly** — it's stored properly (under
  `videos/`, alongside `archive.db`) and played right on the entry page.
- **Paste a cloud link** instead (e.g. Google Drive or iCloud) if you'd
  rather not upload the file itself — just a link to click through and
  watch elsewhere.

Either way, the archive stores: person, date recorded, topic, the
original Gujarati transcript, and the English translation — typed in by
hand. (Automatic transcription was tried and dropped — Gujarati is a
low-resource language for the available AI transcription models, and
the results on real interview footage weren't accurate enough to trust.)

The Gujarati transcript is always treated as the primary record — the
English translation lives alongside it, never in place of it.

## Family tree

Click "Family Tree" in the top nav to see a traditional branching
tree diagram — couples shown together with a connecting line down to
their children, generation by generation. Unlike other pages, this
one uses the full width of your window rather than a narrow reading
column, since a wide family spreads out horizontally. Click "+ Add a
person" to add someone new, or go to an existing person's profile
page to add their parents, spouse, or children directly — either way
you can link to someone already in the tree or type a new name to
create them on the spot.

Every new person has to be connected to someone already in the tree —
their child, parent, or spouse/partner — so nobody ends up added by
mistake with no link to the rest of the family. The only exception is
the very first person ever added to an empty tree, since there's
nobody to connect them to yet.

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

**Who can see which branch:** everyone only sees the branch(es) they
actually belong to — by blood or by marriage to someone in that
branch. This applies everywhere, not just the tree: Videos,
Contributions, Time Capsules, and person profile pages all quietly
hide anyone from a branch you're not part of, and person-picker
dropdowns (adding a relation, tagging a contribution, etc.) only list
people you're allowed to see. Marrying into a branch adds it to your
list — it doesn't merge branches together, so a distant in-law
connection (e.g. your child's spouse's parents) doesn't itself grant
you access, only a direct link does. Admin accounts always see
everything, regardless of branch.

Each person's profile lists any story/video entries and contributions
linked to them (with shortcuts to add a new one), and now also has room
for a surname, where they were born, and three words to describe them —
edit any of that from their profile's "Edit" button.

## Contribution feed

Click "Contributions" in the top nav to see the shared feed — anyone
in the family can add a memory, photo, story, or tradition. Each
entry has a title, an optional longer write-up, an optional photo
(stored in `uploads/`, unlike videos these are small enough to
keep locally), who added it, and which family member(s) it's about.
Filter the feed by type using the pills at the top — the "Photo"
filter shows a proper gallery grid instead of a list. Anything tagged
to a person also shows up on their profile page.

Uploading photos from a phone one at a time gets tedious after an
event with lots of them, so **"+ Add several photos"** lets you pick
multiple photos in one go — they share a single caption, story, and
tagged people, but each still lands in the feed as its own separate
photo (so they can be viewed, tagged, and used in Legacy Books
individually afterwards, exactly as if they'd been added one by one).

## Time capsule letters

Click "Time Capsules" to write a letter now, addressed to someone,
sealed until a future date (e.g. a child's 18th birthday). Until that
date, the letter's title and contents stay hidden — the feed and the
recipient's profile only show who it's for and roughly how long until
it unlocks. A sealed letter also can't be edited (delete and rewrite
it if you need to change something before it opens).

Worth knowing: the seal is enforced by the app for everyone (including
whoever wrote the letter) until the unlock date, but it's not
encryption — anyone with direct access to the `archive.db` file itself
could technically read the raw text early. It's there to stop casual
peeking within the app, not a determined look at the database file.

## Backing up / exporting your data

Because everything is in one SQLite file (`archive.db`), you can:
- Copy that single file anywhere as a backup.
- Open it with any free SQLite viewer if you ever want to look at the
  raw data outside this app.
- Export it to CSV or another format later — nothing here locks the
  data into this particular website.

Uploaded photos live in `uploads/`, and uploaded videos in `videos/`
(both next to `archive.db`, inside `DATA_DIR`) — back both folders up
alongside `archive.db` (the database only stores the filenames, not the
actual image/video data).

## Legacy Books

Click "Legacy Books" in the top nav for a second thing this site can do,
separate from the ongoing family portal above: a time-boxed biography
project for one person or a couple (e.g. "The Life of Mavji & Radha").

An admin starts one from "+ New Book" by picking one person, or a couple,
as the subject. From then on, the subject's own video interviews (already
logged under "Videos") automatically form the spine of the book, and
everyone else in the family who visits that book's page is shown a set of
interview questions tailored to how they're related to the subject —
children get the deepest set (their own upbringing, the subject's life
before them, who the subject was as a parent), sons/daughters-in-law get
a set about joining the family, grandchildren and great-grandchildren get
shorter, more personal sets, and anyone else gets a small general set.
Answers save per-person and can be revisited/edited any time. Each
question box has a **"🎤 Dictate"** button — click it and speak instead
of typing, using your browser's own built-in speech recognition (the
same technology as iPhone dictation). It's free, needs no setup, and
works well for English. Supported in Safari and Chrome; if your browser
doesn't support it, the button simply won't appear.

Every new book starts with a default set of questions (an admin can
customize it — see below), but **each book gets its own independent
copy** — editing one book's questions never affects any other book. This
matters because different branches of the family have genuinely
different histories (e.g. one side migrated from Uganda, another from
Kenya), so the default wording won't always fit. From a book's page,
admins see an "Edit these questions for this book" link to reword any
question just for that book.

Photos aren't uploaded separately per book — there's just one place to
add a photo to the archive at all, the Contributions feed (see below).
Each book has a **"Select photos for this book"** page instead, listing
every photo from Contributions with a checkbox for whether it's relevant
to this book. Selected photos can be used when the book is eventually
compiled, alongside the interviews and written answers.

### Inviting people outside the family

Sometimes the best memories of someone come from a close friend or
neighbour who isn't in the family tree at all and won't have a login.
From a book's page, admins see a **"Manage invite links"** link — creating
one there generates a private, unguessable web address for one named
person (e.g. "Priya — Parbat's best friend"). Share that link with them
directly (text, WhatsApp, email, however you'd normally reach them); no
account or password is needed on their end. It opens a simple page where
they can write a memory and optionally attach a photo or video, with no
access to anything else on the site.

Nothing they submit appears in the book automatically — it lands in a
**"Waiting for your review"** queue on the book's page, visible only to
admins, where it can be approved or rejected. Once approved, it shows up
under "Memories from friends & family" for everyone who can see that
book. An invite link can be revoked at any time from the same "Manage
invite links" page, which immediately stops it from working (anything
already submitted through it stays exactly as it was).

What's built so far is just the data-collection side — gathering the
interviews and everyone's answers in one place. Turning all of that into
an actual compiled, readable book (using AI to weave the video interviews
and answers into flowing chapters) and a proper reading/print view are
still to come.

## Installing it like an app on a phone

Anvay isn't in the App Store or Play Store, but it can still sit on
someone's home screen with its own icon and open full-screen, no
address bar — Google/Apple's technical name for this is a "PWA," but it
just means a website that offers to install itself.

- **iPhone (Safari)**: open the site, tap the **Share** button, then
  **"Add to Home Screen."**
- **Android (Chrome)**: open the site, tap the **⋮** menu in the top
  right, then **"Add to Home Screen"** or **"Install app."**

Once added, tapping that icon opens Anvay exactly like any other app —
no browser bar, no needing to remember a web address. Combined with the
year-long login (see "Logging in" above), day-to-day use should feel
like a normal app: tap the icon, already logged in, add a photo.

## Deploying so the family can access it remotely

Running it locally (above) is still the easiest way to develop or test
changes. But so that family members can log in from their own phones or
laptops, rather than everyone gathering around one computer, the same
app can be hosted online at [Render.com](https://render.com) for about
$7-8/month (their "Starter" web service plan plus a small persistent
disk). This needs a few one-time setup steps that only you can do,
since they involve creating accounts in your own name.

### 1. Put the code on GitHub (one-time)

The code already has a local git repository with everything committed
(`git log` will show it). You just need somewhere on GitHub, privately,
for Render to pull it from:

1. Go to [github.com/new](https://github.com/new), sign in (or create a
   free account), and create a new **private** repository — any name,
   e.g. `anvay`. Don't check any of the "initialize with..." boxes.
2. GitHub will show you a page with commands like `git remote add
   origin ...`. Back in Terminal:

```bash
cd "/Users/arun/Desktop/Anvay"
git remote add origin PASTE_THE_URL_GITHUB_GAVE_YOU
git push -u origin main
```

### 2. Create the Render service (one-time)

1. Go to [render.com](https://render.com) and sign up (you can sign in
   with your GitHub account, which makes the next step easier).
2. Click **New +** → **Web Service**, and connect the GitHub repo you
   just pushed.
3. Render should auto-detect Python. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app` (this is also in the
     `Procfile`, so Render may fill it in automatically)
   - **Instance type**: Starter (the cheapest paid tier — the free tier
     doesn't support the persistent disk this app needs)
4. **Add a persistent disk** (Render calls this "Disks" in the service
   settings) — **this step matters more than any other one here**.
   Without it, every time you redeploy, all the photos, stories, and
   people you've added would be wiped, because the container's own
   filesystem is thrown away on each redeploy.
   - Mount path: anything, e.g. `/var/data`
   - Size: 1 GB is plenty to start
5. **Add environment variables** (Render calls these "Environment"):
   - `SECRET_KEY` — generate one by running this in Terminal:
     `python3 -c "import secrets; print(secrets.token_hex(32))"`,
     then paste the result in as the value.
   - `DATA_DIR` — set this to the same mount path you chose above, e.g.
     `/var/data`. This tells the app to store `archive.db` and keep
     photos on the persistent disk instead of the throwaway container.
6. Click **Create Web Service**. Render will build and deploy it, and
   give you a URL like `https://anvay-xyz.onrender.com` — that's the
   link the family uses to log in remotely. HTTPS is automatic, no
   extra setup needed.

The very first deploy creates a brand-new, empty `archive.db` on the
disk — it starts blank, it does **not** copy your local data
automatically. If you want the family to see the same tree/stories you
already have locally, copy your local `archive.db` and `uploads/` folder
onto the Render disk before inviting anyone in (Render's dashboard has a
"Shell" tab that can help with this, or ask for help with this specific
step when you get there).

### 3. Every time you make future changes

```bash
cd "/Users/arun/Desktop/Anvay"
git add -A
git commit -m "Describe what changed"
git push
```

Render watches the GitHub repo and redeploys automatically within a
minute or two of each push. Local dev (`python3 app.py`) keeps working
exactly as before, completely separately from the deployed version.

## What's next

Login, remote hosting, and the Legacy Book question-collection flow are
all in place. What's left on the Legacy Book side: using AI to compile
the collected interviews and answers into an actual written biography,
and a proper reading/print view for the finished result — plus, further
out, a single landing page after login to choose between the family
portal and a Legacy Book, rather than reaching Legacy Books from the nav
bar as it works today.
