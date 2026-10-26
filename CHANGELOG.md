# Changelog

All notable changes to Nextup are recorded here, newest first. Small releases
made close together are described as one.

## [2.0.0], 2026-10-26

Nextup now uses TheTVDB for everything, and nothing needs a key. Your shows and watched marks carry over.

- **TheTVDB for everything, with nothing to sign up for.** Nextup finds shows and movies, and fetches their episodes, dates, covers and cast, from TheTVDB through its own small lookup service, which holds the key so you do not need one.
- **TMDB is gone.** Discover, where to watch, streaming alerts, age certificates, star ratings, taglines, guest cast, and the country and language settings went with it. No key of any kind is asked for.
- **Movies use their release date.** A movie sits under coming soon until its release date has passed, then moves to ready to watch by itself. The date is re-checked every few days.
- **Your shows carry over.** Shows saved under TMDB numbers are matched to TheTVDB on their next refresh, and keep their watched marks.
- **Smaller backups.** A backup holds what you follow, what you watched and your settings. Names, pictures and dates are fetched fresh from TheTVDB when you restore. The mail password is the only secret left.
- **Easier to install.** Nextup gives the data folder to its own user when it starts, so there is no chown step and no helper container.
- **Credit.** The footer carries TheTVDB's credit and a link, as their terms ask.

## [1.7.2], 2026-10-24

Fixes and tidying. Your data is untouched.

- **A show no longer fails to sync when TMDB moves an episode.** If TMDB gave an episode a new season or number under the same id, the show stopped updating with a "unique constraint failed" error. The episode now moves and keeps its watched mark.
- **Where to watch.** The button that sent you to TMDB is gone. The services are named on the page, and the episode page names them too.
- **Trailers open in a new tab.**
- **Up to here goes grey** on an episode you have already marked watched.
- **Smaller fixes.** The Mail Remove button keeps its two-click confirm after a setting saves. Discover asks for several languages at once and says so if TMDB cannot give release dates, instead of showing "Nothing new". The email address is filled in once from the page and is no longer changed by opening Settings from another address.

## [1.7.1], 2026-10-24

Everything since 1.6.0 in one release. Your data is untouched.

- **Languages.** Each show and movie shows its original language in a small outlined label at the right of its card. A new Languages setting decides which languages Discover lists: every language to begin with, or English plus the ones you add. Your own lists and search are never filtered.
- **Discover shows only what is new.** It lists exactly the days you pick, then a line, then what came out in the last 14 days. Movies are new films whose streaming date falls in the window, so old films shown on television no longer appear. Each date is labelled Streaming, because it is the day the movie reaches streaming or television, not its cinema date.
- **One Order setting.** Newest first or oldest first, for seasons, episodes, Ready to watch, Movies, Maybe and Discover. Coming soon and Coming to streaming always show the next thing first.
- **Maybe has a TV | Movies switch,** like Discover, and follows the Order setting.
- **Archived shows can unarchive themselves.** An archived show has a box, ticked by default, that brings it back when a newer season turns up.
- **Movies.** Film is now Movie everywhere. Coming to streaming is a poster grid with a Check now button, and names are cut to two lines so every card in a row lines up.
- **Settings save quietly.** Changing a setting no longer reloads the page, and the cards stay in fixed columns. The address used for links in the morning email is taken from the page you are on instead of being typed.
- **Tidier show page and dashboard.** Season buttons, Cast and Details the same size, plain icons, no ticks or green, and a plain Mark watched button. The menu now runs Shows, Movies, Discover, Maybe, Coming soon, Calendar, Settings.

## [1.6.0], 2026-10-24

Nextup no longer assumes you live in the UK. Your data is untouched.

- **A country setting.** Release dates, streaming services and age ratings
  come from the country chosen on the Settings page. The first time you sign
  in, Nextup sets it from your computer's time zone, so South Africa and
  India are told apart even though both may use UK English. Nothing is looked
  up online to do this, and you can change it at any time.
