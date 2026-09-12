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
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def unfold_lines(text):
    """
    iCalendar gebruikt folded lines:
    een regel die begint met een spatie of tab is een vervolg
    van de vorige regel.

    Deze functie maakt daar logische regels van voor parsing.
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
    Haalt een property uit een VEVENT.

    Werkt ook wanneer de property over meerdere fysieke
    iCalendar-regels verdeeld is.
    """
    lines = unfold_lines(event)

    prefix = property_name.upper()

    for line in lines:
        upper_line = line.upper()

        if upper_line.startswith(prefix + ":") or upper_line.startswith(prefix + ";"):
            if ":" in line:
                return line.split(":", 1)[1].strip()

    return ""


def get_start_datetime(event):
    """
    Haalt DTSTART uit een event.
    Ondersteunt zowel datum als datum+tijd.
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


def replace_summary(event, title):
    """
    Vervangt SUMMARY inclusief eventuele folded continuation lines.
    """
    lines = event.replace("\r\n", "\n").replace("\r", "\n").split("\n")

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
            # Een regel die begint met spatie/tab is een continuation
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

    if "PRACTICE 1" in text:
        return "F1 VT1"

    if "FREE PRACTICE 1" in text:
        return "F1 VT1"

    if "FP1" in text:
        return "F1 VT1"

    if "PRACTICE 2" in text:
        return "F1 VT2"

    if "FREE PRACTICE 2" in text:
        return "F1 VT2"

    if "FP2" in text:
        return "F1 VT2"

    if "PRACTICE 3" in text:
        return "F1 VT3"

    if "FREE PRACTICE 3" in text:
        return "F1 VT3"

    if "FP3" in text:
        return "F1 VT3"

    if "QUALIFYING" in text:
        return "F1 Kwalificatie"

    if "SPRINT" in text:
        return "F1 Sprint"

    if "RACE" in text:
        return "F1 Race"

    if "GRAND PRIX" in text:
        return "F1 Race"

    return None


# ============================================================
# F2
# ============================================================

def f2_title(summary):
    text = summary.upper()

    if "PRACTICE" in text:
        return "F2 Practice"

    if "FREE PRACTICE" in text:
        return "F2 Practice"

    if "QUALIFYING" in text:
        return "F2 Kwalificatie"

    if "SPRINT" in text:
        return "F2 Sprint"

    if "FEATURE" in text:
        return "F2 Feature Race"

    return None


def get_f2_generic_races(events):
    """
    Sommige F2-feeds noemen beide races simpelweg 'Race'.

    Per raceweekend:
      eerste Race  = Sprint
      tweede Race  = Feature Race

    Expliciete Sprint/Feature-events worden hierbij genegeerd.
    """

    generic_races = []

    for event in events:
        summary = get_property(event, "SUMMARY")
        text = summary.upper()

        if "RACE" not in text:
            continue

        if "SPRINT" in text:
            continue

        if "FEATURE" in text:
            continue

        start = get_start_datetime(event)

        if start == datetime.max:
            continue

        generic_races.append(event)

    weekends = {}

    for event in generic_races:
        start = get_start_datetime(event)

        iso = start.isocalendar()
        weekend_key = (iso.year, iso.week)

        if weekend_key not in weekends:
            weekends[weekend_key] = []

        weekends[weekend_key].append(event)

    race_titles = {}

    for weekend_events in weekends.values():
        weekend_events.sort(
            key=get_start_datetime
        )

        for number, event in enumerate(
            weekend_events,
            start=1
        ):
            if number == 1:
                race_titles[id(event)] = "F2 Sprint"

            elif number == 2:
                race_titles[id(event)] = "F2 Feature Race"

    return race_titles


# ============================================================
# F3
# ============================================================

def f3_title(summary):
    text = summary.upper()

    if "PRACTICE" in text:
        return "F3 Practice"

    if "FREE PRACTICE" in text:
        return "F3 Practice"

    if "QUALIFYING 1" in text:
        return "F3 Q1"

    if "QUALIFYING 2" in text:
        return "F3 Q2"

    if re.search(r"\bQ1\b", text):
        return "F3 Q1"

    if re.search(r"\bQ2\b", text):
        return "F3 Q2"

    if "SPRINT" in text:
        return "F3 Sprint"

    if "FEATURE" in text:
        return "F3 Feature Race"

    if "QUALIFYING" in text:
        return "F3 Kwalificatie"

    return None


def get_f3_feature_numbers(events):
    """
    Nummer F3 Feature races per raceweekend chronologisch.

    Eerste Feature = Feature 1
    Tweede Feature = Feature 2
    """

    feature_events = []

    for event in events:
        summary = get_property(event, "SUMMARY")

        if "FEATURE" in summary.upper():
            feature_events.append(event)

    weekends = {}

    for event in feature_events:
        start = get_start_datetime(event)

        if start == datetime.max:
            continue

        iso = start.isocalendar()
        weekend_key = (iso.year, iso.week)

        if weekend_key not in weekends:
            weekends[weekend_key] = []

        weekends[weekend_key].append(event)

    numbers = {}

    for weekend_events in weekends.values():
        weekend_events.sort(
            key=get_start_datetime
        )

        for number, event in enumerate(
            weekend_events,
            start=1
        ):
            numbers[id(event)] = number

    return numbers


# ============================================================
# Calendar processing
# ============================================================

def process_calendar(series, source):

    source = source.replace("\r\n", "\n")
    source = source.replace("\r", "\n")

    events = re.findall(
        r"BEGIN:VEVENT.*?END:VEVENT",
        source,
        flags=re.S
    )

    # --------------------------------------------------------
    # F2 generic races
    # --------------------------------------------------------

    f2_race_titles = {}

    if series == "f2":
        f2_race_titles = get_f2_generic_races(events)

    # --------------------------------------------------------
    # F3 feature numbering
    # --------------------------------------------------------

    f3_feature_numbers = {}

    if series == "f3":
        f3_feature_numbers = get_f3_feature_numbers(events)

    output = source

    # --------------------------------------------------------
    # Process every event
    # --------------------------------------------------------

    for event in events:

        summary = get_property(
            event,
            "SUMMARY"
        )

        title = None

        # ====================================================
        # F1
        # ====================================================

        if series == "f1":

            title = f1_title(
                summary
            )

        # ====================================================
        # F2
        # ====================================================

        elif series == "f2":

            # First check explicitly identifiable events
            title = f2_title(
                summary
            )

            # If it is a generic Race, use chronological
            # weekend assignment.
            if title is None:
                title = f2_race_titles.get(
                    id(event)
                )

        # ====================================================
        # F3
        # ====================================================

        elif series == "f3":

            title = f3_title(
                summary
            )

            if title == "F3 Feature Race":

                number = f3_feature_numbers.get(
                    id(event),
                    1
                )

                if number == 1:
                    title = "F3 Feature 1"

                elif number == 2:
                    title = "F3 Feature 2"

                else:
                    title = f"F3 Feature {number}"

        # ====================================================
        # Replace SUMMARY
        # ====================================================

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

    # iCalendar standaard gebruikt CRLF
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
