import re
import urllib.request
from datetime import datetime

SOURCES = {
    "f1": "https://ics.ecal.com/ecal-sub/6aa50ef6bc1c410003d96fbf/Formula%201.ics",
    "f2": "https://ics.ecal.com/ecal-sub/6aa50eb99c648e00038ee83c/Formula%202.ics",
    "f3": "https://ics.ecal.com/ecal-sub/6aa50e5abc1c410003d96fb1/Formula%203.ics",
}


def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def get_summary(event):
    match = re.search(
        r"(?im)^SUMMARY(?:;[^:]*)?:(.*)$",
        event
    )
    return match.group(1).strip() if match else ""


def replace_summary(event, title):
    return re.sub(
        r"(?im)^SUMMARY(?:;[^:]*)?:.*$",
        "SUMMARY:" + title,
        event,
        count=1
    )


def f1_title(summary):
    s = summary.upper()

    if "SPRINT QUALIFYING" in s:
        return "F1 Sprint Kwalificatie"
    if "QUALIFYING" in s:
        return "F1 Kwalificatie"
    if "PRACTICE 1" in s or "FREE PRACTICE 1" in s or "FP1" in s:
        return "F1 VT1"
    if "PRACTICE 2" in s or "FREE PRACTICE 2" in s or "FP2" in s:
        return "F1 VT2"
    if "PRACTICE 3" in s or "FREE PRACTICE 3" in s or "FP3" in s:
        return "F1 VT3"
    if "SPRINT" in s:
        return "F1 Sprint"
    if "RACE" in s or "GRAND PRIX" in s:
        return "F1 Race"

    return None


def f2_title(summary):
    s = summary.upper()

    if "QUALIFYING" in s:
        return "F2 Kwalificatie"
    if "SPRINT" in s:
        return "F2 Sprint"
    if "FEATURE" in s:
        return "F2 Feature Race"
    if "PRACTICE" in s or "FREE PRACTICE" in s:
        return "F2 Practice"

    return None


def f3_title(summary):
    s = summary.upper()

    if "QUALIFYING 1" in s or "Q1" in s:
        return "F3 Q1"
    if "QUALIFYING 2" in s or "Q2" in s:
        return "F3 Q2"
    if "SPRINT" in s:
        return "F3 Sprint"
    if "FEATURE" in s:
        return "F3 Feature Race"
    if "PRACTICE" in s or "FREE PRACTICE" in s:
        return "F3 Practice"
    if "QUALIFYING" in s:
        return "F3 Kwalificatie"

    return None


def process(series, text):
    text = unfold(text)

    events = re.findall(
        r"BEGIN:VEVENT.*?END:VEVENT",
        text,
        flags=re.S
    )

    if series == "f1":
        mapper = f1_title
    elif series == "f2":
        mapper = f2_title
    else:
        mapper = f3_title

    for event in events:
        summary = get_summary(event)
        title = mapper(summary)

        if title:
            text = text.replace(
                event,
                replace_summary(event, title),
                1
            )

    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")


for series, url in SOURCES.items():
    print(f"Downloading {series}...")
    source = download(url)

    output = process(series, source)

    filename = f"{series}.ics"

    with open(filename, "w", encoding="utf-8", newline="") as file:
        file.write(output)

    print(f"Created {filename}")
