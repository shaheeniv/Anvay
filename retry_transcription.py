"""
Re-runs automatic transcription on a video entry that already has a
video file uploaded — without needing to re-upload it. Useful after an
improvement to the transcription logic, or if it failed/came out wrong
the first time.

Usage:
    OPENAI_API_KEY=sk-... python3 retry_transcription.py ENTRY_ID
"""

import sys
from pathlib import Path

import app as a

if len(sys.argv) != 2:
    print("Usage: python3 retry_transcription.py ENTRY_ID")
    sys.exit(1)

entry_id = int(sys.argv[1])

with a.app.app_context():
    db = a.get_db()
    entry = db.execute(
        "SELECT video_filename FROM video_entries WHERE id = ?", (entry_id,)
    ).fetchone()

if entry is None:
    print(f"No video entry with id {entry_id}.")
    sys.exit(1)
if not entry["video_filename"]:
    print(f"Entry {entry_id} has no uploaded video file to transcribe.")
    sys.exit(1)

a.transcribe_video_entry(entry_id, Path(a.VIDEO_DIR) / entry["video_filename"])
print("done")
