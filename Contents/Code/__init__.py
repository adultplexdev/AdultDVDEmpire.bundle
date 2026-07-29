# AdultDVDEmpire Plex Metadata Agent
# Update: 29 July 2026 (v1.1.2)
# Description: Plex metadata agent for Adult DVD Empire (movies).
#              Search + metadata update with format prioritization,
#              safer prefs parsing, and more reliable page parsing.
#              Avoid getattr/hasattr (not defined in Plex Framework sandbox).

import re
import datetime
import random

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = 'https://www.adultdvdempire.com'
SEARCH_URL_TEMPLATE = BASE_URL + '/allsearch/search?view=list&q=%s'
MOVIE_INFO_URL = BASE_URL + '/%s/'

INITIAL_SCORE = 100
DEFAULT_GOOD_SCORE = 96
HTTP_TIMEOUT = 15
MAX_IMAGE_COUNT = 50

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/138.0.0.0 Safari/537.36'
)
COOKIE_AGE_CONFIRMED = 'ageConfirmed=true'

TITLE_FORMATS = r'\(DVD\)|\(Blu-Ray\)|\(Blu-ray\)|\(BR\)|\(VOD\)|\(Video On Demand\)'
MOVIE_ID_REGEX = r'/(\d+)/'
ACTOR_ID_REGEX = r'/(\d{3,8})/'
YEAR_IN_PARENS = r'\((\d{4})\)'
DATE_IN_BRACKETS = r'\[\d{4}-\d{2}-\d{2}\]'
VOL_NUMBER = r'\s*(?:vol\.?|#)\s*(\d+)\s*$'
# Tuple (not frozenset): Plex Framework sandbox does not expose frozenset
EXCLUDED_CAST_TERMS = ('bio', 'interview')

# Default format priority (lower = better). Overridden by preferredformat pref.
MEDIA_FORMAT_PRIORITIES = {'dvd': 0, 'bluray': 1, 'vod': 2, 'NA': 3}

# Pref enum helpers
DATEFORMAT_YEAR = 'Year (YYYY)'
DATEFORMAT_FULL = 'Full date (YYYY-MM-DD)'
DATEFORMAT_NONE = 'None'
TITLESOURCE_PAGE = 'Adult DVD Empire page'
TITLESOURCE_FILE = 'Keep filename / existing title'

# Search result containers (first match wins)
SEARCH_RESULTS_XPATHS = [
    '//div[contains(@class,"row list-view-item")]',
    '//div[contains(@class,"list-view-item")]',
    '//div[contains(@class,"product-card")]',
]

TITLE_XPATHS = [
    './/a[contains(@label,"Title")]',
    './/a[@href and contains(@class,"title")]',
    './/h3//a[@href]',
    './/a[contains(@href,"/") and @title]',
]

RELEASE_DATE_XPATHS = [
    './/small[contains(translate(text(),"RELEASED","released"),"released")]/following-sibling::text()[1]',
    './/small[contains(text(),"released")]/following-sibling::text()[1]',
    './/span[contains(@class,"release-date")]/text()',
]

PRODUCTION_YEAR_XPATHS = [
    './/a[contains(@aria-label, "View")]/following-sibling::text()[1]',
    './/span[contains(@class,"production-year")]/text()',
]

MEDIA_FORMAT_DVD_XPATHS = [
    './/div[contains(@class,"list-view-item-controls_content-type") and contains(text(),"DVD")]',
    './/span[contains(@class,"format") and contains(text(),"DVD")]',
    './/*[contains(text(),"DVD") and (contains(@class,"format") or contains(@class,"content-type"))]',
]

MEDIA_FORMAT_BLURAY_XPATHS = [
    './/div[contains(@class,"list-view-item-controls_content-type") and (contains(text(),"Blu-ray") or contains(text(),"Blu-Ray"))]',
    './/span[contains(@class,"format") and (contains(text(),"Blu-ray") or contains(text(),"Blu-Ray") or contains(text(),"BR"))]',
]

MEDIA_FORMAT_VOD_XPATHS = [
    './/div[contains(@class,"list-view-item-controls_content-type") and contains(text(),"Video On Demand")]',
    './/span[contains(@class,"format") and contains(text(),"VOD")]',
    './/*[contains(text(),"Video On Demand") or contains(text(),"VOD")]',
]

PRODUCT_INFO_XPATHS = [
    '//ul[@class="list-unstyled m-b-2"]',
    '//ul[contains(@class,"list-unstyled") and contains(@class,"m-b")]',
]