- **Upgrading:** until a country is set, films show their first home release
  anywhere, and no services or age ratings appear. Sign in again, or open
  Settings and choose your country, to get them back.
- **Services and age ratings from another country are no longer shown** in
  place of your own, because you cannot use them where you are.

### Fixes from the code review

- **Changing only the username no longer lifts the starter lock.** While the
  password is still the public starter one, a new password must be chosen
  before anything else opens.
- **Wrong passwords slow you down instead of locking everyone out.** Five
  wrong tries for one username are free, then each try waits twice as long as
  the last, up to five minutes. Before, eight wrong tries could lock the owner
  out for 15 minutes.
- **Removing the TMDB key or the mail settings now needs a second click,** the
  same as removing a show or a film. Without scripting, a "Yes, remove it" box
  must be ticked.
- **The search shortcut is now Alt and /,** so it can no longer be set off by
  a single key, which catches out people using speech or screen readers.
- **Clearer button text** on the delete button and on several accent colours,
  which were too faint to read easily.
- **A bad reply from TMDB no longer breaks pages,** and one bad show no longer
  stops the refresh of all the others.
- **A mistake in the mail settings now saves none of them,** rather than
  saving some and reporting the mistake.
- **Settings opens quickly when TMDB is slow,** because the list of countries
  is kept for a week.
- **The install steps on the website now use the same locked-down setup as the
  README,** which listens only on this computer. The setup also limits memory
  and processes, and every library in the image is pinned and checked.
- **Every season is shown open on a show's page,** with no folding.
- **The dashboard draws a small chart beside each number:** rings for shows
  waiting and films, and columns for the last 12 weeks of watching.
- **A sign-in mistake shows as red words under the password box,** in space
  kept for it, so the form never moves.
- **Notes are words only,** with no tick, and links change colour on hover
  instead of being underlined. A link inside grey text is bold as well, so it
  stands out without colour.
- **Watched buttons say "Watched" or "Mark watched",** with no tick, and nothing
  in the app or on the website is green any more. The add button on Discover is a plus, and the chosen highlight colour
  is ringed rather than ticked.
- **The image is built on Python 3.14,** and the base image's own installer is
  removed because nothing uses it.

## [1.5.5], 2026-10-21

Nothing here changes how you use Nextup, and your data is untouched.

- **Two libraries updated:** Werkzeug to 3.1.9 and cryptography to 50.0.2.
- **The image is built from one exact base image,** so the same version always
  builds the same image. Every release is now scanned for known security holes
  before it is published, and a serious one stops the release.
- **The published source has its comments stripped** to keep it lean.
- **The website works on phones again.** The email section ran off the side of
  the screen, and the menu wrapped onto two rows at some widths. Links are
  easier to tap and the small print is larger.

## [1.5.4], 2026-10-18

This entry covers every release since 1.5.0 (13 September). It starts with a
round of fixes after a full code review. Nothing in them changes how you use
Nextup, and your data is untouched.

