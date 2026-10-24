# What to do on your computer (about 10 minutes)

The organisation and repo already exist: https://github.com/SE-498-515-534-911/SE_498_515_534_911

I could not log in to GitHub from here, so nothing has been pushed. Everything is ready for you to push.

## 0. Check you can push
Open the repo link. You should see a **Code** button and be listed under the organisation's members (or as a collaborator). If GitHub says you only have read access, ask Soumya (owner) to open **Settings -> Collaborators and teams** (or the organisation's **People** page) and give you **Write** access. Without it, no push or branch can reach GitHub.

## 1. Get the repo on your computer (skip if you have it)
Open **Git Bash** (Windows) in the folder where you keep projects:
```
git clone https://github.com/SE-498-515-534-911/SE_498_515_534_911.git
cd SE_498_515_534_911
git config user.name "Varnika Sadineni"
git config user.email "sadinenivarnika@gmail.com"
```
Unzip this package somewhere, for example `C:\Users\you\member2_user_stories`.

## 2. Create all 9 branches locally
Inside the repo folder:
```
bash /c/Users/you/member2_user_stories/create_branches.sh
git branch
```
You will see the 9 `feature/us-..` branches on your computer only. Each commit is authored by you. Check one: `git log --oneline feature/us-08-background-training`.

## 3. Push them to GitHub
```
bash /c/Users/you/member2_user_stories/create_branches.sh --push
```
(Branches that already exist are skipped, so run it with `--push` only if you did not already push. To push existing ones: `git push -u origin --all`.)

## 4. Open the pull requests, one at a time, in order
For each branch in the order of `PR_DESCRIPTIONS.md` (US-06, 07, 08, 11, 20, 21, 39, 28, 30):
1. On GitHub choose **Compare & pull request**, base `main`, compare = the branch.
2. Paste the matching text from `PR_DESCRIPTIONS.md`.
3. Ask the repo owner to review and merge. Open the next PR only after the previous one is merged (the branches build on each other).

Course rule: the assigned member raises the PR and the repo owner reviews and merges. Do not merge your own.

## 5. GitHub Project and Actions
- The workflow `.github/workflows/member2-tests.yml` arrives with the last branch; once merged, the **Actions** tab runs my tests on every PR touching my folders.
- Move your 9 cards to **Done** in the GitHub Project after each merge. `SE_Mini_Project_Backlog_Varnika_updated.xlsx` shows the same in the spreadsheet.

## If `git am` reports a conflict
Tell me the message. It means someone already added a file with the same path as one of mine (for example a `training/` folder).