PAGE_TITLE_XPATHS = [
    '//h1[contains(@class,"title")]//text()',
    '//h1//text()',
    '//*[@id="front-cover"]/img/@title',
    '//*[@id="front-cover"]/img/@alt',
]

POSTER_XPATHS = [
    '//*[@id="front-cover"]/img',
    '//img[contains(@class,"front-cover")]',
    '//div[contains(@class,"front-cover")]//img',
]

TAGLINE_XPATHS = [
    '//h2[contains(@class, "test")]/text()',
    '//p[contains(@class,"Tagline")]//text()',
    '//div[contains(@class,"tagline")]//text()',
]

SUMMARY_XPATHS = [
    '//div[@class="synopsis-content"]/p',
    '//div[contains(@class,"synopsis")]//p',
    '//div[@id="synopsis"]//p',
]

CAST_UPPER_XPATH = '//div[@class="hover-popover-detail"]/img'
CAST_LOWER_XPATH = '//a[contains(@label, "Performers - detail")]'
DIRECTOR_XPATHS = [
    '//div[contains(@class, "movie-page__content-tags__directors")]//a/text()',
    '//a[contains(@label,"Director")]/text()',
    '//small[contains(text(),"Director")]/following-sibling::a/text()',
]
SERIES_XPATHS = [
    '//a[@label="Series"]/text()',
    '//a[contains(@label,"Series")]/text()',
]
GENRES_XPATHS = [
    '//ul[@class="list-unstyled m-b-2"]//a[@label="Category"]/text()',
    '//a[@label="Category"]/text()',
    '//a[contains(@label,"Category")]/text()',
]
RATING_XPATHS = [
    '//span[@class="rating-stars-avg"]/text()',
    '//span[contains(@class,"rating-stars-avg")]/text()',
    '//span[contains(@class,"rating")]/text()',
]
SCREENSHOTS_XPATH = '//a[contains(@rel, "scenescreenshots")]'
GALLERY_XPATHS = [
    '//div[@class="user-action"]/a[contains(@class, "gallery")]',
    '//a[contains(@class,"gallery") and contains(@href,"gallery")]',
]
GALLERY_IMAGES_XPATH = '//div/a[contains(@class, "thumb fancy")]'

# Plex Framework agents run on Python 2.7 (unicode + str both exist)
try:
    STRING_TYPES = (str, unicode)
except NameError:
    STRING_TYPES = (str,)


# ---------------------------------------------------------------------------
# Framework lifecycle
# ---------------------------------------------------------------------------

def Start():
    # Cache pages for a day - do not ClearCache on every start (was very costly).
    HTTP.CacheTime = CACHE_1DAY
    HTTP.Headers['User-agent'] = USER_AGENT
    HTTP.Headers['Cookie'] = COOKIE_AGE_CONFIRMED
    Log('AdultDVDEmpire agent started')


