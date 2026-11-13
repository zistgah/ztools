# zseed and Zenodo minting manual

This manual explains how to prepare, validate, and publish a ztools project
with `zseed.sh`. It covers both first Zenodo deposits and new versions under
an existing concept DOI. Read the relevant sections before using a publishing
flag: a Zenodo mint is permanent, and the repository push path can replace a
remote branch.

## What the tools do

- **`zseed.sh`** reads a project's `seed.json`, validates the configured
  artifact, runs release preflight checks, and optionally performs gated
  repository, Zenodo, or issue-tracker actions.
- **`misty-doi` (`misty`)** handles first Zenodo depositions.
- **`mistyx/mistyx.py`** adds `newversion` for a new deposition under an
  existing Zenodo concept DOI. `misty publish` is not a substitute: it creates
  a separate record rather than linking a new version to the existing concept.

The root `zseed.sh` and `zseed/zseed.sh` are maintained as matching copies.
Run the project-root copy with that project's manifest and release files.

## Requirements

Install and verify the tools needed for the action you intend to run:

- Python 3 for manifest parsing, validation, and `mistyx`.
- `misty-doi` (`misty`) for first deposits; the command is also used as an
  OpenTimestamps fallback if the standalone `ots` command is unavailable.
- `ots` (recommended) for OpenTimestamps proof creation.
- `gh` authenticated to the intended GitHub account only for `--push` or
  `--issues`.
- A Zenodo API token in the `ZENODO_TOKEN` environment variable for
  authenticated preflight and publishing.

Set the token in the local shell without putting its value in scripts, command
history, manifests, documentation, or logs. Do not paste it into agent chat.
The publishing client must send it to Zenodo over HTTPS for API
authentication. Never print it to verify that it is set; check only whether
the variable exists.

## Project manifest

Each project uses a `seed.json` alongside the seed script. The ztools manifest
uses these fields:

| Field | Purpose |
| --- | --- |
| `name` | Human-readable project name used in logs. |
| `repo` | Canonical GitHub `owner/repository` target. |
| `site` | Optional project URL reported after a push. |
| `artifact` | Exact file whose bytes are deposited and timestamped. |
| `doi_placeholder` | Literal string to replace with the returned version DOI. |
| `inject_into` | Project files in which that placeholder should be replaced. |
| `push_files` | Allowlisted files copied to the seeded GitHub repository. |
| `provenance_dir` | Directory in which the artifact's `.ots` proof is stored. |
| `backlog` | Markdown backlog used by `--issues`. |
| `pages` | Whether the push flow should configure GitHub Pages. |
| `doi_mode` | Optional: `new` (default) for a first deposit, or `newversion`. |
| `concept_doi` | Required for `newversion`; the existing concept DOI, not a
  version DOI. |
| `mistyx` | Optional path to `mistyx.py`; defaults to
  `mistyx/mistyx.py`. |

Keep the manifest, `misty.json`, artifact, and citation metadata consistent.
Before publishing, check that the artifact exists, the expected placeholder
actually appears in every intended injection target, and the `misty.json`
version matches the release being prepared.

## Safe preflight

Start from the project root and inspect the manifest and repository state:

```bash
git status --short
cat seed.json
cat misty.json
bash zseed.sh
```

The no-flag invocation validates the artifact and metadata and runs a
read-only DOI preflight. In `new` mode it uses `misty validate` and
`misty publish --dry-run` when available. In `newversion` mode it uses
`mistyx newversion` to query Zenodo and verify the requested concept and
version. That check is read-only, but it is authenticated and therefore needs
`ZENODO_TOKEN`.

Do not treat a successful local validation as proof that a DOI is new or that
the intended concept was selected. Check Zenodo's returned record and concept
DOIs. If the DOI already exists, do not run the first-deposit workflow again.

## First deposition

Use this only when the project has no existing Zenodo record or concept DOI:

1. Complete `misty.json` with verified title, creators, version, description,
   license, access rights, and related identifiers.
2. Set `doi_mode` to `new` or leave it out; this is the default.
3. Configure the artifact and a placeholder in each intended citation/display
   target.
4. Run `bash zseed.sh` and resolve all validation warnings.
5. Confirm the production destination and exact artifact checksum.
6. When ready to publish, run:

   ```bash
   bash zseed.sh --publish
   ```

7. Review the displayed project and artifact details. Type `MINT` only if you
   authorize the irreversible production deposition.