### Fixes from the code review
- **Signing in is tighter.** The first time you sign in with the starter password, Nextup makes you choose your own before it shows anything else. Changing your username or password now asks for the current password first, and a refused change alters nothing. Changing the password signs out every other browser. Eight wrong passwords from one address pause sign-in for fifteen minutes.
- **A sign-in link could send you to another website.** A specially built link could carry you off this site after you signed in. Only plain paths on Nextup are followed now.
- **Your TMDB key could be written into the sync history.** When TMDB could not be reached, the error text included the full address, key and all, and was saved. Errors no longer carry it, and any old message that does is replaced when Nextup starts.
- **A TMDB outage no longer wipes the streaming services you had saved.** A film's saved dates and services are only changed when TMDB actually answered.
- **A show is only marked fresh when every season came through.** A season TMDB would not serve used to be skipped without a word, and the show was left alone for up to two weeks. It is now reported and tried again at the next refresh.
- **The morning email cannot go out twice.** The day is claimed before sending, so a dropped connection after the mail server accepted the message does not trigger a second copy. After a real failure it waits half an hour before trying again, instead of every two minutes.
- **Buttons are safe to press twice.** Mark watched, favourite, archive and the maybe list now ask for the state you want rather than flipping the current one, so a double click no longer undoes itself. The archive button says Unarchive on an archived show.
- **Removing a film asks for a second click,** the same as removing a show does.
- **Odd values in an address or a form no longer cause an error page.** Page numbers, day counts, the calendar month and year, the mail port and the send time are all read in one careful way.
- **Nextup tells you when it cannot read a saved key.** If secret.key is lost or replaced, a notice names what cannot be read so you can enter it again, instead of the key just looking as if it was never saved.
- **Restoring a backup is clearer.** The message says when the file had no keys in it, and you stay signed in. Backup downloads are never cached by the browser, and the documentation says every backup holds your username and a password hash.
- **One clock.** Which episodes have aired, which are coming and which films are arriving now all use the same local date, so they no longer disagree for the hour after midnight in summer time.
- **Quicker pages.** The Shows page asks the database fewer questions, the Settings page no longer builds a whole backup to count rows, and Refresh everything now runs in the background instead of holding the page. A long wait asked for by TMDB is capped at ten seconds.
- **Posters are only kept if they are whole images.** Each download uses its own temporary file, and anything that is not an image or arrives cut short is thrown away.
- **The sync interval is fixed at twelve hours,** so the NEXTUP_SYNC_HOURS variable is gone. If you still have it in your compose file it does nothing, and you can delete the line.
- **Small things:** page titles and a few messages no longer use dashes, unused code was removed, and the release workflow runs the tests before it builds the image.

### Also in this release
- **The image is `ghcr.io/gh-lm/nextup`.** If your `docker-compose.yml` names a
  different image, change that one line to:

  ```yaml
      image: ghcr.io/gh-lm/nextup:latest
  ```

  Then `docker compose pull` and `docker compose up -d`. The build is the same
  and your data is untouched.
- The source, problems and suggestions are at
  <https://github.com/gh-lm/nextup>, or by email as before. Releases are built
  and published by a workflow when a version tag is pushed.
- **The season you were working in stays open.** Ticking off the last unwatched
  episode in, say, season two used to close it and open season one instead. The
  page now remembers which seasons you had open, the same way it remembers where
  you had scrolled to.
- **The morning email is dark too,** and tells a mail client it is a dark
  message, so nothing tries to invert it.
- **Fixed a broken grid on the Films page.** The Mark watched button sat beside
  the film tile instead of under it, so every film took two columns.
- **The container takes its timezone from the machine it runs on,** by mounting
  `/etc/localtime` read-only, rather than having Europe/London written into the
  compose file.
- **The website** has new documentation, runbook and security pages, a licence
  page at `/licence`, pages that use the full width of the screen, and every
  screenshot retaken on the current build.

## [1.4.0], 2026-09-06

### Dark, and only dark
- **Light mode and the appearance switch are gone**, from the app and from the
  website, along with everything behind them: the switch itself, the route and
  cookie it used, the light half of every colour token, the light half of all
  nineteen accent colours, and the button style that existed only for the
  switch. Pages stay dark whatever the browser asks for.
- Because the theme cookie has gone, **Nextup sets one cookie, not two**. The
  cookies page, the front page and the accessibility page all said two.

### Legal sub-footer
- The company details, registered office and the date the page was last updated
  sit on the left; **Privacy, Cookies, Terms, Accessibility and Complaints are
  right-justified** on the same line. They drop underneath and align left on a
  narrow screen.

### Checked
- Every page of the app and the site at every width from 3440 down to 320:
  1,660 measurements, nothing overflows, every page dark even with the browser
  asking for light, no errors.
