# Anvay — Project Brief

## What this is
A private, multi-generational family archive and living record — built to
last decades, not just this year. It captures family history (especially
grandparents' stories, recorded on video in Gujarati), tracks daily/weekly
family life going forward, and gives every family member a way to contribute.

## Who it's for
- Immediate family: parents (Mum & Dad), brother, his wife, their two kids,
  the user, her husband, and her son (1 year old), plus future kids.
- Everyone should eventually be able to log in and contribute their own
  entries — not just view. Kids can be added as they grow old enough.

## Core features (in priority order)

### 1. Story & video archive (build first — most time-sensitive)
- Store video recordings of grandparents (currently in Gujarati).
- Each video entry has: person, date recorded, topic/summary, original
  Gujarati transcript, English translation, and the video file itself
  (or a link to where it's stored, since video files are large).
- Never replace the Gujarati original — it's stored as the primary source.
  English translation lives alongside it, not instead of it.
- Should be searchable by person, topic, and keyword (across translated text).

### 2. Family tree
- Living, expandable tree of relationships (parents, siblings, spouses,
  children, future generations).
- Each person has a profile page linking to their story entries, photos,
  milestones, etc.

### 3. Contribution feed
- Any family member can add: a memory, a photo, a story, a tradition,
  a note.
- Entries are tagged by author and date, and linked to relevant family
  members.

### 4. Time capsule letters
- Write a letter/message now, addressed to a specific person, sealed
  until a future date (e.g. son's 18th birthday).
- Locked/hidden until the unlock date passes.

### 5. Traditions
- Family traditions recorded with context — not just the "what" but
  the "why" and the story behind them.

### 6. Yearly almanac (later phase)
- Auto-compiled summary of the year's entries, could be exported as a
  printable book eventually.

## Technical preferences
- Should run locally / privately — this is a private family archive, not
  a public app. No public deployment unless the user explicitly asks later.
- Simple, warm, non-corporate visual design — this is a family keepsake,
  not a SaaS product.
- Data should be durable and exportable (avoid formats that lock the
  family into one tool long-term).
- Start simple. Build incrementally: story archive + family tree first,
  then contribution feed, then time capsules, then the rest.
- The user is comfortable following guided instructions but is new to
  coding — explain technical steps in plain language as you go, and
  check in before big structural decisions.

## Tone
This is a deeply personal, long-term family project. Prioritize getting
the foundational pieces right (data structure, family tree, story archive)
over speed. Ask clarifying questions about family-specific details
(names, relationships, preferences) rather than assuming.
