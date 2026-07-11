#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mistyx — extensions to misty-doi.                       v0.1.0

Two capabilities misty-doi lacks today:

  1) TRUE VERSION UPDATES.  `misty publish` always creates a brand-new record;
     it never chains versions under a concept DOI.  `mistyx newversion` uses
     Zenodo's  POST /deposit/depositions/{id}/actions/newversion  to mint a
     real new version of an EXISTING record: same concept DOI, new version DOI,
     "Versions" box on the record page, correct citation graph.

  2) PERSONAL BIBLIOGRAPHY.  `mistyx bib` retrieves ALL your deposition JSON
     from Zenodo (paginated) and writes:
        records.json        raw retrieval (audit trail)
        bibliography.bib    BibTeX
        bibliography.md     Markdown
        bibliography.html   a styled, citable HTML page (dark navy/gold)

Safety (standing engineering rules):
  * newversion is DRY-RUN BY DEFAULT; the real mint needs --mint AND a typed
    MINT confirmation.  bib is read-only (GET only) — safe.
  * ZENODO_TOKEN from the environment only; never stored, never printed.
  * All writes stay inside the working directory.  No /tmp.
  * --api-base overrides the endpoint (sandbox or a local mock for testing).

Usage:
  mistyx newversion --concept 21303400 -m misty.json -f artifact.html
  mistyx newversion --concept 10.5281/zenodo.21303400 -m misty.json -f a.html --mint
  mistyx bib [--out bib] [--mine-only] [--api-base URL]

