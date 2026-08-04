"""
BunkMarte - Attendance Tracker
==============================
A Flet (Python -> Flutter) mobile app for tracking college attendance against
a fixed weekly timetable, with full per-class history editing.

Runs as a pure Python script (Flet + SQLite only - no Java/Kotlin) so it can
be tested locally on Windows and later packaged into an Android APK via
`flet build apk` inside a GitHub Actions workflow.

Author: BunkMarte
"""

import os
import sqlite3
import datetime as dt

import flet as ft

# ---------------------------------------------------------------------------
# 1. STORAGE / DATABASE PATH
# ---------------------------------------------------------------------------
# When packaged as an Android app, Flet exposes a writable per-app data
# directory via the FLET_APP_STORAGE_DATA environment variable. When running
# locally as a plain script (Windows/Mac/Linux) that variable does not exist,
# so we simply fall back to the current working directory.
DB_DIR = os.getenv("FLET_APP_STORAGE_DATA", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "bunkmarte.db")


# ---------------------------------------------------------------------------
# 2. THEME / COLOR PALETTE  (Black & Purple aesthetic dark mode)
# ---------------------------------------------------------------------------
COLOR_BG = "#000000"          # pure black page background
COLOR_SURFACE = "#121212"     # deep gray surface (cards' container background)
COLOR_CARD = "#1C1526"        # slightly elevated purple-tinted dark gray for class cards
COLOR_CARD_BORDER = "#2A1F3D"
COLOR_PRIMARY = "#A855F7"     # vibrant purple accent
COLOR_PRIMARY_DARK = "#7C3AED"
COLOR_TEXT = "#F5F5F7"
COLOR_SUBTEXT = "#A0A0AA"

# Neon / pastel status colors - chosen so they pop against black/purple.
STATUS_COLORS = {
    "Present": "#39FF14",        # neon green
    "Absent": "#FF4C4C",         # red
    "Bunk": "#FFA733",           # orange
    "Mass Bunk": "#FF6EC7",      # neon pink (distinct "planned" bunk)
    "Proxy/Freebie": "#33E6FF",  # neon cyan
    "Cancelled": "#5B8CFF",      # soft blue
    "Exam Day": "#B983FF",       # light neon purple
    "Holiday": "#FFD700",        # gold
}

# Ordered list of statuses as they will appear in the picker dialog.
STATUS_LIST = list(STATUS_COLORS.keys())

# Grayed-out color for calendar days that were scheduled but never logged
# ("Unmarked" is a UI-only placeholder status - it is intentionally NOT in
# STATUS_COLORS/STATUS_LIST above, so it can never be picked as a real status
# and never gets written to the database).
UNMARKED_COLOR = "#5A5A66"

# Math rules -> (attended_delta, total_delta) added per logged class.
# Present / Proxy / Cancelled all count as a "free" attended class.
# Absent / Bunk / Mass Bunk count against you (total goes up, attended does not).
# Exam Day / Holiday wipe the class from the math entirely (0, 0).
STATUS_MATH = {
    "Present": (1, 1),
    "Absent": (0, 1),
    "Bunk": (0, 1),
    "Mass Bunk": (0, 1),
    "Proxy/Freebie": (1, 1),
    "Cancelled": (1, 1),
    "Exam Day": (0, 0),
    "Holiday": (0, 0),
}