- 162 tests, including new ones that fail if a theme switch or a light theme
  ever comes back.

## [1.3.0], 2026-09-05

This entry covers 1.1.0 to 1.3.0. It starts with a rework of the front page and ends with a security and quality pass over the whole project.

### Next up
- **Next up is one line per episode**, not one per show. A series you were eight
  behind on took a single line, so the top of the list ran out of recent things
  quickly and episodes from months back appeared inside the first twenty. It is
  now a straight run of everything that has come out and is still waiting,
  newest first, films among the episodes at the date they reached home viewing.
- **Films and episodes share one list on the front page**, each saying the day
  it came out, with a **Just out / Oldest first** switch so catching up is still
  one click.
- **Next up names the episode that has just aired**, rather than the next one
  you had not ticked off. For a show never started that was the pilot, so a
  series from years ago sat at the top.
- How far behind you are is shown once per show rather than on every line.
- An **Up to here** button on every line, and long lists are paged sixty at a
  time.
- **The page stays where it was after you tick something off,** so marking off a
  run of episodes no longer means scrolling down again after every click.

### Security
- **Dependencies updated**, clearing 16 known vulnerabilities: Flask 3.0.3 to
  3.1.3, Werkzeug 3.0.4 to 3.1.8, requests 2.32.3 to 2.34.2, cryptography 43.0.1
  to 50.0.1, gunicorn 23 to 26.
- **The sign-in page can no longer be used to bounce you off the site.** A
  `next` value beginning with two slashes is a whole other website, and it was
  being accepted. Only a plain path is now kept.
- **Security headers on every response**: a content security policy that allows
  scripts from nowhere but this app, plus `nosniff`, a referrer policy and a
  refusal to be framed.
- **The sign-in cookie can be marked Secure** with `NEXTUP_HTTPS_ONLY=1`, for
  installations where every way in is HTTPS.
- **Restoring a backup is now all or nothing.** Settings were written after the
  transaction had already been committed, so a failure at that point could leave
  you with your data back but no settings at all.
- **The container runs read-only**, with no extra privileges and no Linux
  capabilities. Gunicorn's control socket, the one thing that wanted to write
  outside the data directory, is switched off.
- **The installer is removed from the finished image.** Nothing installs
  anything at runtime, and pip and setuptools were the only remaining things a
  vulnerability scanner objected to. The image now scans clean.

### Quality
- **No typed glyphs anywhere.** Thirty pasted symbols in the app and twelve on
  the website have gone. Where the shape carried meaning, such as a rating star,
  it is now drawn; everywhere else the words already said it.
- **Tooltips are short.** Several grew with the length of a film title, one
  reaching 106 characters, which is what pushed them off a narrow screen. The
  longest is now well under half that, and the full wording is still there for a
  screen reader.
- **Everything you tap on a phone is at least 44 pixels tall.** Buttons were 31.

### Checked
- Every page measured at every width from 3440 pixels down to 320, in twenty
  pixel steps, in light and dark. No horizontal overflow anywhere.
- 161 tests, twelve of them new and covering the security fixes above.

## [1.0.0], 2026-09-03

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

## [0.13.1], 2026-09-03

This entry covers 0.4.0 to 0.13.1.

### Added
- **Backup and restore.** One button writes everything to a single JSON file:
  every show and film, everything watched, what was dismissed, your settings,
  and enough show detail that a restored copy works before it has spoken to
  TMDB. Another button reads it back. All of it or none of it, so a file that
  cannot be read leaves the database exactly as it was. Your TMDB key and mail
  password are left out of the plain download, and a second button includes them
  as plain text and says so.
- **The morning email shows the cover of each show and film,** a couple of
  sentences about it, and a link back to its page in Nextup. The artwork is
  attached to the message rather than linked, so no mail client ever calls out
  to fetch it, and the plain text version carries the same descriptions and
  links.
