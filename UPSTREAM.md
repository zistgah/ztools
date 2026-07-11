# Upstream plan — fold mistyx into misty-doi (aab#9)

misty-doi today: `misty publish` always creates a NEW record; no version
chaining; no record retrieval. Proposed PR to project-ilm/misty-doi:

1. `misty publish --new-version-of <id|doi>` — wraps Zenodo
   `POST /deposit/depositions/{id}/actions/newversion`; replace draft files,
   PUT metadata from misty.json (require a bumped `version`), gated publish.
   Port mistyx's resolution + MANDATORY client-side concept verification
   (refuse when the resolved record doesn't match the requested id — this
   exact bug was caught in testing and must ship with its regression test).
2. `misty bib [--out DIR] [--public --query Q]` — paginated retrieval of all
   depositions (or public records), writing records.json + BibTeX + Markdown +
   HTML. Read-only; safe.
3. `misty result` schema gains `"action": "newversion"` and keeps
   `concept_doi` mandatory, so downstream tooling (zseed) can verify chains.
4. Tests: ship mock_zenodo.py as the test double; CI runs the same four
   scenarios proven here (bib outputs, dry-run inert, correct-concept mint,
   wrong-record refusal).

Until merged, mistyx.py runs standalone beside the installed misty.
