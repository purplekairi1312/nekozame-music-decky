// nekozame music: a tab in steam's quick access menu. the top shows what tauon is
// playing, with its buttons; below, youtube: search, pick, and it plays (no ads).
// starting youtube pauses tauon, and playing tauon again stops youtube.
import {
  ButtonItem,
  DialogButton,
  Focusable,
  PanelSection,
  PanelSectionRow,
  TextField,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin } from "@decky/api";
import { useEffect, useState } from "react";
import { FaMusic, FaPause, FaPlay, FaStepBackward, FaStepForward, FaStop } from "react-icons/fa";

type Tauon = { running: boolean; status?: string; title?: string; artist?: string; album?: string };
type Video = { id: string; title: string; channel: string; duration: number };
type YouTube = { playing: boolean; paused?: boolean; title?: string; position?: number; duration?: number };

const tauonStatus = callable<[], Tauon>("tauon_status");
const tauon = callable<[what: string], boolean>("tauon");
const search = callable<[query: string], Video[] | { error: string }>("youtube_search");
const play = callable<[id: string, title: string], { ok?: boolean; error?: string }>("youtube_play");
const ytStatus = callable<[], YouTube>("youtube_status");
const ytToggle = callable<[], void>("youtube_toggle");
const ytStop = callable<[], void>("youtube_stop");

const time = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const row = { display: "flex", gap: "8px", justifyContent: "center" } as const;
const button = { minWidth: "0", width: "56px", height: "40px", padding: "0", display: "flex",
  alignItems: "center", justifyContent: "center" } as const;
const title = { fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } as const;
const sub = { fontSize: "12px", opacity: 0.75, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } as const;

function useEvery<T>(get: () => Promise<T>, ms: number): [T | undefined, () => void] {
  const [value, setValue] = useState<T>();
  const refresh = () => { get().then(setValue).catch(() => {}); };
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, ms);
    return () => clearInterval(t);
  }, []);
  return [value, refresh];
}

function TauonSection() {
  const [s, refresh] = useEvery(tauonStatus, 1500);
  const go = (what: string) => tauon(what).then(refresh);
  if (!s) return null;
  if (!s.running) {
    return (
      <PanelSection title="Tauon">
        <PanelSectionRow>
          <div style={sub}>Open Tauon from your library, and turn on its remote control
            (settings → remote) if nothing shows up here.</div>
        </PanelSectionRow>
      </PanelSection>
    );
  }
  const playing = s.status === "playing";
  return (
    <PanelSection title="Tauon">
      <PanelSectionRow>
        <div style={title}>{s.title || (s.status === "stopped" ? "nothing playing" : "")}</div>
        <div style={sub}>{[s.artist, s.album].filter(Boolean).join(" · ")}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <Focusable style={row} flow-children="horizontal">
          <DialogButton style={button} onClick={() => go("back")}><FaStepBackward /></DialogButton>
          <DialogButton style={button} onClick={() => go(playing ? "pause" : "play")}>
            {playing ? <FaPause /> : <FaPlay />}
          </DialogButton>
          <DialogButton style={button} onClick={() => go("next")}><FaStepForward /></DialogButton>
        </Focusable>
      </PanelSectionRow>
    </PanelSection>
  );
}

function YouTubeSection() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Video[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [yt, refresh] = useEvery(ytStatus, 1500);

  const find = async () => {
    if (!query.trim() || busy) return;
    setBusy(true);
    setNote("searching…");
    const r = await search(query);
    setBusy(false);
    if (Array.isArray(r)) { setResults(r); setNote(r.length ? "" : "nothing found"); }
    else setNote(r.error);
  };
  const pick = async (v: Video) => {
    setNote("loading…");
    const r = await play(v.id, v.title);
    setNote(r.error || "");
    refresh();
  };

  return (
    <PanelSection title="YouTube">
      {yt?.playing && (
        <>
          <PanelSectionRow>
            <div style={title}>{yt.title}</div>
            <div style={sub}>{yt.duration ? `${time(yt.position || 0)} / ${time(yt.duration)}` : "loading…"}</div>
          </PanelSectionRow>
          <PanelSectionRow>
            <Focusable style={row} flow-children="horizontal">
              <DialogButton style={button} onClick={() => ytToggle().then(refresh)}>
                {yt.paused ? <FaPlay /> : <FaPause />}
              </DialogButton>
              <DialogButton style={button} onClick={() => ytStop().then(refresh)}><FaStop /></DialogButton>
            </Focusable>
          </PanelSectionRow>
        </>
      )}
      <PanelSectionRow>
        <TextField label="Search" value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") find(); }} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={busy || !query.trim()} onClick={find}>Search</ButtonItem>
      </PanelSectionRow>
      {note && <PanelSectionRow><div style={sub}>{note}</div></PanelSectionRow>}
      {results.map((v) => (
        <PanelSectionRow key={v.id}>
          <ButtonItem layout="below" onClick={() => pick(v)}>
            <div style={{ textAlign: "left" }}>
              <div style={title}>{v.title}</div>
              <div style={sub}>{[v.channel, v.duration ? time(v.duration) : ""].filter(Boolean).join(" · ")}</div>
            </div>
          </ButtonItem>
        </PanelSectionRow>
      ))}
    </PanelSection>
  );
}

export default definePlugin(() => ({
  name: "nekozame music",
  titleView: <div className={staticClasses.Title}>nekozame music</div>,
  content: (
    <>
      <TauonSection />
      <YouTubeSection />
    </>
  ),
  icon: <FaMusic />,
}));
