# AdultDVDEmpire Plex Metadata Agent
# Update: 16 July 2025
# Description: A Plex metadata agent to scrape movie data from Adult DVD Empire.
#              Supports searching and updating metadata with preferences for debugging,
#              and media format prioritization. See README.md for details.

import re
import datetime
import random

# Constants for URLs and configuration
BASE_URL                = 'https://www.adultdvdempire.com'
SEARCH_URL_TEMPLATE     = BASE_URL + '/allsearch/search?view=list&q=%s'
MOVIE_INFO_URL          = BASE_URL + '/%s/'
INITIAL_SCORE           = 100
TITLE_FORMATS           = r'\(DVD\)|\(Blu-Ray\)|\(BR\)|\(VOD\)'
USER_AGENT              = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36')
COOKIE_AGE_CONFIRMED    = 'ageConfirmed=true'
HTTP_TIMEOUT            = 10
ACTOR_ID_REGEX          = r'\d{3,8}'
MOVIE_ID_REGEX          = r'/(\d+)/'
PRODUCTION_YEAR_REGEX   = r'\(\d{4}\)'
EXCLUDED_CAST_TERMS     = ['bio', 'interview']
MAX_IMAGE_COUNT         = 50

# Constants for media format prioritization
MEDIA_FORMAT_PRIORITIES = {'dvd': 0,'vod': 1,'NA': 2}

# Constants for XPath selectors
SEARCH_RESULTS_XPATHS   = ['//div[contains(@class,"row list-view-item")]','//div[contains(@class,"list-view-item")]','//div[contains(@class,"product-card")]']
TITLE_XPATHS            = ['.//a[contains(@label,"Title")]','.//a[@href and contains(@class,"title")]']
RELEASE_DATE_XPATHS     = ['.//small[contains(text(),"released")]/following-sibling::text()[1]','.//span[contains(@class,"release-date")]/text()']
PRODUCTION_YEAR_XPATHS  = ['.//a[contains(@aria-label, "View")]/following-sibling::text()[1]','.//span[contains(@class,"production-year")]/text()']
MEDIA_FORMAT_DVD_XPATHS = ['.//div[contains(@class,"list-view-item-controls_content-type") and contains(text(),"DVD")]','.//span[contains(@class,"format") and contains(text(),"DVD")]']
MEDIA_FORMAT_VOD_XPATHS = ['.//div[contains(@class,"list-view-item-controls_content-type") and contains(text(),"Video On Demand")]','.//span[contains(@class,"format") and contains(text(),"VOD")]']
PRODUCT_INFO_XPATHS     = ['//ul[@class="list-unstyled m-b-2"]']

POSTER_XPATH            = '//*[@id="front-cover"]/img'
TAGLINE_XPATH           = '//h2[contains(@class, "test")]/text()'
SUMMARY_XPATH           = '//div[@class="synopsis-content"]/p'
CAST_UPPER_XPATH        = '//div[@class="hover-popover-detail"]/img'
CAST_LOWER_XPATH        = '//a[contains(@label, "Performers - detail")]'
DIRECTOR_XPATH          = '//div[contains(@class, "movie-page__content-tags__directors")]//a/text()'
SERIES_XPATH            = '//a[@label="Series"]/text()'
GENRES_XPATH            = '//ul[@class="list-unstyled m-b-2"]//a[@label="Category"]/text()'
RATING_XPATH            = '//span[@class="rating-stars-avg"]/text()'
SCREENSHOTS_XPATH       = '//a[contains(@rel, "scenescreenshots")]'
GALLERY_XPATH           = '//div[@class="user-action"]/a[contains(@class, "gallery")]'
GALLERY_IMAGES_XPATH    = '//div/a[contains(@class, "thumb fancy")]'

def Start():
    HTTP.ClearCache()
    HTTP.Headers['User-agent'] = USER_AGENT
    HTTP.Headers['Cookie'] = COOKIE_AGE_CONFIRMED

def ValidatePrefs():
    pass