- A field in Settings for this Nextup's own address, which is what the links in
  the email point at.
- A setting for **when something counts as watchable.** A programme going out at
  eleven at night is not really available until the next day, so Nextup waits a
  number of days you choose before putting it in Next up, moving a film into
  Ready to watch, or mentioning it in the email. The default is one day.
- A **morning email.** Mail server details go in the Settings page, with the
  password stored encrypted alongside the TMDB key. Once a day it sends a short
  list of what has become watchable. If nothing has, nothing is sent. Buttons
  send a test message or today's email straight away.
- The email can go out at **any time of day, to the minute,** with a switch
  between the 24 hour clock and am and pm. It is rebuilt with television and
  films in separate sections and the channel or streaming service beside each,
  and it loads nothing from anywhere else.
- Show and film pages carry proper detail: the cast with photographs, the
  genres, the certificate, the tagline, the creators of a series or the director
  and writers of a film, and links out to a trailer, IMDb and a where-to-watch
  page. Shows list which UK services carry them. Cast photographs go through the
  same local cache as posters.
- Films appear on the calendar, on the day they reach home viewing, in blue
  against the yellow used for episodes, each labelled and with a key above the
  month. Films you have already seen are faded.

### Changed
- **Settings is a bento:** panels of different sizes that fit together, packed
  by measurement so none is padded out to match a neighbour. It steps from six
  columns to four, two and one, and form fields pack across the width they are
  given.
- **The accent colour, the watchable delay and the email schedule save
  themselves** the moment you change them. The mail server, the TMDB key, the
  password and the restore still need a deliberate press.
- The headline asks which episode you were on, and a line beneath types out the
  answer. With scripting off, or reduced motion asked for, the first answer
  stands.
- The website has been rebuilt on retaken screenshots, with a section of its own
  for the morning email.
- Confirmations no longer appear as a banner at the top of the page. They sit
  beside the control that caused them, and saving a setting returns you to that
  panel.
- No coloured edges anywhere, and a test walks both stylesheets and fails if
  one comes back.
- The scheduler checks every two minutes rather than every ten.

### Fixed
- Form fields were nearly invisible in dark mode. Fields now have their own
  background and an edge clearing 3 to 1 in both themes, and buttons have an
  edge you can see.
- The upload limit was two megabytes, which a large library's own backup would
  have exceeded. It is now sixty-four.
- A column with a fixed minimum width pushed the website sideways at 320 pixels.
- Anything hidden by script stayed on screen.
- On a middling screen the search box dropped to a second row and sat against
  the right edge.
- The cast strip pushed the whole page off to the right instead of scrolling
  inside its own panel.
- On a phone, the poster stayed beside the text on a show or film page, leaving
  the synopsis in a narrow column. Below 520 pixels it now sits above the text.

## [0.3.0], 2026-09-02

This entry covers 0.1.0 to 0.3.0, the first working version and the first two additions to it.

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
  either side.
- Films can go on the Maybe list too, so the tick, question mark and cross mean
  the same thing whichever page you are on.
- A **Maybe** list for shows you are curious about but are not following. They
  stay out of Next up, the calendar and Coming soon until you press Start
  watching.
- Films now show **when they reach streaming**, not just when they were in
  cinemas. Nextup reads the digital, physical and TV release dates from TMDB and
  prefers a UK one, falling back to Ireland then the US.
- Films also show **which UK services carry them**, using the JustWatch data
  TMDB publishes. Subscription, free and ad-supported services are listed;
  rental and purchase are left out.
- The Films page is now three sections: ready to watch, coming to streaming, and
  seen. A "Check now" button re-asks TMDB about any film without a date.
- Coming soon lists films landing on streaming alongside the episodes airing.
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
  no page ever points a browser at a third-party host.
- Light and dark themes, following the system by default, plus a 20-colour
  accent picker.
- Single-user sign-in with a starter account of admin / nextup that the app
  nags you to change.
