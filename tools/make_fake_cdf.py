#!/usr/bin/env python3
"""
make_fake_cdf.py - build FAKE NWEA MAP "Comprehensive Data File" (CDF) CSVs.

WHY THIS EXISTS
    We want to build and test the cohort viewer before any real student data
    arrives. This script invents a pretend school district (about 1,500
    students, grades K-12) and writes CSV files that look like a real CDF
    export. Every name, ID and score below is made up with random numbers.

HOW TO RUN (from the project folder)
    python tools/make_fake_cdf.py
    python tools/make_fake_cdf.py --students 3000 --seed 7

WHAT IT WRITES (into the sample/ folder)
    Two overlapping "exports", the way a user might download several years:
        fake_exportA_AssessmentResults.csv   Fall 2019-2020 .. Spring 2022-2023
        fake_exportA_StudentsBySchool.csv
        fake_exportB_AssessmentResults.csv   Fall 2022-2023 .. Fall 2026-2027
        fake_exportB_StudentsBySchool.csv
    The 2022-2023 school year appears in BOTH exports with identical rows,
    so the web page's duplicate-removal gets exercised.

TERMS
    Fall:   all four subjects (Math, Reading K-12; Language Usage, Science 3-8)
    Winter: Math and Reading, grades K-8 only (many districts skip HS in winter)
    Spring: all four subjects
    Winter/Spring 2026-2027 haven't happened yet, so they are not generated.

DELIBERATE "MESSY DATA" BUILT IN (so the page has to cope with it)
    * Spring 2019-2020 is missing (COVID closures); the 2020-2021 school year
      has low participation and lower scores.
    * Some students re-test in the same term (rule 3: pick one test).
    * Kindergarten is written "K" in early years and "KG" in later years.
    * About 1% of students repeat a grade, so their cohort changes.
    * DistrictName contains a comma, so CSV quoting must be handled.
    * Students enroll and leave every year; seniors graduate.

Only the Python standard library is used - nothing to install.
"""

import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings for the pretend district
# ---------------------------------------------------------------------------

FIRST_FALL = 2019          # first school year is 2019-2020
LAST_FALL = 2026           # last school year is 2026-2027 (only Fall exists yet)
DISTRICT = "Sample School District, Unit 1"   # the comma is on purpose

ELEMENTARY = ["Maple Elementary", "Cedar Elementary"]
MIDDLE = "Birch Middle School"
HIGH = "Oakridge High School"

# Real CDF exports have many columns. We include the ones the viewer needs
# plus several it does NOT need, so the page proves it finds columns by
# their header name rather than by position.
ASSESSMENT_HEADERS = [
    "TermName", "DistrictName", "SchoolName", "StudentID", "Subject", "Course",
    "NormsReferenceData", "TestType", "TestName", "TestID", "TestStartDate",
    "TestStartTime", "TestDurationMinutes", "TestRITScore", "TestStandardError",
    "TestPercentile", "AchievementQuintile", "PercentCorrect",
    "RapidGuessingPercent", "GrowthMeasureYN",
]
STUDENT_HEADERS = [
    "TermName", "DistrictName", "SchoolName", "StudentLastName",
    "StudentFirstName", "StudentMI", "StudentID", "StudentDateOfBirth",
    "StudentEthnicGroup", "StudentGender", "Grade",
]

# Subject -> (Course name, lowest grade tested, highest grade tested)
SUBJECTS = {
    "Mathematics":    ("Math K-12", 0, 12),
    "Reading":        ("Reading", 0, 12),
    "Language Usage": ("Language Usage", 3, 8),
    "Science":        ("Science K-12", 3, 8),
}

# Rough fall RIT score (mean, spread) for grades K..12. Only for realism;
# the viewer never uses RIT scores.
RIT_FALL = {
    "Mathematics": [(140, 12), (160, 13), (174, 13), (187, 13), (198, 14), (207, 15),
                    (212, 15), (217, 16), (221, 17), (224, 18), (226, 18), (228, 19), (229, 19)],
    "Reading":     [(137, 11), (156, 13), (172, 15), (186, 16), (196, 16), (204, 16),
                    (209, 15), (213, 15), (216, 15), (217, 16), (219, 16), (220, 16), (221, 16)],
}
RIT_FALL["Language Usage"] = [(m + 2, s) for m, s in RIT_FALL["Reading"]]
RIT_FALL["Science"] = [(m - 5, s - 2) for m, s in RIT_FALL["Mathematics"]]

