import os,sys,time,json,hashlib,socket,traceback,zipfile,io
D="/tmp/mdpilot/corpus"; os.makedirs(D,exist_ok=True)
# ---- corpus (synthetic, generated here; no real data) ----
import docx, pptx, openpyxl
from ebooklib import epub
d=docx.Document(); d.add_heading("Quarterly Report",1); p=d.add_paragraph("Normal text with "); r=p.add_run("bold"); r.bold=True
d.add_paragraph("item one",style="List Bullet"); d.add_paragraph("item two",style="List Bullet")
t=d.add_table(rows=2,cols=3); 
for i,row in enumerate([["Name","Qty","Cost"],["A","1","2.5"]]):
    for j,v in enumerate(row): t.cell(i,j).text=v
d.save(f"{D}/ok.docx")
pr=pptx.Presentation(); s=pr.slides.add_slide(pr.slide_layouts[1]); s.shapes.title.text="Slide Title"; s.placeholders[1].text="point one\npoint two"
s.notes_slide.notes_text_frame.text="speaker note"; pr.save(f"{D}/ok.pptx")
wb=openpyxl.Workbook(); ws=wb.active; ws.title="Data"; ws.append(["id","value"]); ws.append([1,10]); ws.append([2,20]); ws["D1"]="=SUM(B2:B3)"; wb.save(f"{D}/ok.xlsx")
open(f"{D}/ok.html","w").write('<html><body><h1>Title</h1><p>See <a href="https://example.org/x">link</a></p><table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table><img src="x.png" alt="alt text"></body></html>')
bk=epub.EpubBook(); bk.set_identifier("id1"); bk.set_title("T"); bk.set_language("en"); c=epub.EpubHtml(title="C1",file_name="c1.xhtml",lang="en"); c.content="<h1>Chapter</h1><p>epub text</p>"
bk.add_item(c); bk.toc=(c,); bk.add_item(epub.EpubNcx()); bk.add_item(epub.EpubNav()); bk.spine=["nav",c]; epub.write_epub(f"{D}/ok.epub",bk)
raw=open(f"{D}/ok.docx","rb").read()
open(f"{D}/bad_truncated.docx","wb").write(raw[:len(raw)//2])
open(f"{D}/bad_empty.docx","wb").write(b"")
open(f"{D}/bad_random.pptx","wb").write(os.urandom(2048))
open(f"{D}/bad_text_as.xlsx","w").write("this is not a workbook")
open(f"{D}/bad_unclosed.html","w").write("<html><body><h1>Unclosed<p>para<table><tr><td>x")
open(f"{D}/unsupported.bin","wb").write(b"\x7fELF"+os.urandom(512))
# nested zip (decompression-safety probe, small)
b=io.BytesIO()
with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z: z.writestr("big.txt","A"*5_000_000)
open(f"{D}/zip_ratio.zip","wb").write(b.getvalue())
# ---- baseline: naive direct text extraction ----
def naive(path):
    e=path.rsplit(".",1)[-1]
    if e=="docx":
        x=docx.Document(path); return "\n".join(p.text for p in x.paragraphs)
    if e=="pptx":
        x=pptx.Presentation(path); return "\n".join(sh.text_frame.text for sl in x.slides for sh in sl.shapes if sh.has_text_frame)
    if e=="xlsx":
        x=openpyxl.load_workbook(path); return "\n".join(" ".join(str(c.value) for c in r if c.value is not None) for ws in x for r in ws.iter_rows())
    if e=="html":
        import re; return re.sub(r"<[^>]+>"," ",open(path,encoding="utf-8",errors="replace").read())
    raise ValueError("no naive extractor")
# ---- network denial during conversion ----
attempts=[]
_orig=socket.socket.connect
def deny(self,*a,**k): attempts.append(str(a)[:80]); raise OSError("network denied in pilot")
socket.socket.connect=deny
from markitdown import MarkItDown
import markitdown
md=MarkItDown(enable_plugins=False)
def feats(s):
    return {"chars":len(s),"headings":sum(1 for l in s.splitlines() if l.startswith("#")),"table_rows":sum(1 for l in s.splitlines() if l.startswith("|")),"links":s.count("]("),"bullets":sum(1 for l in s.splitlines() if l.lstrip().startswith(("- ","* "))) }
rows=[]
for f in sorted(os.listdir(D)):
    p=f"{D}/{f}"; sha=hashlib.sha256(open(p,"rb").read()).hexdigest()[:12]
    rec={"file":f,"sha256_12":sha,"bytes":os.path.getsize(p)}
    t0=time.perf_counter()
    try:
        out=md.convert_local(p).text_content; rec["markitdown"]={"ok":True,**feats(out),"ms":round((time.perf_counter()-t0)*1000,1),"sample":out[:160].replace("\n","\n")}
    except Exception as e:
        rec["markitdown"]={"ok":False,"exc":type(e).__name__,"msg":str(e)[:100],"ms":round((time.perf_counter()-t0)*1000,1)}
    try:
        n=naive(p); rec["naive"]={"ok":True,**feats(n)}
    except Exception as e:
        rec["naive"]={"ok":False,"exc":type(e).__name__}
    rows.append(rec)
res={"markitdown_version":getattr(markitdown,"__version__","unknown"),"python":sys.version.split()[0],"network_connect_attempts":len(attempts),"attempt_samples":attempts[:3],"results":rows}
json.dump(res,open("/tmp/mdpilot/results.json","w"),indent=1)
print(json.dumps({k:v for k,v in res.items() if k!="results"}))
for r in rows:
    m=r["markitdown"]; n=r["naive"]
    print(f"{r['file']:22} md={'OK ' if m['ok'] else 'ERR'} {('h%d t%d l%d b%d c%d'%(m['headings'],m['table_rows'],m['links'],m['bullets'],m['chars'])) if m['ok'] else m['exc']:28} naive={'OK ' if n['ok'] else 'ERR'} {('h%d t%d l%d b%d c%d'%(n['headings'],n['table_rows'],n['links'],n['bullets'],n['chars'])) if n['ok'] else n['exc']}")
