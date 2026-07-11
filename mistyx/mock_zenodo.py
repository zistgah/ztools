#!/usr/bin/env python3
"""Mock Zenodo API for testing mistyx locally. Fixtures mirror real records."""
import json, re, sys
from http.server import HTTPServer, BaseHTTPRequestHandler

DEPS = {
 101: {"id":101,"doi":"10.5281/zenodo.21264248","conceptdoi":"10.5281/zenodo.21264247","submitted":True,
   "links":{"html":"https://zenodo.org/record/21264248"},
   "metadata":{"title":"Verification-Gated Human-AI Co-Development: A Methodology and Cost Analysis",
     "upload_type":"publication","publication_date":"2026-06-20","version":"1.0.0",
     "creators":[{"name":"Choudhary, Abhishek","affiliation":"AyeAI, Hyderabad, India"}]}},
 102: {"id":102,"doi":"10.5281/zenodo.21303401","conceptdoi":"10.5281/zenodo.21303400","submitted":True,
   "links":{"html":"https://zenodo.org/record/21303401"},
   "metadata":{"title":"VGC-Health: A Verification-Gated Clinical Co-Development Manifold - A Research Proposal",
     "upload_type":"publication","publication_date":"2026-07-11","version":"1.0.0",
     "creators":[{"name":"Choudhary, Abhishek","affiliation":"AyeAI, Hyderabad, India"}]}},
 103: {"id":103,"doi":"10.5281/zenodo.20719388","conceptdoi":"10.5281/zenodo.20719387","submitted":True,
   "links":{"html":"https://zenodo.org/record/20719388"},
   "metadata":{"title":"misty-doi: one canonical record in, many outputs out",
     "upload_type":"software","publication_date":"2026-04-30","version":"1.0.1",
     "creators":[{"name":"Choudhary, Abhishek","affiliation":"AyeAI, Hyderabad, India"}]}},
}
STATE = {"draft": None, "published_new": None, "files": []}

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _j(self, code, obj):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p=self.path.split("?")[0]
        if p=="/api/deposit/depositions":
            q=self.path
            page=int(re.search(r"page=(\d+)",q).group(1)) if "page=" in q else 1
            items=list(DEPS.values()) if page==1 else []
            m=re.search(r"conceptrecid(?::|%3A)(\d+)",q)
            if m:
                cid=m.group(1)
                items=[d for d in items if cid in ((d.get("doi") or "")+" "+(d.get("conceptdoi") or ""))]
            self._j(200, items)
        elif re.match(r"^/api/deposit/depositions/\d+$",p):
            rid=int(p.rsplit("/",1)[1])
            if rid in DEPS: self._j(200,DEPS[rid])
            elif STATE["draft"] and rid==STATE["draft"]["id"]: self._j(200,STATE["draft"])
            else: self._j(404,{"message":"not found"})
        else: self._j(404,{"message":"nf "+p})
    def do_POST(self):
        p=self.path.split("?")[0]
        if re.match(r"^/api/deposit/depositions/\d+/actions/newversion$",p):
            base=DEPS[int(p.split("/")[4])]
            STATE["draft"]={"id":201,"submitted":False,"conceptdoi":base["conceptdoi"],
              "metadata":dict(base["metadata"]),
              "files":[{"id":"oldf1","filename":"old.html"}],
              "links":{"latest_draft":"http://%s/api/deposit/depositions/201"%self.headers["Host"],
                       "bucket":"http://%s/api/files/bucket201"%self.headers["Host"]}}
            self._j(201,{"links":STATE["draft"]["links"]})
        elif p=="/api/deposit/depositions/201/actions/publish":
            d=STATE["draft"]; ver=d["metadata"].get("version","?")
            STATE["published_new"]={"id":201,"doi":"10.5281/zenodo.21309999","conceptdoi":d["conceptdoi"],
              "metadata":d["metadata"],"files":STATE["files"]}
            self._j(202,STATE["published_new"])
        else: self._j(404,{"message":"nf "+p})
    def do_PUT(self):
        p=self.path.split("?")[0]
        if p=="/api/deposit/depositions/201":
            ln=int(self.headers.get("Content-Length",0)); body=json.loads(self.rfile.read(ln))
            STATE["draft"]["metadata"]=body.get("metadata",{}); self._j(200,STATE["draft"])
        elif p.startswith("/api/files/bucket201/"):
            ln=int(self.headers.get("Content-Length",0)); blob=self.rfile.read(ln)
            fn=p.rsplit("/",1)[1]; STATE["files"]=[{"filename":fn,"size":len(blob)}]
            self._j(201,{"key":fn,"size":len(blob)})
        else: self._j(404,{"message":"nf "+p})
    def do_DELETE(self):
        if re.match(r"^/api/deposit/depositions/201/files/",self.path.split("?")[0]):
            STATE["draft"]["files"]=[]; self._j(204,{})
        else: self._j(404,{"message":"nf"})

if __name__=="__main__":
    port=int(sys.argv[1]); HTTPServer(("127.0.0.1",port),H).serve_forever()