# District-wide bump/dip per school year (in "standard deviation" units).
# Negative numbers model the post-2020 learning dip and slow recovery.
YEAR_EFFECT = {
    "Mathematics": {2019: 0.10, 2020: -0.20, 2021: -0.15, 2022: -0.05,
                    2023: 0.00, 2024: 0.05, 2025: 0.08, 2026: 0.10},
    "Reading":     {2019: 0.10, 2020: -0.10, 2021: -0.10, 2022: -0.05,
                    2023: 0.00, 2024: 0.02, 2025: 0.05, 2026: 0.06},
}
YEAR_EFFECT["Language Usage"] = YEAR_EFFECT["Reading"]
YEAR_EFFECT["Science"] = YEAR_EFFECT["Mathematics"]

# Small within-year gain relative to national norms (z-score units).
SEASON_GAIN = {"Fall": 0.0, "Winter": 0.04, "Spring": 0.08}

FIRST_NAMES = ["Avery", "Blake", "Casey", "Devon", "Emerson", "Finley", "Gray", "Harper",
               "Indy", "Jordan", "Kai", "Logan", "Morgan", "Noel", "Oakley", "Parker",
               "Quinn", "Riley", "Sawyer", "Taylor", "Umi", "Val", "Wren", "Yael", "Zion"]
LAST_NAMES = ["Alder", "Brook", "Cobalt", "Dune", "Ember", "Fern", "Glade", "Harbor",
              "Indigo", "Juniper", "Kestrel", "Lark", "Moss", "North", "Opal", "Pike",
              "Quill", "Reed", "Sage", "Thorne", "Umber", "Vale", "Wynn", "Yarrow", "Zephyr"]
ETHNIC_GROUPS = ["White", "Hispanic or Latino", "Black or African American", "Asian",
                 "Two or more races", "American Indian or Alaska Native",
                 "Native Hawaiian or Other Pacific Islander"]


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def normal_cdf(z):
    """Turn a z-score into a fraction 0..1 (the classic bell-curve lookup)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def quintile_for(percentile):
    """NWEA's achievement quintiles: Low <21, LoAvg 21-40, Avg 41-60, HiAvg 61-80, High >80."""
    if percentile <= 20:
        return "Low"
    if percentile <= 40:
        return "LoAvg"
    if percentile <= 60:
        return "Avg"
    if percentile <= 80:
        return "HiAvg"
    return "High"


def school_for(student, grade):
    if grade <= 5:
        return student.elementary
    if grade <= 8:
        return MIDDLE
    return HIGH


def grade_label(grade, fall_year):
    """Kindergarten is 'K' before 2023 and 'KG' after - messy on purpose."""
    if grade == 0:
        return "K" if fall_year < 2023 else "KG"
    return str(grade)


def us_date(d):
    """CDF dates look like 9/14/2023 (month/day/year, no leading zeros)."""
    return f"{d.month}/{d.day}/{d.year}"


def clock(rng):
    hour = rng.randint(8, 14)
    minute = rng.randint(0, 59)
    suffix = "AM" if hour < 12 else "PM"
    return f"{(hour - 1) % 12 + 1}:{minute:02d}:00 {suffix}"


# ---------------------------------------------------------------------------
# The pretend students
# ---------------------------------------------------------------------------

class Student:
    """One made-up student who ages through the district year by year."""

    def __init__(self, sid, grade, fall_year, rng, cohort_shift):
        self.sid = sid
        self.grade = grade
        self.elementary = rng.choice(ELEMENTARY)
        self.first = rng.choice(FIRST_NAMES)
        self.last = rng.choice(LAST_NAMES)
        self.mi = rng.choice("ABCDEFGHJKLMNPRSTW")
        self.gender = rng.choice(["F", "M"])
        self.ethnic = rng.choices(ETHNIC_GROUPS, weights=[50, 22, 12, 7, 6, 2, 1])[0]
        # Birthday: roughly 5 years old at the start of kindergarten.
        birth_year = fall_year - grade - 5 - (1 if rng.random() < 0.3 else 0)
        self.dob = date(birth_year, 1, 1) + timedelta(days=rng.randint(0, 364))
        # "Ability" per subject, as a z-score. A shared general part makes a
        # student's math and reading scores related, like real data.
        general = rng.gauss(0, 1)
        self.ability = {s: 0.75 * general + 0.66 * rng.gauss(0, 1) + cohort_shift
                        for s in SUBJECTS}
        # Note: ethnicity and gender are deliberately NOT linked to scores.

    def drift(self, rng):
        """Each year a student's standing wobbles a little."""
        for s in self.ability:
            self.ability[s] = 0.95 * self.ability[s] + rng.gauss(0, 0.25)


