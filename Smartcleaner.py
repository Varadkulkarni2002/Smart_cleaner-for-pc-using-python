"""
SmartCleaner — Fast, lag-free system cleaner.
Single file. No external dependencies beyond psutil (optional).
"""

import os, sys, threading, shutil, hashlib, collections, queue, time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM PATHS
# ─────────────────────────────────────────────────────────────────────────────

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WIN:
    _EV = os.path.expandvars
    CACHE_DIRS   = list(filter(os.path.isdir, [
        _EV(r"%TEMP%"),
        _EV(r"%LOCALAPPDATA%\Temp"),
        _EV(r"%APPDATA%\Microsoft\Windows\Recent"),
        _EV(r"%LOCALAPPDATA%\Microsoft\Windows\INetCache"),
    ]))
    APP_DIRS     = list(filter(os.path.isdir, [
        _EV(r"%PROGRAMFILES%"),
        _EV(r"%PROGRAMFILES(X86)%"),
        _EV(r"%LOCALAPPDATA%\Programs"),
    ]))
    HOME         = os.path.expanduser("~")
    DISK_ROOT    = "C:\\"
    HARD_BLOCK   = [os.path.normpath(p).lower() for p in [
        r"C:\Windows\System32", r"C:\Windows\SysWOW64",
        r"C:\Windows\WinSxS",  r"C:\Windows\Boot",
        r"C:\Windows\Fonts",   r"C:\Windows\Servicing",
        r"C:\Program Files\Windows Defender",
        r"C:\Program Files\WindowsApps",
    ]]
    HARD_NAMES   = {"ntoskrnl.exe","hal.dll","bootmgr","ntldr",
                    "winlogon.exe","lsass.exe","csrss.exe","smss.exe",
                    "wininit.exe","pagefile.sys","hiberfil.sys","swapfile.sys"}
    SYS_WARN_ROOTS = [os.path.normpath(r"C:\Windows").lower(),
                      os.path.normpath(r"C:\ProgramData\Microsoft").lower()]
    SYS_WARN_EXT   = {".sys",".dll",".drv",".ocx",".msi",".cat",".inf",".mui"}

elif IS_MAC:
    HOME      = os.path.expanduser("~")
    CACHE_DIRS= list(filter(os.path.isdir,[
        os.path.join(HOME,"Library","Caches"),
        "/Library/Caches", "/tmp",
        os.path.join(HOME,".cache"),
    ]))
    APP_DIRS  = list(filter(os.path.isdir,["/Applications",
                os.path.join(HOME,"Applications")]))
    DISK_ROOT = "/"
    HARD_BLOCK= ["/system/library","/usr/bin","/usr/lib","/bin","/sbin",
                 "/private/var/db"]
    HARD_NAMES= {"kernel","dyld","launchd"}
    SYS_WARN_ROOTS=["/system","/library/launchdaemons"]
    SYS_WARN_EXT  ={".kext",".dylib",".plist"}

else:
    HOME      = os.path.expanduser("~")
    CACHE_DIRS= list(filter(os.path.isdir,[
        os.path.join(HOME,".cache"),"/tmp","/var/tmp",
        os.path.join(HOME,".local/share/Trash/files"),
    ]))
    APP_DIRS  = list(filter(os.path.isdir,["/usr/bin","/usr/local/bin","/opt"]))
    DISK_ROOT = "/"
    HARD_BLOCK= ["/bin","/sbin","/lib","/lib64","/usr/lib","/usr/bin",
                 "/etc","/boot","/proc","/sys"]
    HARD_NAMES= {"vmlinuz","initrd","grub"}
    SYS_WARN_ROOTS=["/usr/share","/var/lib"]
    SYS_WARN_EXT  ={".so",".conf",".service"}

JUNK_EXT = {".tmp",".log",".bak",".old",".chk",
            ".cache",".dmp",".crdownload",".part","._"}

# ─────────────────────────────────────────────────────────────────────────────
# COLOURS & FONTS
# ─────────────────────────────────────────────────────────────────────────────

C = {
    "bg"     : "#0f0f1a", "surface": "#1a1a2e", "card"   : "#16213e",
    "accent1": "#7c3aed", "accent2": "#a78bfa", "accent3": "#06b6d4",
    "accent4": "#f43f5e", "accent5": "#10b981",
    "text"   : "#f1f5f9", "muted"  : "#94a3b8",
    "border" : "#2d2d4e", "hover"  : "#2a2a4a", "sel_bg" : "#3b1f6e",
    "warn"   : "#f59e0b", "danger" : "#ef4444",
}

