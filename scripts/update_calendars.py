import urllib.request
import re
from datetime import datetime
from collections import defaultdict


SOURCES = {
    "f1": "https://ics.ecal.com/ecal-sub/6aa50ef6bc1c410003d96fbf/Formula%201.ics",
    "f2": "https://ics.ecal.com/ecal-sub/6aa50eb99c648e00038ee83c/Formula%202.ics",
    "f3": "https://ics.ecal.com/ecal-sub/6aa50e5abc1c410003d96fb1/Formula%203.ics",
}


# ============================================================
# Download
# ============================================================

def download_calendar(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


# ============================================================
# iCalendar helpers
# ============================================================

def unfold_lines(text):
    """
    iCalendar gebruikt folded lines:
    een regel die begint met spatie of tab hoort bij de vorige regel.
    """

    raw_lines = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )

    lines = []

    for line in raw_lines:

        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]

        else:
            lines.append(line)

    return lines


def get_property(lines, property_name):
    """
    Haalt de eerste waarde van bijvoorbeeld SUMMARY,
    DTSTART of LOCATION op.
    """

    prefix = property_name.upper() + ":"

    for line in lines:

        if line.upper().startswith(prefix):
            return line[len(prefix):].strip()

    return ""


def get_start_datetime(event):
    """
    Zet DTSTART om naar een datetime.

    Ondersteunt:
        YYYYMMDDTHHMMSS
        YYYYMMDDTHHMM
        YYYYMMDD
    """

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
# Algemene weekend helper
# ============================================================

