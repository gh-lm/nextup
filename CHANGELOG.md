# Changelog

All notable changes to Nextup are recorded here.

## [0.3.0] — 2026-09-02

### Added
- **Discover**, two pages for deciding what to take on. Films lists what reaches
  streaming or television in the next 7, 14, 30 or 60 days, with cinema releases
  left out. TV lists series starting soon, or everything on air now.
- A tick, a question mark and a cross on every Discover card. Tick adds it,
  question mark puts it on the Maybe list, cross hides it from Discover for
  good. Hidden items still turn up in a search, and one button brings them all
  back.
- **Episode pages.** Click any episode title and you get its still, synopsis,
  air date, runtime, rating, guest cast and director, with links to the episode
  either side. Episode titles across the dashboard, calendar, show pages and
  Coming soon all lead there.
- Films can go on the Maybe list too, so the tick, question mark and cross mean
  the same thing whichever page you are on. The Maybe page now has a Shows
  section and a Films section.

## [0.2.0] — 2026-09-02

### Added
- A **Maybe** list for shows you are curious about but are not following. They
  stay out of Next up, the calendar and Coming soon until you press Start
  watching, at which point they join your shows as normal.
- Search results and show pages can add straight to Maybe as well as to your
  shows.
- Films now show **when they reach streaming**, not just when they were in
  cinemas. Nextup reads the digital, physical and TV release dates from TMDB and
  prefers a UK one, falling back to Ireland then the US.
- Films also show **which UK services carry them**, using the JustWatch data
  TMDB publishes. Subscription, free and ad-supported services are listed;
  rental and purchase are left out.
- The Films page is now three sections: ready to watch, coming to streaming, and
  seen. A "Check now" button re-asks TMDB about any film without a date.
- Coming soon lists films landing on streaming alongside the episodes airing.

### Changed
- The scheduled refresh also updates film availability, and skips shows on the
  Maybe list.

## [0.1.0] — 2026-09-02

First working version.

### Added
- Next up dashboard: shows with aired, unwatched episodes, oldest first, with
  watched counts, time watched and a films-to-watch tile.
- My shows: poster grid with per-show progress, favourites, archive, and filters
  for all / behind / archived.
- Show page with every season and episode; tick one episode, a whole season, or
  everything up to a given episode.
- Month calendar of episodes for tracked shows, with watched ones faded.
- Coming soon list over 14, 30, 60 or 180 days.
- Film watchlist with a to-watch and a seen section.
- TMDB search across shows and films, added in one click.
- Automatic refresh from TMDB every 12 hours, plus a manual refresh button.
  Ended shows are refreshed on a two-week cycle instead.
- TMDB API key entered in the Settings page and stored encrypted, never in a
  plaintext environment file.
- Poster and still proxy: artwork is cached locally and served from this app, so
  no page loads anything from a third-party host.
- Light and dark themes, following the system by default, plus a 20-colour
  accent picker.
- Single-user sign-in with a starter account of admin / nextup that the app
  nags you to change.