def ValidatePrefs():
    # Prefs UI saves; nothing to reject - values are normalized when read.
    try:
        Log('[ADE] Preferences saved / validated')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ADEAgent(Agent.Movies):
    name = 'Adult DVD Empire'
    languages = [Locale.Language.English]
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    # ------------------------------------------------------------------
    # Prefs / logging helpers
    # ------------------------------------------------------------------

    def debug_enabled(self):
        try:
            return bool(Prefs['debug'])
        except Exception:
            return False

    def log(self, message):
        if self.debug_enabled():
            Log('[ADE] %s' % message)

    def pref_raw(self, key, default=None):
        try:
            value = Prefs[key]
            if value is None:
                return default
            return value
        except Exception:
            return default

    def pref_bool(self, key, default=False):
        try:
            value = Prefs[key]
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            # Section headers and unused toggles may be stored as strings
            return str(value).lower() in ('true', '1', 'yes')
        except Exception:
            return default

    def pref_text(self, key, default=''):
        value = self.pref_raw(key, default)
        if value is None:
            return default
        return str(value)

    def pref_int(self, key, default, minimum=None, maximum=None):
        """Parse int from free text or enum labels like '96 - Default' / '3'."""
        raw = self.pref_text(key, str(default))
        value = default
        try:
            # Prefer first integer token in the string
            match = re.search(r'-?\d+', raw)
            if match:
                value = int(match.group(0))
            else:
                value = int(raw.strip())
        except Exception:
            value = default
        if minimum is not None and value < minimum:
            value = default
        if maximum is not None and value > maximum:
            value = default
        return value

    def pref_list(self, key, separator='|'):
        try:
            raw = Prefs[key] or ''
        except Exception:
            raw = ''
        return [part.strip().lower() for part in raw.split(separator) if part.strip()]

    def format_priorities(self):
        """Return format priority map based on preferredformat pref."""
        preferred = self.pref_text('preferredformat', 'DVD').strip().lower()
        # Base order then put preferred first
        order = ['dvd', 'bluray', 'vod', 'NA']
        if preferred.startswith('blu'):
            order = ['bluray', 'dvd', 'vod', 'NA']
        elif preferred.startswith('vod'):
            order = ['vod', 'dvd', 'bluray', 'NA']
        elif preferred.startswith('no'):
            # Keep default DVD-first but treat all known formats equally-ish
            order = ['dvd', 'bluray', 'vod', 'NA']
        else:
            # DVD (default)
            order = ['dvd', 'bluray', 'vod', 'NA']
        return dict((name, idx) for idx, name in enumerate(order))

    def match_date_mode(self):
        """How to annotate dates on search result names."""
        raw = self.pref_text('dateformat', DATEFORMAT_YEAR)
        raw_l = raw.lower().strip()
        # Backward compatible with old bool prefs
        if raw_l in ('true', '1', 'yes') or 'year' in raw_l:
            return 'year'
        if raw_l in ('false', '0', 'no') or 'full' in raw_l or 'yyyy-mm-dd' in raw_l:
            return 'full'
        if 'none' in raw_l:
            return 'none'
        return 'year'

    # ------------------------------------------------------------------
    # DOM / URL helpers
    # ------------------------------------------------------------------

    def first_nodes(self, root, xpaths):
        """Return first non-empty xpath result list from candidates."""
        if root is None:
            return []
        if isinstance(xpaths, STRING_TYPES):
            xpaths = [xpaths]
        elif not isinstance(xpaths, (list, tuple)):
            xpaths = [xpaths]
        for xpath in xpaths:
            try:
                nodes = root.xpath(xpath)
                if nodes:
                    return nodes
            except Exception:
                continue
        return []

    def first_node(self, root, xpaths):
        nodes = self.first_nodes(root, xpaths)
        return nodes[0] if nodes else None

    def first_text(self, root, xpaths, join_all=False):
        nodes = self.first_nodes(root, xpaths)
        if not nodes:
            return None
        if join_all:
            parts = []
            for node in nodes:
                text = self.node_text(node)
                if text:
                    parts.append(text)
            joined = ' '.join(parts).strip()
            return joined or None
        return self.node_text(nodes[0])

    def node_text(self, node):
        if node is None:
            return None
        try:
            # Attribute results from xpath are already strings.
            # Plex sandbox has no hasattr/getattr - probe with try/except.
            if isinstance(node, STRING_TYPES):
                text = node
            else:
                try:
                    text = node.text_content()
                except Exception:
                    text = str(node)
            text = text.strip()
            text = re.sub(r'\s+', ' ', text).strip()
            return text or None
        except Exception:
            return None

    def absolute_url(self, url):
        if not url:
            return None
        url = url.strip()
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return BASE_URL + url
        if url.startswith('http://') or url.startswith('https://'):
            return url
        return BASE_URL + '/' + url.lstrip('/')

    def fetch_html(self, url):
        self.log('GET %s' % url)
        response = HTTP.Request(url, timeout=HTTP_TIMEOUT)
        return HTML.ElementFromString(response)

    # ------------------------------------------------------------------
    # Title / scoring helpers
    # ------------------------------------------------------------------

    def clean_title(self, title):
        if not title:
            return ''
        title = re.sub(TITLE_FORMATS, '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'\s*' + DATE_IN_BRACKETS, '', title).strip()
        title = re.sub(r'\s*' + YEAR_IN_PARENS, '', title).strip()
        # "Something, The" -> "The Something"
        if re.search(r',\s*The\s*$', title, re.IGNORECASE):
            title = 'The ' + re.sub(r',\s*The\s*$', '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'\s+', ' ', title).strip(' -_')
        return title

    def extract_year_from_text(self, text):
        if not text:
            return None
        match = re.search(YEAR_IN_PARENS, text)
        if match:
            try:
                year = int(match.group(1))
                if 1900 <= year <= 2100:
                    return year
            except Exception:
                pass
        return None

    def normalize_for_scoring(self, title):
        title = (title or '').lower().strip()
        title = self.clean_title(title).lower()
        # Treat "Vol. 2" / "#2" as bare number for better fuzzy match
        title = re.sub(VOL_NUMBER, r' \1', title, flags=re.IGNORECASE)
        title = re.sub(r'[^a-z0-9\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    def score_titles(self, search_title, movie_title, media_year=None, result_year=None):
        norm_search = self.normalize_for_scoring(search_title)
        norm_movie = self.normalize_for_scoring(movie_title)
        if not norm_search or not norm_movie:
            return 0

        distance = Util.LevenshteinDistance(norm_search, norm_movie)
        score = INITIAL_SCORE - distance

        if norm_search == norm_movie:
            score = 100
        elif norm_search in norm_movie or norm_movie in norm_search:
            # Substring match (e.g. missing Vol. in filename)
            score = max(score, 98)
        else:
            # Token overlap boost for reordered words
            search_tokens = set(norm_search.split())
            movie_tokens = set(norm_movie.split())
            if search_tokens and movie_tokens:
                overlap = float(len(search_tokens & movie_tokens)) / float(len(search_tokens | movie_tokens))
                if overlap >= 0.8:
                    score = max(score, int(90 + (overlap * 10)))

        if media_year and result_year:
            try:
                if int(media_year) == int(result_year):
                    score = min(100, score + 5)
                elif abs(int(media_year) - int(result_year)) > 2:
                    score = max(0, score - 5)
            except Exception:
                pass

        return max(0, min(100, score))

    def parse_date_string(self, text):
        if not text:
            return None
        text = text.strip()
        for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%b %d, %Y', '%B %d, %Y', '%Y'):
            try:
                return datetime.datetime.strptime(text, fmt)
            except ValueError:
                continue
        # Fallback: Datetime.ParseDate if available
        try:
            parsed = Datetime.ParseDate(text)
            if parsed:
                return parsed
        except Exception:
            pass
        return None

    def parse_runtime_minutes(self, text):
        """Parse ADE length strings into minutes."""
        if not text:
            return None
        text = text.strip().lower()
        hours = 0
        minutes = 0
        h_match = re.search(r'(\d+)\s*h(?:r|our)?s?', text)
        m_match = re.search(r'(\d+)\s*m(?:in)?s?', text)
        if h_match:
            hours = int(h_match.group(1))
        if m_match:
            minutes = int(m_match.group(1))
        if hours or minutes:
            return hours * 60 + minutes
        only = re.search(r'^(\d+)$', text)
        if only:
            value = int(only.group(1))
            # ADE sometimes stores minutes as bare number
            if value < 1000:
                return value
        return None

    # ------------------------------------------------------------------
    # Search result parsing
    # ------------------------------------------------------------------

    def element_title_and_url(self, movie_element):
        for xpath in TITLE_XPATHS:
            try:
                elements = movie_element.xpath(xpath)
            except Exception:
                continue
            for title_element in elements:
                try:
                    href = title_element.get('href')
                    if not href or '/' not in href:
                        continue
                    movie_title = self.node_text(title_element)
                    if not movie_title:
                        try:
                            movie_title = (title_element.get('title') or '').strip() or None
                        except Exception:
                            movie_title = None
                    if not movie_title:
                        continue
                    return movie_title, href
                except Exception:
                    continue
        return None, None

    def detect_media_format(self, movie_element):
        if self.first_node(movie_element, MEDIA_FORMAT_DVD_XPATHS):
            return 'dvd'
        if self.first_node(movie_element, MEDIA_FORMAT_BLURAY_XPATHS):
            return 'bluray'
        if self.first_node(movie_element, MEDIA_FORMAT_VOD_XPATHS):
            return 'vod'
        return 'NA'

    def parse_movie_result(self, movie_element, search_title, media_year=None):
        try:
            raw_title, movie_url = self.element_title_and_url(movie_element)
            if not raw_title or not movie_url:
                self.log('Skipping result: missing title or URL')
                return None

            movie_title = self.clean_title(raw_title)
            if not movie_title:
                return None

            movie_id_match = re.search(MOVIE_ID_REGEX, movie_url)
            if not movie_id_match:
                self.log('No movie ID in URL: %s' % movie_url)
                return None
            movie_id = movie_id_match.group(1)

            # Release date
            release_date = None
            release_text = self.first_text(movie_element, RELEASE_DATE_XPATHS)
            if release_text:
                parsed = self.parse_date_string(release_text)
                if parsed:
                    release_date = parsed.strftime('%Y-%m-%d')

            # Production year
            production_year = None
            year_text = self.first_text(movie_element, PRODUCTION_YEAR_XPATHS)
            if year_text:
                year_match = re.search(r'(\d{4})', year_text)
                if year_match:
                    production_year = year_match.group(1)
            if not production_year and release_date:
                production_year = release_date[:4]

            result_year = None
            try:
                result_year = int(production_year) if production_year else None
            except Exception:
                result_year = None

            media_type = self.detect_media_format(movie_element)
            score = self.score_titles(search_title, movie_title, media_year, result_year)

            # Display name for match picker
            display_name = movie_title
            date_mode = self.match_date_mode()
            if date_mode == 'year':
                year_to_show = production_year
                if not year_to_show and release_date:
                    year_to_show = release_date[:4]
                if year_to_show:
                    display_name = '%s (%s)' % (movie_title, year_to_show)
            elif date_mode == 'full' and release_date:
                display_name = '%s [%s]' % (movie_title, release_date)

            # Annotate format so users can distinguish DVD vs VOD
            if self.pref_bool('showformat', True) and media_type in ('dvd', 'bluray', 'vod'):
                label = {'dvd': 'DVD', 'bluray': 'Blu-ray', 'vod': 'VOD'}.get(media_type, media_type.upper())
                display_name = '%s [%s]' % (display_name, label)

            return {
                'id': movie_id,
                'name': movie_title,
                'display_name': display_name,
                'format': media_type,
                'score': score,
                'release_date': release_date,
                'production_year': production_year,
                'url': movie_url,
            }
        except Exception as e:
            self.log('Error parsing movie result: %s' % e)
            return None

    def search(self, results, media, lang):
        goodscore = self.pref_int('goodscore', DEFAULT_GOOD_SCORE, minimum=1, maximum=100)

        # Plex sandbox: no getattr/hasattr - access attributes directly.
        title = media.name or ''
        if not title:
            try:
                if media.primary_metadata:
                    title = media.primary_metadata.title or ''
            except Exception:
                title = ''

        media_year = None
        try:
            if media.year:
                media_year = int(media.year)
        except Exception:
            media_year = self.extract_year_from_text(title)

        search_title = self.clean_title(title)
        if not search_title:
            self.log('Search aborted: empty title')
            return

        # Query without year / format noise for broader site search
        query_text = search_title
        query = String.URLEncode(String.StripDiacritics(query_text.replace('-', ' ')))
        search_url = SEARCH_URL_TEMPLATE % query
        self.log('Search title=%r year=%s url=%s' % (search_title, media_year, search_url))

        try:
            html = self.fetch_html(search_url)
            movie_results = []
            for xpath in SEARCH_RESULTS_XPATHS:
                try:
                    movies = html.xpath(xpath)
                except Exception:
                    movies = []
                if not movies:
                    continue
                self.log('Using search xpath %s (%d hits)' % (xpath, len(movies)))
                for movie_element in movies:
                    result = self.parse_movie_result(movie_element, search_title, media_year)
                    if result:
                        movie_results.append(result)
                break

            # Prefer best format per title+year, keep distinct years separate
            format_rank = self.format_priorities()
            unique_results = []
            seen_keys = set()
            ordered = sorted(
                movie_results,
                key=lambda x: (
                    x['name'].lower(),
                    x.get('production_year') or '',
                    format_rank.get(x['format'], 99),
                    -x['score'],
                ),
            )
            for result in ordered:
                key = (result['name'].lower(), result.get('production_year') or result.get('release_date') or '')
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                unique_results.append(result)

            added = 0
            search_lower = search_title.lower()
            for result in unique_results:
                name_lower = result['name'].lower()
                display_lower = result['display_name'].lower()
                # Exact/substring title hits always shown; else require goodscore
                title_hit = (
                    search_lower == name_lower
                    or search_lower in name_lower
                    or name_lower in search_lower
                    or search_lower in display_lower
                )
                if title_hit or result['score'] >= goodscore:
                    # Exact title match: present as perfect score for picker UX
                    final_score = 100 if search_lower == name_lower else result['score']
                    if title_hit and final_score < 98:
                        final_score = max(final_score, 98)
                    result_year = None
                    if result.get('production_year') and str(result['production_year']).isdigit():
                        result_year = int(result['production_year'])
                    if result_year is not None:
                        results.Append(MetadataSearchResult(
                            id=result['id'],
                            name=result['display_name'],
                            score=final_score,
                            lang=lang,
                            year=result_year,
                        ))
                    else:
                        results.Append(MetadataSearchResult(
                            id=result['id'],
                            name=result['display_name'],
                            score=final_score,
                            lang=lang,
                        ))
                    added += 1

            results.Sort('score', descending=True)
            self.log('Search completed: %d parsed, %d unique, %d added' % (
                len(movie_results), len(unique_results), added
            ))
        except Exception as e:
            self.log('Search failed: %s' % e)

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def extract_product_info(self, html):
        product_info = {}
        for xpath in PRODUCT_INFO_XPATHS:
            try:
                info_elements = html.xpath(xpath)
            except Exception:
                info_elements = []
            for info_element in info_elements:
                try:
                    local = {}
                    for item in info_element.xpath('./li'):
                        label_elements = item.xpath('./small')
                        if not label_elements:
                            continue
                        label_text = label_elements[0].text_content().strip()
                        key = label_text.rstrip(':').strip()
                        value = item.text_content()
                        if label_text in value:
                            value = value.replace(label_text, '', 1)
                        value = re.sub(r'\s+', ' ', value).strip()
                        if key and value:
                            local[key] = value
                    if local:
                        product_info.update(local)
                except Exception as e:
                    self.log('Product info block failed: %s' % e)
            if product_info:
                break
        if not product_info:
            self.log('No product info extracted')
        return product_info

    def extract_directors(self, html):
        names = []
        seen = set()
        for xpath in DIRECTOR_XPATHS:
            try:
                nodes = html.xpath(xpath)
            except Exception:
                nodes = []
            for node in nodes:
                name = self.node_text(node)
                if not name:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                names.append(name)
            if names:
                break
        return names

    def extract_series_title(self, html):
        text = self.first_text(html, SERIES_XPATHS)
        if not text:
            return None
        # Common ADE forms: Series "Title" / "Title" Series / Title
        quoted = re.findall(r'"([^"]+)"', text)
        if quoted:
            return quoted[0].strip()
        text = re.sub(r'^\s*series\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
        return text or None

    def extract_cast(self, html):
        actors = []
        photo_base_url = None
        featured_actors = set()
        director_names = set(name.lower() for name in self.extract_directors(html))

        try:
            for actor_elem in html.xpath(CAST_UPPER_XPATH):
                try:
                    actor_name = actor_elem.xpath('./@title')[0].strip()
                    if not actor_name or actor_name.lower() in director_names:
                        continue
                    if actor_name.lower() in EXCLUDED_CAST_TERMS:
                        continue
                    thumb_src = actor_elem.xpath('./@src')[0]
                    abs_thumb = self.absolute_url(thumb_src)
                    if abs_thumb and not photo_base_url:
                        photo_base_url = abs_thumb.rsplit('/', 1)[0] + '/'
                    # Prefer full-size when ADE uses h.jpg thumbs
                    actor_photo = abs_thumb.replace('h.jpg', '.jpg') if abs_thumb else None
                    featured_actors.add(actor_name.lower())
                    actors.append({'name': actor_name, 'photo': actor_photo})
                except Exception:
                    continue

            for actor_elem in html.xpath(CAST_LOWER_XPATH):
                try:
                    parent_li = actor_elem.getparent()
                    if parent_li is not None:
                        label_texts = parent_li.xpath('./small/text()')
                        if label_texts and 'Director' in label_texts[0]:
                            continue
                    actor_name = self.node_text(actor_elem)
                    if not actor_name:
                        continue
                    if actor_name.lower() in director_names:
                        continue
                    if actor_name.lower() in featured_actors:
                        continue
                    if actor_name.lower() in EXCLUDED_CAST_TERMS:
                        continue
                    profile_url = actor_elem.xpath('./@href')[0]
                    actor_id_match = re.search(ACTOR_ID_REGEX, profile_url)
                    actor_photo = None
                    # Do not HEAD-check every photo (was very slow). Use constructed URL;
                    # Plex ignores missing images.
                    if actor_id_match and photo_base_url:
                        actor_photo = photo_base_url + actor_id_match.group(1) + '.jpg'
                    featured_actors.add(actor_name.lower())
                    actors.append({'name': actor_name, 'photo': actor_photo})
                except Exception:
                    continue
        except Exception as e:
            self.log('Cast extraction failed: %s' % e)
        return actors

    def set_poster(self, metadata, html):
        poster_img = self.first_node(html, POSTER_XPATHS)
        if poster_img is None:
            self.log('Poster not found')
            return
        poster_url = self.absolute_url(poster_img.get('src') or poster_img.get('data-src'))
        if not poster_url:
            return
        # Skip re-download when poster already keyed
        if poster_url in metadata.posters:
            self.log('Poster already present: %s' % poster_url)
            return
        poster_data = HTTP.Request(poster_url, timeout=HTTP_TIMEOUT)
        metadata.posters[poster_url] = Proxy.Preview(poster_data)
        self.log('Poster set: %s' % poster_url)

    def set_art_from_links(self, metadata, links, count, kind):
        if not links or count < 1:
            return
        indices = list(range(len(links)))
        if len(indices) > count:
            indices = random.sample(indices, count)
        for idx in indices:
            try:
                href = links[idx].attrib.get('href')
                image_url = self.absolute_url(href)
                if not image_url:
                    continue
                if image_url in metadata.art:
                    continue
                image_data = HTTP.Request(image_url, timeout=HTTP_TIMEOUT)
                metadata.art[image_url] = Proxy.Media(image_data)
                self.log('%s art set: %s' % (kind, image_url))
            except Exception as e:
                self.log('%s art failed: %s' % (kind, e))

    def page_title(self, html, fallback):
        # Prefer joined h1 text (ADE sometimes splits spans)
        title = self.first_text(html, PAGE_TITLE_XPATHS, join_all=True)
        if title:
            return self.clean_title(title)
        return self.clean_title(fallback or '')

    def update(self, metadata, media, lang):
        studio_as_collection = self.pref_bool('studioascollection', False)
        series_as_collection = self.pref_bool('seriesascollection', True)
        use_production_date = self.pref_bool('useproductiondate', True)
        pull_screens = self.pref_bool('pullscreens', False)
        pull_gallery = self.pref_bool('pullgallery', False)
        pull_screens_count = self.pref_int('pullscreenscount', 3, minimum=1, maximum=MAX_IMAGE_COUNT - 1)
        pull_gallery_count = self.pref_int('pullgallerycount', 3, minimum=1, maximum=MAX_IMAGE_COUNT - 1)
        ignore_genres = set(self.pref_list('ignoregenres'))
        title_source = self.pref_text('titlesource', TITLESOURCE_PAGE)

        try:
            page_url = MOVIE_INFO_URL % metadata.id
            page_html = self.fetch_html(page_url)

            # Title: ADE page (default) or keep filename / existing title.
            # Plex sandbox has no getattr - read media attrs with try/except.
            media_title = ''
            try:
                media_title = media.title or ''
            except Exception:
                media_title = ''
            if not media_title:
                try:
                    media_title = media.name or ''
                except Exception:
                    media_title = ''
            if TITLESOURCE_FILE.lower() in title_source.lower() or 'filename' in title_source.lower():
                metadata.title = self.clean_title(media_title) or self.page_title(page_html, media_title)
            else:
                metadata.title = self.page_title(page_html, media_title) or self.clean_title(media_title)

            # Poster
            try:
                self.set_poster(metadata, page_html)
            except Exception as e:
                self.log('Poster update failed: %s' % e)

            # Tagline
            tagline = self.first_text(page_html, TAGLINE_XPATHS, join_all=True)
            if tagline:
                metadata.tagline = tagline
            else:
                self.log('Tagline not found')

            # Summary
            summary_node = self.first_node(page_html, SUMMARY_XPATHS)
            if summary_node is not None:
                summary = self.node_text(summary_node)
                if summary:
                    metadata.summary = summary
            else:
                self.log('Summary not found')

            details = self.extract_product_info(page_html)
            self.log('Product info keys: %s' % list(details.keys()))

            if 'Rating' in details:
                metadata.content_rating = details['Rating']

            studio_name = details.get('Studio')
            if studio_name:
                metadata.studio = studio_name

            # Release date / year
            if 'Released' in details:
                try:
                    parsed = self.parse_date_string(details['Released'])
                    if parsed is not None:
                        # datetime has .date(); date objects do not (Plex: no hasattr)
                        try:
                            metadata.originally_available_at = parsed.date()
                        except Exception:
                            metadata.originally_available_at = parsed
                        metadata.year = metadata.originally_available_at.year
                except Exception as e:
                    self.log('Release date update failed: %s' % e)

            if use_production_date and 'Production Year' in details:
                try:
                    prod_year = int(re.search(r'(\d{4})', details['Production Year']).group(1))
                    if prod_year > 1900:
                        if not metadata.year or (metadata.year - prod_year) > 1:
                            metadata.year = prod_year
                            metadata.originally_available_at = datetime.date(prod_year, 1, 1)
                except Exception as e:
                    self.log('Production year update failed: %s' % e)

            # Runtime (minutes -> ms)
            length_value = details.get('Length') or details.get('Run Time') or details.get('Runtime')
            minutes = self.parse_runtime_minutes(length_value) if length_value else None
            if minutes:
                try:
                    metadata.duration = int(minutes) * 60 * 1000
                    self.log('Duration set to %d minutes' % minutes)
                except Exception as e:
                    self.log('Duration update failed: %s' % e)

            # Cast
            metadata.roles.clear()
            for actor in self.extract_cast(page_html):
                role = metadata.roles.new()
                role.name = actor['name']
                if actor.get('photo'):
                    role.photo = actor['photo']

            # Directors
            directors = self.extract_directors(page_html)
            if directors:
                metadata.directors.clear()
                for name in directors:
                    director = metadata.directors.new()
                    director.name = name

            # Collections: rebuild once so studio is not wiped by a later clear()
            metadata.collections.clear()
            if series_as_collection:
                series_title = self.extract_series_title(page_html)
                if series_title:
                    metadata.collections.add(series_title)
            if studio_as_collection and studio_name:
                metadata.collections.add(studio_name)

            # Genres / categories
            metadata.genres.clear()
            genre_nodes = []
            for xpath in GENRES_XPATHS:
                try:
                    genre_nodes = page_html.xpath(xpath)
                except Exception:
                    genre_nodes = []
                if genre_nodes:
                    break
            for genre_name in genre_nodes:
                genre_name = self.node_text(genre_name)
                if not genre_name:
                    continue
                if genre_name.lower() in ignore_genres:
                    continue
                metadata.genres.add(genre_name)

            # Community rating (ADE ~0-5 stars -> Plex 0-10)
            try:
                rating_text = self.first_text(page_html, RATING_XPATHS)
                if rating_text:
                    self.log('Found rating text: %s' % rating_text)
                    rating_numbers = re.findall(r'\d+\.?\d*', rating_text)
                    if rating_numbers:
                        metadata.rating = float(rating_numbers[0]) * 2.0
                    else:
                        metadata.rating = 0.0
                else:
                    metadata.rating = 0.0
            except Exception as e:
                self.log('Rating update failed: %s' % e)
                metadata.rating = 0.0

            # Screenshots
            if pull_screens:
                try:
                    screenshot_links = page_html.xpath(SCREENSHOTS_XPATH)
                    self.set_art_from_links(metadata, screenshot_links, pull_screens_count, 'Screenshot')
                except Exception as e:
                    self.log('Screenshots update failed: %s' % e)

            # Gallery
            if pull_gallery:
                try:
                    gallery_link = self.first_node(page_html, GALLERY_XPATHS)
                    if gallery_link is not None:
                        gallery_page_url = self.absolute_url(gallery_link.attrib.get('href'))
                        gallery_html = self.fetch_html(gallery_page_url)
                        gallery_images = gallery_html.xpath(GALLERY_IMAGES_XPATH)
                        self.set_art_from_links(metadata, gallery_images, pull_gallery_count, 'Gallery')
                    else:
                        self.log('Gallery link not found')
                except Exception as e:
                    self.log('Gallery images update failed: %s' % e)

            if self.debug_enabled():
                duration_val = None
                try:
                    duration_val = metadata.duration
                except Exception:
                    duration_val = None
                debug_metadata = {
                    'title': metadata.title,
                    'content_rating': metadata.content_rating,
                    'studio': metadata.studio,
                    'originally_available_at': str(metadata.originally_available_at) if metadata.originally_available_at else None,
                    'year': metadata.year,
                    'duration': duration_val,
                    'tagline': metadata.tagline,
                    'summary': (metadata.summary[:120] + '...') if metadata.summary and len(metadata.summary) > 120 else metadata.summary,
                    'rating': metadata.rating,
                    'genres': list(metadata.genres),
                    'roles': [role.name for role in metadata.roles],
                    'directors': [director.name for director in metadata.directors],
                    'collections': list(metadata.collections),
                    'posters': list(metadata.posters.keys()),
                    'art': list(metadata.art.keys()),
                }
                Log('[ADE] Metadata contents: %s' % str(debug_metadata))
                Log('[ADE] Metadata updated for ID: %s' % metadata.id)
        except Exception as e:
            self.log('Metadata update failed: %s' % e)
