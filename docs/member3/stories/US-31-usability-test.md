# US-31: Usability test

| | |
| --- | --- |
| Epic | WBMME-5 Testing & Validation |
| Requirement | MLE-NF-005 (usable by a first-time user without training); SAD 4.5.5 usability target |
| Points / sprint | 3 / Sprint 2 |
| Owner | Tejas (Member 3) |

**Story.** As a Student, I want to finish the main task without help, so that the product is easy to use.

## Acceptance criteria

- [x] Five first-time users: at least four log in, upload, train and view metrics within 10 minutes. **Result: 5 of 5**, in 3 to 7 minutes.
- [x] Nobody needed help: no tester asked for help and no hint was given.
- [x] The version tested and the method are recorded so the test can be repeated.

## Result

| Tester | Time | Within 10 minutes | Asked for help | Ease rating (1 to 5) |
| --- | --- | --- | --- | --- |
| T1 | 5 min | Yes | No | 4 |
| T2 | 3 min | Yes | No | 4 |
| T3 | 7 min | Yes | No | 5 |
| T4 | 6 min | Yes | No | 4 |
| T5 | 5 min | Yes | No | 3 |

All five finished within the limit (average 5.2 minutes, median 5, slowest 7). The average ease rating was 4.0, and the lowest was 3.

## Method

- **Testers:** five people who had never used WBMME, recruited by the observer. They are not a random sample.
- **Setup:** one laptop and one browser for everyone. Each tester used their own Student account (`tester1` to `tester5`) on a separate test database, so the data of one tester never showed up for the next.
- **Task given to everyone:** log in with the details on the card, upload `iris.csv`, train any model to predict the column `species`, and look at the results.
- **Timing:** by stopwatch, from "go" until the tester had opened the results, read them and logged out. This includes reading and logging out, so the times are on the long side.
- **Help:** the observer gave no hints. A request for help would have counted as not finishing unaided; there were none.
- **Rating:** after the task each tester rated how easy it was, from 1 (hard) to 5 (easy). The ratings were given in tester order.
- **Version tested:** the code at commit `ea73ad6` (head of pull request #113 at the time of the test).

## Where testers hesitated

After uploading a dataset, some testers had to work out how to continue to training. Everyone found it without help. Tester 5, who gave the lowest rating (3), suggested a "continue to training" button on the Datasets page, and a way to download a preprocessed copy of a dataset.

## Pilot before the test

Three people tried an earlier version first. They are not counted among the five above. Their feedback led to these changes before the formal test (pull request #113):

- The **Preview** button on the Datasets page did nothing (the data it read was not valid JSON).
- The **Models page** refused a maximum depth of 5, because the number was sent as text.
- The **Training page** never showed that training was done and had no way to the results. It now says "Training done: click to view results".
- The **Models page** repeated what the Training page already offers, so its sidebar link was removed.
- The **Preprocess panel** on the Datasets page only showed a preview that nothing used, so it was removed.
- The dashboard still said "Planned" for pages that exist, and some decorative symbols were removed.

## What came out of the test

| Change | Where |
| --- | --- |
| A **Train** button on each saved dataset that opens Training with that dataset selected (tester 5's suggestion) | pull request #113 |
| **US-42: Download a prepared dataset** (also tester 5's suggestion), so the Datasets page has a use after the Preprocess panel was removed | issue #114, pull request #115 |

## Limits

- Five testers is a small sample, and they were not chosen at random.
- One laptop and one browser, with timings by stopwatch from a single observer.
- The three pilot testers used an earlier version, so only the five testers above count towards the result.

## How to repeat the test

Use a separate database, so test data stays away from normal data. In PowerShell, in the project folder:

```powershell
$env:DB_PATH="C:\temp\usability\db.sqlite3"
$env:DATA_ROOT="C:\temp\usability\data"
$env:MODEL_ARTIFACT_ROOT="C:\temp\usability\models"
python manage.py migrate
python manage.py shell -c "from django.contrib.auth import get_user_model as g; [g().objects.create_user(f'tester{i}', f'tester{i}@example.com', f'Test-pass-{i}9') for i in range(1, 6)]"
python manage.py runserver
```

Open `http://127.0.0.1:8000/accounts/login/`. The sample file was the iris data (150 rows; four measurements and the class `species`) saved as `iris.csv`. Give each tester one account, read the same task to everyone, and time them as described above.