def build_district(n_students, rng):
    """
    Walk year by year from 2019 to 2026, aging students up, graduating
    seniors, and enrolling/withdrawing students. Returns a dict:
        { fall_year: [ (student, grade_that_year), ... ] }
    """
    per_grade = n_students // 13
    next_id = [100001]
    shifts = {}  # each graduating class gets its own small "personality"

    def new_student(grade, fall_year):
        grad_year = fall_year + 1 + (12 - grade)
        if grad_year not in shifts:
            shifts[grad_year] = rng.gauss(0.1, 0.15)
        s = Student(str(next_id[0]), grade, fall_year, rng, shifts[grad_year])
        next_id[0] += rng.randint(1, 3)  # gaps in IDs, like a real SIS
        return s

    roster = [new_student(g, FIRST_FALL) for g in range(13) for _ in range(per_grade)]
    years = {}
    for fall_year in range(FIRST_FALL, LAST_FALL + 1):
        if fall_year > FIRST_FALL:
            survivors = []
            for s in roster:
                if rng.random() < 0.07:      # moved away
                    continue
                if rng.random() > 0.01:      # ~1% repeat the grade
                    s.grade += 1
                if s.grade > 12:             # graduated
                    continue
                s.drift(rng)
                survivors.append(s)
            roster = survivors
            # New kindergarten class, plus a few new students in other grades.
            roster += [new_student(0, fall_year)
                       for _ in range(int(rng.gauss(per_grade, per_grade * 0.08)))]
            # About 8% new per grade roughly balances the 7% who move away.
            for g in range(1, 13):
                roster += [new_student(g, fall_year)
                           for _ in range(rng.randint(per_grade // 25, per_grade // 8))]
        years[fall_year] = [(s, s.grade) for s in roster]
    return years


# ---------------------------------------------------------------------------
# Turning students into CSV rows
# ---------------------------------------------------------------------------

def test_rows(student, grade, term, season, fall_year, rng):
    """Return 0, 1, or 2+ AssessmentResults rows for one student in one term."""
    rows = []
    for subject in SUBJECTS:
        course, low, high = SUBJECTS[subject]
        if not (low <= grade <= high):
            continue
        if season == "Winter" and (subject not in ("Mathematics", "Reading") or grade > 8):
            continue                  # winter: math & reading, K-8 only
        take_rate = 0.95
        if fall_year == 2020:         # remote / partial testing year
            take_rate = {"Fall": 0.60, "Winter": 0.75, "Spring": 0.85}[season]
        if grade >= 11:
            take_rate *= 0.55         # many high schools don't test juniors/seniors
        if rng.random() > take_rate:
            continue

        # SEASON_GAIN: in the fake district, students gain a little ground on
        # national peers as the year goes on (more so in recent years).
        z = (student.ability[subject] + YEAR_EFFECT[subject][fall_year]
             + SEASON_GAIN[season] * (1 if fall_year >= 2022 else 0.3)
             + rng.gauss(0, 0.3))
        pct = min(99, max(1, round(normal_cdf(z) * 100)))
        mean, sd = RIT_FALL[subject][grade]
        next_mean = RIT_FALL[subject][min(grade + 1, 12)][0]
        mean += {"Fall": 0, "Winter": 0.45, "Spring": 0.8}[season] * (next_mean - mean)
        rit = round(mean + z * sd)

        if season == "Fall":
            when = date(fall_year, 9, 1) + timedelta(days=rng.randint(0, 44))
        elif season == "Winter":
            when = date(fall_year, 12, 1) + timedelta(days=rng.randint(0, 50))
        else:
            when = date(fall_year + 1, 4, 15) + timedelta(days=rng.randint(0, 46))

        band = "K-2" if grade <= 2 else ("2-5" if grade <= 5 else "6+")
        short = {"Mathematics": "Math", "Reading": "Reading",
                 "Language Usage": "Language", "Science": "Science"}[subject]
        base = {
            "TermName": term,
            "DistrictName": DISTRICT,
            "SchoolName": school_for(student, grade),
            "StudentID": student.sid,
            "Subject": subject,
            "Course": course,
            "NormsReferenceData": "2020" if fall_year < 2025 else "2025",
            "TestType": "Growth",
            "TestName": f"Growth: {short} {band}",
            "TestID": str(rng.randint(10_000_000, 99_999_999)),
            "TestStartDate": us_date(when),
            "TestStartTime": clock(rng),
            "TestDurationMinutes": str(rng.randint(25, 75)),
            "TestRITScore": str(rit),
            "TestStandardError": f"{rng.uniform(2.8, 3.6):.1f}",
            "TestPercentile": str(pct),
            "AchievementQuintile": quintile_for(pct),
            "PercentCorrect": str(rng.randint(40, 70)),
            "RapidGuessingPercent": str(rng.choice([0, 0, 0, 0, 3, 5, 10])),
            "GrowthMeasureYN": "TRUE",
        }
        rows.append(base)

        # ~3%: a re-test a few days later. Only ONE of the two is the growth
        # measure (rule 3 keeps that one).
        roll = rng.random()
        if roll < 0.03:
            retest = dict(base)
            later = when + timedelta(days=rng.randint(3, 12))
            retest["TestStartDate"] = us_date(later)
            retest["TestID"] = str(rng.randint(10_000_000, 99_999_999))
            new_pct = min(99, max(1, pct + rng.randint(-12, 12)))
            retest["TestPercentile"] = str(new_pct)
            retest["AchievementQuintile"] = quintile_for(new_pct)
            if rng.random() < 0.5:
                retest["GrowthMeasureYN"] = "FALSE"
            else:
                base["GrowthMeasureYN"] = "FALSE"
            rows.append(retest)
        # ~1%: two tests and NEITHER is flagged; rule 3 then keeps the latest date.
        elif roll < 0.04:
            base["GrowthMeasureYN"] = "FALSE"
            retest = dict(base)
            retest["TestStartDate"] = us_date(when + timedelta(days=rng.randint(3, 12)))
            retest["TestID"] = str(rng.randint(10_000_000, 99_999_999))
            new_pct = min(99, max(1, pct + rng.randint(-12, 12)))
            retest["TestPercentile"] = str(new_pct)
            retest["AchievementQuintile"] = quintile_for(new_pct)
            rows.append(retest)
    return rows


def student_row(student, grade, term, fall_year):
    return {
        "TermName": term,
        "DistrictName": DISTRICT,
        "SchoolName": school_for(student, grade),
        "StudentLastName": student.last,
        "StudentFirstName": student.first,
        "StudentMI": student.mi,
        "StudentID": student.sid,
        "StudentDateOfBirth": us_date(student.dob),
        "StudentEthnicGroup": student.ethnic,
        "StudentGender": student.gender,
        "Grade": grade_label(grade, fall_year),
    }


def write_csv(path, headers, rows):
    # newline="" lets the csv module write Windows-style line endings (\r\n),
    # which is what real exports usually have.
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path}  ({len(rows):,} rows)")


def main():
    parser = argparse.ArgumentParser(description="Generate fake NWEA MAP CDF CSV files.")
    parser.add_argument("--students", type=int, default=1500, help="approximate students per year")
    parser.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same files)")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "sample"),
                        help="output folder (default: ../sample)")
    args = parser.parse_args()

    rng = random.Random(args.seed)   # seeded, so results are repeatable
    years = build_district(args.students, rng)

    # Collect rows tagged with their school year (fall_year).
    assess, students = [], []
    for fall_year, roster in years.items():
        seasons = ["Fall", "Winter", "Spring"]
        if fall_year == LAST_FALL:
            seasons = ["Fall"]                  # winter/spring 2026-27 haven't happened yet
        for season in seasons:
            if fall_year == 2019 and season == "Spring":
                continue                        # spring 2020 cancelled (COVID)
            term = f"{season} {fall_year}-{fall_year + 1}"
            for s, grade in roster:
                students.append((fall_year, student_row(s, grade, term, fall_year)))
                for row in test_rows(s, grade, term, season, fall_year, rng):
                    assess.append((fall_year, row))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Fake district: ~{args.students} students/year, seed {args.seed}")
    exports = {"A": range(2019, 2023), "B": range(2022, LAST_FALL + 1)}  # 2022 overlaps
    for name, span in exports.items():
        write_csv(out / f"fake_export{name}_AssessmentResults.csv", ASSESSMENT_HEADERS,
                  [r for y, r in assess if y in span])
        write_csv(out / f"fake_export{name}_StudentsBySchool.csv", STUDENT_HEADERS,
                  [r for y, r in students if y in span])

if __name__ == "__main__":
    main()
