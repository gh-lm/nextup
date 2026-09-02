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
- **Calendar** — a month at a glance of when your shows air.
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

To get one: make a free account at themoviedb.org, open Settings → API, and copy
the **API Key (v3 auth)**.

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

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `NEXTUP_DATA_DIR` | `/data` | Where the database, encryption key and poster cache live |
| `NEXTUP_PORT` | `8080` | Port inside the container |
| `NEXTUP_SYNC_HOURS` | `12` | Hours between automatic refreshes |

Everything else — the TMDB key, your password, the accent colour — is set in the
app itself.

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
