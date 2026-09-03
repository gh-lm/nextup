# Changelog

All notable changes to Nextup are recorded here.

## [1.0.0] — 2026-09-03

The first release. Everything below has been in daily use on a real library of
93 shows and 964 watched episodes before being called finished.

### What it does
- **Next up**: every show with an aired episode you have not watched, oldest
  first, with a one-press Watched button and a count of how far behind you are.
- **Catching up**: tick one episode, a whole season, or everything up to a given
  episode. Unaired episodes cannot be ticked by accident and progress counts only
  what has actually been broadcast.
- **Episode pages** with the still, synopsis, air date, runtime, guest cast and
  director, linked from everywhere an episode is named.
- **Discover**: what is arriving, with a tick, a question mark and a cross on
  each. Films are filtered to home releases rather than cinema ones. A cross
  hides a title from Discover without deleting it.
- **Maybe list** for shows and films you are curious about but not following.
  They stay out of Next up, the calendar and the email.
- **Films** split into ready to watch, coming to streaming, and seen, with the
  UK services that carry each one.
- **Calendar** of the month: episodes in yellow, films reaching home viewing in
  blue, each labelled so colour is never the only signal.
- **A morning email** with the cover, a description and a link for each thing
  that has become watchable. Covers travel inside the message. Any send time, to
  the minute.
- **A watchable-after setting**, because a programme going out at eleven at
  night is not really available until the next day.
- **Backup and restore**: one file holds everything, and restoring is all of it
  or none of it.

### How it behaves
- Artwork is fetched once and served by Nextup, so no page ever points a browser
  at another host.
- The TMDB key and the mail password are entered in the app and stored
  encrypted, never in an environment file.
- No analytics, no telemetry, no account with anyone.
- Light and dark, following the system by default, with twenty accent colours.
- Runs as a non-root user in the container, with all state in one directory.

## [0.13.1] — 2026-09-03

### Fixed
- The email panel takes the full width now. Squeezed into a masonry column its
  fields stacked one per row and it grew twice as tall as anything else, which
  left its column running well past the others. Across the whole width the
  fields pack three to a row and it is short and wide instead.

## [0.13.0] — 2026-09-03

### Changed
- Settings is masonry now. Nothing lines up with anything: each panel takes only
  the height its content needs and the columns fill themselves, so no panel is
  padded out to match a neighbour. Three columns, then two, then one.
- The TMDB panel was the worst offender for wasted space. Its explanation is
  shorter and the key now sits on one line with its buttons rather than
  stretched across the whole panel on its own.
- The email panel's address hint was three lines, which made that whole row of
  fields tall. It is one line. The send time, the clock switch and the tick box
  share a line rather than taking three.

## [0.12.0] — 2026-09-03

### Changed
- The accent colour, the watchable delay and the email schedule now save
  themselves the moment you change them. Their buttons remain underneath for
  anyone without scripting, and are only removed once the page knows it can do
  the job instead. The mail server, the TMDB key, the password and the restore
  still need a deliberate press, because half-typed credentials should not save
  themselves.
- Buttons have an edge you can see. An ordinary button's border sat at 1.27 to 1
  against a white panel and 1.12 to 1 in the dark, and the quiet ones had no
  fill and no border at all, so they read as plain text. Both now use the same
  edge as the form fields, clearing the 3 to 1 asked of a control.

## [0.11.1] — 2026-09-03

### Fixed
- On a medium screen the bento was only 81 per cent full: three panels sat in a
  two-column stack, leaving a hole, and the backup panel sat alone in a
  four-column row. Stacks now spread across whatever width they are given.
  Measured fill is 88 per cent at desktop, 94 in the middle, 92 to 97 on a
  tablet and 95 on a phone.

## [0.11.0] — 2026-09-03

### Changed
- Form fields pack across the width they are given instead of stacking down it.
  The mail settings had five rows of fields, two of which held a single input
  stretched across the whole panel. They are three rows now, which makes the
  panel considerably shorter and stops the bento having to be padded out around
  it.

## [0.10.5] — 2026-09-03

### Changed
- The bento's two pairs are balanced by measurement rather than guesswork. The
  stack beside the morning email overshot it by 230 pixels and sign-in fell 272
  short of backup, which is where the leftover space was going.

## [0.10.4] — 2026-09-03

### Changed
- The bento is packed properly now. Panels are sized to their content rather
  than stretched to a shared row height, which was what created the empty space.
  The TMDB key runs across the top, the morning email sits beside a stack of
  four short panels picked so the two come out level, and backup and sign-in
  finish the bottom row. It steps from six columns to four, then two, then one.

