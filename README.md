# nekozame music 🦈🎵

A [Decky](https://decky.xyz) plugin: your music in Steam's Quick Access menu, while you play.

- **Tauon**: what [Tauon Music Box](https://tauonmusicbox.rocks) is playing, with previous,
  play/pause and next. Your library, Navidrome or Jellyfin: whatever Tauon plays.
- **YouTube, without ads**: search, pick a result, and it plays in the background.
  [yt-dlp](https://github.com/yt-dlp/yt-dlp) fetches the audio straight from YouTube and
  [mpv](https://mpv.io) plays it. Starting YouTube pauses Tauon.

It comes with [nekozame os](https://github.com/purplekairi1312/nekozame-os), and works on any
Steam Deck or Steam machine with Decky.

## What it needs

- **Tauon**, running (open it from your library), with its remote control on:
  Tauon's settings → remote → "Enable remote control". Tauon's remote isn't hardened, so
  nekozame os keeps port 7814 to the Deck itself and your Tailscale network; on other systems,
  only turn it on on networks you trust.
- **mpv** for YouTube: nekozame os has it; elsewhere `flatpak install flathub io.mpv.Mpv`.
- yt-dlp is downloaded the first time you search, from its GitHub releases, and keeps
  itself updated.

The plugin runs as your user, not root.

## Building

```sh
pnpm install
pnpm build
```

Then copy `plugin.json`, `main.py`, `package.json`, `LICENSE` and `dist/` to
`~/homebrew/plugins/nekozame-music/`. GitHub Actions builds a zip of that on every push.

## License

GPL-3.0-or-later. Started from Decky's [plugin template](https://github.com/SteamDeckHomebrew/decky-plugin-template) (BSD-3-Clause).
