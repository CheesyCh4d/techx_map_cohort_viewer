# MAP Cohort Viewer

One web page (`index.html`) that shows NWEA MAP achievement-quintile results by graduation-year cohort.
Open it in a browser and drop your CDF CSV files onto it. Everything runs in the browser; no data is uploaded or saved.

## Download
Get the latest version from the repository's **Releases** page (right-hand side of the GitHub page, or `/releases`). Under **Assets**, download **MAP-Cohort-Viewer-vX.Y.Z.html**. That one file is the whole tool. The version number also shows next to the page title and in the PDF footer.

To share it, send that file. Zip it first if your email system blocks `.html` attachments.

## Use it
1. In MAP Growth, download the Comprehensive Data File (CDF) for one or more terms.
2. Double-click `index.html` (Chrome, Edge, Firefox or Safari).
3. Drop the downloads onto the page. Any of these work, and you can mix them:
   - the `.zip` files exactly as downloaded;
   - unzipped folders;
   - `AssessmentResults.csv` and `StudentsBySchool.csv` on their own.

   Drop several years at once if you like; repeated rows are skipped. Other CSVs in the download (such as ClassAssignments) are listed as ignored.
4. Use the three settings boxes above the chart.

**Report** (what to show)
- **View:**
  - **By cohort**: one graduating class over time. Cohort starts on All cohorts.
  - **One school year**: every grade in one year.
- **Subjects** and **Terms** (Fall, Winter, Spring).
- **Compare: Off / On.** On shows From and To menus (e.g. Fall → Spring, Spring → Fall, Fall → Winter). **Same students only** (on by default) counts just the students who tested in both terms.

**Students** (who is included)
- **School**, **Ethnicity** and **Gender**. The menus list whatever values your files contain.
- Each student is counted by their details as listed for that term. In same-students comparisons, the first term counts.
- Small groups are greyed out, and the chosen group is named on charts, PDFs and exports.
- **Show students** turns on the student drill-down (see below).

**Format** (how to view or share)
- **Display: Chart / Table.**
- **Download: PDF** saves the current view straight to a PDF file: landscape, multi-page, with page numbers. The page builds the PDF itself, so it works offline.
- **Download: Summary CSV** saves counts and percentages for all cohorts (never student rows).

Elsewhere:
- **Clear data** (under the file list) removes everything loaded.
- **Auto / Light / Dark** (top right) sets the color theme.

### Seeing the students behind a bar (district staff only)
- Tick **Show students**. It's off every time the page opens.
- Click any bar segment, median circle or N. A panel slides up from the bottom of the screen, full width, listing those students: name, StudentID, school, RIT, percentile and quintile. Close it with × or Esc.
- In compare mode the panel shows both terms side by side, with the change. Its **Show** menu can filter to students who moved up, moved down or stayed in the same quintile.
- Click a column heading to sort by it.
- **Find** (under Students, shown while Show students is on) looks up one student. Type a name or StudentID (suggestions appear as you type), then click **Find** or press Enter.
  - The panel shows that student's full history: one row per term, with grade, school, and each subject's quintile, percentile and RIT.
  - **Show** narrows it to Fall, Winter or Spring only.
  - The history ignores the chart filters; it's that student's whole record in the loaded files.
- **Export student list** saves the panel's table (a group or one student's history) as a CSV after a confidentiality warning. The file name starts with `CONFIDENTIAL_`.
- Names appear only in that panel. They are never included in the PDF or the summary CSV.

To share the tool with another district, send them `index.html`. That one file is the whole tool.

## Rules it applies
- Joins the two files on StudentID + TermName.
- Uses Fall, Winter and Spring terms (e.g. "Fall 2026-2027"); Summer is skipped.
- Keeps one test per student, subject and term: the one with GrowthMeasureYN = TRUE, otherwise the latest TestStartDate.
- Cohort (graduation year) = spring year of the term + (12 - grade). K counts as 0; "K", "KG" and "0" are all read as kindergarten.
- Category = AchievementQuintile (Low, LoAvg, Avg, HiAvg, High).
- Subject comes from the Subject column, except when Course names Reading or Language Usage. Newer CDFs file both under Subject "Language Arts", so Course is used to split them into Reading, Language Usage and Reading (Spanish).
- Comparisons end on the next "To" term after the "From" term. Spring → Fall means the following fall.
- Changes are shown as median-percentile change and the change in % of students in HiAvg + High.
- Bars with fewer than 10 students are greyed out.

## Fake data for testing
```
python tools/make_fake_cdf.py              # ~1,500 students, writes sample/fake_*.csv
python tools/make_fake_cdf.py --students 3000 --seed 7
```
The script writes two overlapping exports (2019-20 to 2022-23, and 2022-23 to 2026-27). Drop all four files to test the duplicate check.
- Fall and Spring include all four subjects. Winter is Math and Reading for grades K–8 only.
- Ethnicity and gender are not linked to scores in the fake data.
- Spring 2019-20 is missing on purpose (COVID).

## Never commit real data
`.gitignore` blocks every `*.csv` except `sample/fake_*.csv`.
