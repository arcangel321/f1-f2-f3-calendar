import re
import urllib.request
from datetime import datetime
SOURCES = {
    "f1": "https://ics.ecal.com/ecal-sub/6aa50ef6bc1c410003d96fbf/Formula%201.ics",
    "f2": "https://ics.ecal.com/ecal-sub/6aa50eb99c648e00038ee83c/Formula%202.ics",
    "f3": "https://ics.ecal.com/ecal-sub/6aa50e5abc1c410003d96fb1/Formula%203.ics",
}
def download_calendar(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")
def unfold_lines(text):
    """
    iCalendar folded lines:
    een regel die begint met spatie/tab is een vervolg
    van de vorige regel.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded
def get_property(event, property_name):
    """
    Haalt een iCalendar-property op en ondersteunt folded lines.
    """
    lines = unfold_lines(event)
    property_name = property_name.upper()
    for line in lines:
        upper = line.upper()
        if (
            upper.startswith(property_name + ":")
            or upper.startswith(property_name + ";")
        ):
            if ":" in line:
                return line.split(":", 1)[1].strip()
    return ""
def get_start_datetime(event):
    """
    Haalt DTSTART op als datetime.
    Werkt voor zowel datum als datum+tijd.
    """
    lines = unfold_lines(event)
    for line in lines:
        if not line.upper().startswith("DTSTART"):
            continue
        if ":" not in line:
            continue
        value = line.split(":", 1)[1].strip()
        match = re.match(
            r"(\d{8})(?:T(\d{6}))?",
            value
        )
        if not match:
            continue
        date_part = match.group(1)
        time_part = match.group(2) or "000000"
        try:
            return datetime.strptime(
                date_part + time_part,
                "%Y%m%d%H%M%S"
            )
        except ValueError:
            return datetime.max
    return datetime.max
def get_weekend_key(event):
    """
    Gebruikt de ISO-week van DTSTART als raceweekend.
    """
    start = get_start_datetime(event)
    if start == datetime.max:
        return None
    iso = start.isocalendar()
    return (iso.year, iso.week)
def replace_summary(event, title):
    """
    Vervangt SUMMARY inclusief folded continuation lines.
    """
    lines = (
        event
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )
    result = []
    replacing = False
    for line in lines:
        if not replacing:
            if re.match(
                r"^SUMMARY(?:;[^:]*)?:",
                line,
                flags=re.IGNORECASE
            ):
                result.append("SUMMARY:" + title)
                replacing = True
            else:
                result.append(line)
        else:
            if line.startswith((" ", "\t")):
                continue
            replacing = False
            result.append(line)
    return "\n".join(result)
# ============================================================
# F1
# ============================================================
def f1_title(summary):
    text = summary.upper()
    if "SPRINT QUALIFYING" in text:
        return "F1 Sprint Kwalificatie"
    if "PRACTICE 1" in text or "FREE PRACTICE 1" in text:
        return "F1 VT1"
    if "PRACTICE 2" in text or "FREE PRACTICE 2" in text:
        return "F1 VT2"
    if "PRACTICE 3" in text or "FREE PRACTICE 3" in text:
        return "F1 VT3"
    if "QUALIFYING" in text:
        return "F1 Kwalificatie"
    if "SPRINT" in text:
        return "F1 Sprint"
    if "RACE" in text or "GRAND PRIX" in text:
        return "F1 Race"
    return None
# ============================================================
# F2
# ============================================================
def f2_explicit_title(summary):
    text = summary.upper()
    if "PRACTICE" in text or "FREE PRACTICE" in text:
        return "F2 Practice"
    if "QUALIFYING" in text:
        return "F2 Kwalificatie"
    if "SPRINT" in text:
        return "F2 Sprint"
    if "FEATURE" in text:
        return "F2 Feature Race"
    return None
def get_f2_race_titles(events):
    """
    F2 kan races expliciet 'Sprint'/'Feature' noemen,
    maar soms heten ze simpelweg 'Race'.
    Voor generieke Race-events:
      eerste race van weekend = Sprint
      tweede race van weekend = Feature Race
    """
    generic = []
    for event in events:
        summary = get_property(event, "SUMMARY")
        text = summary.upper()
        if "RACE" not in text:
            continue
        if "SPRINT" in text:
            continue
        if "FEATURE" in text:
            continue
        if "GRAND PRIX" in text and "RACE" not in text:
            continue
        generic.append(event)
    weekends = {}
    for event in generic:
        key = get_weekend_key(event)
        if key is None:
            continue
        weekends.setdefault(key, []).append(event)
    titles = {}
    for weekend_events in weekends.values():
        weekend_events.sort(
            key=get_start_datetime
        )
        if len(weekend_events) >= 1:
            titles[id(weekend_events[0])] = "F2 Sprint"
        if len(weekend_events) >= 2:
            titles[id(weekend_events[1])] = "F2 Feature Race"
        # Eventuele extra generieke races krijgen geen
        # automatische titel.
    return titles
# ============================================================
# F3
# ============================================================
def is_f3_qualifying(summary):
    text = summary.upper()
    return "QUALIFYING" in text or re.search(r"\bQ[12]\b", text) is not None
def is_f3_race(summary):
    text = summary.upper()
    if "RACE" in text:
        return True
    if "FEATURE" in text:
        return True
    return False
def is_f3_sprint(summary):
    return "SPRINT" in summary.upper()
def get_f3_session_groups(events):
    """
    Bepaalt per raceweekend:
      - qualifying 1 = Q1
      - qualifying 2 = Q2
      - eerste Race/Feature = Feature 1
      - tweede Race/Feature = Feature 2
    Dit gebeurt chronologisch per ISO-week.
    """
    weekends = {}
    for event in events:
        summary = get_property(event, "SUMMARY")
        text = summary.upper()
        relevant = (
            is_f3_qualifying(summary)
            or is_f3_race(summary)
            or is_f3_sprint(summary)
        )
        if not relevant:
            continue
        key = get_weekend_key(event)
        if key is None:
            continue
        weekends.setdefault(key, []).append(event)
    assignments = {}
    for weekend_events in weekends.values():
        weekend_events.sort(
            key=get_start_datetime
        )
        qualifying_events = []
        race_events = []
        for event in weekend_events:
            summary = get_property(
                event,
                "SUMMARY"
            )
            if is_f3_qualifying(summary):
                qualifying_events.append(event)
            elif is_f3_race(summary):
                race_events.append(event)
        # --------------------------------------------
        # Qualifying
        # --------------------------------------------
        qualifying_events.sort(
            key=get_start_datetime
        )
        if len(qualifying_events) >= 1:
            assignments[id(qualifying_events[0])] = "F3 Q1"
        if len(qualifying_events) >= 2:
            assignments[id(qualifying_events[1])] = "F3 Q2"
        # --------------------------------------------
        # Feature races
        # --------------------------------------------
        # Sprint nooit als Feature behandelen.
        feature_events = []
        for event in race_events:
            summary = get_property(
                event,
                "SUMMARY"
            )
            if is_f3_sprint(summary):
                continue
            feature_events.append(event)
        feature_events.sort(
            key=get_start_datetime
        )
        for number, event in enumerate(
            feature_events,
            start=1
        ):
            assignments[id(event)] = (
                f"F3 Feature {number}"
            )
    return assignments
def f3_basic_title(summary):
    text = summary.upper()
    if "PRACTICE" in text or "FREE PRACTICE" in text:
        return "F3 Practice"
    if "SPRINT" in text:
        return "F3 Sprint"
    return None
# ============================================================
# Calendar processing
# ============================================================
def process_calendar(series, source):
    source = (
        source
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    events = re.findall(
        r"BEGIN:VEVENT.*?END:VEVENT",
        source,
        flags=re.S
    )
    # --------------------------------------------
    # F2
    # --------------------------------------------
    f2_race_titles = {}
    if series == "f2":
        f2_race_titles = get_f2_race_titles(
            events
        )
    # --------------------------------------------
    # F3
    # --------------------------------------------
    f3_assignments = {}
    if series == "f3":
        f3_assignments = get_f3_session_groups(
            events
        )
    output = source
    # --------------------------------------------
    # Process events
    # --------------------------------------------
    for event in events:
        summary = get_property(
            event,
            "SUMMARY"
        )
        title = None
        # ========================================
        # F1
        # ========================================
        if series == "f1":
            title = f1_title(
                summary
            )
        # ========================================
        # F2
        # ========================================
        elif series == "f2":
            title = f2_explicit_title(
                summary
            )
            if title is None:
                title = f2_race_titles.get(
                    id(event)
                )
        # ========================================
        # F3
        # ========================================
        elif series == "f3":
            # Eerst de speciale classificatie
            # voor Q1/Q2/Feature 1/2.
            title = f3_assignments.get(
                id(event)
            )
            # Daarna Practice/Sprint.
            if title is None:
                title = f3_basic_title(
                    summary
                )
        # ========================================
        # Replace SUMMARY
        # ========================================
        if title:
            new_event = replace_summary(
                event,
                title
            )
            output = output.replace(
                event,
                new_event,
                1
            )
    return output.replace(
        "\n",
        "\r\n"
    )
# ============================================================
# Main
# ============================================================
def main():
    for series, url in SOURCES.items():
        print(
            f"Downloading {series.upper()} calendar..."
        )
        try:
            source = download_calendar(
                url
            )
            output = process_calendar(
                series,
                source
            )
            filename = f"{series}.ics"
            with open(
                filename,
                "w",
                encoding="utf-8",
                newline=""
            ) as file:
                file.write(
                    output
                )
            print(
                f"Successfully created {filename}"
            )
        except Exception as error:
            print(
                f"ERROR processing {series.upper()}: {error}"
            )
            raise
if __name__ == "__main__":
    main()