## [0.10.3] — 2026-09-03

### Fixed
- The bento's short panels had a hole between the heading and the content,
  because forms were being pushed to the foot of their compartment. Content sits
  at the top now and spare room falls to the bottom, where it reads as space
  rather than a mistake.

## [0.10.2] — 2026-09-03

### Changed
- Settings is a bento: compartments of different sizes that tessellate, rather
  than two columns of whatever happened to land in them. The sizes are chosen so
  the grid fills with no gaps and nothing has to be shuffled out of order, which
  keeps what you read in the same order as what you see. It steps down to four
  columns, then to one.

## [0.10.1] — 2026-09-03

### Changed
- The privacy and cookies pages now give privacy@lightmorphic.com, and the
  complaints page and the accessibility statement give
  complaints@lightmorphic.com.

## [0.10.0] — 2026-09-03

### Added
- **Backup and restore.** One button writes everything to a single JSON file:
  every show and film, everything watched, what was dismissed, your settings,
  and enough show detail that a restored copy works before it has spoken to
  TMDB. Another button reads it back. All of it or none of it, so a file that
  cannot be read leaves the database exactly as it was.
- Your TMDB key and mail password are left out of the plain download, because
  they are encrypted with a key that stays on that server. A second button
  includes them as plain text, and says so.

### Fixed
- Form fields were nearly invisible in dark mode: the field was the same colour
  as the panel behind it, with an edge at 1.1 to 1 against it. Fields now have
  their own background and an edge clearing 3 to 1 in both themes. Light mode
  failed the same standard at 1.27 to 1 and was fixed with it.
- The upload limit was two megabytes, which a large library's own backup would
  have exceeded. It is now sixty-four.

## [0.9.4] — 2026-09-03

### Changed
- The headline no longer underlines a phrase to draw the eye. It asks which
  episode you were on, and a line beneath types out the answer, cycling through
  real examples. With scripting off, or with reduced motion asked for, the first
  answer simply stands.
- The link for the TMDB key now goes straight to the page that holds it, in the
  app, on the website and in the README, rather than to the front of the site to
  be hunted for.

### Fixed
- Three error banners in the app were still the old top-of-page sort. They now
  sit beside what caused them like everything else.

### Added
- Tests for three standing rules: no decorative underlining, no left-hand edges
  on boxes, and no banner notifications. Link hover underlines are allowed, and
  the test says why: without them an inline link is told apart by colour alone.

## [0.9.3] — 2026-09-03

### Changed
- The website has been rebuilt. Every screenshot retaken on the current build,
  including the show page, whose cast row used to run off the side of its panel
  in the old picture.
- The decorative label above the headline is gone, along with the grid of eight
  small feature cards. Each section now stands on a real screenshot instead.
- The morning email has a section of its own, since nothing else in this class
  of software does it.
- Fixed a column with a fixed minimum width that pushed the page sideways at 320
  pixels, which is what a 1280 pixel screen becomes at 400 per cent zoom.

## [0.9.2] — 2026-09-03

### Changed
- A linked cover in the email now says it carries no border, because some mail
  clients ring a linked picture in blue otherwise.
- The Settings page says so plainly when the email is switched on but the
  address box is empty, since that is the one thing that stops anything in the
  email being clickable.

## [0.9.1] — 2026-09-03

### Fixed
- The plain text version of the email had neither the descriptions nor the
  links, so anyone whose mail client shows text rather than pictures got less
  than everyone else. It now carries the same.

## [0.9.0] — 2026-09-03

### Added
- The morning email now shows the cover of each show and film, a couple of
  sentences about it, and links each one back to its page in Nextup.
- The artwork is attached to the message rather than linked, so it appears even
  though this server is not reachable from the wider internet, and no mail
  client ever calls out to fetch it.
- A field in Settings for this Nextup's own address, which is what the links in
  the email point at. Left blank, the email still lists everything, just with
  nothing to click.

### Changed
- Poster caching moved out of the web route into its own module, so the pages
  and the email share one copy of each picture rather than fetching it twice.

## [0.8.2] — 2026-09-02

### Changed
- No coloured edges anywhere. The confirmation strips lose their coloured rule
  and keep the coloured tick or exclamation. Today on the calendar is a filled
  date rather than a ring round the cell. The tick buttons, the yes, no and
  maybe buttons and the calendar key all carry their meaning in the fill or the
  text instead. A test now walks both stylesheets and fails if one comes back.
- Focus outlines stay, since they are outlines rather than borders and taking
  them away would leave anyone using a keyboard with nowhere to look.

## [0.8.1] — 2026-09-02