Upstream plan: both commands are written to fold into misty-doi as
`misty publish --new-version-of <id>` and `misty bib` (tracked as aab#9).

© 1993-2026 Abhishek Choudhary. All rights reserved. GPL-3.0-or-later.
"""
import argparse, json, os, sys, time
import urllib.request, urllib.parse, urllib.error

API_DEFAULT = "https://zenodo.org/api"

# ---------------------------------------------------------------- helpers
def log(msg): print("  " + msg)
def die(msg): print("FATAL: " + msg, file=sys.stderr); sys.exit(1)

def token(required=True):
    t = os.environ.get("ZENODO_TOKEN", "")
    if required and not t:
        die("ZENODO_TOKEN not set in environment")
    return t

class Zen:
    """Minimal Zenodo API client (urllib only, no deps)."""
    def __init__(self, base, tok):
        self.base = base.rstrip("/"); self.tok = tok
    def _req(self, method, path, body=None, raw=None, ctype="application/json"):
        url = path if path.startswith("http") else self.base + path
        sep = "&" if "?" in url else "?"
        if self.tok: url = url + sep + "access_token=" + urllib.parse.quote(self.tok)
        data = None
        if raw is not None: data = raw
        elif body is not None: data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None: req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = r.read().decode() or "{}"
                return r.status, json.loads(txt)
        except urllib.error.HTTPError as e:
            try: detail = json.loads(e.read().decode())
            except Exception: detail = {"message": str(e)}
            return e.code, detail
    def get(self, p):            return self._req("GET", p)
    def post(self, p, body=None):return self._req("POST", p, body=body)
    def put(self, p, body):      return self._req("PUT", p, body=body)
    def delete(self, p):         return self._req("DELETE", p)
    def upload(self, bucket, fname, blob):
        return self._req("PUT", bucket.rstrip("/") + "/" + urllib.parse.quote(fname),
                         raw=blob, ctype="application/octet-stream")

def concept_id(s):
    """Accept a bare id, a DOI, or a DOI URL; return the numeric id string."""
    s = s.strip()
    for pre in ("https://doi.org/", "doi:", "10.5281/zenodo."):
        if pre in s: s = s.split("zenodo.")[-1]
    return s.split("/")[-1]

# ---------------------------------------------------------------- newversion
def cmd_newversion(a):
    tok = token()
    z = Zen(a.api_base, tok)
    cid = concept_id(a.concept)
    meta = json.load(open(a.metadata)) if a.metadata else None
    blob = open(a.file, "rb").read()
    import hashlib
    sha = hashlib.sha256(blob).hexdigest()
    log(f"concept/record id: {cid}")
    log(f"artifact: {a.file} ({len(blob)} bytes, sha256 {sha[:16]}…)")

    # 1. resolve the latest published deposition for this concept.
    #    HARD RULE: never trust server-side filtering alone — verify client-side
    #    that the resolved record actually belongs to the requested id, else die.
    def matches(d):
        tails = {str(d.get("id", "")),
                 (d.get("doi") or "").rsplit(".", 1)[-1],
                 (d.get("conceptdoi") or "").rsplit(".", 1)[-1],
                 str(d.get("conceptrecid", ""))}
        return cid in tails
    code, rec = z.get(f"/deposit/depositions/{cid}")
    if code == 200 and not matches(rec):
        die(f"resolved record {rec.get('id')} does not match requested id {cid} — refusing")
    if code == 404:
        code, lst = z.get(f"/deposit/depositions?q=conceptrecid:{cid}&size=100")
        if code != 200: die(f"could not search for concept {cid} [{code}]")
        pub = [d for d in (lst if isinstance(lst, list) else []) if d.get("submitted") and matches(d)]
        if not pub: die(f"no published record matching {cid} found (client-side verified) — refusing to guess")
        rec = sorted(pub, key=lambda d: d.get("id", 0))[-1]
    elif code != 200:
        die(f"lookup failed [{code}]: {rec}")
    dep_id = rec["id"]
    old_doi = (rec.get("doi") or rec.get("metadata", {}).get("prereserve_doi", {}).get("doi", "?"))
    log(f"latest published version: deposition {dep_id} (doi {old_doi})")

    if not a.mint:
        log("")
        log("DRY-RUN (default). Would now:")
        log(f"  1. POST /deposit/depositions/{dep_id}/actions/newversion")
        log(f"  2. on the new draft: replace files with {a.file}")
        log(f"  3. PUT updated metadata" + (f" from {a.metadata}" if a.metadata else " (carried over)"))
        log(f"  4. POST actions/publish  -> new version DOI under the same concept")
        log("Re-run with --mint to perform it (typed MINT confirmation required).")
        return 0

    print("  " + "=" * 58)
    print("   NEW VERSION on PRODUCTION — same concept DOI, new version DOI")
    print(f"   base record: {old_doi}   new artifact sha256: {sha[:16]}…")
    print("   This is IRREVERSIBLE once published.")
    print("  " + "=" * 58)
    if input("  Type MINT to proceed: ").strip() != "MINT":
        log("aborted — nothing changed"); return 0

    code, nv = z.post(f"/deposit/depositions/{dep_id}/actions/newversion")
    if code not in (200, 201): die(f"newversion failed [{code}]: {nv}")
    draft_url = nv.get("links", {}).get("latest_draft")
    if not draft_url: die("no latest_draft link returned")
    code, draft = z.get(draft_url)
    if code != 200: die(f"draft fetch failed [{code}]")
    did = draft["id"]; log(f"new draft deposition: {did}")

    # replace files: delete carried-over ones, upload the new artifact
    for f in draft.get("files", []):
        z.delete(f"/deposit/depositions/{did}/files/{f['id']}")
    bucket = draft.get("links", {}).get("bucket")
    if bucket:
        code, up = z.upload(bucket, os.path.basename(a.file), blob)
    else:
        code, up = z._req("POST", f"/deposit/depositions/{did}/files",
                          raw=blob, ctype="application/octet-stream")
    if code not in (200, 201): die(f"upload failed [{code}]: {up}")
    log(f"uploaded {os.path.basename(a.file)}")

    if meta:
        md = dict(meta)
        code, r = z.put(f"/deposit/depositions/{did}", {"metadata": md})
        if code != 200: die(f"metadata update failed [{code}]: {r}")
        log("metadata updated (version " + str(md.get("version", "?")) + ")")

    code, pub = z.post(f"/deposit/depositions/{did}/actions/publish")
    if code not in (200, 201, 202): die(f"publish failed [{code}]: {pub}")
    new_doi = pub.get("doi") or pub.get("metadata", {}).get("doi", "?")
    concept = pub.get("conceptdoi", "?")
    log(f"PUBLISHED new version: doi {new_doi}  (concept {concept})")
    json.dump({"tool": "mistyx", "action": "newversion", "doi": new_doi,
               "concept_doi": concept, "deposition_id": pub.get("id"),
               "sha256": sha, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              open("mistyx_result.json", "w"), indent=2)
    log("wrote mistyx_result.json")
    return 0

# ---------------------------------------------------------------- bib
BIB_TYPE = {"publication": "article", "software": "software", "dataset": "misc",
            "presentation": "misc", "poster": "misc", "image": "misc"}

def bib_key(md, rid):
    yr = (md.get("publication_date", "") or "")[:4] or "nd"
    fam = "anon"
    cs = md.get("creators", [])
    if cs: fam = cs[0].get("name", "anon").split(",")[0].strip().lower().replace(" ", "")
    w = "".join(c for c in (md.get("title", "") or "x") if c.isalnum())[:12].lower()
    return f"{fam}{yr}{w}_{rid}"

def esc_tex(s): return s.replace("&", r"\&").replace("_", r"\_").replace("#", r"\#")
def esc_html(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def cmd_bib(a):
    tok = token(required=not a.public)
    z = Zen(a.api_base, tok)
    recs, page = [], 1
    while True:
        path = (f"/deposit/depositions?status=published&size=25&page={page}"
                if not a.public else
                f"/records?q={urllib.parse.quote(a.query or '')}&size=25&page={page}")
        code, batch = z.get(path)
        if code != 200: die(f"retrieval failed [{code}]: {batch}")
        items = batch if isinstance(batch, list) else batch.get("hits", {}).get("hits", [])
        if not items: break
        recs.extend(items); page += 1
        if page > 40: log("stopping at 1000 records"); break
    if not recs: die("no records retrieved")
    log(f"retrieved {len(recs)} records")

    os.makedirs(a.out, exist_ok=True)
    json.dump(recs, open(os.path.join(a.out, "records.json"), "w"), indent=2)

    entries = []
    for r in recs:
        md = r.get("metadata", {})
        doi = r.get("doi") or md.get("doi") or ""
        cdoi = r.get("conceptdoi") or md.get("conceptdoi") or ""
        entries.append({
            "id": r.get("id"), "doi": doi, "concept": cdoi,
            "title": md.get("title", "(untitled)"),
            "date": md.get("publication_date", ""), "version": md.get("version", ""),
            "type": md.get("upload_type", "publication"),
            "creators": [c.get("name", "") for c in md.get("creators", [])],
            "url": (r.get("links", {}) or {}).get("html", f"https://doi.org/{doi}" if doi else ""),
            "desc": (md.get("description", "") or "").strip(),
        })
    entries.sort(key=lambda e: e["date"], reverse=True)

    # BibTeX
    with open(os.path.join(a.out, "bibliography.bib"), "w") as f:
        for e in entries:
            bt = BIB_TYPE.get(e["type"], "misc")
            auth = " and ".join(e["creators"]) or "Unknown"
            f.write(f"@{bt}{{{bib_key({'publication_date':e['date'],'creators':[{'name':c} for c in e['creators']],'title':e['title']}, e['id'])},\n")
            f.write(f"  author  = {{{esc_tex(auth)}}},\n")
            f.write(f"  title   = {{{esc_tex(e['title'])}}},\n")
            if e["date"]: f.write(f"  year    = {{{e['date'][:4]}}},\n")
            if e["version"]: f.write(f"  version = {{{e['version']}}},\n")
            f.write(f"  doi     = {{{e['doi']}}},\n  publisher = {{Zenodo}},\n  url     = {{https://doi.org/{e['doi']}}}\n}}\n\n")

    # Markdown
    with open(os.path.join(a.out, "bibliography.md"), "w") as f:
        f.write("# Personal Bibliography — Zenodo records\n\n")
        f.write(f"_{len(entries)} records · generated by mistyx bib · "
                + time.strftime("%Y-%m-%d") + "_\n\n")
        for e in entries:
            f.write(f"- **{e['title']}**"
                    + (f" (v{e['version']})" if e["version"] else "")
                    + (f" · {e['date']}" if e["date"] else "")
                    + f" · [doi:{e['doi']}](https://doi.org/{e['doi']})"
                    + (f" · concept [{e['concept']}](https://doi.org/{e['concept']})" if e["concept"] else "")
                    + "\n")

    # HTML (house style)
    rows = ""
    for e in entries:
        rows += ('<div class="rec"><div class="t">' + esc_html(e["title"])
                 + (f' <span class="v">v{esc_html(str(e["version"]))}</span>' if e["version"] else "")
                 + '</div><div class="m">'
                 + esc_html("; ".join(e["creators"])) + (" · " + esc_html(e["date"]) if e["date"] else "")
                 + f' · <a href="https://doi.org/{e["doi"]}">doi:{esc_html(e["doi"])}</a>'
                 + (f' · <span class="c">concept <a href="https://doi.org/{e["concept"]}">{esc_html(e["concept"])}</a></span>' if e["concept"] else "")
                 + "</div></div>\n")
    html = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Personal Bibliography</title><style>"
            "body{margin:0;background:#0a0e27;color:#e7ebf7;font-family:Georgia,serif;font-size:17px;line-height:1.55}"
            ".w{max-width:820px;margin:0 auto;padding:2.5rem 20px 4rem}"
            "h1{font-size:1.7rem;color:#f2f4fb}.sub{color:#b9c6ea;font-style:italic}"
            "a{color:#d4a843;text-decoration:none;border-bottom:1px solid rgba(212,168,67,.3)}"
            ".rec{border:1px solid #28305a;background:#141a3a;border-radius:8px;padding:.7rem .9rem;margin:.6rem 0}"
            ".t{font-weight:600;color:#eaeefb}.v{font-family:monospace;font-size:.7rem;color:#d4a843}"
            ".m{font-size:.8rem;color:#aeb8d8;margin-top:.15rem}.c{color:#828cb2}"
            "footer{color:#828cb2;font-size:.78rem;border-top:1px solid #28305a;margin-top:1.6rem;padding-top:1rem}"
            "</style></head><body><div class=\"w\">"
            "<h1>Personal Bibliography</h1>"
            f"<p class=\"sub\">{len(entries)} Zenodo records · generated by mistyx bib · "
            + time.strftime("%Y-%m-%d") + "</p>" + rows +
            "<footer>© Abhishek Choudhary · AyeAI · generated locally from the Zenodo API; "
            "records.json holds the raw retrieval for audit.</footer>"
            "</div></body></html>")
    open(os.path.join(a.out, "bibliography.html"), "w").write(html)
    log(f"wrote {a.out}/records.json, bibliography.bib, bibliography.md, bibliography.html")
    return 0

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="mistyx", description="misty-doi extensions: true version chaining + personal bibliography")
    ap.add_argument("--api-base", default=API_DEFAULT, help="Zenodo API base (sandbox/mock for testing)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    nv = sub.add_parser("newversion", help="mint a NEW VERSION of an existing record (same concept DOI)")
    nv.add_argument("--concept", required=True, help="record/concept id or DOI (e.g. 21303400 or 10.5281/zenodo.21303400)")
    nv.add_argument("-m", "--metadata", help="misty.json with the updated metadata (bump 'version'!)")
    nv.add_argument("-f", "--file", required=True, help="the new artifact")
    nv.add_argument("--mint", action="store_true", help="actually publish (default is dry-run)")
    nv.set_defaults(fn=cmd_newversion)

    bb = sub.add_parser("bib", help="retrieve all your DOI records and build a bibliography")
    bb.add_argument("--out", default="bib", help="output directory (default ./bib)")
    bb.add_argument("--public", action="store_true", help="use the public /records search instead of your depositions (no token)")
    bb.add_argument("--query", default="", help="query for --public mode (e.g. creators.name:\"Choudhary, Abhishek\")")
    bb.set_defaults(fn=cmd_bib)

    a = ap.parse_args()
    sys.exit(a.fn(a))

if __name__ == "__main__":
    main()
