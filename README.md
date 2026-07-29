# AdultDVDEmpire.bundle

Plex metadata agent for Adult DVD Empire movie libraries.

**Updates & source:** [github.com/adultplexdev/AdultDVDEmpire.bundle](https://github.com/adultplexdev/AdultDVDEmpire.bundle)

---

## Install

1. Download or clone the latest release from GitHub (link above).
2. Copy/rename the folder to:

   - **Windows (default):** `%LOCALAPPDATA%\Plex Media Server\Plug-ins\AdultDVDEmpire.bundle`
   - **Custom data dir:** `<Plex data>\Plex Media Server\Plug-ins\AdultDVDEmpire.bundle`

3. Restart **Plex Media Server**.
4. Set the movie library agent to **Adult DVD Empire** (order Local Media Assets as you prefer for local posters).

---

## Matching tips

- Prefer clean names: `Title (Year).ext`.
- Weak search: use **Fix Match**, lower **Minimum match score**, or enable **debug logging** and check  
  `Plex Media Server\Logs\PMS Plugin Logs\com.plexapp.agents.adultdvdempire.log`.
- Same title on DVD / Blu-ray / VOD: set **Preferred media format** so duplicates resolve the way you want.
- Site HTML changes can break scrapers - if matching suddenly fails, check GitHub for an update.

---

## Privacy & disclaimer

Plex may collect library and viewing data. This agent contacts Adult DVD Empire over the network for metadata and artwork.

This project is **not affiliated** with Adult DVD Empire / AdultEmpire and is not endorsed by them.

---

## 2026-07-29 - v1.1.2 Plex sandbox crash fix

### Bug fix
- **Metadata update aborted with no title/poster/art** - Plex Framework does not define `getattr` / `hasattr`. Update hit `global name 'getattr' is not defined` and exited before writing any fields. Replaced with direct attribute access and try/except (same pattern as the original agent).

---

## 2026-07-25 - Reliability & code quality rewrite

### Bug fixes
- **Studio collection no longer wiped** - `collections.clear()` used to run *after* adding the studio collection, so `studioascollection` never stuck. Collections are rebuilt once (series + optional studio).
- **Safer prefs parsing** - invalid `goodscore` / screenshot counts no longer crash search/update.
- **Series titles** - quote parsing no longer assumes `"Title"` always has index `[1]`.
- **Search matching** - proper substring checks instead of fragile `.count()` logic.
- **HTTP cache** - `Start()` no longer calls `HTTP.ClearCache()` on every load (that forced cold fetches). Uses `CACHE_1DAY`.

### Search improvements
- Cleans years, DVD/VOD markers, and date suffixes from filenames before query/scoring.
- Normalizes `Vol.` / `#` volume markers for better fuzzy matches.
- Year match boost / mismatch penalty when `media.year` is known.
- Token-overlap scoring for reordered titles.
- Dedupes by **title + year** (not title alone), preferring DVD → Blu-ray → VOD.
- Format tag shown in match picker: `[DVD]`, `[BLURAY]`, `[VOD]`.

### Metadata improvements
- Title taken from the product page (`h1` / cover) with media title as fallback.
- Duration parsed from Length / Runtime when present.
- Absolute URL normalization for posters, galleries, and actor thumbs.
- Cast photos: removed per-actor **HEAD** probes (slow); URLs still set for Plex.
- Posters/art skipped when the same URL is already stored.
- Extra XPath fallbacks for title, poster, tagline, summary, genres, rating, directors.
- Runtime, series, and studio collections applied more consistently.

### Code structure
- Shared helpers: prefs, logging, xpath fallbacks, date/runtime parsing, scoring.
- Debug logs prefixed with `[ADE]` when **Enable debug logging** is on.

---

## Earlier upstream notes

20250716 - Complete rebuild of the whole agent.
- New way of search if files are missing "Vol." or "#" in filenames.
- Rework of the metadata gathering.

20250713 - Fixed category lookup and some default settings to give more results.

20241217 - Fixed new ageConfirmation requirement cookie.

---

## Preferences (agent menu)

Updated agent UI: short labels, enums end with `": "`, related options
grouped.

| Setting | Type | Default |
|---------|------|---------|
| Minimum match score | enum | 96 |
| Search result date format | enum | Year (YYYY) |
| Preferred media format | enum | DVD |
| Show media format in search results | bool | on |
| Title source | enum | Adult DVD Empire page |
| Prefer production year when release year is much later | bool | on |
| Use series / studio name as collection | bool | series on, studio off |
| Genres to ignore (separated by \|) | text | _(empty)_ |
| Download screenshots / gallery as art | bool | off |
| Maximum screenshots / gallery images | enum | 3 |
| Enable debug logging | bool | off |