class ADEAgent(Agent.Movies):
    name = 'Adult DVD Empire'
    languages = [Locale.Language.English]
    primary_provider = True
    accepts_from = ['com.plexapp.agents.localmedia']

    def file_exists(self, url):
        debug = Prefs['debug']
        try:
            HTTP.Request(url, method='HEAD', timeout=HTTP_TIMEOUT)
            if debug: Log('URL exists: %s' % url)
            return True
        except Exception as e:
            if debug: Log('URL check failed: %s' % e)
            return False

    def clean_title(self, title):
        debug = Prefs['debug']
        title = re.sub(TITLE_FORMATS, '', title).strip()
        title = re.sub(r'\ \[\d{4}-\d{2}-\d{2}\]', '', title).strip()
        title = re.sub(r'\ \(\d{4}\)', '', title).strip()
        if debug: Log('Title cleaned: %s' % title)
        return title

    def normalize_for_scoring(self, title):
        title = title.lower()
        title = re.sub(r'\s*(vol\.?|#)\s*(\d+)$', r' \2', title)
        return title

    def parse_movie_result(self, movie_element, search_title):
        debug = Prefs['debug']
        dateformat = Prefs['dateformat']
        try:
            # Extract movie title and URL
            title_element = None
            movie_url = None
            for xpath in TITLE_XPATHS:
                try:
                    elements = movie_element.xpath(xpath)
                    if elements:
                        title_element = elements[0]
                        href = title_element.get('href')
                        if href and '/' in href:
                            movie_url = href
                            break
                        title_element = None
                except Exception:
                    title_element = None
            
            # Extract title text
            movie_title = None
            text_content = title_element.text_content().strip() if title_element else ''
            if text_content:
                movie_title = text_content
            else:
                try:
                    child_texts = title_element.xpath('./text()')
                    if child_texts:
                        movie_title = ''.join(child_texts).strip()
                except Exception:
                    pass
                
                if not movie_title:
                    title_attr = title_element.get('title', '').strip() if title_element else ''
                    if title_attr:
                        movie_title = title_attr
            
            if not movie_title:
                if debug: Log('No title found for URL: %s' % movie_url)
                return None
            
            # Clean title and handle 'The' suffix
            movie_title = self.clean_title(movie_title)
            if ', The' in movie_title:
                movie_title = 'The ' + movie_title.replace(', The', '', 1)
            
            # Extract movie ID
            movie_id_match = re.search(MOVIE_ID_REGEX, movie_url)
            if not movie_id_match:
                if debug: Log('No movie ID in URL: %s' % movie_url)
                return None
            movie_id = movie_id_match.group(1)
            
            # Normalize titles for scoring
            norm_search = self.normalize_for_scoring(search_title)
            norm_movie = self.normalize_for_scoring(movie_title)
            score = INITIAL_SCORE - Util.LevenshteinDistance(norm_search, norm_movie)
            
            # Extract release date
            release_date = None
            for xpath in RELEASE_DATE_XPATHS:
                try:
                    release_text = movie_element.xpath(xpath)
                    if release_text:
                        release_text = release_text[0].strip()
                        if release_text:
                            try:
                                release_date = datetime.datetime.strptime(release_text, "%m/%d/%Y").strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                pass
                except Exception:
                    pass

            # Extract production year
            production_year = None
            for xpath in PRODUCTION_YEAR_XPATHS:
                try:
                    year_text = movie_element.xpath(xpath)
                    if year_text:
                        year_text = year_text[0].strip()
                        if re.match(PRODUCTION_YEAR_REGEX, year_text):
                            production_year = year_text.strip('()')
                            break
                except Exception:
                    pass

            # Determine media format
            media_type = 'NA'
            for xpath in MEDIA_FORMAT_DVD_XPATHS:
                try:
                    if movie_element.xpath(xpath):
                        media_type = 'dvd'
                        break
                except Exception:
                    pass
            if media_type == 'NA':
                for xpath in MEDIA_FORMAT_VOD_XPATHS:
                    try:
                        if movie_element.xpath(xpath):
                            media_type = 'vod'
                            break
                    except Exception:
                        pass

            # Construct display name
            display_name = movie_title
            if dateformat:
                year_to_show = production_year
                if not year_to_show and release_date:
                    year_to_show = release_date[:4]
                if year_to_show:
                    display_name += ' (%s)' % year_to_show
            else:
                if release_date:
                    display_name += ' [%s]' % release_date

            return {
                'id': movie_id,
                'name': movie_title,
                'display_name': display_name,
                'format': media_type,
                'score': score,
                'release_date': release_date,
                'production_year': production_year
            }
        except Exception as e:
            if debug: Log('Error parsing movie result: %s' % e)
            return None

    def search(self, results, media, lang):
        debug = Prefs['debug']
        goodscore = int(Prefs['goodscore'])
        if goodscore < 1:
            goodscore = 96
        title = media.name or (media.primary_metadata.title if media.primary_metadata else '')
        query = String.URLEncode(String.StripDiacritics(title.replace('-', '')))
        search_url = SEARCH_URL_TEMPLATE % query
        
        try:
            response = HTTP.Request(search_url, timeout=HTTP_TIMEOUT)
            html = HTML.ElementFromString(response)
            movie_results = []
            for xpath in SEARCH_RESULTS_XPATHS:
                try:
                    movies = html.xpath(xpath)
                    if movies:
                        for movie_element in movies:
                            result = self.parse_movie_result(movie_element, title)
                            if result:
                                movie_results.append(result)
                        break
                except Exception:
                    pass
            
            # Filter to keep the best format for each unique title
            unique_results = []
            seen_titles = set()
            for result in sorted(movie_results, key=lambda x: (x['name'], MEDIA_FORMAT_PRIORITIES[x['format']])):
                if result['name'] not in seen_titles:
                    unique_results.append(result)
                    seen_titles.add(result['name'])
            
            # Add filtered results to Plex
            for result in unique_results:
                if result['display_name'].lower().count(title.lower()) or result['score'] >= goodscore:
                    results.Append(MetadataSearchResult(
                        id=result['id'],
                        name=result['display_name'],
                        score=result['score'],
                        lang=lang
                    ))
            
            results.Sort('score', descending=True)
            if debug: Log('Search completed: %d results' % len(unique_results))
        except Exception as e:
            if debug: Log('Search failed: %s' % e)

    def extract_product_info(self, html):
        debug = Prefs['debug']
        product_info = {}
        for xpath in PRODUCT_INFO_XPATHS:
            try:
                info_element = html.xpath(xpath)[0]
                product_info = {}
                for item in info_element.xpath('./li'):
                    label_elements = item.xpath('./small')
                    if label_elements:
                        label_text = label_elements[0].text_content().strip()
                        key = label_text.rstrip(':').strip()
                        value = item.text_content().replace(label_text, '', 1).strip().encode('utf-8', 'ignore').decode('utf-8')
                        product_info[key] = value
                if product_info:
                    return product_info
            except Exception as e:
                if debug: Log('Product info extraction failed: %s' % e)
        if debug: Log('No product info extracted')
        return product_info

    def extract_cast(self, html):
        debug = Prefs['debug']
        actors = []
        photo_base_url = None
        featured_actors = set()
        # Extract directors to filter them from cast
        director_names = set()
        try:
            director_elements = html.xpath(DIRECTOR_XPATH)
            director_names = set(d.strip().lower() for d in director_elements if d.strip())
        except Exception:
            if debug: Log('Failed to extract directors for filtering')

        try:
            for actor_elem in html.xpath(CAST_UPPER_XPATH):
                try:
                    actor_name = actor_elem.xpath('./@title')[0].strip()
                    # Skip if name is a director
                    if actor_name.lower() in director_names:
                        continue
                    thumb_src = actor_elem.xpath('./@src')[0]
                    if not photo_base_url:
                        photo_base_url = thumb_src.rsplit('/', 1)[0] + '/'
                    actor_photo = thumb_src.replace('h.jpg', '.jpg')
                    if actor_name.lower() not in EXCLUDED_CAST_TERMS:
                        featured_actors.add(actor_name)
                        actors.append({'name': actor_name, 'photo': actor_photo})
                except Exception:
                    pass
            
            for actor_elem in html.xpath(CAST_LOWER_XPATH):
                try:
                    parent_li = actor_elem.getparent()
                    label_texts = parent_li.xpath('./small/text()')
                    if label_texts and 'Director' in label_texts[0].strip():
                        continue
                    actor_name = actor_elem.xpath('./text()')[0].strip()
                    # Skip if name is a director
                    if actor_name.lower() in director_names:
                        continue
                    profile_url = actor_elem.xpath('./@href')[0]
                    actor_id_match = re.search(ACTOR_ID_REGEX, profile_url)
                    if actor_id_match and actor_name not in featured_actors and actor_name.lower() not in EXCLUDED_CAST_TERMS:
                        actor_id = actor_id_match.group(0)
                        actor_photo = None
                        if photo_base_url:
                            actor_photo = photo_base_url + actor_id + '.jpg'
                        actors.append({
                            'name': actor_name,
                            'photo': actor_photo if (actor_photo and self.file_exists(actor_photo)) else None
                        })
                except Exception:
                    pass
        except Exception as e:
            if debug: Log('Cast extraction failed: %s' % e)
        return actors

    def update(self, metadata, media, lang):
        debug = Prefs['debug']
        studioascollection = Prefs['studioascollection']
        useproductiondate = Prefs['useproductiondate']
        pullscreens = Prefs['pullscreens']
        pullscreenscount = int(Prefs['pullscreenscount'])
        if not (0 < pullscreenscount < MAX_IMAGE_COUNT):
            pullscreenscount = 3
        pullgallery = Prefs['pullgallery']
        pullgallerycount = int(Prefs['pullgallerycount'])
        if not (0 < pullgallerycount < MAX_IMAGE_COUNT):
            pullgallerycount = 3
        ignoregenres = [x.lower().strip() for x in (Prefs['ignoregenres'] or '').split('|')]
        try:
            page_content = HTTP.Request(MOVIE_INFO_URL % metadata.id, timeout=HTTP_TIMEOUT)
            page_html = HTML.ElementFromString(page_content)
            
            # Title
            metadata.title = self.clean_title(media.title)
            
            # Poster
            try:
                poster_img = page_html.xpath(POSTER_XPATH)[0]
                poster_url = poster_img.get('src')
                poster_data = HTTP.Request(poster_url)
                metadata.posters[poster_url] = Proxy.Preview(poster_data)
            except Exception:
                if debug: Log('Poster update failed')
            
            # Tagline
            try:
                tagline_text = page_html.xpath(TAGLINE_XPATH)[0].strip()
                metadata.tagline = tagline_text
            except Exception:
                if debug: Log('Tagline update failed')
            
            # Summary
            try:
                summary_text = page_html.xpath(SUMMARY_XPATH)[0].text_content().strip()
                metadata.summary = summary_text
            except Exception:
                if debug: Log('Summary update failed')
            
            # Product Info
            details = self.extract_product_info(page_html)
            
            # Content Rating
            if 'Rating' in details:
                metadata.content_rating = details['Rating']
            
            # Studio
            if 'Studio' in details:
                metadata.studio = details['Studio']
                if studioascollection:
                    metadata.collections.add(details['Studio'])
            
            # Release Date
            if 'Released' in details:
                try:
                    metadata.originally_available_at = Datetime.ParseDate(details['Released']).date()
                    metadata.year = metadata.originally_available_at.year
                except Exception:
                    if debug: Log('Release date update failed')
            
            # Production Year
            if useproductiondate and 'Production Year' in details:
                try:
                    prod_year = int(details['Production Year'])
                    if prod_year > 1900 and metadata.year and (metadata.year - prod_year) > 1:
                        metadata.year = prod_year
                        metadata.originally_available_at = Datetime.ParseDate('%s-01-01' % prod_year).date()
                except Exception:
                    if debug: Log('Production year update failed')
            
            # Cast
            metadata.roles.clear()
            actors = self.extract_cast(page_html)
            for actor in actors:
                actor_role = metadata.roles.new()
                actor_role.name = actor['name']
                if actor['photo']:
                    actor_role.photo = actor['photo']
           
            # Directors
            try:
                director_list = page_html.xpath(DIRECTOR_XPATH)
                if director_list:
                    metadata.directors.clear()
                    unique_dirs = set(d.strip() for d in director_list if d.strip())
                    for name in unique_dirs:
                        director = metadata.directors.new()
                        director.name = name
            except Exception:
                if debug: Log('Director update failed')
            
            # Collections and Series
            try:
                metadata.collections.clear()
                series_links = page_html.xpath(SERIES_XPATH)
                if series_links:
                    series_title = series_links[0].strip().split('"')[1]
                    metadata.collections.add(series_title)
            except Exception as e:
                if debug: Log('Series update failed: %s' % e)
            
            # Genres
            try:
                metadata.genres.clear()
                for genre_name in page_html.xpath(GENRES_XPATH):
                    genre_name = genre_name.strip()
                    if genre_name.lower() not in ignoregenres:
                        metadata.genres.add(genre_name)
            except Exception:
                if debug: Log('Genres update failed')
            
            # Average Rating
            try:
                rating_elems = page_html.xpath(RATING_XPATH)
                if rating_elems:
                    rating_text = rating_elems[0].strip()
                    if debug: Log('Found rating text: %s' % rating_text)
                    rating_numbers = re.findall(r'\d+\.*\d*', rating_text)
                    if rating_numbers:
                        metadata.rating = float(rating_numbers[0]) * 2.0
                        if debug:
                            Log('Set rating to %f' % metadata.rating)
                    else:
                        metadata.rating = 0.0
                        if debug:
                            Log('No numeric match in rating text')
                else:
                    if debug: Log('No rating element found with XPath')
                    metadata.rating = 0.0
            except Exception as e:
                if debug: Log('Rating update failed: %s' % e)
                metadata.rating = 0.0
            
            # Screenshots
            if pullscreens:
                try:
                    screenshot_links = page_html.xpath(SCREENSHOTS_XPATH)
                    if screenshot_links:
                        selected_indices = random.sample(range(1, len(screenshot_links) + 1), min(pullscreenscount, len(screenshot_links)))
                        for idx, link in enumerate(screenshot_links, 1):
                            if idx in selected_indices:
                                screenshot_url = link.attrib['href']
                                screenshot_data = HTTP.Request(screenshot_url)
                                metadata.art[screenshot_url] = Proxy.Media(screenshot_data)
                except Exception:
                    if debug: Log('Screenshots update failed')
            
            # Gallery Images
            if pullgallery:
                try:
                    gallery_links = page_html.xpath(GALLERY_XPATH)
                    if gallery_links:
                        gallery_page_url = BASE_URL + gallery_links[0].attrib['href']
                        gallery_content = HTTP.Request(gallery_page_url, timeout=HTTP_TIMEOUT)
                        gallery_html = HTML.ElementFromString(gallery_content)
                        gallery_images = gallery_html.xpath(GALLERY_IMAGES_XPATH)
                        if gallery_images:
                            selected_indices = random.sample(range(1, len(gallery_images) + 1), min(pullgallerycount, len(gallery_images)))
                            for idx, img in enumerate(gallery_images, 1):
                                if idx in selected_indices:
                                    gallery_image_url = img.attrib['href']
                                    image_data = HTTP.Request(gallery_image_url)
                                    metadata.art[gallery_image_url] = Proxy.Media(image_data)
                except Exception:
                    if debug: Log('Gallery images update failed')
            
            # Log metadata for debugging
            if debug:
                debug_metadata = {
                    'title': metadata.title,
                    'content_rating': metadata.content_rating,
                    'studio': metadata.studio,
                    'originally_available_at': str(metadata.originally_available_at) if metadata.originally_available_at else None,
                    'year': metadata.year,
                    'tagline': metadata.tagline,
                    'summary': metadata.summary,
                    'rating': metadata.rating,
                    'genres': list(metadata.genres),
                    'roles': [role.name for role in metadata.roles],
                    'directors': [director.name for director in metadata.directors],
                    'collections': list(metadata.collections),
                    'posters': list(metadata.posters.keys()),
                    'art': list(metadata.art.keys())
                }
                Log('Metadata contents: %s' % str(debug_metadata))
                Log('Metadata updated for ID: %s' % metadata.id)
        except Exception as e:
            if debug: Log('Metadata update failed: %s' % e)