# ---------------------------------------------------------------------------
# 3. TIMETABLE
# ---------------------------------------------------------------------------
# Each block: start, end (24h "HH:MM"), subject, is_lab (2hr single entry),
# is_recess (non-clickable, never tracked).
# time_slot key stored in DB is f"{start}-{end}" so a 2-hour lab block is
# ONE row in the schedule (and therefore one attendance entry) rather than two.
TIMETABLE = {
    "Monday": [
        {"start": "10:00", "end": "12:00", "subject": "DAA", "is_lab": True},
        {"start": "12:00", "end": "13:00", "subject": "FML", "is_lab": False},
        {"start": "13:00", "end": "14:00", "subject": "Recess", "is_recess": True},
        {"start": "14:00", "end": "15:00", "subject": "MDM", "is_lab": False},
        {"start": "15:00", "end": "16:00", "subject": "DAA", "is_lab": False},
        {"start": "16:00", "end": "17:00", "subject": "TFCS", "is_lab": False},
    ],
    "Tuesday": [
        {"start": "10:00", "end": "11:00", "subject": "AI", "is_lab": False},
        {"start": "11:00", "end": "12:00", "subject": "PE", "is_lab": False},
        {"start": "12:00", "end": "13:00", "subject": "DAA", "is_lab": False},
        {"start": "13:00", "end": "14:00", "subject": "Recess", "is_recess": True},
        {"start": "14:00", "end": "15:00", "subject": "MDM", "is_lab": False},
        {"start": "15:00", "end": "16:00", "subject": "FML", "is_lab": False},
        {"start": "16:00", "end": "17:00", "subject": "AI", "is_lab": False},
    ],
    "Wednesday": [
        {"start": "10:00", "end": "11:00", "subject": "OE", "is_lab": False},
        {"start": "11:00", "end": "12:00", "subject": "AI", "is_lab": False},
        {"start": "12:00", "end": "13:00", "subject": "FML", "is_lab": False},
        {"start": "13:00", "end": "14:00", "subject": "Recess", "is_recess": True},
        {"start": "14:00", "end": "15:00", "subject": "MDM", "is_lab": False},
        {"start": "15:00", "end": "16:00", "subject": "TFCS", "is_lab": False},
        {"start": "16:00", "end": "17:00", "subject": "TFCS", "is_lab": False},
    ],
    "Thursday": [
        {"start": "09:00", "end": "10:00", "subject": "OE", "is_lab": False},
        {"start": "10:00", "end": "11:00", "subject": "AI", "is_lab": False},
        {"start": "11:00", "end": "12:00", "subject": "DAA", "is_lab": False},
        {"start": "12:00", "end": "13:00", "subject": "PE", "is_lab": False},
        {"start": "13:00", "end": "14:00", "subject": "Recess", "is_recess": True},
        {"start": "14:00", "end": "16:00", "subject": "AI", "is_lab": True},
    ],
    "Friday": [
        {"start": "09:00", "end": "10:00", "subject": "OE", "is_lab": False},
        {"start": "10:00", "end": "12:00", "subject": "PE", "is_lab": True},
        {"start": "12:00", "end": "13:00", "subject": "PE", "is_lab": False},
        {"start": "13:00", "end": "14:00", "subject": "Recess", "is_recess": True},
        {"start": "14:00", "end": "15:00", "subject": "TFCS", "is_lab": False},
        {"start": "15:00", "end": "16:00", "subject": "DAA", "is_lab": False},
    ],
    "Saturday": [],
    "Sunday": [],
}

# The semester start date. The "ghost calendar" backfill in
# get_subject_history() scans every day from here up to today, regardless of
# whether attendance was actually logged for it.
HISTORY_START_DATE = dt.date(2026, 7, 1)


# ---------------------------------------------------------------------------
# 4. DATABASE LAYER
# ---------------------------------------------------------------------------
def get_conn():
    """Open a fresh SQLite connection (SQLite connections aren't thread-safe
    to share, and Flet may run handlers off the main thread)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the attendance table if it doesn't already exist."""
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,        -- ISO date, e.g. 2026-08-03
            day_name TEXT NOT NULL,    -- e.g. Monday
            time_slot TEXT NOT NULL,   -- e.g. 10:00-12:00
            subject TEXT NOT NULL,     -- e.g. DAA
            status TEXT NOT NULL
        )
        """
    )
    # One attendance record per (date, time_slot, subject) - re-tapping a
    # class just overwrites its status instead of duplicating rows.
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_block
        ON attendance(date, time_slot, subject)
        """
    )
    conn.commit()
    conn.close()


def upsert_record(date_str, day_name, time_slot, subject, status):
    """Insert a new attendance record, or update the status if one already
    exists for this exact class instance (same date + time_slot + subject)."""
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO attendance (date, day_name, time_slot, subject, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date, time_slot, subject)
        DO UPDATE SET status = excluded.status
        """,
        (date_str, day_name, time_slot, subject, status),
    )
    conn.commit()
    conn.close()


def get_record(date_str, time_slot, subject):
    """Fetch the logged status (if any) for one specific class instance."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM attendance WHERE date=? AND time_slot=? AND subject=?",
        (date_str, time_slot, subject),
    ).fetchone()
    conn.close()
    return row


def delete_record(record_id):
    """Permanently remove a single attendance entry (used by History undo)."""
    conn = get_conn()
    conn.execute("DELETE FROM attendance WHERE id=?", (record_id,))
    conn.commit()
    conn.close()


