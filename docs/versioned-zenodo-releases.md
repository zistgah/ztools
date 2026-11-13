# Versioned Zenodo releases

This document records the versioned-release changes made to ztools, what they
do, and why they exist. The implementation is in `mistyx/mistyx.py` and both
copies of the seeding engine, `zseed.sh` and `zseed/zseed.sh`.

## Why this change was needed

`misty publish` creates a new Zenodo deposition. It does not create a new
version under an existing concept DOI. Using it for an update would therefore
break the intended version chain. The new `mistyx newversion` command uses
Zenodo's `actions/newversion` endpoint and verifies that the resolved published
record belongs to the requested concept before it can create a draft.

The seeding engine also needed to distinguish this workflow from a first
deposition, keep the irreversible action explicitly gated, and avoid deleting
or overwriting scratch data or a user's existing proof.

## Changes

### `mistyx/mistyx.py`

- Added `newversion`, which resolves the latest published record for the
  supplied concept DOI, checks that the metadata version is newer, creates a
  Zenodo version draft, uploads the artifact, and publishes only when `--mint`
  and the typed `MINT` confirmation are both supplied.
- Kept the default invocation read-only. The dry run performs an authenticated
  Zenodo lookup but does not create a draft or publish anything.
- Added client-side concept verification so an unrelated record cannot be
  versioned accidentally.
- Validated metadata against Zenodo's supported API fields before opening a
  draft. The ztools-specific `repository` and `programming_language` fields
  are translated to `related_identifiers` and `keywords`.
- Added `--output` for the result JSON and verified the returned version DOI
  and concept DOI so callers can check the result rather than infer success
  from a command exit alone.

### `zseed.sh` and `zseed/zseed.sh`

- Added manifest settings `doi_mode: "newversion"`, `concept_doi`, and
  `mistyx` (defaulting to `mistyx/mistyx.py`). Versioned mode fails early if
  required configuration or files are missing.
- Routed the read-only preflight and gated publish through `mistyx newversion`
  instead of `misty publish`. The new-version preflight requires
  `ZENODO_TOKEN` because it checks the actual concept and current version at
  Zenodo; the token is not printed by the workflow.
- Preserved the existing typed `MINT` gate. Before making the Zenodo
  publication request, the script stamps a private copy of the exact artifact,
  verifies that the `.ots` proof exists, and preserves it under the configured
  provenance directory. If stamping or proof preservation fails, publication
  is not attempted.
- Refuses to overwrite an existing proof sidecar. After a successful publish,
  records the returned DOI and injects it into configured placeholders.
- Names new-version proof sidecars with the artifact SHA-256, so a later
  release of the same artifact path does not collide with an earlier proof.
  First-deposit proof names retain the original convention.
- Replaced shared temporary paths with unique per-run directories under
  `.seedwork`; cleanup is limited to that run's directory. Existing
  `.seedwork` contents and `.doi-dryrun` data are left untouched.
- Kept the top-level and `zseed/` script copies in sync.

### Mock and regression tests

- Extended `mistyx/mock_zenodo.py` to model version creation, artifact upload,
  concept linkage, and whether an OpenTimestamps proof existed before the
  version request.
- Added `tests/test_mistyx_newversion.py` for dry-run safety, successful
  versioning under the same concept, metadata mapping, invalid metadata,
  unchanged versions, and refusing a mismatched concept.
- Added `tests/test_zseed_versioned_publish.py` to exercise the integrated
  seed-and-publish path and assert that proof stamping precedes publication
  and pre-existing scratch files survive cleanup.
- Added `.gitattributes` rules to keep both shell scripts LF-terminated,
  avoiding platform-dependent line-ending changes.

## Operational behavior and limits

Use `doi_mode: "newversion"` only when the project has a verified existing
concept DOI. A first deposition remains a separate workflow. Bump `version`
in `misty.json` before running the versioned preflight.

The `--publish` command is irreversible once the user types `MINT`. OpenTimestamps
proof creation is a prerequisite, but Bitcoin calendar confirmation can remain
pending after the proof is created. The proof attests the exact artifact bytes;
it does not attest the repository tree or establish authorship or correctness.

The expected tests are:

```bash
python3 -m unittest tests/test_mistyx_newversion.py
python3 -m unittest tests/test_zseed_versioned_publish.py
python3 -m unittest discover -s tests
```

These tests use a local mock Zenodo API and a mock `ots` executable. They do
not make a production Zenodo request or mint a DOI.