### Fixed
- On a middling screen the search box dropped to a second row and sat against
  the right edge with a wide gap beside it. When it wraps it now takes the whole
  row.

## [0.8.0] — 2026-09-02

### Changed
- Confirmations no longer appear as a coloured banner at the top of the page.
  They now sit beside the control that caused them, as a quiet line with a
  coloured edge, and saving a setting returns you to that panel rather than
  throwing you back to the top to read the message.
- The top bar drops its "Next up" link, since the logo already goes there, which
  leaves the search box room to stay on the same row.
- The light, dark and automatic switch is now an icon on its own. It still
  announces which mode it is in to a screen reader.

## [0.7.2] — 2026-09-02

### Fixed
- Anything hidden by script stayed on screen. The browser hides such elements
  with its own stylesheet, and any rule of ours that sets how an element is laid
  out overrode it. The clock switch's fallback button was the visible symptom.

## [0.7.1] — 2026-09-02

### Changed
- The clock choice is now a toggle switch reading "12 hours" and "24 hours",
  sitting beside the time rather than up beside the heading, since the time is
  the only thing it changes. It applies as soon as it is pressed, and still
  works without scripting.
- Hours and minutes are dropdowns rather than number boxes, so the 24 hour
  clock reads 08 and 09 rather than 8 and 9. A number box strips a leading
  zero, so it could never show them properly.

## [0.7.0] — 2026-09-02

### Added
- The morning email can go out at **any time of day, to the minute**, rather
  than on the hour. Twelve minutes past seven is a perfectly good answer.
- A small switch beside the heading turns the time controls from the 24 hour
  clock to **am and pm**, for anyone who would rather read it that way. The 24
  hour clock stays the default, and the choice only changes what is shown; the
  time is stored the same way either way.
- The email has been rebuilt: the Nextup name at the top, the date it covers,
  television and films in separate sections with the channel or the streaming
  service beside each, and a Lightmorphic credit at the foot linking to
  lightmorphic.com. Built from tables and inline styles, which is what mail
  clients understand, and it loads nothing from anywhere else.

### Changed
- The scheduler now checks every two minutes rather than every ten, so a time
  like 07:12 is not a quarter of an hour late.
- An older install that stored only an hour is read and converted on the way
  past, so nothing needs re-entering.

## [0.6.0] — 2026-09-02

### Added
- A setting for **when something counts as watchable**. A programme going out at
  eleven at night is not really available until the next day, so Nextup now
  waits a number of days you choose before putting it in Next up, moving a film
  into Ready to watch, or mentioning it in the email. The default is one day.
  Nought restores the old behaviour of counting it the day it airs.
- A **morning email**. Mail server details go in the Settings page, with the
  password stored encrypted alongside the TMDB key. Once a day it sends a short
  list of what has become watchable, in plain text and simple HTML. If nothing
  has, nothing is sent.
- Buttons to send a test message and to send today's email straight away,
  so the settings can be proved without waiting until morning.
- `TZ` in the compose file, since the send hour and the meaning of "today" both
  depend on the container's clock.

## [0.5.2] — 2026-09-02

### Fixed
- On a phone, the poster stayed beside the text on a show or film page, leaving
  the synopsis in a column about 190 pixels wide. Below 520 pixels the poster
  now sits above the text and the writing gets the full width.

## [0.5.1] — 2026-09-02

### Fixed
- The cast strip on a show or film page pushed the whole page off to the right
  instead of scrolling inside its own panel. The column it sits in was sizing
  itself to the full width of every cast photograph laid end to end.

## [0.5.0] — 2026-09-02

### Added
- Films now appear on the calendar, on the day they reach home viewing, in blue
  against the yellow used for episodes. Every entry is also labelled, so the two
  are told apart by more than colour, and a small key sits above the month.
- Films you have already seen are faded on the calendar the same way watched
  episodes are, rather than disappearing.

### Changed
- Films on the maybe list stay off the calendar, matching how maybe shows behave.

## [0.4.0] — 2026-09-02

### Added
- Show and film pages now carry proper detail: the cast with photographs, the
  genres, the certificate, the tagline, the creators of a series or the director
  and writers of a film, and links out to a trailer, IMDb and a where-to-watch
  page.
- Shows list which UK services carry them, the way films already did.
- Cast photographs go through the same local cache as posters, so the pages
  still call out to nobody.

### Changed
- The image proxy accepts filenames with dashes and underscores, which cast
  photographs use and posters do not.
- The extra detail is fetched when the page is opened rather than stored, so it
  is never stale, and both pages render fine when TMDB cannot be reached.

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
