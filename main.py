"""nekozame music's backend. it runs as your user (not root), and does two things:

  tauon:   talks to Tauon's remote api on this machine (127.0.0.1:7814), so the tab
           shows what's playing and can skip and pause. Tauon has to be running, with
           its remote control on (settings → remote; nekozame os turns it on for you)
  youtube: searches with yt-dlp and plays the audio in mpv, in the background, with no
           ads (yt-dlp gets the audio straight from youtube). yt-dlp is downloaded the
           first time, from its own github releases, and keeps itself updated
"""
import asyncio
import json
import os
import shutil
import socket
import ssl
import subprocess
import time
import urllib.request

import decky

TAUON = "http://127.0.0.1:7814/api1/"
YTDLP = os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "yt-dlp")
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux"
# decky's own python has no certificates of its own: the system's
CA = next((f for f in ("/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem", "/etc/pki/tls/certs/ca-bundle.crt",
                       "/etc/ssl/certs/ca-certificates.crt",
                       "/etc/ssl/cert.pem") if os.path.exists(f)), None)
UID = os.getuid()
RUN = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{UID}"
SOCK = os.path.join(RUN, "nekozame-music-youtube.sock")


def env():
    """the environment for programs we start: decky's own bundled libraries out of the
    way (they break other programs), and your session's audio in reach."""
    e = dict(os.environ)
    for k in ("LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONHOME", "PYTHONPATH"):
        e.pop(k, None)
    e["XDG_RUNTIME_DIR"] = RUN
    e.setdefault("HOME", decky.DECKY_USER_HOME)
    e["PATH"] = "/usr/local/bin:/usr/bin:/bin:" + e.get("PATH", "")
    return e


def tauon(path):
    try:
        with urllib.request.urlopen(TAUON + path, timeout=1.5) as r:
            body = r.read()
        return json.loads(body) if body.strip().startswith(b"{") else {}
    except (OSError, ValueError):
        return None


def download(url, path):
    context = ssl.create_default_context(cafile=CA)
    with urllib.request.urlopen(url, timeout=60, context=context) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)


def mpv_command():
    if shutil.which("mpv", path=env()["PATH"]):
        return ["mpv"]
    if subprocess.run(["flatpak", "info", "io.mpv.Mpv"], env=env(), capture_output=True).returncode == 0:
        return ["flatpak", "run", f"--filesystem={RUN}", f"--filesystem={decky.DECKY_PLUGIN_RUNTIME_DIR}:ro", "io.mpv.Mpv"]
    return None


class Plugin:
    mpv = None
    title = ""

    # --- tauon ---------------------------------------------------------------

    async def tauon_status(self):
        s = await asyncio.to_thread(tauon, "status")
        if s is None:
            return {"running": False}
        return {
            "running": True,
            "status": s.get("status", "stopped"),
            "title": s.get("title", ""),
            "artist": s.get("artist", ""),
            "album": s.get("album", ""),
        }

    async def tauon(self, what):
        if what not in ("play", "pause", "next", "back", "stop"):
            return False
        if what == "play":
            await self.youtube_stop()
        return await asyncio.to_thread(tauon, what) is not None

    # --- youtube -------------------------------------------------------------

    async def _ytdlp(self):
        """yt-dlp, downloaded the first time and updated once a week."""
        if not os.path.exists(YTDLP):
            os.makedirs(os.path.dirname(YTDLP), exist_ok=True)
            tmp = YTDLP + ".part"
            await asyncio.to_thread(download, YTDLP_URL, tmp)
            os.chmod(tmp, 0o755)
            os.replace(tmp, YTDLP)
        elif time.time() - os.path.getmtime(YTDLP) > 7 * 86400:
            os.utime(YTDLP)
            subprocess.Popen([YTDLP, "-U"], env=env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return YTDLP

    async def youtube_search(self, query):
        query = (query or "").strip()
        if not query:
            return []
        try:
            ytdlp = await self._ytdlp()
        except OSError as e:
            decky.logger.error(f"yt-dlp download: {e}")
            return {"error": "couldn't get yt-dlp (no internet?)"}
        proc = await asyncio.create_subprocess_exec(
            ytdlp, "--flat-playlist", "-J", "--no-warnings", f"ytsearch10:{query}",
            env=env(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode != 0:
            decky.logger.error(f"search: {err.decode(errors='replace')[-500:]}")
            return {"error": "the search didn't work (no internet?)"}
        results = []
        for e in json.loads(out).get("entries", []):
            if not e.get("id"):
                continue
            results.append({
                "id": e["id"],
                "title": e.get("title", ""),
                "channel": e.get("channel") or e.get("uploader") or "",
                "duration": int(e.get("duration") or 0),
            })
        return results

    def _ipc(self, *args):
        try:
            with socket.socket(socket.AF_UNIX) as s:
                s.settimeout(1)
                s.connect(SOCK)
                s.sendall((json.dumps({"command": list(args), "request_id": 1}) + "\n").encode())
                buf = b""
                while True:
                    chunk = s.recv(65536)
                    if not chunk:
                        return None
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        msg = json.loads(line)
                        if msg.get("request_id") == 1:
                            return msg.get("data")
        except (OSError, ValueError):
            return None

    async def youtube_play(self, video_id, title):
        # only a youtube video id: nothing else gets handed to mpv
        if not video_id or not all(c.isalnum() or c in "-_" for c in video_id) or len(video_id) > 20:
            return {"error": "not a youtube video"}
        cmd = mpv_command()
        if not cmd:
            return {"error": "needs mpv (flatpak install flathub io.mpv.Mpv)"}
        try:
            ytdlp = await self._ytdlp()
        except OSError:
            return {"error": "couldn't get yt-dlp (no internet?)"}
        await self.youtube_stop()
        await asyncio.to_thread(tauon, "pause")
        self.title = title or ""
        self.mpv = subprocess.Popen(cmd + [
            "--no-video", "--no-terminal", "--force-window=no", "--ytdl-format=bestaudio/best",
            f"--script-opts=ytdl_hook-ytdl_path={ytdlp}", f"--input-ipc-server={SOCK}",
            f"--force-media-title={self.title}", "--",
            f"https://www.youtube.com/watch?v={video_id}",
        ], env=env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True}

    async def youtube_status(self):
        if not self.mpv or self.mpv.poll() is not None:
            return {"playing": False}
        paused = await asyncio.to_thread(self._ipc, "get_property", "pause")
        pos = await asyncio.to_thread(self._ipc, "get_property", "time-pos")
        dur = await asyncio.to_thread(self._ipc, "get_property", "duration")
        return {"playing": True, "paused": bool(paused), "title": self.title,
                "position": pos or 0, "duration": dur or 0}

    async def youtube_toggle(self):
        if self.mpv and self.mpv.poll() is None:
            await asyncio.to_thread(self._ipc, "cycle", "pause")

    async def youtube_stop(self):
        if self.mpv and self.mpv.poll() is None:
            self.mpv.terminate()
            try:
                await asyncio.to_thread(self.mpv.wait, 3)
            except subprocess.TimeoutExpired:
                self.mpv.kill()
        self.mpv = None

    # --- decky ---------------------------------------------------------------

    async def _main(self):
        decky.logger.info("nekozame music is here")

    async def _unload(self):
        await self.youtube_stop()

    async def _uninstall(self):
        await self.youtube_stop()
