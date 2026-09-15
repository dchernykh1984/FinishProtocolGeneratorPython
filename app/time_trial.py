"""Start-order data and layout for the time-trial window.

A time trial sends riders off one at a time, so the start line needs a board showing
who goes next and how long is left. A rider's start time is their group's start time
(groups.txt) plus their personal offset (start.txt), which is exactly the pair of files
the generator already re-reads on every run.

Everything here is plain data and arithmetic: the widget only paints what
``board_items`` returns, so the board can be checked without a screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.models import GroupStartElement, StartProtocolElement

_EPOCH = date(1970, 1, 1)

# The board is laid out in these coordinates and scaled to the window, so every glyph
# grows by the same factor and the arrangement never reflows.
DESIGN_WIDTH = 800.0
DESIGN_HEIGHT = 480.0

ALIGN_LEFT = "left"
ALIGN_CENTER = "center"
ALIGN_RIGHT = "right"


@dataclass(frozen=True)
class StartEntry:
    """One rider and the moment they are due to start."""

    competitor_id: str
    name: str
    start_time: float


@dataclass(frozen=True)
class TimeTrialView:
    """What the board shows at one instant.

    ``started`` is the rider who most recently went, ``next_up`` the one the clock
    counts down to, ``after_next`` the one following them. Any of the three is None
    once there is nobody left to put there.
    """

    now: float
    started: StartEntry | None
    next_up: StartEntry | None
    after_next: StartEntry | None
    countdown: float | None


@dataclass(frozen=True)
class BoardItem:
    """A single run of text placed in design coordinates."""

    text: str
    x: float
    y: float
    width: float
    height: float
    font_size: float
    align: str


def now_seconds(moment: datetime | None = None) -> float:
    """Local wall clock on the same scale as the timing files.

    The chronometers write "<days since 1970-01-01> <local H:M:S>", so a value is whole
    local days times 86400 plus seconds since local midnight. "Now" has to be built the
    same way: a UTC timestamp would sit a whole timezone offset away from the start
    times it is compared against.
    """
    m = moment if moment is not None else datetime.now()
    days = (m.date() - _EPOCH).days
    seconds = m.hour * 3600 + m.minute * 60 + m.second + m.microsecond / 1_000_000
    return days * 86400.0 + seconds


def _sort_key(entry: StartEntry) -> tuple[float, int, str]:
    """Order by start time, then by bib so equal times keep a stable, sane order."""
    try:
        number = int(entry.competitor_id)
    except ValueError:
        number = 0
    return (entry.start_time, number, entry.competitor_id)


def build_start_entries(
    start_list: list[StartProtocolElement],
    group_list: list[GroupStartElement],
) -> list[StartEntry]:
    """The start schedule, earliest first.

    A rider whose group has no start time is left out. The generator substitutes 0.0
    for a group missing from groups.txt, and carrying that through would date the rider
    to 1970 and permanently show them as the one who just started.
    """
    group_times = {g.group_id: g.seconds for g in group_list if g.seconds > 0}
    entries = [
        StartEntry(
            competitor_id=s.competitor_id,
            name=s.name,
            start_time=group_times[s.group_id] + s.start_delay,
        )
        for s in start_list
        if s.group_id in group_times
    ]
    return sorted(entries, key=_sort_key)


def select_view(entries: list[StartEntry], now: float) -> TimeTrialView:
    """Pick the three riders around ``now`` from an ordered schedule.

    A rider is "away" the instant their time arrives, so the split is on
    ``start_time <= now``. As the field empties, ``next_up`` and then ``after_next``
    fall away to None while ``started`` keeps the last rider sent off.
    """
    started: StartEntry | None = None
    upcoming: list[StartEntry] = []
    for entry in entries:
        if entry.start_time <= now:
            started = entry
        else:
            upcoming.append(entry)
            if len(upcoming) == 2:
                break
    next_up = upcoming[0] if upcoming else None
    after_next = upcoming[1] if len(upcoming) > 1 else None
    return TimeTrialView(
        now=now,
        started=started,
        next_up=next_up,
        after_next=after_next,
        countdown=None if next_up is None else next_up.start_time - now,
    )


def format_clock(value: float) -> str:
    """A timing-file value as the wall clock it stands for."""
    seconds_of_day = int(value) % 86400
    hours, rest = divmod(seconds_of_day, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_countdown(seconds: float | None) -> str:
    """Whole seconds still to run, or "" when nobody is left to start.

    Truncated rather than rounded, so the board reads the way a start is called: with
    15.7 seconds left it says 15, and it shows 0 for the last second before the off.
    """
    if seconds is None:
        return ""
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def board_transform(width: float, height: float) -> tuple[float, float, float]:
    """Scale and centring offsets that map design coordinates onto a window.

    One factor is taken for both axes -- the smaller of the two ratios -- so the board
    keeps its arrangement and every glyph grows by exactly the same amount when the
    window is resized. The leftover space is split evenly, which centres the board in
    whatever aspect ratio the window happens to have.
    """
    if width <= 0 or height <= 0:
        return 0.0, 0.0, 0.0
    scale = min(width / DESIGN_WIDTH, height / DESIGN_HEIGHT)
    offset_x = (width - DESIGN_WIDTH * scale) / 2
    offset_y = (height - DESIGN_HEIGHT * scale) / 2
    return scale, offset_x, offset_y


def _entry_text(entry: StartEntry | None) -> tuple[str, str]:
    """Bib and name of a rider, or a pair of blanks when there is none."""
    if entry is None:
        return "", ""
    return entry.competitor_id, entry.name


def board_items(view: TimeTrialView) -> list[BoardItem]:
    """The board contents in design coordinates, with empty slots left out.

    Dropping blank runs is what makes the field empty itself: when nobody is left to
    start, the countdown, the bib and the name simply stop being drawn instead of
    showing a stale rider or a zero.
    """
    next_number, next_name = _entry_text(view.next_up)
    after_number, after_name = _entry_text(view.after_next)
    started_number, started_name = _entry_text(view.started)
    margin = 24.0
    side_width = 260.0
    candidates = [
        BoardItem(format_clock(view.now), 0, 18, DESIGN_WIDTH, 70, 54, ALIGN_CENTER),
        BoardItem(
            format_countdown(view.countdown),
            0,
            96,
            DESIGN_WIDTH,
            150,
            132,
            ALIGN_CENTER,
        ),
        BoardItem(next_number, 0, 250, DESIGN_WIDTH, 110, 104, ALIGN_CENTER),
        BoardItem(next_name, 0, 360, DESIGN_WIDTH, 38, 30, ALIGN_CENTER),
        BoardItem(after_number, margin, 402, side_width, 42, 40, ALIGN_LEFT),
        BoardItem(after_name, margin, 444, side_width, 26, 18, ALIGN_LEFT),
        BoardItem(
            started_number,
            DESIGN_WIDTH - margin - side_width,
            402,
            side_width,
            42,
            40,
            ALIGN_RIGHT,
        ),
        BoardItem(
            started_name,
            DESIGN_WIDTH - margin - side_width,
            444,
            side_width,
            26,
            18,
            ALIGN_RIGHT,
        ),
    ]
    return [item for item in candidates if item.text]
