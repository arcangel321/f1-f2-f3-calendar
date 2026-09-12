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


def get_property(event, property_name):
    pattern = rf"(?im)^{re.escape(property_name)}(?:;[^:]*)?:(.*)$"
    match = re.search(pattern, event)

    if match:
        return match.group(1).strip()

    return ""


def get_start_datetime(event):
    match = re.search(
        r"(?im)^DTSTART(?:;[^:]*)?:(\d{8})(?:T(\d{6}))?",
        event
    )

    if not match:
        return datetime.max

    date_part = match.group(1)
    time_part = match.group(2) or "000000"

    try:
        return datetime.strptime(
            date_part + time_part,
            "%Y%m%d%H%M%S"
        )
    except ValueError:
        return datetime.max


def replace_summary(event, title):
    pattern = (
        r"(?im)^SUMMARY(?:;[^:]*)?:.*"
        r"(?:\r?\n[ \t].*)*"
    )

    return re.sub(
        pattern,
        "SUMMARY:" + title,
        event,
        count=1
    )


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


def process_calendar(series, source):
    source = source.replace("\r\n", "\n")
    source = source.replace("\r", "\n")

    events = re.findall(
        r"BEGIN:VEVENT.*?END:VEVENT",
        source,
        flags=re.S
    )

    f3_feature_numbers = {}

    if series == "f3":
        f3_feature_numbers = get_f3_feature_numbers(events)

    output = source

    for event in events:
        summary = get_property(event, "SUMMARY")

        if series == "f1":
            title = f1_title(summary)

        elif series == "f2":
            title = f2_title(summary)

        elif series == "f3":
            title = f3_title(summary)

            if title == "F3 Feature Race":
                number = f3_feature_numbers.get(
                    id(event),
                    1
                )

                if number == 1:
                    title = "F3 Feature 1"
                else:
                    title = "F3 Feature 2"

        else:
            title = None

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


def main():
    for series, url in SOURCES.items():

        print(
            f"Downloading {series.upper()} calendar..."
        )

        try:
            source = download_calendar(url)

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
                file.write(output)

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