8. Verify the resulting version DOI and concept DOI in the command output and
   Zenodo. The script writes `ZENODO_DOI.txt` and injects the returned version
   DOI into configured files.

If publishing fails, inspect the run log and Zenodo before retrying. Do not
assume a network timeout means the deposition did not succeed.

## New version under an existing concept DOI

Use this when the project already has a Zenodo record:

1. Find the **concept DOI** for the existing record in Zenodo. Do not pass a
   version DOI where the concept DOI is required.
2. Set `doi_mode` to `newversion`, set `concept_doi` to that verified concept
   DOI, and confirm the `mistyx` path.
3. Bump `misty.json`'s version above the latest published version. Update
   `CITATION.cff`'s version and release date as appropriate.
4. Keep the release DOI placeholder in citation/display files so the new
   version DOI can be injected after publication.
5. Run `bash zseed.sh` to verify the concept and version against Zenodo. Fix
   any mismatch before continuing.
6. Run `bash zseed.sh --publish`, review the details, and type `MINT` only
   after confirming the intended concept and version.
7. Verify the new version DOI and ensure the concept DOI remains unchanged.

`mistyx newversion` validates API metadata before opening a draft, maps
`repository` to Zenodo `related_identifiers` and `programming_language` to
`keywords`, requires a bumped version, uploads the configured artifact, and
checks the published response. Its result JSON is written into the run's
private scratch directory.

## OpenTimestamps and artifact provenance

Before calling Zenodo to publish, `zseed.sh --publish` stamps a private copy of
the configured artifact. It refuses to overwrite an existing
`provenance/<artifact>.ots` proof. It verifies that the proof was created and
preserved before proceeding to publication; if stamping fails, publication is
not attempted.

An OTS proof commits to the exact artifact bytes. It does not attest every
file in the Git repository, establish authorship, or prove that the contents
are correct. Bitcoin calendar confirmation may remain pending after the proof
is created. Preserve the artifact alongside its proof so the hash can be
checked later.

## GitHub push and issue actions

`--push` and `--issues` are independent from a Zenodo mint:

- `bash zseed.sh --push` requires GitHub CLI authentication and a typed
  `PUSH`. It creates a temporary repository from the manifest allowlist and
  publishes to `repo`. **For an existing repository, the current script uses
  `git push --force` to `main`.** Review the script, destination, allowlist,
  and remote state before choosing this action; the confirmation prompt does
  not make a force-push non-destructive.
- `bash zseed.sh --issues` requires a backlog, an existing GitHub repository,
  and typed `YES`.
- `bash zseed.sh --all` runs push and publish in sequence. It is not a
  substitute for separately reviewing both actions. A push made before
  minting will not contain the injected DOI or new proof; the script reminds
  the operator to push the updated files afterward.

The publish action alone does not push DOI-injected files to GitHub. Review,
commit, and push those changes through the project's normal Git workflow.

## Scratch files, logs, and failures

Logs are written under `~/work/logs/`. A unique per-run working directory is
created under `.seedwork/zseed-<timestamp>-<pid>` and removed on exit. Cleanup
is limited to that run's directory; existing `.seedwork` contents and the
legacy `.doi-dryrun` directory are not deleted. Do not put credentials in
these directories.

Common preflight failures:

- **Missing `ZENODO_TOKEN`:** set it in the current shell; do not store it in
  the manifest.
- **Concept mismatch:** re-check the concept DOI in Zenodo; never bypass the
  client-side verification.
- **Version not bumped:** update release metadata to a new version before
  retrying.
- **Missing placeholder:** correct the `doi_placeholder` or injection target
  before minting; otherwise publication can succeed while displayed citation
  metadata remains stale.
- **OTS failure:** publication is deliberately blocked. Resolve the timestamp
  tool/network issue and rerun after checking whether a proof or deposition
  already exists.
- **Timeout after publish:** query Zenodo for the record before retrying to
  avoid duplicate first deposits.

## Tests

Run the focused local regression suite before changing release behavior:

```bash
python3 -m unittest tests/test_mistyx_newversion.py
python3 -m unittest tests/test_zseed_versioned_publish.py
python3 -m unittest discover -s tests
bash -n zseed.sh zseed/zseed.sh
```

The tests use a local mock Zenodo API and a mock timestamp executable. They do
not publish to production or mint a DOI.
