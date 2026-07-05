# Kaggle submission checklist — GrantScout

Competition: [AI Agents: Intensive Vibe Coding Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project)
**Deadline: Monday, July 6, 2026 at 11:59 PM PT.** Draft (unsubmitted) writeups are NOT judged — you must click **Submit**.

## Done (in this repo)

- [x] Writeup text ready to paste: `submission/WRITEUP.md` (~1,450 words; limit is 2,500)
- [x] Cover image (required by Kaggle): `submission/screenshots/cover_image.png` (1200×675)
- [x] App screenshots for the media gallery: `submission/screenshots/01–04_*.png`
- [x] Architecture diagram (judges ask for one in video + writeup): `submission/screenshots/05_architecture.png`
- [x] Submission document with everything embedded: `submission/GrantScout_Kaggle_Submission.docx`
- [x] Tests green (39 passed), no API keys anywhere in the repo, Phase 2 changes committed
- [x] README covers problem, solution, architecture, setup — worth 20 of the 100 points

## To do (only you can do these)

1. **Push the repo to public GitHub** — there is currently **no git remote**. A public project link is mandatory.
   ```
   gh repo create grantscout --public --source . --push
   ```
   (or create the repo on github.com and `git remote add origin … && git push -u origin master`)
2. **Record the video (≤5 minutes) and publish it on YouTube** (public or unlisted). Suggested beats, matching the 10-point video rubric:
   - Problem (30s): scattered African grant data + the over-optimism trap
   - Why agents (20s)
   - Architecture (45s): show `05_architecture.png`
   - Demo (2.5 min): web UI run — form → honesty banner → the two 100%-fit-but-not-yet-eligible grants ranked last → review gate edit/reject → NOT SUBMITTED package → .docx download
   - The build (45s): **show Antigravity + agents-cli on screen** — Antigravity is a rubric concept that can ONLY be demonstrated in the video; also flash the security tests
3. **Create the Kaggle Writeup**: New Writeup on the competition page → paste `WRITEUP.md` content → set title/subtitle → **select track: Agents for Good**.
4. **Fill the two placeholders** in the writeup: YouTube link + GitHub repo link.
5. **Media gallery**: upload `cover_image.png` (set as cover), screenshots 01–05, and attach the YouTube video.
6. **Attach the project link** (the GitHub repo URL).
7. **Click Submit** (top-right) and confirm it shows as submitted — before July 6, 11:59 PM PT.

## Notes

- Rubric: Pitch 30 pts (concept 10, video 10, writeup 10) + Implementation 70 pts (technical 50, documentation 20).
- You must demonstrate ≥3 course concepts; GrantScout has ADK multi-agent, MCP server, Security, and HITL solidly in code, plus agents-cli scaffolding — put Antigravity + deployability evidence in the video.
- Deployment to a live endpoint is **not required** for judging. If you did deploy via agents-cli, add the reproduce-steps to the README and mention it in the video.
- If you attach any private Kaggle resource to the writeup, it becomes public after the deadline.
