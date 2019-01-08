# AdultDVDEmpire - nag
# Update: 29 July 2018
# Description: Updated for the changes to the new site.

# URLS
ADE_BASEURL = 'http://www.adultdvdempire.com'
ADE_SEARCH_MOVIES = ADE_BASEURL + '/dvd/search?q=%s'
ADE_MOVIE_INFO = ADE_BASEURL + '/%s/'

INITIAL_SCORE = 100
GOOD_SCORE = 98

def Start():
  HTTP.CacheTime = CACHE_1MINUTE
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

class ADEAgent(Agent.Movies):
  name = 'Adult DVD Empire'
  languages = [Locale.Language.English]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang):
    title = media.name
    if media.primary_metadata is not None:
      title = media.primary_metadata.title

    query = String.URLEncode(String.StripDiacritics(title.replace('-','')))
    # Finds div with class=item
    for movie in HTML.ElementFromURL(ADE_SEARCH_MOVIES % query).xpath('//div[contains(@class, "col-xs-6")]//div[@class="item-title"]/a[1]'):
      # curName = The text in the 'title' p
      curName = movie.text_content().strip()
      if curName.count(', The'):
        curName = 'The ' + curName.replace(', The','',1)

      # curID = the ID portion of the href in 'movie'
      curID = movie.get('href').split('/',2)[1]
      score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), curName.lower())
      if curName.lower().count(title.lower()):
        results.Append(MetadataSearchResult(id = curID, name = curName, score = INITIAL_SCORE, lang = lang))
      elif (score >= GOOD_SCORE):
        results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))

    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    html = HTML.ElementFromURL(ADE_MOVIE_INFO % metadata.id)
    metadata.title = media.title

    # Thumb and Poster
    try:
      img = html.xpath('//*[@id="front-cover"]/img')[0]
      thumbUrl = img.get('src')

      thumb = HTTP.Request(thumbUrl)
      posterUrl = img.get('src')
      metadata.posters[posterUrl] = Proxy.Preview(thumb)
    except: pass

    # Tagline
    try: metadata.tagline = html.xpath('//p[@class="Tagline"]')[0].text_content().strip()
    except: pass

    # Summary.
    try:
      for summary in html.xpath('//*[@class="product-details-container"]/div/div/p'):
        metadata.summary = summary.text_content()
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Product info div
    data = {}

    # Match diffrent code, some titles are missing parts -- Still fails and needs to be refined.
    if html.xpath('//*[@id="content"]/div[2]/div[3]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[3]/div/div[1]/ul')[0])    
    if html.xpath('//*[@id="content"]/div[2]/div[4]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[4]/div/div[1]/ul')[0])
    if html.xpath('//*[@id="content"]/div[2]/div[2]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[2]/div/div[1]/ul')[0])
    if html.xpath('//*[@id="content"]/div[3]/div[3]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[3]/div[3]/div/div[1]/ul')[0])
    if html.xpath('//*[@id="content"]/div[3]/div[4]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[3]/div[4]/div/div[1]/ul')[0])

    productinfo = productinfo.replace('<small>', '|')
    productinfo = productinfo.replace('</small>', '')
    productinfo = productinfo.replace('<li>', '').replace('</li>', '')
    productinfo = HTML.ElementFromString(productinfo).text_content()

    for div in productinfo.split('|'):
      if ':' in div:
        name, value = div.split(':')
        data[name.strip()] = value.strip()

    # Rating
    if data.has_key('Rating'):
      metadata.content_rating = data['Rating']

    # Studio    
    if data.has_key('Studio'):
      metadata.studio = data['Studio']

    # Release   
    if data.has_key('Released'):
      try:
        metadata.originally_available_at = Datetime.ParseDate(data['Released']).date()
        metadata.year = metadata.originally_available_at.year
      except: pass

    # Cast
    try:
      metadata.roles.clear()
      if html.xpath('//*[contains(@class, "cast listgrid item-cast-list")]'):
        htmlcast = HTML.StringFromElement(html.xpath('//*[contains(@class, "cast listgrid item-cast-list")]')[0])
		
		# -- Terrible setup but works for now.
        htmlcast = htmlcast.replace('\n', '|').replace('\r', '').replace('\t', '').replace(');">', 'DIVIDER')
        htmlcast = htmlcast.replace('<span>', '').replace('</span>', '')
        htmlcast = htmlcast.replace('<li>', '').replace('</li>', '')
        htmlcast = htmlcast.replace('<small>Director</small>', '')
		
		# Change to high res img -- This part need to be made better.
        htmlcast = htmlcast.replace('t.jpg', 'h.jpg')
        htmlcast = htmlcast.replace('<img src="https://imgs2cdn.adultempire.com/res/pm/pixel.gif" alt="" title="" class="img-responsive headshot" style="background-image:url(', '|')
        htmlcast = HTML.ElementFromString(htmlcast).text_content()
        htmlcast = htmlcast.split('|')
        htmlcast = htmlcast[1:]
        for cast in htmlcast:
          if (len(cast) > 0):
            imgURL, nameValue = cast.split('DIVIDER')
            role = metadata.roles.new()
            role.name = nameValue
            role.photo = imgURL
    except Exception, e:
      Log('Got an exception while parsing cast %s' %str(e))
     
    # Director
    try:
      metadata.directors.clear()
      if html.xpath('//a[contains(@label, "Director - details")]'):    
        htmldirector = HTML.StringFromElement(html.xpath('//a[contains(@label, "Director - details")]')[0])
        htmldirector = HTML.ElementFromString(htmldirector).text_content().strip()
        if (len(htmldirector) > 0):
          director = metadata.directors.new()
          director.name = htmldirector
    except Exception, e:
      Log('Got an exception while parsing director %s' %str(e))

    # Genres
    try:
      metadata.genres.clear()
      if html.xpath('//*[contains(@class, "col-sm-4 spacing-bottom")]'):
        htmlgenres = HTML.StringFromElement(html.xpath('//*[contains(@class, "col-sm-4 spacing-bottom")]')[2])
        htmlgenres = htmlgenres.replace('\n', '|')
        htmlgenres = htmlgenres.replace('\r', '')
        htmlgenres = htmlgenres.replace('\t', '')
        htmlgenres = HTML.ElementFromString(htmlgenres).text_content()
        htmlgenres = htmlgenres.split('|')
        htmlgenres = filter(None, htmlgenres)
        htmlgenres = htmlgenres[1:]
        htmlgenres = htmlgenres[:-1]
        for gname in htmlgenres:
          if len(gname) > 0:
            metadata.genres.add(gname)
    except Exception, e:
      Log('Got an exception while parsing genres %s' %str(e))

