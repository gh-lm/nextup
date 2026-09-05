# Nextup

A personal TV and film tracker: what to watch next, how far behind you are,
and when the next episode airs. Self-hosted, single user, no accounts to make
and nothing phoning home.

## What it does

- **Next up** — every show with an aired episode you have not watched, oldest
  first, with a one-click "watched" button.
- **My shows** — poster grid with a progress bar per show, and filters for the
  ones you are behind on.
- **Show page** — every season and episode, tick them off one at a time, a whole
  season at once, or "up to here" for catching up.
- **Calendar** — a month at a glance: episodes of your shows in yellow, films
  reaching home viewing in blue, each labelled so colour is not the only signal.
- **Coming soon** — the next 14 to 180 days as a plain list.
- **Maybe** — shows you fancy the look of but are not following. They stay out
  of Next up and the calendar until you decide to watch one.
- **Films** — split into ready to watch, coming to streaming, and seen. Each
  film shows the date it reaches home viewing and which UK services carry it,
  which is more use than a cinema release date if you do not go to the cinema.
- **Discover** — separate pages for films and TV. Films shows what reaches
  streaming in the next fortnight, not what opens at the cinema. A tick, a
  question mark and a cross on every card send it to your list, your maybe list,
  or out of sight.
- **Episode pages** — the still, synopsis, air date, runtime, guest cast and
  director for any episode, with links either side of it.
- **Detail worth reading** — show and film pages carry the cast with
  photographs, genres, the certificate, the tagline, who made it, which UK
  services carry it, and links to a trailer and IMDb.
- **A morning email** — one short message a day listing what has become
  watchable, at any time you choose, to the minute. Mail server details go in
  the Settings page, password encrypted. A switch turns the clock from 24 hour
  to am and pm.
- **A watchable-after setting** — something that airs at eleven at night is not
  really available until the next day, so Nextup waits however long you say
  before it counts. This governs Next up, the films list and the email alike.
- **Search** — shows and films from TMDB, added in one click.

Data comes from [TMDB](https://www.themoviedb.org/). Tracked shows refresh
automatically every 12 hours; finished shows are checked far less often. Film
availability is re-checked every few days, and streaming service listings come
from JustWatch by way of TMDB.

## Posters stay on your server

Artwork is fetched from TMDB once, cached in the data directory and then served
by this app. No page ever points a browser at a third-party host, and the font
is served locally too.

## The TMDB key

Nextup needs a free TMDB API key. It is **not** an environment variable — you
paste it into the Settings page, where it is checked against TMDB and then
stored encrypted in the database. The encryption key lives beside the database
as `secret.key` with 0600 permissions.

To get one: make a free account, then go straight to
<https://www.themoviedb.org/settings/api> and copy the **API Key (v3 auth)**.

## Running it

```bash
sudo mkdir -p /opt/nextup
sudo chown -R 1000:1000 /opt/nextup
docker compose up -d
```

The container runs as UID 1000, so the bind-mounted directory has to be owned by
that same UID or writes fail silently.

Then open the app, sign in with **admin / nextup**, and change both on the
Settings page straight away.

Updating:

```bash
docker compose pull
docker compose down
docker compose up -d
```

`docker compose up -d` on its own does not re-pull a `:latest` tag.

### If you put a proxy in front of it on the same port

Something like Tailscale Serve listening on the same port number the container
publishes will fight it for that port, and whichever starts first wins. The
symptom is `address already in use` on a restart that worked yesterday. Bind the
container to the loopback address instead, and let the proxy be the only thing
listening publicly:

```yaml
    ports:
      - "127.0.0.1:4090:8080"
```

### Locking the container down

Nextup never needs to become root and only ever writes to `/data`, so the
compose file in this repo runs it with no extra privileges, no Linux
capabilities and a read-only filesystem:

```yaml
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp
```

If you wrote your own compose file before, adding those four blocks is worth
doing. Nothing else has to change.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `NEXTUP_DATA_DIR` | `/data` | Where the database, encryption key and poster cache live |
| `NEXTUP_PORT` | `8080` | Port inside the container |
| `NEXTUP_SYNC_HOURS` | `12` | Hours between automatic refreshes |
| `NEXTUP_HTTPS_ONLY` | `0` | Set to `1` only when every way in really is HTTPS. It marks the sign-in cookie Secure, so a browser will not send it over plain HTTP at all. Leave it off if you ever reach the container directly on `127.0.0.1:4090` |
| `TZ` | unset | Your timezone, for example `Europe/London`. The morning email and the meaning of "today" both read the clock |

Everything else — the TMDB key, your password, the accent colour — is set in the
app itself.

## Taking it with you

The Settings page has a **Download a backup** button. One JSON file holds every
show and film you added, everything you marked watched, what you dismissed, and
your settings, alongside enough show detail for a fresh copy to be usable
immediately. Restore it on another machine and you carry on where you left off.

Your TMDB key and mail password are left out by default, because they are
encrypted with a key that stays on that server. A second button includes them,
written into the file as plain text, so keep that one somewhere safe.

## What lives in the data directory

- `nextup.db` — shows, episodes, what you have watched
- `secret.key` — encrypts the TMDB key (0600)
- `session.key` — signs the login cookie (0600)
- `images/` — cached posters and stills

Backing up that one directory backs up everything.

## Running it without Docker

```bash
pip install -r requirements.txt
NEXTUP_DATA_DIR=./data python run.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Licence

GPL-3.0. See [LICENSE](LICENSE).

This product uses the TMDB API but is not endorsed or certified by TMDB.