def get_weekend_key(event):
    """
    Geeft een eenvoudige sleutel terug voor F2.

    F3 gebruikt een aparte, uitgebreidere weekend-groepering.
    """

    location = get_property(
        event,
        "LOCATION"
    ).strip().lower()

    dt = get_start_datetime(event)

    if dt == datetime.max:
        return ("unknown", location)

    return (
        dt.date().isoformat(),
        location
    )


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

    Eventuele generieke Race-events worden als Feature Race
    behandeld.
    """

    groups = defaultdict(list)

    for event in events:

        summary = get_property(
            event,
            "SUMMARY"
        )

        if not summary:
            continue

        s = summary.upper()

        if (
            "RACE" in s
            and "SPRINT" not in s
            and "QUALIFYING" not in s
            and "PRACTICE" not in s
        ):

            groups[
                get_weekend_key(event)
            ].append(event)

    return groups


# ============================================================
# F3 herkenning
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

    return "SPRINT" in summary.upper()


def is_f3_race(summary):

    s = summary.upper()

    return (
        "RACE" in s
        or "FEATURE" in s
    )


# ============================================================
# F3 weekend groepering
# ============================================================

def get_f3_weekend_groups(events):
    """
    Groepeert F3-events per raceweekend.

    De vorige versie gebruikte:
        datum + locatie

    Dat was fout omdat bijvoorbeeld:

        5 september = Sprint
        6 september = Feature Race

    dan als twee verschillende weekends werden gezien.

    Hier worden events eerst per locatie verzameld.
    Zolang er maximaal 4 dagen tussen opeenvolgende
    event-datums zit, behoren ze tot hetzelfde weekend.

    Dit werkt ook voor weekends die over meerdere dagen lopen.
    """

    by_location = defaultdict(list)

    for event in events:

        dt = get_start_datetime(event)

        if dt == datetime.max:
            continue

        location = get_property(
            event,
            "LOCATION"
        ).strip().lower()

        by_location[location].append(event)

    weekend_groups = []

    for location, location_events in by_location.items():

        location_events.sort(
            key=get_start_datetime
        )

        current_group = []
        previous_date = None

        for event in location_events:

            event_date = get_start_datetime(
                event
            ).date()

            if (
                previous_date is not None
                and (
                    event_date - previous_date
                ).days > 4
            ):

                if current_group:
                    weekend_groups.append(
                        current_group
                    )

                current_group = []

            current_group.append(event)

            previous_date = event_date

        if current_group:
            weekend_groups.append(
                current_group
            )

    return weekend_groups


# ============================================================
# F3 sessies bepalen
# ============================================================

def get_f3_session_groups(events):
    """
    Bepaalt de juiste F3-benaming per raceweekend.

    Normaal F3-weekend:

        Practice
        Qualifying
        Sprint
        Feature 1

    Madrid 2026:

        Practice
        Q1
        Q2
        Sprint
        Feature 1
        Feature 2

    Belangrijk:
    De ECAL-feed noemt sommige races alleen "Race".
    Daarom wordt de eerste race chronologisch als Sprint
    gezien wanneer de bron geen expliciet Sprint-label bevat.
    """

    assignments = {}

    weekend_groups = get_f3_weekend_groups(
        events
    )

    for weekend_events in weekend_groups:

        qualifying = []
        explicit_sprints = []
        generic_races = []

        for event in weekend_events:

            summary = get_property(
                event,
                "SUMMARY"
            )

            if not summary:
                continue

            # Practice
            if is_f3_practice(summary):
                continue

            # Qualifying
            if is_f3_qualifying(summary):

                qualifying.append(event)

            # Expliciete Sprint
            elif is_f3_sprint(summary):

                explicit_sprints.append(event)

            # Alle overige races
            elif is_f3_race(summary):

                generic_races.append(event)

        # ----------------------------------------------------
        # Qualifying
        # ----------------------------------------------------

        qualifying.sort(
            key=get_start_datetime
        )

        for index, event in enumerate(qualifying):

            if index == 0:

                assignments[
                    id(event)
                ] = "F3 Q1"

            elif index == 1:

                assignments[
                    id(event)
                ] = "F3 Q2"

        # ----------------------------------------------------
        # Expliciete Sprint
        # ----------------------------------------------------

        explicit_sprints.sort(
            key=get_start_datetime
        )

        for event in explicit_sprints:

            assignments[
                id(event)
            ] = "F3 Sprint"

        # ----------------------------------------------------
        # Races
        # ----------------------------------------------------

        generic_races.sort(
            key=get_start_datetime
        )

        if generic_races:

            # Als de bron geen Sprint-label heeft,
            # is de eerste race chronologisch de Sprint.
            if not explicit_sprints:

                assignments[
                    id(generic_races[0])
                ] = "F3 Sprint"

                feature_events = generic_races[1:]

            else:

                feature_events = generic_races

            # Daarna Feature 1, Feature 2 enz.
            for index, event in enumerate(
                feature_events
            ):

                if index == 0:

                    assignments[
                        id(event)
                    ] = "F3 Feature 1"

                elif index == 1:

                    assignments[
                        id(event)
                    ] = "F3 Feature 2"

                else:

                    # Onverwachte extra race.
                    assignments[
                        id(event)
                    ] = "F3 Race"

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

    events = split_events(
        source_text
    )

    output_events = []

    # --------------------------------------------------------
    # F3 assignments
    # --------------------------------------------------------

    if series == "f3":

        f3_assignments = (
            get_f3_session_groups(
                events
            )
        )

    else:

        f3_assignments = {}

    # --------------------------------------------------------
    # F2 assignments
    # --------------------------------------------------------

    f2_race_groups = {}

    if series == "f2":

        f2_race_groups = (
            get_f2_race_groups(
                events
            )
        )

    f2_race_assignments = {}

    if series == "f2":

        for weekend, race_events in (
            f2_race_groups.items()
        ):

            race_events.sort(
                key=get_start_datetime
            )

            for event in race_events:

                f2_race_assignments[
                    id(event)
                ] = "F2 Feature Race"

    # --------------------------------------------------------
    # Events verwerken
    # --------------------------------------------------------

    for event in events:

        summary = get_property(
            event,
            "SUMMARY"
        )

        if not summary:
            continue

        new_title = None

        # ----------------------------------------------------
        # F1
        # ----------------------------------------------------

        if series == "f1":

            new_title = f1_title(
                summary
            )

        # ----------------------------------------------------
        # F2
        # ----------------------------------------------------

        elif series == "f2":

            if id(event) in f2_race_assignments:

                new_title = (
                    f2_race_assignments[
                        id(event)
                    ]
                )

            else:

                new_title = f2_title(
                    summary
                )

        # ----------------------------------------------------
        # F3
        # ----------------------------------------------------

        elif series == "f3":

            if id(event) in f3_assignments:

                new_title = (
                    f3_assignments[
                        id(event)
                    ]
                )

            else:

                new_title = f3_basic_title(
                    summary
                )

        # ----------------------------------------------------
        # Event opslaan
        # ----------------------------------------------------

        if new_title:

            output_events.append(
                replace_summary(
                    event,
                    new_title
                )
            )

        else:

            # Onbekende sessies behouden
            output_events.append(
                event
            )

    # ========================================================
    # Calendar header
    # ========================================================

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

    # ========================================================
    # Events toevoegen
    # ========================================================

    for event in output_events:

        output.extend(
            event
        )

    # ========================================================
    # Footer
    # ========================================================

    output.append(
        "END:VCALENDAR"
    )

    return (
        "\r\n".join(output)
        + "\r\n"
    )


# ============================================================
# Main
# ============================================================

def main():

    for series, url in SOURCES.items():

        print(
            f"Downloading {series.upper()}..."
        )

        try:

            source_text = download_calendar(
                url
            )

            calendar_text = build_calendar(
                source_text,
                series
            )

            filename = (
                f"{series}.ics"
            )

            with open(
                filename,
                "w",
                encoding="utf-8",
                newline=""
            ) as file:

                file.write(
                    calendar_text
                )

            print(
                f"Created {filename}"
            )

        except Exception as error:

            print(
                f"ERROR processing "
                f"{series.upper()}: {error}"
            )

            raise


if __name__ == "__main__":

    main()
