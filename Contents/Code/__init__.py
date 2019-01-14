# AdultDVDEmpire
# Update: 8 January 2019
# Description: New updates from a lot of diffrent forks and people. Please read README.md for more details.
import re
import datetime

# URLS
ADE_BASEURL = 'http://www.adultdvdempire.com'
ADE_SEARCH_MOVIES = ADE_BASEURL + '/allsearch/search?view=list&q=%s'
ADE_MOVIE_INFO = ADE_BASEURL + '/%s/'

INITIAL_SCORE = 100
GOOD_SCORE = 93

titleFormats = r'\(DVD\)|\(Blu-Ray\)|\(BR\)|\(VOD\)'

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

    # resultarray[] is used to filter out duplicate search results
    resultarray=[]
    yearName = title

    # Finds the entire media enclosure <DIV> elements then steps through them
    for movie in HTML.ElementFromURL(ADE_SEARCH_MOVIES % query).xpath('//div[contains(@class,"row list-view-item")]'):
      # curName = The text in the 'title' p
      moviehref = movie.xpath('.//a[contains(@label,"Title")]')[0]
      curName = moviehref.text_content().strip()
      if curName.count(', The'):
        curName = 'The ' + curName.replace(', The','',1)

      # curID = the ID portion of the href in 'movie'
      curID = moviehref.get('href').split('/',2)[1]
      score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), curName.lower())

      # In the list view the release date is available.  Let's get that and append it to the title
      # This has been superseded by Production Year instead, but leaving the code in in case we want
      # to display that later instead
      try:
        moviedate = movie.xpath('.//small[contains(text(),"released")]/following-sibling::text()[1]')[0].strip()
        if len(moviedate) > 0:
          moviedate = datetime.datetime.strptime(moviedate, "%m/%d/%Y").strftime("%Y-%m-%d")
          yearName = curName
          curName += "  [" + moviedate +"]"
      except: pass

      # Parse out the "Production Year" and use that for identification since release date is usually different
      # between formats.  Also the Try: block is because not all releases have Production Year associated
      try:
        curYear = movie.xpath('.//a[@label="Title"]/following-sibling::small')[0].text_content().strip()
        if len(curYear):
          if not re.match(r"\(\d\d\d\d\)",curYear):
            curYear = None
          else:
            yearName += " " + curYear
      except: pass

      #If the category is VOD then lower the score by half to place it lower than DVD results
      #movie2 = movie.xpath('//small[contains(text(),"DVD-Video") or contains(text(),"Video On Demand") or contains(text(),"Blu-ray")]')
      movie2 = movie.xpath('.//small[contains(text(),"DVD-Video")]')
      if len(movie2) > 0:
        mediaformat = "dvd"
        #score = (score / 10) + 90
        #curName += "  (DVD)"

      movie2 = movie.xpath('.//small[contains(text(),"Blu-ray")]')
      if len(movie2) > 0:
        mediaformat = "br"
        #score = (score / 10) + 40
        #curName += "  (BR)"

      movie2 = movie.xpath('.//small[contains(text(),"Video On Demand")]')
      if len(movie2) > 0:
        #score = (score / 10) + 20
        mediaformat = "vod"
        #curName += "  (VOD)"

      # This is pretty kludgey, but couldn't wrap my mind around Python's handling of associative arrays
      # Therefore I just write the row into a delimited string and then process
      # Essentially this is to make sure that you only have VOD results in the list if there's no dvd
      # or Blu-Ray entry available
      # It builds up the resultarray[] array, which is then stepped through in the next section
      # This is run on each found result
      resultrow = yearName + "<DIVIDER>" + curID + "<DIVIDER>" + mediaformat + "<DIVIDER>" + str(score)
      resultpointer = None
      for resulttempentry in resultarray:
        resultname, resultid, resultformat, resultscore = resulttempentry.split("<DIVIDER>")
        if resultname == yearName:
            if (resultformat == 'dvd' or resultformat == 'br') and mediaformat == 'vod':
                resultpointer = 1
            if resultformat == 'br' and mediaformat =='dvd':
                resultpointer = 1
      if resultpointer is None:
        resultarray.append(resultrow)

    # Just need to step through the returned resultarray[], split out the segments and pop them onto the stack
    # IF: 1) the returned media name contains the exact search term
    # or: 2) if the resulting score is higher than GOOD_SCORE (93 for me) on a Levenshtein Distance calculation
    for entry in resultarray:
      entryName, entryID, entryFormat, entryScore = entry.split("<DIVIDER>")
      entryScore = int(entryScore)
      if entryName.lower().count(title.lower()):
        results.Append(MetadataSearchResult(id = entryID, name = entryName, score = entryScore, lang = lang))
      elif (entryScore >= GOOD_SCORE):
        results.Append(MetadataSearchResult(id = entryID, name = entryName, score = entryScore, lang = lang))

    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    html = HTML.ElementFromURL(ADE_MOVIE_INFO % metadata.id)
    metadata.title = media.title
    metadata.title = re.sub(r'\ \ \[\d+-\d+-\d+\]','',metadata.title).strip()
    metadata.title = re.sub(r'\ \(\d\d\d\d\)','',metadata.title).strip()
    #This strips the format type returned in the "curName += "  (VOD)" style lines above
    #You can uncomment them and this to make it work, I jsut thought it was too busy with
    #The dates listed as well, not to mention that formats are sorted by type with the score
    #DVD = 91-100, Blu-Ray = 71-80, VOD = 31-40
    #metadata.title = re.sub(titleFormats,'',metadata.title).strip()

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

    # Cast - added updated by Briadin / 20190108
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
        htmlcast = htmlcast.replace('<img src="https://imgs1cdn.adultempire.com/res/pm/pixel.gif" alt="" title="" class="img-responsive headshot" style="background-image:url(', '|')
        htmlcast = HTML.ElementFromString(htmlcast).text_content()
        htmlcast = htmlcast.split('|')
        htmlcast = htmlcast[1:]
        # upperlist is simply an array of the top list to compare the bottom list against
        upperlist = []
        for cast in htmlcast:
          if (len(cast) > 0):
            imgURL, nameValue = cast.split('DIVIDER')
            upperlist.append(nameValue.strip())
            role = metadata.roles.new()
            role.name = nameValue
            role.photo = imgURL

        # Bottom List: doesn't have photo links available, so only uses to add names to the ones from the upper
        if html.xpath('//a[contains(@class,"PerformerName")][not(ancestor::small)]'):
          htmlcastLower = html.xpath('//a[contains(@class,"PerformerName")][not(ancestor::small)]/text()')
          lowerlist = []
          for removedupestar in htmlcastLower:
            lowerlist.append(removedupestar.strip())
          lowerlist = list(set(lowerlist))
          for lowerstar in lowerlist:
            if (len(lowerstar) > 0):
              # There are different descriptors that will show up as a name, for now just adding them ad-hoc
              # to following statement with "and lowerstar.lower() != 'bio'"
              if (lowerstar not in upperlist and lowerstar.lower() != 'bio' and lowerstar.lower() != 'interview'):
                role = metadata.roles.new()
                role.name = lowerstar
                Log('Added Lower List Star: %s' %str(lowerstar))

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

    # Collections and Series
    try:
      metadata.collections.clear()
      if html.xpath('//a[contains(@label, "Series")]'):
        series = HTML.StringFromElement(html.xpath('//a[contains(@label, "Series")]')[0])
        series = HTML.ElementFromString(series).text_content().strip()
        series = series.split('"')
        series = series[1]
        metadata.collections.add(series)
    except: pass

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
              if gname != "Sale": metadata.genres.add(gname)
    except Exception, e:
      Log('Got an exception while parsing genres %s' %str(e))
