# zistgah-tools — the generalized engine set

Extracted from the vgc-health / aab / fiza / zistgah-home builds, which each
hand-rolled ~80% identical seed scripts (and fiza shipped with none — the exact
failure a shared engine eliminates). © 1993–2026 Abhishek Choudhary · AyeAI ·
GPL-3.0-or-later (code) · maintain contract and context.

## zseed/ — one seed engine, per-project manifest
`zseed.sh` + a small `seed.json` per project replaces every bespoke seed script.

    bash zseed.sh                 # SAFE default: validate + offline DOI dry-run
    bash zseed.sh --push          # create/push repo (+Pages)      [typed PUSH]
    ZENODO_TOKEN=... bash zseed.sh --publish   # mint DOI, inject placeholder
                                  # everywhere, OTS-stamp          [typed MINT]
    bash zseed.sh --issues        # open backlog sprint items      [typed YES]

Manifests included: `seed.fiza.json`, `seed.aab.json`. To adopt in a project:
copy `zseed.sh` + a manifest named `seed.json` into it. Rules enforced:
in-folder scratch `./.seedwork` only (never /tmp), tokens from env, typed
confirmations, logs to `~/work/logs/`, provenance `.ots` always pushed.

**Proven by execution**: ran against the real fiza tree — and immediately caught
a real defect (fiza's artifact and CONTRACT had no DOI placeholder; now fixed).

## mistyx/ — misty-doi extensions
`mistyx.py` (stdlib-only, no deps):

**`mistyx newversion`** — TRUE version chaining. misty-doi's `publish` always
creates a fresh record; mistyx uses Zenodo's `actions/newversion` so an update
gets a new version DOI under the SAME concept DOI (proper Versions box, correct
citation graph). Dry-run by default; `--mint` + typed MINT to publish.
Client-side verification refuses to chain under a record that doesn't match the
requested id (regression-tested — the mock caught exactly this bug in v0 of the
tool).

    ZENODO_TOKEN=... python3 mistyx.py newversion \
        --concept 10.5281/zenodo.21303400 -m misty.json -f vgc-health.html          # dry-run
    ZENODO_TOKEN=... python3 mistyx.py newversion --concept 21303400 \
        -m misty.json -f vgc-health.html --mint                                     # gated mint

(Bump `"version"` in misty.json first.)

**`mistyx bib`** — retrieves ALL your deposition JSON from Zenodo (paginated,
read-only) and writes a personal bibliography:

    ZENODO_TOKEN=... python3 mistyx.py bib --out bib
    # -> bib/records.json (raw audit)  bibliography.bib  bibliography.md
    #    bibliography.html (dark navy/gold, publishable as a page)

`--public --query 'creators.name:"Choudhary, Abhishek"'` works without a token
against the public records API (published records only).

Tested end-to-end against a local mock Zenodo (`mock_zenodo.py`, fixtures from
real records): retrieval + all four outputs, dry-run inertness, gated mint under
the correct concept, abort path, and the wrong-record refusal.

## UPSTREAM.md — folding into misty-doi proper
See UPSTREAM.md for the PR plan (tracked as aab#9).

Cite: https://doi.org/10.5281/zenodo.21312769 (once minted)
