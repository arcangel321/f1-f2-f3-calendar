import urllib.request
import re
from datetime import datetime
from collections import defaultdict

SOURCES = {
    "f1": "https://ics.ecal.com/ecal-sub/6aa50ef6bc1c410003d96fbf/Formula%201.ics",
    "f2": "https://ics.ecal.com/ecal-sub/6aa50eb99c648e00038ee83c/Formula%202.ics",
    "f3": "https://ics.ecal.com/ecal-sub/6aa50e5abc1c410003d96fb1/Formula%203.ics",
}


def download_calendar(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def unfold_lines(text):
    """
    iCalendar gebruikt folded lines:
    een regel die begint met spatie of tab hoort bij de vorige regel.
    """
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    lines = []

    for line in raw_lines:
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)

    return lines


def get_property(lines, property_name):
    """
    Haalt de eerste waarde van bijvoorbeeld SUMMARY of DTSTART op.
    """
    prefix = property_name.upper() + ":"

    for line in lines:
        if line.upper().startswith(prefix):
            return line[len(prefix):].strip()

    return ""


def get_start_datetime(event):
    value = get_property(event, "DTSTART")

    if not value:
        return datetime.max

    value = value.replace("Z", "")

    for fmt in (
        "%Y%m%dT%H%M%S",
        "%Y%m%dT%H%M",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return datetime.max


def get_weekend_key(event):
    """
    Gebruikt datum + locatie om sessies van hetzelfde raceweekend
    bij elkaar te houden.
    """
    location = get_property(event, "LOCATION").strip().lower()

    dt = get_start_datetime(event)

    if dt == datetime.max:
        return ("unknown", location)

    return (dt.date().isoformat(), location)


def split_events(text):
    """
    Splitst een VCALENDAR op in losse VEVENT-blokken.
    """
    lines = unfold_lines(text)

    events = []
    current = None

    for line in lines:
        if line == "BEGIN:VEVENT":
            current = [line]

        elif line == "END:VEVENT":
            if current is not None:
                current.append(line)
                events.append(current)
                current = None

        elif current is not None:
            current.append(line)

    return events


def replace_summary(event, new_summary):
    """
    Vervangt SUMMARY in een event.
    """
    result = []

    replaced = False

    for line in event:
        if line.upper().startswith("SUMMARY:"):
            result.append("SUMMARY:" + new_summary)
            replaced = True
        else:
            result.append(line)

    if not replaced:
        result.append("SUMMARY:" + new_summary)

    return result


# ============================================================
# F1
# ============================================================

def f1_title(summary):
    s = summary.upper()

    if "PRACTICE 1" in s:
        return "F1 VT1"

    if "PRACTICE 2" in s:
        return "F1 VT2"

    if "PRACTICE 3" in s:
        return "F1 VT3"

    if "SPRINT QUALIFYING" in s:
        return "F1 Sprint Kwalificatie"

    if "QUALIFYING" in s:
        return "F1 Kwalificatie"

    if re.search(r"\bSPRINT\b", s):
        return "F1 Sprint"

    if re.search(r"\bRACE\b", s):
        return "F1 Race"

    return None


# ============================================================
# F2
# ============================================================

def f2_title(summary):
    s = summary.upper()

    if "PRACTICE" in s:
        return "F2 Practice"

    if "QUALIFYING" in s:
        return "F2 Kwalificatie"

    if "SPRINT" in s:
        return "F2 Sprint"

    if "FEATURE RACE" in s:
        return "F2 Feature Race"

    return None


def get_f2_race_groups(events):
    """
    F2 heeft normaal één Feature Race per weekend.
    Eventuele generieke 'Race'-events worden als Feature Race behandeld.
    """
    groups = defaultdict(list)

    for event in events:
        summary = get_property(event, "SUMMARY")

        if not summary:
            continue

        s = summary.upper()

        if (
            "RACE" in s
            and "SPRINT" not in s
            and "QUALIFYING" not in s
            and "PRACTICE" not in s
        ):
            groups[get_weekend_key(event)].append(event)

    return groups


# ============================================================
# F3
# ============================================================

def is_f3_practice(summary):
    return "PRACTICE" in summary.upper()


def is_f3_qualifying(summary):
    s = summary.upper()

    return (
        "QUALIFYING" in s
        or re.search(r"\bQ[12]\b", s) is not None
    )


def is_f3_sprint(summary):
    s = summary.upper()

    return "SPRINT" in s


def is_f3_race(summary):
    s = summary.upper()

    return (
        "RACE" in s
        or "FEATURE" in s
    )


def get_f3_session_groups(events):
    """
    Bepaalt per F3-weekend:

    - eerste qualifying = Q1
    - tweede qualifying = Q2
    - Sprint = Sprint
    - eerste niet-sprint race = Feature 1
    - tweede niet-sprint race = Feature 2

    Belangrijk:
    Madrid 2026 heeft naast de twee Feature Races ook
    een Sprint. De Sprint moet dus expliciet vóór de
    Feature Races worden uitgesloten.
    """

    groups = defaultdict(
        lambda: {
            "qualifying": [],
            "sprint": [],
            "races": [],
        }
    )

    for event in events:
        summary = get_property(event, "SUMMARY")

        if not summary:
            continue

        if is_f3_qualifying(summary):
            groups[get_weekend_key(event)]["qualifying"].append(event)

        elif is_f3_sprint(summary):
            groups[get_weekend_key(event)]["sprint"].append(event)

        elif is_f3_race(summary):
            groups[get_weekend_key(event)]["races"].append(event)

    assignments = {}

    for weekend, data in groups.items():

        # ----------------------------------------------------
        # Qualifying
        # ----------------------------------------------------

        qualifying = sorted(
            data["qualifying"],
            key=get_start_datetime
        )

        for index, event in enumerate(qualifying):
            if index == 0:
                assignments[id(event)] = "F3 Q1"

            elif index == 1:
                assignments[id(event)] = "F3 Q2"

        # ----------------------------------------------------
        # Sprint
        # ----------------------------------------------------

        sprint_events = sorted(
            data["sprint"],
            key=get_start_datetime
        )

        for event in sprint_events:
            assignments[id(event)] = "F3 Sprint"

        # ----------------------------------------------------
        # Feature Races
        # ----------------------------------------------------

        races = sorted(
            data["races"],
            key=get_start_datetime
        )

        for index, event in enumerate(races):

            if index == 0:
                assignments[id(event)] = "F3 Feature 1"

            elif index == 1:
                assignments[id(event)] = "F3 Feature 2"

            else:
                # Extra race: alleen als de bron onverwacht
                # meer dan twee non-sprint races bevat.
                #
                # Niet als Feature 3 benoemen; liever een
                # duidelijke fallback dan een verkeerde naam.
                assignments[id(event)] = "F3 Race"

    return assignments


def f3_basic_title(summary):
    s = summary.upper()

    if "PRACTICE" in s:
        return "F3 Practice"

    if "SPRINT" in s:
        return "F3 Sprint"

    return None


# ============================================================
# ICS generator
# ============================================================

def build_calendar(source_text, series):
    events = split_events(source_text)

    output_events = []

    if series == "f3":
        f3_assignments = get_f3_session_groups(events)
    else:
        f3_assignments = {}

    f2_race_groups = {}

    if series == "f2":
        f2_race_groups = get_f2_race_groups(events)

    f2_race_assignments = {}

    if series == "f2":
        for weekend, race_events in f2_race_groups.items():

            race_events = sorted(
                race_events,
                key=get_start_datetime
            )

            for event in race_events:
                f2_race_assignments[id(event)] = "F2 Feature Race"

    for event in events:

        summary = get_property(event, "SUMMARY")

        if not summary:
            continue

        new_title = None

        # ----------------------------------------------------
        # F1
        # ----------------------------------------------------

        if series == "f1":
            new_title = f1_title(summary)

        # ----------------------------------------------------
        # F2
        # ----------------------------------------------------

        elif series == "f2":

            if id(event) in f2_race_assignments:
                new_title = f2_race_assignments[id(event)]
            else:
                new_title = f2_title(summary)

        # ----------------------------------------------------
        # F3
        # ----------------------------------------------------

        elif series == "f3":

            if id(event) in f3_assignments:
                new_title = f3_assignments[id(event)]
            else:
                new_title = f3_basic_title(summary)

        if new_title:
            output_events.append(
                replace_summary(event, new_title)
            )
        else:
            # Onbekende sessies worden behouden.
            output_events.append(event)

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    if series == "f1":
        calendar_name = "Formula 1"

    elif series == "f2":
        calendar_name = "Formula 2"

    else:
        calendar_name = "Formula 3"

    output = [
        "BEGIN:VCALENDAR",
        "PRODID:-//E-DIARY//E-DIARY 1.0//EN",
        "VERSION:2.0",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + calendar_name,
        "X-Built-On-Cache-Miss:true",
    ]

    for event in output_events:
        output.extend(event)

    output.append("END:VCALENDAR")

    return "\r\n".join(output) + "\r\n"


# ============================================================
# Main
# ============================================================

def main():

    for series, url in SOURCES.items():

        print(f"Downloading {series.upper()}...")

        try:
            source_text = download_calendar(url)

            calendar_text = build_calendar(
                source_text,
                series
            )

            filename = f"{series}.ics"

            with open(
                filename,
                "w",
                encoding="utf-8",
                newline=""
            ) as file:
                file.write(calendar_text)

            print(f"Created {filename}")

        except Exception as error:
            print(
                f"ERROR processing {series.upper()}: {error}"
            )
            raise


if __name__ == "__main__":
    main()
