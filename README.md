# Casa La Parrott

A static family dashboard that rebuilds itself from your calendars every 15 minutes.

- **Today / Tomorrow** agendas from everyone's calendars, color-coded by person
- **Alert bar** for "working late", early release, pickup changes (today + tomorrow)
- **Pack the bags** checklists for practices and games, with "Pack tonight" for tomorrow-morning events
- **Coming up** countdowns for birthdays, trips and other special events
- **7-day strip** at the bottom; works on a wall tablet, laptop or phone, light and dark

How it works: a GitHub Action runs `build.py` on a schedule. It downloads each calendar's
ICS feed, expands repeating events, tags them using `config.yml`, and publishes `site/` to
GitHub Pages. The page itself checks for new data every 5 minutes, so a tablet left open
stays current without anyone touching it.

## Setup (about 15 minutes)

1. **Create a GitHub repository** (private is fine) and upload this folder's contents,
   including the hidden `.github` folder.
2. **Get an ICS link for each calendar.**
   - Google Calendar: calendar *Settings → Integrate calendar → Secret address in iCal format*.
   - Apple/iCloud: share the calendar as a *Public Calendar* and copy the link (`webcal://` is fine).
   - Outlook / Microsoft 365: *Settings → Calendar → Shared calendars → Publish a calendar* → ICS link.
   - School and sports apps (TeamSnap, SportsEngine, GameChanger, school sites) usually offer
     a "subscribe" / iCal link too.
   Treat these links like passwords: anyone with one can read that calendar.
3. **Add each link as a repository secret:** *Settings → Secrets and variables → Actions →
   New repository secret*, using the names in `config.yml` — seven of them:
   `CAL_MOM`, `CAL_MOM_WORK`, `CAL_DAD`, `CAL_DAD_WORK`, `CAL_PIPER`, `CAL_PAIGE`, `CAL_FAMILY`.
   Skip any you don't have; that calendar is simply left out.
4. **Turn on Pages:** *Settings → Pages → Source: GitHub Actions*.
5. **Edit `config.yml`:** names, colors, which secrets go with which person, packing lists.
   Committing the change triggers a rebuild. Run it any time from *Actions → Update family hub
   → Run workflow*.

Your page will be at `https://<your-username>.github.io/<repo-name>/`.

## Teaching the hub about your events

Tagging is by keywords in the event **title** (set in `config.yml` under `categories`):

| Put in the title… | You get… |
|---|---|
| practice, open gym, conditioning, clinic | 🏐 Practice tag + volleyball bag list |
| game, match, tournament, invitational | 🏆 Game day tag + game bag list (tournaments add charger, lunch money, hoodie) |
| working late, late shift, `[late]` | 🌙 Alert bar on the day and the day before |
| no school, half day, early release, pickup change | 📣 Alert bar |
| home for, coming home, break, visit, move-in, parents weekend | 🏠 Paige's trips home: countdown + alert bar |
| birthday, party, trip, vacation, senior night, `[special]` | 🎉 Countdown in "Coming up" |

In an event's **description** you can also write:

- `Pack: away jersey, folding chair` (or `Bring: …`) to add items for that event
- `#special`, `#late`, `#notice`, `#home` to force a tag without changing the title

Packing rules match the title *and* location, so "Volleyball practice" and a plain
"Practice" both get Piper's bag list.

**Work calendars:** Mom's and Dad's work calendars use `only: [late]`, so the hub shows
only "working late" events from them; meetings stay private.

**Paige's calendar** uses `only: [home, special]`: her classes and college plans stay off the
board, and only trips home, breaks and special events show up. Remove that line if you'd
rather see everything.

## Showing it on the TV

Add `?tv` to the end of the address, e.g. `https://<you>.github.io/<repo>/?tv`.
TV mode locks the page to one 16:9 screen (no scrolling), sizes text for reading from the
couch, uses the dark theme, hides the mouse pointer, shows packing lists as read-only tags,
and nudges the layout a few pixels every 10 minutes so an OLED TV won't burn in.
Phones and laptops keep using the normal address with the tick-off checklists.

**Apple TV has no built-in web browser**, so the page needs a way onto the screen:

- **AirPlay from a Mac or iPad** (simplest, nothing to install): open the `?tv` address
  full-screen and mirror it to the Apple TV. The Mac or iPad has to stay on and awake.
- **A browser app for tvOS** from the App Store (search "web browser"). Quality varies; pick
  one that can stay on a single page full-screen without the screen saver kicking in.
- **A small streaming stick or mini PC with a real browser** on that TV input
  (Fire TV, Google TV, a Raspberry Pi in kiosk mode). This is the most dependable option
  for a screen that's always on.

Also add `?theme=light` or `?theme=dark` to force a theme on any screen.

## Privacy

GitHub Pages sites are public, even from a private repo: anyone who has (or guesses) the URL
can see the page. The page tells search engines not to index it, but if that's not enough:
use an unguessable repo name, set `show_locations: false`, or host `site/` somewhere with a
login (Cloudflare Pages + Access, or a computer on your home network).

## Try it locally

```bash
pip install -r requirements.txt
python demo/make_demo.py        # sample calendars dated around today
python build.py demo/config.yml # writes site/index.html
open site/index.html
```

## Good to know

- GitHub's scheduled runs can lag 5–15 minutes at busy times; "Run workflow" is instant.
- GitHub pauses scheduled workflows after 60 days with no commits to the repo. A small
  config tweak, or the "Enable workflow" button on the Actions tab, restarts it.
- If a feed fails to load, the footer says which one; the rest still update.
- Checkbox ticks in packing lists are saved on that device (per event), so the wall tablet
  remembers what's been packed.