def update_status(record_id, new_status):
    """Change the status of an existing record (used by History edit)."""
    conn = get_conn()
    conn.execute("UPDATE attendance SET status=? WHERE id=?", (new_status, record_id))
    conn.commit()
    conn.close()


def get_all_records():
    """Every attendance record ever logged, most recent first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM attendance ORDER BY date DESC, time_slot DESC"
    ).fetchall()
    conn.close()
    return rows


def get_subject_history(subject):
    """Build the FULL chronological "ghost calendar" for a subject: every
    single date from HISTORY_START_DATE up to today, oldest first, on which
    the timetable says this subject was scheduled - not just the dates that
    were actively logged.

    For each scheduled date/time_slot:
      - If a real attendance row already exists, that row (as a dict) is
        used, so its real `id` and logged `status` are returned.
      - Otherwise a placeholder dict with id=None and status="Unmarked" is
        returned instead, so the UI can offer to backfill it.

    "Unmarked" placeholders are generated on the fly and never touch the
    database, so compute_subject_summary() (which reads straight from the
    attendance table via get_all_records()) automatically ignores them -
    they can never affect the attendance percentage.
    """
    # One query to grab every real record ever logged for this subject, then
    # look it up in memory while walking the calendar (avoids one DB round
    # trip per scheduled day).
    conn = get_conn()
    existing_rows = conn.execute(
        "SELECT * FROM attendance WHERE subject=?", (subject,)
    ).fetchall()
    conn.close()
    existing_lookup = {(row["date"], row["time_slot"]): dict(row) for row in existing_rows}

    history = []
    current = HISTORY_START_DATE
    today = dt.date.today()

    while current <= today:
        day_name = current.strftime("%A")
        date_str = current.isoformat()

        for block in TIMETABLE.get(day_name, []):
            if block.get("is_recess"):
                continue
            if block["subject"] != subject:
                continue

            time_slot = f"{block['start']}-{block['end']}"
            entry = existing_lookup.get((date_str, time_slot))
            if entry is None:
                # Scheduled but never logged - a "ghost" placeholder.
                entry = {
                    "id": None,
                    "date": date_str,
                    "day_name": day_name,
                    "time_slot": time_slot,
                    "subject": subject,
                    "status": "Unmarked",
                }
            entry["is_lab"] = block.get("is_lab", False)
            history.append(entry)

        current += dt.timedelta(days=1)

    return history


def compute_subject_summary():
    """Aggregate attended/total per subject across the whole history,
    applying the STATUS_MATH rules. Returns dict: subject -> (attended, total).

    This reads only real rows from the `attendance` table (via
    get_all_records()), so "Unmarked" ghost-calendar placeholders - which are
    generated on the fly by get_subject_history() and never written to the
    database - are automatically excluded (0 attended, 0 total) from the
    percentage math, exactly as required.
    """
    summary = {}
    for row in get_all_records():
        subj = row["subject"]
        attended_d, total_d = STATUS_MATH.get(row["status"], (0, 0))
        a, t = summary.get(subj, (0, 0))
        summary[subj] = (a + attended_d, t + total_d)
    return summary


# ---------------------------------------------------------------------------
# 5. SMALL HELPERS
# ---------------------------------------------------------------------------
def to_12h(time_24):
    """'14:00' -> '2:00 PM' for friendlier display."""
    h, m = time_24.split(":")
    h, m = int(h), int(m)
    period = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {period}"


def format_slot_label(start, end):
    return f"{to_12h(start)} - {to_12h(end)}"


def percentage_color(pct):
    """Green if healthy attendance, amber if borderline, red if in danger."""
    if pct >= 75:
        return STATUS_COLORS["Present"]
    if pct >= 65:
        return STATUS_COLORS["Bunk"]
    return STATUS_COLORS["Absent"]


# ---------------------------------------------------------------------------
# 6. MAIN APP
# ---------------------------------------------------------------------------
def main(page: ft.Page):
    init_db()

    # ---- page-level look & feel -----------------------------------------
    page.title = "BunkMarte"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.window.width = 420
    page.window.height = 880
    page.theme = ft.Theme(
        color_scheme_seed=COLOR_PRIMARY,
        scaffold_bgcolor=COLOR_BG,
    )

    # ---- app state ---------------------------------------------------
    state = {"tab": 0, "history_subject": None}  # tab 0 = Today, 1 = Summary

    body = ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)

    # =======================================================================
    # DIALOG: pick / change a status for one class block
    # =======================================================================
    def open_status_picker(date_str, day_name, time_slot, subject, label, on_done):
        """Shows a purple/black themed dialog with every status as a
        colored chip button. Selecting one writes to the DB and refreshes."""

        def choose(status):
            def handler(e):
                upsert_record(date_str, day_name, time_slot, subject, status)
                page.pop_dialog()
                on_done()

            return handler

        chips = []
        for status in STATUS_LIST:
            color = STATUS_COLORS[status]
            chips.append(
                ft.ElevatedButton(
                    content=status,
                    on_click=choose(status),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.with_opacity(0.18, color),
                        color=color,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        side=ft.BorderSide(1, color),
                    ),
                )
            )

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=COLOR_SURFACE,
            title=ft.Text(label, color=COLOR_TEXT, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Row(chips, wrap=True, spacing=8, run_spacing=8),
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: page.pop_dialog(),
                    style=ft.ButtonStyle(color=COLOR_SUBTEXT),
                )
            ],
        )
        page.show_dialog(dialog)

    # =======================================================================
    # DIALOG: edit / delete an existing history record
    # =======================================================================
    def open_edit_record_dialog(record, on_done):
        rec_id = record["id"]
        subject = record["subject"]

        def choose(status):
            def handler(e):
                update_status(rec_id, status)
                page.pop_dialog()
                on_done()

            return handler

        def do_delete(e):
            delete_record(rec_id)
            page.pop_dialog()
            on_done()

        chips = []
        for status in STATUS_LIST:
            color = STATUS_COLORS[status]
            is_current = status == record["status"]
            chips.append(
                ft.ElevatedButton(
                    content=("\u2713 " + status) if is_current else status,
                    on_click=choose(status),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.with_opacity(0.32 if is_current else 0.18, color),
                        color=color,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        side=ft.BorderSide(2 if is_current else 1, color),
                    ),
                )
            )

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=COLOR_SURFACE,
            title=ft.Text(
                f"{subject} \u2022 {record['date']}",
                color=COLOR_TEXT,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"{record['day_name']}, {format_slot_label(*record['time_slot'].split('-'))}",
                            color=COLOR_SUBTEXT,
                            size=12,
                        ),
                        ft.Divider(color=COLOR_CARD_BORDER),
                        ft.Text("Change status to:", color=COLOR_SUBTEXT, size=12),
                        ft.Row(chips, wrap=True, spacing=8, run_spacing=8),
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "Delete Entry",
                    on_click=do_delete,
                    style=ft.ButtonStyle(color=STATUS_COLORS["Absent"]),
                ),
                ft.TextButton(
                    "Close",
                    on_click=lambda e: page.pop_dialog(),
                    style=ft.ButtonStyle(color=COLOR_SUBTEXT),
                ),
            ],
        )
        page.show_dialog(dialog)

    # =======================================================================
    # VIEW: TODAY
    # =======================================================================
    def build_today_view():
        today = dt.date.today()
        date_str = today.isoformat()
        day_name = today.strftime("%A")
        blocks = TIMETABLE.get(day_name, [])

        header = ft.Container(
            padding=ft.Padding(20, 50, 20, 10),
            content=ft.Column(
                [
                    ft.Text("BunkMarte", size=26, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
                    ft.Text(f"{day_name}, {today.strftime('%d %b %Y')}", size=14, color=COLOR_SUBTEXT),
                ],
                spacing=2,
            ),
        )

        if not blocks:
            body_list = ft.Container(
                padding=30,
                content=ft.Text(
                    "No classes scheduled today. Enjoy! \U0001F389",
                    color=COLOR_SUBTEXT,
                    size=16,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
            )
            return ft.Column([header, body_list], spacing=0, expand=True)

        cards = []
        for block in blocks:
            if block.get("is_recess"):
                cards.append(
                    ft.Container(
                        margin=ft.Margin(16, 6, 16, 6),
                        padding=14,
                        border_radius=14,
                        bgcolor="#0A0A0A",
                        border=ft.Border.all(1, "#222222"),
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.FREE_BREAKFAST, color=COLOR_SUBTEXT, size=18),
                                ft.Text(
                                    f"Recess  \u2022  {format_slot_label(block['start'], block['end'])}",
                                    color=COLOR_SUBTEXT,
                                    size=13,
                                    italic=True,
                                ),
                            ],
                            spacing=8,
                        ),
                    )
                )
                continue

            time_slot = f"{block['start']}-{block['end']}"
            subject = block["subject"]
            existing = get_record(date_str, time_slot, subject)
            status = existing["status"] if existing else None
            chip_color = STATUS_COLORS.get(status, COLOR_SUBTEXT)

            label = subject + (" (Lab)" if block.get("is_lab") else "")

            def make_click(ts=time_slot, subj=subject, lbl=label):
                def handler(e):
                    open_status_picker(
                        date_str, day_name, ts, subj, f"{lbl} \u2014 mark status",
                        on_done=refresh_body,
                    )

                return handler

            status_pill = (
                ft.Container(
                    padding=ft.Padding(10, 4, 10, 4),
                    border_radius=20,
                    bgcolor=ft.Colors.with_opacity(0.2, chip_color),
                    content=ft.Text(status, size=12, color=chip_color, weight=ft.FontWeight.W_600),
                )
                if status
                else ft.Container(
                    padding=ft.Padding(10, 4, 10, 4),
                    border_radius=20,
                    bgcolor="#1E1E1E",
                    content=ft.Text("Tap to mark", size=12, color=COLOR_SUBTEXT),
                )
            )

            cards.append(
                ft.Container(
                    margin=ft.Margin(16, 6, 16, 6),
                    padding=16,
                    border_radius=18,
                    bgcolor=COLOR_CARD,
                    border=ft.Border.all(1, COLOR_CARD_BORDER if not status else ft.Colors.with_opacity(0.5, chip_color)),
                    on_click=make_click(),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(label, size=17, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                                    ft.Text(
                                        format_slot_label(block["start"], block["end"]),
                                        size=12,
                                        color=COLOR_SUBTEXT,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            status_pill,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        return ft.Column(
            [header, ft.Column(cards, spacing=0), ft.Container(height=90)],
            spacing=0,
            expand=True,
        )

    # =======================================================================
    # VIEW: SUMMARY
    # =======================================================================
    def build_summary_view():
        header = ft.Container(
            padding=ft.Padding(20, 50, 20, 10),
            content=ft.Column(
                [
                    ft.Text("Attendance Summary", size=24, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
                    ft.Text("Tap a subject to view its full history", size=13, color=COLOR_SUBTEXT),
                ],
                spacing=2,
            ),
        )

        summary = compute_subject_summary()
        # Always show every subject that appears anywhere in the timetable,
        # even if it has zero logged classes yet.
        all_subjects = sorted(
            {b["subject"] for day in TIMETABLE.values() for b in day if not b.get("is_recess")}
        )

        rows = []
        for subject in all_subjects:
            attended, total = summary.get(subject, (0, 0))
            pct = (attended / total * 100) if total > 0 else 0.0
            color = percentage_color(pct) if total > 0 else COLOR_SUBTEXT

            def make_click(subj=subject):
                def handler(e):
                    state["history_subject"] = subj
                    state["tab"] = 2  # history pseudo-tab
                    refresh_body()

                return handler

            rows.append(
                ft.Container(
                    margin=ft.Margin(16, 6, 16, 6),
                    padding=16,
                    border_radius=18,
                    bgcolor=COLOR_CARD,
                    border=ft.Border.all(1, COLOR_CARD_BORDER),
                    on_click=make_click(),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(subject, size=17, weight=ft.FontWeight.BOLD, color=COLOR_TEXT),
                                    ft.Text(
                                        f"{pct:.1f}%" if total > 0 else "N/A",
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        color=color,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.ProgressBar(
                                value=(pct / 100) if total > 0 else 0,
                                color=color,
                                bgcolor="#2A2A2A",
                                border_radius=8,
                            ),
                            ft.Text(
                                f"Attended {attended} / {total} classes",
                                size=12,
                                color=COLOR_SUBTEXT,
                            ),
                        ],
                        spacing=8,
                    ),
                )
            )

        if not rows:
            rows.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No subjects yet.", color=COLOR_SUBTEXT),
                )
            )

        return ft.Column(
            [header, ft.Column(rows, spacing=0), ft.Container(height=90)],
            spacing=0,
            expand=True,
        )

    # =======================================================================
    # VIEW: SUBJECT HISTORY
    # =======================================================================
    def build_history_view(subject):
        def go_back(e):
            state["tab"] = 1
            state["history_subject"] = None
            refresh_body()

        header = ft.Container(
            padding=ft.Padding(10, 46, 20, 10),
            content=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color=COLOR_TEXT,
                        on_click=go_back,
                    ),
                    ft.Column(
                        [
                            ft.Text(f"{subject} History", size=22, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
                            ft.Text(
                                f"Since {HISTORY_START_DATE.strftime('%d %b %Y')} \u2022 tap grayed-out days to backfill",
                                size=12,
                                color=COLOR_SUBTEXT,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # The full ghost calendar: real logged rows (id is an int) mixed
        # with generated "Unmarked" placeholders (id is None) for every
        # scheduled day since HISTORY_START_DATE that was never logged.
        records = get_subject_history(subject)

        entries = []
        for rec in records:
            is_unmarked = rec["id"] is None
            color = UNMARKED_COLOR if is_unmarked else STATUS_COLORS.get(rec["status"], COLOR_SUBTEXT)
            start, end = rec["time_slot"].split("-")
            slot_label = format_slot_label(start, end) + (" \u2022 Lab" if rec.get("is_lab") else "")

            def make_click(r=rec, unmarked=is_unmarked):
                def handler(e):
                    if unmarked:
                        # Never logged - open the same picker used on the
                        # Today view so this missed day can be backfilled.
                        open_status_picker(
                            r["date"],
                            r["day_name"],
                            r["time_slot"],
                            r["subject"],
                            f"{r['subject']} \u2014 {r['day_name']}, {r['date']}",
                            on_done=refresh_body,
                        )
                    else:
                        # Already logged - open the normal edit/delete dialog.
                        open_edit_record_dialog(r, on_done=refresh_body)

                return handler

            entries.append(
                ft.Container(
                    margin=ft.Margin(16, 5, 16, 5),
                    padding=14,
                    border_radius=16,
                    bgcolor=COLOR_CARD if not is_unmarked else "#151018",
                    border=ft.Border.all(
                        1,
                        COLOR_CARD_BORDER if not is_unmarked else "#2A2A32",
                    ),
                    on_click=make_click(),
                    content=ft.Row(
                        [
                            ft.Container(
                                width=4,
                                height=40,
                                bgcolor=color,
                                border_radius=4,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{rec['day_name']}, {rec['date']}",
                                        size=14,
                                        weight=ft.FontWeight.W_600,
                                        color=COLOR_TEXT if not is_unmarked else COLOR_SUBTEXT,
                                    ),
                                    ft.Text(slot_label, size=12, color=COLOR_SUBTEXT),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Container(
                                padding=ft.Padding(10, 4, 10, 4),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.14 if is_unmarked else 0.2, color),
                                content=ft.Text(
                                    rec["status"],
                                    size=12,
                                    color=color,
                                    weight=ft.FontWeight.W_600,
                                    italic=is_unmarked,
                                ),
                            ),
                            ft.Icon(
                                ft.Icons.ADD_CIRCLE_OUTLINE if is_unmarked else ft.Icons.CHEVRON_RIGHT,
                                color=COLOR_SUBTEXT,
                                size=18,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        if not entries:
            entries.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        "No classes scheduled for this subject yet.", color=COLOR_SUBTEXT
                    ),
                )
            )

        return ft.Column(
            [header, ft.Column(entries, spacing=0), ft.Container(height=40)],
            spacing=0,
            expand=True,
        )

    # =======================================================================
    # NAVIGATION BAR
    # =======================================================================
    def on_nav_change(e):
        state["tab"] = e.control.selected_index
        state["history_subject"] = None
        refresh_body()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        bgcolor=COLOR_SURFACE,
        indicator_color=ft.Colors.with_opacity(0.35, COLOR_PRIMARY),
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.TODAY_OUTLINED, selected_icon=ft.Icons.TODAY, label="Today"),
            ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART_OUTLINE, selected_icon=ft.Icons.PIE_CHART, label="Summary"),
        ],
    )

    def refresh_body():
        body.controls.clear()
        if state["tab"] == 0:
            page.navigation_bar = nav_bar
            nav_bar.selected_index = 0
            body.controls.append(build_today_view())
        elif state["tab"] == 1:
            page.navigation_bar = nav_bar
            nav_bar.selected_index = 1
            body.controls.append(build_summary_view())
        else:  # tab == 2 -> subject history (no bottom nav, has back button)
            page.navigation_bar = None
            body.controls.append(build_history_view(state["history_subject"]))
        page.update()

    page.add(body)
    refresh_body()


if __name__ == "__main__":
    ft.run(main)