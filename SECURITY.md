# Security

## Supported versions

| Version | Supported |
|---|---|
| 1.6.10 (latest) | Yes |
| 1.6.9 | Yes |
| 1.6.8 | Yes |
| 1.6.7 | Yes |
| 1.6.6 | Yes |
| 1.6.5 | Yes |
| 1.6.4 | Yes |
| Anything older | No |

There is one line of releases and no long-term branch. A fix goes into the
next version and nowhere else, so updating is the way to get it. Updating is
two commands and your data is untouched.

## Reporting a vulnerability

Please report it privately first, not as a public issue.

1. **Preferred:** use GitHub's private vulnerability reporting on this
   repository, under the Security tab, then "Report a vulnerability". Only
   you and the maintainer can see it.
2. **Or email** <complaints@lightmorphic.com>, with "Nextup security" in the
   subject.

It helps to have what you found, how to make it happen, and the version
number from the corner of any page in the app.

## What to expect

Nextup is maintained by one person at a small company, so please be realistic
about timing. You should get a reply within a few days. If what you found is
real, the fix goes into the next release and the
[changelog](./CHANGELOG.md) says what changed. You will be credited if you
would like to be, and not if you would rather not.

Nothing you send is published while it is being looked at, and there is no
bounty programme.

## What is already in place

- Passwords are never stored, only a hash.
- The TMDB key and the mail password are encrypted before they reach the
  database. The key that encrypts them sits beside it at 0600, readable only
  by the user the app runs as, and never leaves that server.
- Forms carry no separate anti-forgery token. Protection against another
  site posting a form to Nextup rests on the session cookie being SameSite
  Lax: browsers do not send it with a form posted from another site, so such
  a request arrives signed out and is refused. Every change goes through a
  POST, never a GET.
- The login cookie is signed, HttpOnly and SameSite Lax, and marked Secure
  when `NEXTUP_HTTPS_ONLY` is set.
- The `next` parameter on the sign-in page only accepts a plain path, so it
  cannot be used to bounce someone off the site.
- The container runs as user 1000, never root, and the published compose file
  drops every Linux capability, forbids gaining new privileges, and uses a
  read-only filesystem with a small writable `/tmp`.
- No analytics, no telemetry, no third-party script. The only outbound calls
  are to TMDB and to your own mail server.

## What is not in place

Worth knowing before you decide where to put it.

- One account, no second user, and no two-factor.
- Only a simple limit on password guesses: five wrong tries for one username
  from one address are free, then each try must wait twice as long as the
  last, up to five minutes. The count lives in memory, so a restart clears
  it, and behind a proxy every visitor shares the proxy's address.
  A weak password on an open address would still be guessed in the end.
- No audit log of who signed in and when.

Nextup is a notebook for one person. Keep it on your own network or a
tailnet. If something does sit in front of it, bind the container to
`127.0.0.1`, give the proxy a certificate, and set `NEXTUP_HTTPS_ONLY=1`.
