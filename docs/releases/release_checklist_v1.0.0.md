# Release checklist: v1.0.0

Who does what: Claude prepares commits and pushes `main`; Randall makes the repo public, pushes the tag, creates the
GitHub release and handles Zenodo.

## State now

- Release commit on branch `release/v1.0.0`: the tagged 1.0.0 commit (825a295, engine, suite log and C3 checkpoint)
  plus release files only: `CITATION.cff`, `.zenodo.json`, `docs/releases/v1.0.0.md` (the release notes), this
  checklist, `pyproject.toml` version 0.1.0 → 1.0.0, and the README Cite text with its two TODOs removed. No engine,
  agent, analysis or test file changes.
- Local tag `v1.0.0` (annotated, never pushed) points at the release commit (moved from 825a295 in step 1), so
  Zenodo archives a tree with the citation metadata. Steps 0 and 1 are done; next is step 2.
- Run-cache archive (not in git): `dist/v1.0.0/bazaar-markets-v1.0.0-run-caches.tar.gz`, 79 MB, the 32 chain caches
  behind every summary up to 1.0.0, about 800 MB uncompressed, with per-file SHA-256s inside
  (`SHA256SUMS_caches.txt`). The archive's own SHA-256 is in `dist/v1.0.0/SHA256SUMS.txt`.
- History check: `main`, `origin/main` and the tag carry only the GitHub noreply address. The 46 old gmail-authored
  commits left over from the email rewrite are unreachable, so no push sends them. No key-like strings are in the
  tagged tree or in `main`.

## Steps

0. **Randall → Claude:** your name as it should appear (family name, given names), your ORCID, and the release date.
   Optionally, answers to the open questions in `runs/BASELINE_1_0_0.md` section 6 that change README wording, since
   the README is part of the tagged tree.
1. **Claude:** fill `FAMILY_NAME`, `GIVEN_NAMES`, the ORCID and `RELEASE_DATE` in `CITATION.cff` and `.zenodo.json`;
   commit on `release/v1.0.0`; move the local tag there (same annotated message); merge `release/v1.0.0` into `main`;
   push `main`. The tag stays local.
2. **Randall:** make the repository public (GitHub → Settings → General → Danger Zone → Change visibility). Zenodo's
   GitHub integration archives public repositories only.
3. **Randall:** on Zenodo, Account → GitHub (https://zenodo.org/account/settings/github/), Sync, then switch on
   `RandallSPQR/Bazaar-Markets`. This must be on before the release is published, or Zenodo does not see it.
4. **Randall:** push the tag:

       git push origin v1.0.0

5. **Randall:** create the GitHub release from the tag, with the notes file as its body:

       gh release create v1.0.0 --verify-tag --title "Bazaar Markets v1.0.0: frozen rule-based baseline" --notes-file docs/releases/v1.0.0.md

   (Or GitHub → Releases → Draft a new release → tag v1.0.0, and paste the file.)
6. **Randall:** within a few minutes Zenodo creates the software record. Check its creators, license (MIT), version
   (v1.0.0) and description. Note the version DOI and the concept DOI (the one that always resolves to the latest
   version).
7. **Randall:** the run caches, as a separate Zenodo dataset (the GitHub integration archives only the source zip, not
   release assets). Zenodo → New upload. Files: `dist/v1.0.0/bazaar-markets-v1.0.0-run-caches.tar.gz` and
   `dist/v1.0.0/SHA256SUMS.txt`. Resource type: Dataset. License: CC BY 4.0. Version: 1.0.0. Related works: "Is
   supplement to" the software version DOI from step 6. Publish. Check the upload first:

       shasum -a 256 -c dist/v1.0.0/SHA256SUMS.txt

8. **Randall → Claude:** both DOIs. **Claude:** add the DOI badge and citation to the README on `main`, and the
   `doi` and `identifiers` fields to `CITATION.cff` on `main`. The tag is not touched again.

## Done (2026-11-20)

All steps done. Tag `v1.0.0` at 33714f3; GitHub release published. Zenodo software 10.5281/zenodo.24406533 (all
versions 10.5281/zenodo.24406532); run-cache dataset 10.5281/zenodo.24406657 (CC BY 4.0, "Is supplement to" the
software DOI; both files' MD5s on Zenodo match the local archive).

## Notes

- The tag's engine is 1.0.0. `main` is already at engine 1.1.0 (Stage 3); that work is in the next release.
- If anything in steps 2–5 fails, nothing public has changed until the tag is pushed (step 4). Before then the tag
  can still move.