_F  = "Segoe UI"  if IS_WIN else ("SF Pro Display" if IS_MAC else "Ubuntu")
_FM = "Consolas"  if IS_WIN else ("SF Mono"        if IS_MAC else "Monospace")
FONT_TITLE = (_F,22,"bold"); FONT_HEAD = (_F,13,"bold"); FONT_BODY = (_F,11)
FONT_MONO  = (_FM,10);       FONT_SMALL= (_F, 9);        FONT_BIG  = (_F,28,"bold")

# ─────────────────────────────────────────────────────────────────────────────
# FAST HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_size(b):
    for u in ("B","KB","MB","GB","TB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def safe_size(path):
    try: return os.path.getsize(path)
    except: return 0

def dir_size(path):
    total = 0
    try:
        stack = [path]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        try:
                            if e.is_file(follow_symlinks=False):
                                total += e.stat(follow_symlinks=False).st_size
                            elif e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                        except: pass
            except: pass
    except: pass
    return total

def file_hash_fast(path):
    h = hashlib.md5()
    try:
        with open(path,"rb") as f:
            h.update(f.read(524288))
        return h.hexdigest()
    except: return None

def get_open_files_set():
    s = set()
    if not HAS_PSUTIL: return s
    try:
        for proc in psutil.process_iter(["open_files"]):
            for f in (proc.info.get("open_files") or []):
                s.add(os.path.normpath(f.path).lower())
    except: pass
    return s

def classify(path, open_set=None):
    """Returns (level, reason). Levels: blocked | system_warn | app_warn | safe"""
    pl   = os.path.normpath(path).lower()
    name = os.path.basename(pl)

    if name in HARD_NAMES:
        return "blocked", f"Critical OS file:\n{path}"
    for bp in HARD_BLOCK:
        if pl.startswith(bp):
            return "blocked", f"Inside protected system folder:\n{path}"

    ext = os.path.splitext(name)[1]
    for sr in SYS_WARN_ROOTS:
        if pl.startswith(sr):
            return "system_warn", f"Windows system file:\n{path}"
    if ext in SYS_WARN_EXT:
        return "system_warn", f"System-type file ({ext}):\n{path}"

    if open_set and pl in open_set:
        return "app_warn", f"Open in a running app:\n{path}"

    return "safe", ""

# ─────────────────────────────────────────────────────────────────────────────
# SCAN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class ScanEngine:
    def __init__(self, mode):
        self.mode  = mode
        self.q     = queue.Queue()
        self._stop = threading.Event()

    def stop(self): self._stop.set()

    def run(self):
        try:
            {"cache":self._cache,"optimize":self._optimize,"junk":self._junk}[self.mode]()
        except Exception:
            pass
        self.q.put(("done", None))

    def _emit(self, tab, row): self.q.put(("row",(tab,row)))
    def _prog(self, p):        self.q.put(("progress",p))

    def _cache(self):
        files = []
        for d in CACHE_DIRS:
            for root,_,fs in os.walk(d):
                if self._stop.is_set(): return
                for f in fs: files.append(os.path.join(root,f))
        total = max(len(files),1)
        for i,fp in enumerate(files):
            if self._stop.is_set(): return
            if i%100==0: self._prog(i/total*100)
            sz  = safe_size(fp)
            ext = os.path.splitext(fp)[1].lower() or "(none)"
            self._emit("Cache Files",(fmt_size(sz),sz,ext,os.path.basename(fp),fp))
        self._prog(100)

    def _optimize(self):
        self._prog(2)
        candidates = []
        for base in list(set(CACHE_DIRS+[HOME])):
            try:
                with os.scandir(base) as it:
                    for e in it:
                        if e.is_dir(follow_symlinks=False):
                            candidates.append(e.path)
            except: pass
        candidates = list(set(candidates))[:100]

        results = []
        for i,d in enumerate(candidates):
            if self._stop.is_set(): return
            self._prog(2+i/max(len(candidates),1)*38)
            sz = dir_size(d)
            results.append((sz,d))
        results.sort(reverse=True)
        for sz,d in results[:60]:
            self._emit("Biggest Folders",(fmt_size(sz),sz,os.path.basename(d),d))

        self._prog(42)
        big = []
        try:
            for root,dirs,files in os.walk(HOME):
                if self._stop.is_set(): return
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    fp = os.path.join(root,f)
                    sz = safe_size(fp)
                    if sz > 5*1024*1024: big.append((sz,fp))
        except: pass
        big.sort(reverse=True)
        for sz,fp in big[:80]:
            self._emit("Biggest Files",(fmt_size(sz),sz,
                       os.path.splitext(fp)[1].lower() or "—",
                       os.path.basename(fp),fp))

        self._prog(80)
        apps = []
        for ad in APP_DIRS:
            try:
                with os.scandir(ad) as it:
                    for e in it:
                        sz = dir_size(e.path) if e.is_dir() else safe_size(e.path)
                        apps.append((sz,e.name,e.path))
            except: pass
        apps.sort(reverse=True)
        for sz,name,path in apps[:50]:
            self._emit("Applications",(fmt_size(sz),sz,name,path))
        self._prog(100)

    def _junk(self):
        all_files = []
        for base in list(set(CACHE_DIRS+[HOME])):
            for root,dirs,files in os.walk(base):
                if self._stop.is_set(): return
                dirs[:] = [d for d in dirs
                           if not any(os.path.join(root,d).lower().startswith(b)
                                      for b in HARD_BLOCK)]
                for f in files: all_files.append(os.path.join(root,f))

        total = max(len(all_files),1)
        size_map = collections.defaultdict(list)
        for i,fp in enumerate(all_files):
            if self._stop.is_set(): return
            if i%100==0: self._prog(i/total*60)
            ext = os.path.splitext(fp)[1].lower()
            sz  = safe_size(fp)
            if ext in JUNK_EXT:
                self._emit("Junk Files",(fmt_size(sz),sz,ext,os.path.basename(fp),fp))
            if sz>1024: size_map[sz].append(fp)

        self._prog(62)
        candidates = [fps for fps in size_map.values() if len(fps)>1]
        flat = [fp for fps in candidates for fp in fps]
        total_c = max(len(flat),1); done_c=0
        hash_map = collections.defaultdict(list)
        for fps in candidates:
            for fp in fps:
                if self._stop.is_set(): return
                done_c+=1
                if done_c%50==0: self._prog(62+done_c/total_c*35)
                h = file_hash_fast(fp)
                if h: hash_map[h].append(fp)

        for h,fps in hash_map.items():
            if len(fps)<2: continue
            sz = safe_size(fps[0])
            for fp in fps[1:]:
                self._emit("Duplicate Files",(fmt_size(sz),sz,
                           os.path.basename(fp),os.path.dirname(fp),fp))
        self._prog(100)

# ─────────────────────────────────────────────────────────────────────────────
# SCAN BUTTON
# ─────────────────────────────────────────────────────────────────────────────

class ScanButton(tk.Canvas):
    R=54; CX=64; CY=64
    def __init__(self, parent, command, **kw):
        super().__init__(parent,width=128,height=128,
                         bg=C["bg"],highlightthickness=0,**kw)
        self.command   = command
        self._scanning = False
        self._angle    = 0
        self._anim_id  = None
        self._hovered  = False
        self._draw_idle()
        self.bind("<Button-1>",lambda e: self.command())
        self.bind("<Enter>",   lambda e: self._hover(True))
        self.bind("<Leave>",   lambda e: self._hover(False))

    def _hover(self,s):
        self._hovered=s
        if not self._scanning: self._draw_idle()

    def _draw_idle(self):
        self.delete("all")
        cx,cy,r = self.CX,self.CY,self.R
        for i in range(5,0,-1):
            self.create_oval(cx-r-i,cy-r-i,cx+r+i,cy+r+i,
                             outline=C["border"],width=1)
        col = C["accent2"] if self._hovered else C["accent1"]
        self.create_oval(cx-r,cy-r,cx+r,cy+r,
                         fill=C["surface"],outline=col,width=3)
        self.create_text(cx,cy,text="SCAN",font=(_F,14,"bold"),fill=col)

    def _draw_scan(self):
        self.delete("all")
        cx,cy,r = self.CX,self.CY,self.R
        self.create_oval(cx-r,cy-r,cx+r,cy+r,
                         fill=C["surface"],outline=C["border"],width=2)
        s = self._angle%360
        self.create_arc(cx-r+4,cy-r+4,cx+r-4,cy+r-4,
                        start=s,extent=260,style="arc",
                        outline=C["accent1"],width=5)
        self.create_arc(cx-r+4,cy-r+4,cx+r-4,cy+r-4,
                        start=s+257,extent=6,style="arc",
                        outline=C["accent2"],width=9)
        self.create_text(cx,cy,text="STOP",font=(_F,11,"bold"),fill=C["muted"])

    def start_spin(self):
        self._scanning=True
        self._tick()

    def stop_spin(self):
        self._scanning=False
        if self._anim_id: self.after_cancel(self._anim_id); self._anim_id=None
        self._draw_idle()

    def _tick(self):
        if not self._scanning: return
        self._angle -= 10
        self._draw_scan()
        self._anim_id = self.after(25,self._tick)

# ─────────────────────────────────────────────────────────────────────────────
# RESULT TABLE
# ─────────────────────────────────────────────────────────────────────────────

class ResultTable(tk.Frame):
    def __init__(self, parent, columns, **kw):
        super().__init__(parent,bg=C["card"],**kw)
        self.columns = columns
        self._data   = []
        self._build(columns)

    def _build(self, columns):
        style = ttk.Style()
        style.configure("D.Treeview",
                        background=C["card"],foreground=C["text"],
                        fieldbackground=C["card"],rowheight=23,
                        borderwidth=0,font=FONT_MONO)
        style.configure("D.Treeview.Heading",
                        background=C["surface"],foreground=C["accent2"],
                        font=FONT_SMALL,borderwidth=0,relief="flat")
        style.map("D.Treeview",
                  background=[("selected",C["sel_bg"])],
                  foreground=[("selected",C["accent2"])])

        self.tree = ttk.Treeview(self,columns=columns,show="headings",
                                 style="D.Treeview",selectmode="extended")

        W={"Size":88,"Ext":64,"Name":230,"Path":360,"Folder":280,"App":220,"Location":280}
        for col in columns:
            w = W.get(col,140)
            self.tree.heading(col,text=col,command=lambda c=col: self._sort(c))
            self.tree.column(col,width=w,minwidth=40,stretch=(col==columns[-1]))

        vsb = ttk.Scrollbar(self,orient="vertical",  command=self.tree.yview)
        hsb = ttk.Scrollbar(self,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set,xscrollcommand=hsb.set)
        self.tree.grid(row=0,column=0,sticky="nsew")
        vsb.grid(row=0,column=1,sticky="ns")
        hsb.grid(row=1,column=0,sticky="ew")
        self.rowconfigure(0,weight=1); self.columnconfigure(0,weight=1)
        self.tree.tag_configure("odd", background=C["card"])
        self.tree.tag_configure("even",background=C["surface"])
        self._row_n=0

    def add_rows_batch(self, rows):
        """
        rows: list of tuples where index 1 is raw numeric size (hidden).
        Display columns = index 0 + index 2 onwards.
        """
        for vals in rows:
            tag     = "odd" if self._row_n%2==0 else "even"
            display = (vals[0],) + vals[2:]
            iid     = self.tree.insert("","end",values=display,tags=(tag,))
            self._data.append((vals,iid))
            self._row_n+=1

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self._data=[]; self._row_n=0

    def get_selected_paths(self):
        return [(iid, self.tree.item(iid,"values")[-1])
                for iid in self.tree.selection()]

    def remove_iids(self, iids):
        iid_set = set(iids)
        for iid in iids:
            try: self.tree.delete(iid)
            except: pass
        self._data = [(v,i) for v,i in self._data if i not in iid_set]

    def _sort(self, col):
        dcols = (self.columns[0],)+self.columns[2:]
        try: didx = list(dcols).index(col)
        except: return
        rev = not getattr(self,"_sort_rev",False)
        self._sort_rev = rev

        def key(item):
            if col=="Size":
                try: return float(item[0][1])
                except: return 0
            raw_idx = didx if didx==0 else didx+1
            return str(item[0][raw_idx]).lower()

        self._data.sort(key=key,reverse=rev)
        for i,(_,iid) in enumerate(self._data):
            self.tree.move(iid,"",i)

# ─────────────────────────────────────────────────────────────────────────────
# SMART DELETE (non-blocking)
# ─────────────────────────────────────────────────────────────────────────────

def run_delete(paths, on_removed, on_done):
    """
    Classify files, show warnings (on UI thread), then delete in background.
    on_removed(iids) is called from bg thread → caller must use after().
    on_done(stats)   is called from bg thread → caller must use after().
    """
    if not paths:
        on_done({"deleted":0,"blocked":0,"sys_skip":0,"app_skip":0,"errors":[]})
        return

    open_set = get_open_files_set()   # one psutil scan, not per-file

    blocked=[]; sys_warned=[]; app_warned=[]; safe=[]
    for iid,path in paths:
        level,reason = classify(path,open_set)
        if   level=="blocked":     blocked.append((iid,path,reason))
        elif level=="system_warn": sys_warned.append((iid,path,reason))
        elif level=="app_warn":    app_warned.append((iid,path,reason))
        else:                      safe.append((iid,path))

    if blocked:
        names = "\n".join(f"  \u26d4 {os.path.basename(p)}" for _,p,_ in blocked[:10])
        extra = f"\n  \u2026and {len(blocked)-10} more" if len(blocked)>10 else ""
        messagebox.showerror("\u26d4 Cannot Delete \u2014 Critical System Files",
            f"{len(blocked)} file(s) are critical Windows system files.\n"
            f"Deleting them would break your operating system.\n\n"
            f"{names}{extra}\n\nThese are excluded automatically.")

    sys_approved=[]
    if sys_warned:
        names = "\n".join(f"  \u26a0\ufe0f  {os.path.basename(p)}" for _,p,_ in sys_warned[:12])
        extra = f"\n  \u2026and {len(sys_warned)-12} more" if len(sys_warned)>12 else ""
        if messagebox.askyesno("\u26a0\ufe0f Windows System Files",
                f"{len(sys_warned)} file(s) are Windows system/driver files.\n"
                f"Removing them may cause instability.\n\n"
                f"{names}{extra}\n\nDelete these anyway?",
                default="no",icon="warning"):
            sys_approved=[(i,p) for i,p,_ in sys_warned]

    app_approved=[]
    if app_warned:
        names = "\n".join(f"  \U0001f512 {os.path.basename(p)}" for _,p,_ in app_warned[:12])
        extra = f"\n  \u2026and {len(app_warned)-12} more" if len(app_warned)>12 else ""
        if messagebox.askyesno("\U0001f512 Files Currently In Use",
                f"{len(app_warned)} file(s) are open in running apps.\n"
                f"Force-deleting may crash those apps.\n\n"
                f"{names}{extra}\n\nForce-delete anyway?",
                default="no",icon="warning"):
            app_approved=[(i,p) for i,p,_ in app_warned]

    to_delete = safe+sys_approved+app_approved
    if not to_delete:
        messagebox.showinfo("Nothing Deleted","No files approved for deletion.")
        on_done({"deleted":0,"blocked":len(blocked),
                 "sys_skip":len(sys_warned),"app_skip":len(app_warned),"errors":[]})
        return

    if not messagebox.askyesno("Confirm Deletion",
            f"About to delete {len(to_delete):,} file(s):\n\n"
            f"  \u2705 Safe:               {len(safe)}\n"
            f"  \u26a0\ufe0f  System (approved):  {len(sys_approved)}\n"
            f"  \U0001f512 In-use (forced):    {len(app_approved)}\n"
            f"  \u26d4 Blocked (skipped):  {len(blocked)}\n\n"
            "This cannot be undone. Continue?",default="no"):
        on_done({"deleted":0,"blocked":len(blocked),
                 "sys_skip":len(sys_warned),"app_skip":len(app_warned),"errors":[]})
        return

    # ── actual deletion in background ─────────────────────────────────────
    def _worker():
        removed=[]; errors=[]
        for iid,path in to_delete:
            try:
                if os.path.islink(path) or os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path,ignore_errors=True)
                removed.append(iid)
            except PermissionError:
                errors.append(f"Permission denied: {os.path.basename(path)}")
            except FileNotFoundError:
                removed.append(iid)          # already gone, treat as success
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

            # flush in chunks so UI can update
            if len(removed)%50==0 and removed:
                on_removed(removed[:])
                removed.clear()

        if removed: on_removed(removed)
        on_done({
            "deleted" : len(to_delete)-len(errors),
            "blocked" : len(blocked),
            "sys_skip": len(sys_warned)-len(sys_approved),
            "app_skip": len(app_warned)-len(app_approved),
            "errors"  : errors,
        })

    threading.Thread(target=_worker,daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

class SmartCleaner(tk.Tk):

    MODES    = [("🧹  Cache Cleaner","cache"),
                ("⚡  System Optimizer","optimize"),
                ("🗑️  Junk & Duplicates","junk")]
    TAB_COLS = {
        "Cache Files"    : ("Size","Ext","Name","Path"),
        "Biggest Folders": ("Size","Folder","Path"),
        "Biggest Files"  : ("Size","Ext","Name","Path"),
        "Applications"   : ("Size","App","Path"),
        "Junk Files"     : ("Size","Ext","Name","Path"),
        "Duplicate Files": ("Size","Name","Folder","Path"),
    }
    MODE_TABS = {
        "cache"   : ["Cache Files"],
        "optimize": ["Biggest Folders","Biggest Files","Applications"],
        "junk"    : ["Junk Files","Duplicate Files"],
    }

    BATCH_SIZE     = 80    # rows inserted per UI tick
    DRAIN_INTERVAL = 40    # ms between queue drains

    def __init__(self):
        super().__init__()
        self.title("SmartCleaner"); self.geometry("1120x740")
        self.minsize(900,600); self.configure(bg=C["bg"])

        self._mode     = tk.StringVar(value="cache")
        self._engine   = None
        self._scanning = False
        self._tables   = {}
        self._counters = {}
        self._total_sz = {}
        self._sum_cards= {}
        self._progress = 0.0
        self._drain_id = None
        self._deleting = False

        self._build_ui()
        self.bind("<Configure>",lambda e: self._redraw_prog())

    def _build_ui(self):
        # ── Sidebar ───────────────────────────────────────────────────────
        sb = tk.Frame(self,bg=C["surface"],width=224)
        sb.pack(side="left",fill="y"); sb.pack_propagate(False)

        tk.Label(sb,text="Smart",  font=FONT_TITLE,bg=C["surface"],fg=C["accent2"]).pack(pady=(28,0))
        tk.Label(sb,text="Cleaner",font=FONT_TITLE,bg=C["surface"],fg=C["text"]).pack(pady=(0,3))
        tk.Label(sb,text="by SmartCare",font=FONT_SMALL,bg=C["surface"],fg=C["muted"]).pack(pady=(0,24))
        ttk.Separator(sb,orient="horizontal").pack(fill="x",padx=18)
        tk.Label(sb,text="MODE",font=FONT_SMALL,bg=C["surface"],fg=C["muted"]).pack(anchor="w",padx=22,pady=(16,6))

        self._mode_btns=[]
        for label,val in self.MODES:
            btn=tk.Label(sb,text=label,font=FONT_BODY,
                         bg=C["surface"],fg=C["muted"],
                         cursor="hand2",anchor="w",padx=22)
            btn.pack(fill="x",pady=3)
            btn.bind("<Button-1>",lambda e,v=val: self._select_mode(v))
            btn.bind("<Enter>",   lambda e,b=btn: b.config(fg=C["accent2"]))
            btn.bind("<Leave>",   lambda e,b=btn: self._leave_btn(b))
            self._mode_btns.append((btn,val))

        self._disk_frame=tk.Frame(sb,bg=C["surface"])
        self._disk_frame.pack(side="bottom",fill="x",padx=18,pady=20)
        self._build_disk_bar()

        # ── Main ──────────────────────────────────────────────────────────
        main=tk.Frame(self,bg=C["bg"])
        main.pack(side="left",fill="both",expand=True)

        top=tk.Frame(main,bg=C["bg"])
        top.pack(fill="x",padx=28,pady=(20,0))

        self.scan_btn=ScanButton(top,command=self._toggle_scan)
        self.scan_btn.pack(side="left")

        inf=tk.Frame(top,bg=C["bg"])
        inf.pack(side="left",fill="x",expand=True,padx=20)

        self._status=tk.StringVar(value="Ready \u2014 select a mode and press SCAN")
        tk.Label(inf,textvariable=self._status,font=FONT_BODY,
                 bg=C["bg"],fg=C["muted"],anchor="w").pack(fill="x")

        self._prog_cv=tk.Canvas(inf,height=8,bg=C["surface"],highlightthickness=0)
        self._prog_cv.pack(fill="x",pady=(8,2))
        self._pct_var=tk.StringVar(value="")
        tk.Label(inf,textvariable=self._pct_var,font=FONT_SMALL,
                 bg=C["bg"],fg=C["accent1"]).pack(anchor="w")

        self._cards_row=tk.Frame(main,bg=C["bg"])
        self._cards_row.pack(fill="x",padx=28,pady=(14,0))

        nb_wrap=tk.Frame(main,bg=C["bg"])
        nb_wrap.pack(fill="both",expand=True,padx=28,pady=(12,6))

        style=ttk.Style(); style.theme_use("clam")
        style.configure("D.TNotebook",background=C["bg"],borderwidth=0,tabmargins=[0,0,0,0])
        style.configure("D.TNotebook.Tab",background=C["surface"],foreground=C["muted"],
                        padding=[14,6],font=FONT_SMALL,borderwidth=0)
        style.map("D.TNotebook.Tab",
                  background=[("selected",C["card"])],
                  foreground=[("selected",C["accent2"])])

        self.notebook=ttk.Notebook(nb_wrap,style="D.TNotebook")
        self.notebook.pack(fill="both",expand=True)

        bar=tk.Frame(main,bg=C["surface"],height=44)
        bar.pack(fill="x",padx=28,pady=(0,14)); bar.pack_propagate(False)

        self._count_var=tk.StringVar(value="")
        tk.Label(bar,textvariable=self._count_var,font=FONT_SMALL,
                 bg=C["surface"],fg=C["muted"]).pack(side="left",padx=16,pady=10)

        self._del_btn=self._tbtn(bar,"🗑  Delete Selected",self._delete_selected,C["accent4"])
        self._del_btn.pack(side="right",padx=8,pady=6)
        self._tbtn(bar,"↕  Sort by Size",self._sort_by_size,C["accent3"]).pack(side="right",padx=4,pady=6)
        self._tbtn(bar,"✓  Select All",  self._select_all,  C["accent1"]).pack(side="right",padx=4,pady=6)

        self._select_mode("cache")

    def _tbtn(self,parent,text,cmd,col):
        btn=tk.Label(parent,text=text,font=FONT_SMALL,bg=col,fg="white",
                     padx=12,pady=4,cursor="hand2",relief="flat")
        btn.bind("<Button-1>",lambda e: cmd())
        lc=self._lighten(col)
        btn.bind("<Enter>",lambda e: btn.config(bg=lc))
        btn.bind("<Leave>",lambda e: btn.config(bg=col))
        return btn

    @staticmethod
    def _lighten(h):
        r=min(255,int(h[1:3],16)+28); g=min(255,int(h[3:5],16)+28); b=min(255,int(h[5:7],16)+28)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _build_disk_bar(self):
        for w in self._disk_frame.winfo_children(): w.destroy()
        if not HAS_PSUTIL:
            tk.Label(self._disk_frame,text="pip install psutil\nfor disk info",
                     font=FONT_SMALL,bg=C["surface"],fg=C["muted"],justify="center").pack()
            return
        try:
            disk=psutil.disk_usage("C:\\" if IS_WIN else "/")
            pct=disk.used/disk.total
            tk.Label(self._disk_frame,text="STORAGE",font=FONT_SMALL,
                     bg=C["surface"],fg=C["muted"]).pack(anchor="w")
            cv=tk.Canvas(self._disk_frame,height=6,bg=C["border"],highlightthickness=0)
            cv.pack(fill="x",pady=4)
            cv.update_idletasks()
            w=cv.winfo_width() or 186
            fc=C["accent4"] if pct>0.9 else (C["warn"] if pct>0.75 else C["accent1"])
            cv.create_rectangle(0,0,int(w*pct),6,fill=fc,width=0)
            tk.Label(self._disk_frame,
                     text=f"{fmt_size(disk.used)} / {fmt_size(disk.total)}  ({pct*100:.0f}%)",
                     font=FONT_SMALL,bg=C["surface"],fg=C["muted"]).pack(anchor="w")
        except: pass

    def _redraw_prog(self): self._update_prog(self._progress)

    def _update_prog(self,pct):
        self._progress=pct
        cv=self._prog_cv; cv.update_idletasks()
        w=cv.winfo_width() or 400
        cv.delete("all")
        cv.create_rectangle(0,0,w,8,fill=C["border"],width=0)
        fw=int(w*pct/100)
        if fw>0:
            cv.create_rectangle(0,0,fw,8,fill=C["accent1"],width=0)
            if fw>8: cv.create_rectangle(fw-8,0,fw,8,fill=C["accent2"],width=0)
        self._pct_var.set(f"{pct:.0f}%")

    def _select_mode(self,val):
        if self._scanning: return
        self._mode.set(val)
        for btn,v in self._mode_btns:
            btn.config(fg=(C["accent2"] if v==val else C["muted"]),
                       bg=(C["hover"]   if v==val else C["surface"]))
        self._set_tabs(val)

    def _leave_btn(self,btn):
        cur=self._mode.get()
        for b,v in self._mode_btns:
            if b is btn and v!=cur:
                btn.config(fg=C["muted"],bg=C["surface"])

    def _set_tabs(self,mode):
        for tid in self.notebook.tabs(): self.notebook.forget(tid)
        self._tables.clear(); self._counters.clear()
        self._total_sz.clear(); self._sum_cards.clear()
        for w in self._cards_row.winfo_children(): w.destroy()

        for tab in self.MODE_TABS[mode]:
            cols=self.TAB_COLS[tab]
            fr=tk.Frame(self.notebook,bg=C["card"])
            tbl=ResultTable(fr,cols)
            tbl.pack(fill="both",expand=True)
            self.notebook.add(fr,text=f"  {tab}  ")
            self._tables[tab]=tbl; self._counters[tab]=0; self._total_sz[tab]=0.0

            card=tk.Frame(self._cards_row,bg=C["card"],padx=14,pady=8)
            card.pack(side="left",padx=(0,10))
            tk.Label(card,text=tab,font=FONT_SMALL,bg=C["card"],fg=C["muted"]).pack(anchor="w")
            cv=tk.StringVar(value="\u2014"); sv=tk.StringVar(value="")
            tk.Label(card,textvariable=cv,font=FONT_BIG,bg=C["card"],fg=C["accent2"]).pack(anchor="w")
            tk.Label(card,textvariable=sv,font=FONT_SMALL,bg=C["card"],fg=C["muted"]).pack(anchor="w")
            self._sum_cards[tab]=(cv,sv)

    # ── Scan ─────────────────────────────────────────────────────────────

    def _toggle_scan(self):
        if self._deleting: return
        if self._scanning: self._stop_scan()
        else:              self._start_scan()

    def _start_scan(self):
        mode=self._mode.get()
        self._set_tabs(mode)
        self._update_prog(0)
        self._status.set("Scanning\u2026 click STOP to cancel")
        self._scanning=True
        self.scan_btn.start_spin()
        self._engine=ScanEngine(mode)
        threading.Thread(target=self._engine.run,daemon=True).start()
        self._schedule_drain()

    def _stop_scan(self):
        if self._engine: self._engine.stop()
        self._scanning=False
        self.scan_btn.stop_spin()
        if self._drain_id: self.after_cancel(self._drain_id); self._drain_id=None
        self._status.set("Scan stopped.")

    def _schedule_drain(self):
        self._drain_id=self.after(self.DRAIN_INTERVAL,self._drain)

    def _drain(self):
        """Pull results from queue in batches — zero UI stutter."""
        if not self._engine: return

        q=self._engine.q
        batch=collections.defaultdict(list)
        last_prog=None; done=False; processed=0
        limit=self.BATCH_SIZE*max(len(self._tables),1)

        try:
            while processed<limit:
                typ,data=q.get_nowait()
                processed+=1
                if   typ=="row":      tab,row=data; batch[tab].append(row)
                elif typ=="progress": last_prog=data
                elif typ=="done":     done=True; break
        except queue.Empty: pass

        for tab,rows in batch.items():
            if tab in self._tables:
                self._tables[tab].add_rows_batch(rows)
                self._counters[tab]+=len(rows)
                for r in rows: self._total_sz[tab]+=r[1]
                if tab in self._sum_cards:
                    cv,sv=self._sum_cards[tab]
                    cv.set(str(self._counters[tab]))
                    sv.set(fmt_size(self._total_sz[tab]))

        if last_prog is not None: self._update_prog(last_prog)
        total=sum(self._counters.values())
        if total: self._count_var.set(f"{total:,} items found")

        if done: self._finish_scan()
        else:    self._schedule_drain()

    def _finish_scan(self):
        self._scanning=False
        self.scan_btn.stop_spin()
        self._drain_id=None
        total=sum(self._counters.values())
        size=fmt_size(sum(self._total_sz.values()))
        self._status.set(f"\u2705  Scan complete \u2014 {total:,} items found, {size} recoverable.")
        self._update_prog(100)

    # ── Actions ──────────────────────────────────────────────────────────

    def _current_table(self):
        try:
            tid=self.notebook.select()
            return self._tables.get(self.notebook.tab(tid,"text").strip())
        except: return None

    def _select_all(self):
        t=self._current_table()
        if t: t.tree.selection_set(t.tree.get_children())

    def _sort_by_size(self):
        t=self._current_table()
        if t: t._sort("Size")

    def _delete_selected(self):
        if self._deleting: return
        if self._scanning:
            messagebox.showinfo("Scan Running","Stop the scan before deleting.")
            return
        t=self._current_table()
        if not t: return
        paths=t.get_selected_paths()
        if not paths:
            messagebox.showinfo("Nothing Selected","Select items first.")
            return

        self._deleting=True
        self._del_btn.config(bg="#444455",cursor="arrow",text="⏳  Working…")
        self._status.set(f"\u23f3  Preparing to delete {len(paths):,} item(s)\u2026")

        def on_removed(iids):
            self.after(0, lambda i=iids: t.remove_iids(i))

        def on_done(stats):
            self.after(0, lambda s=stats: self._delete_finished(s))

        run_delete(paths, on_removed, on_done)

    def _delete_finished(self,stats):
        self._deleting=False
        self._del_btn.config(bg=C["accent4"],cursor="hand2",text="\U0001f5d1  Delete Selected")
        d=stats["deleted"]; bl=stats["blocked"]
        ss=stats["sys_skip"]; aps=stats["app_skip"]; er=stats["errors"]

        parts=[f"\u2705 Deleted: {d:,} item(s)"]
        if bl:  parts.append(f"\u26d4 Blocked (system critical): {bl}")
        if ss:  parts.append(f"\u26a0\ufe0f  Skipped (system, declined): {ss}")
        if aps: parts.append(f"\U0001f512 Skipped (in-use, declined): {aps}")
        if er:
            parts.append(f"\n\u274c Errors ({len(er)}):")
            parts+=[f"   {e}" for e in er[:6]]
            if len(er)>6: parts.append(f"   \u2026and {len(er)-6} more")

        messagebox.showinfo("Deletion Complete","\n".join(parts))
        self._status.set(f"\u2705 Done \u2014 deleted {d:,} file(s).")

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = SmartCleaner()
    app.mainloop()