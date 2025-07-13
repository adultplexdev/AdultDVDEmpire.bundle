# AdultDVDEmpire
# Update: 13 July 2025
# Description: New updates from a lot of diffrent forks and people. Please read README.md for more details.
import re
import datetime
import random
import urllib2

# preferences
preference = Prefs
DEBUG = preference['debug']
if DEBUG:
  Log('Agent debug logging is enabled!')
else:
  Log('Agent debug logging is disabled!')

studioascollection = preference['studioascollection']

if len(preference['ADEsearchtype']) and preference['ADEsearchtype'] != 'all':
  ADEsearchtype = preference['ADEsearchtype']
else:
  ADEsearchtype = 'allsearch'
if DEBUG:Log('Search Type: %s' % str(preference['ADEsearchtype']))

# URLS
ADE_BASEURL = 'https://www.adultdvdempire.com'
ADE_SEARCH_MOVIES = ADE_BASEURL + '/' + ADEsearchtype + '/search?view=list&q=%s'
ADE_MOVIE_INFO = ADE_BASEURL + '/%s/'

scoreprefs = int(preference['goodscore'].strip())
if scoreprefs > 1:
    GOOD_SCORE = scoreprefs
else:
    GOOD_SCORE = 96
if DEBUG:Log('Result Score: %i' % GOOD_SCORE)

INITIAL_SCORE = 100

titleFormats = r'\(DVD\)|\(Blu-Ray\)|\(BR\)|\(VOD\)'

def Start():
  HTTP.CacheTime = 0
  HTTP.Headers['User-agent'] = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)'
  HTTP.Headers['Cookie'] = 'ageConfirmed=true'

def ValidatePrefs():
  pass

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
    if DEBUG: Log('Search Query: %s' % str(ADE_SEARCH_MOVIES % query))
    # Finds the entire media enclosure <DIV> elements then steps through them
    for movie in HTML.ElementFromURL(ADE_SEARCH_MOVIES % query).xpath('//div[contains(@class,"row list-view-item")]'):
      # Uncomment below to get all the div tag results for the variable movie
      if DEBUG: Log('--------- RESULT BEGIN ---------')
      if DEBUG: Log('Search Result for variable movie: %s' % str(title))
      # curName = The text in the 'title' p
      try:
        moviehref = movie.xpath('.//a[contains(@label,"Title")]')[0]
        curName = moviehref.text_content().strip()
        # Uncomment below to get the debug logging for the initial name result
        if DEBUG: Log('Initial Result curName found: %s' % str(curName))
        
        if curName.count(', The'):
          curName = 'The ' + curName.replace(', The','',1)
        yearName = curName
        relName = curName
        if DEBUG: Log('Initial Result relName found: %s' % str(relName))

        # curID = the ID portion of the href in 'movie'
        curID = moviehref.get('href').split('/',2)[1]
        if DEBUG: Log('Initial Result curID found: %s' % str(curID))
        score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), curName.lower())
        if DEBUG: Log('Initial Result score found: %s' % str(score))
        
        # In the list view the release date is available.  Let's get that and append it to the title
        # This has been superseded by Production Year instead, but leaving the code in in case we want
        # to display that later instead
        try:
          moviedate = movie.xpath('.//small[contains(text(),"released")]/following-sibling::text()[1]')[0].strip()
          if len(moviedate) > 0:
            moviedate = datetime.datetime.strptime(moviedate, "%m/%d/%Y").strftime("%Y-%m-%d")
            yearName = curName
            relName += " [" + moviedate +"]"
        except: pass
        if DEBUG: Log('Initial Result moviedate found: %s' % str(moviedate))
        # Parse out the "Production Year" and use that for identification since release date is usually different
        # between formats.  Also the Try: block is because not all releases have Production Year associated
        try:
          # Existing Production year code
          # curYear = movie.xpath('.//a[@label="Title"]/following-sibling::small')[0].text_content().strip()
          # New Production Year Code
          curYear = movie.xpath('.//a[contains(@aria-label, "View")]/following-sibling::text()[1]')[0].strip()
          if DEBUG: Log('Initial Result curYear found: %s' % str(curYear))
          if len(curYear):
            if not re.match(r"\(\d\d\d\d\)",curYear):
              curYear = None
            else:
              yearName += " " + curYear
        except: pass
        if DEBUG: Log('Initial Result yearName found: %s' % str(yearName))

        if preference['ADEsearchtype'] == 'all':
          if DEBUG: Log('Checking the category for VOD or DVD')
          #If the category is VOD then lower the score by half to place it lower than DVD results
          #movie2 = movie.xpath('//small[contains(text(),"DVD-Video") or contains(text(),"Video On Demand") or contains(text(),"Blu-ray")]')
          #movie2 = movie.xpath('.//a[@title="DVD" or @title="dvd" or @title=" DVD-Video "]')
          movie2 = movie.xpath('.//div[contains(@class,"list-view-item-controls_content-type m-b-1")="DVD-Video"]')
          if DEBUG: Log('Initial Result movie2 found: %s' % str(movie2))
          if DEBUG: Log('Current title is DVD')
          if len(movie2) > 0:
            mediaformat = "dvd"

          # 2024-09-19 ADE dont use Blu-ray as its own category for the moment.
          #movie2 = movie.xpath('.//small[contains(text(),"Blu-ray")]')
          #if len(movie2) > 0:
          #  mediaformat = "br"

          #movie2 = movie.xpath('.//a[@title="VOD" or @title="vod" or @title="Video On Demand"]')
          movie2 = movie.xpath('.//div[contains(@class,"list-view-item-controls_content-type m-b-1")="Video On Demand"]')
          if DEBUG: Log('Current title is VOD')
          if len(movie2) > 0:
            mediaformat = "vod"

        else:
            mediaformat = 'NA'
            
        if DEBUG: Log('Initial Result mediaformat found: %s' % str(mediaformat))
        # This is pretty kludgey, but couldn't wrap my mind around Python's handling of associative arrays
        # Therefore I just write the row into a delimited string and then process
        # Essentially this is to make sure that you only have VOD results in the list if there's no dvd
        # or Blu-Ray entry available
        # It builds up the resultarray[] array, which is then stepped through in the next section
        # This is run on each found result 
        resultrow = yearName + "<DIVIDER>" + curID + "<DIVIDER>" + mediaformat + "<DIVIDER>" + str(score) + "<DIVIDER>" + relName
        if DEBUG: Log('Result to process for appending: %s' % str(resultrow))

        if preference['ADEsearchtype'] == 'all':
          resulttemparray = []
          resultpointer = None
          for resulttempentry in resultarray:
            resultname, resultid, resultformat, resultscore, resultrelname = resulttempentry.split("<DIVIDER>")

            # The following lines remove less valuable data going forward in the list
            if (((mediaformat == 'vod' and (resultformat == 'dvd' or resultformat == 'br')) or (mediaformat == 'br' and resultformat == 'dvd')) and resultname == yearName):
              resultpointer = 1 #1 indicates that we already have a better result, don't write
            # The following lines remove previously entered less valuable data
            if not (((resultformat == 'vod' and (mediaformat == 'dvd' or mediaformat == 'br')) or (resultformat == 'br' and mediaformat == 'dvd')) and resultname == yearName):
              resulttemparray.append(resulttempentry)
          resultarray = resulttemparray

        if resultpointer is None:
          resultarray.append(resultrow)
      except: pass
      if DEBUG: Log('--------- RESULT END ---------')

    # Just need to step through the returned resultarray[], split out the segments and pop them onto the stack
    # IF: 1) the returned media name contains the exact search term
    # or: 2) if the resulting score is higher than GOOD_SCORE (93 for me) on a Levenshtein Distance calculation
    for entry in resultarray:
      entryYearName, entryID, entryFormat, entryScore, entryRelName = entry.split("<DIVIDER>")
      if preference['dateformat']:
        moviename = entryYearName
        if (not re.search('\(\d{4}\)', entryYearName)) and (re.search('\[\d{4}-\d{2}-\d{2}\]', entryRelName)):
          moviename = entryRelName
          if DEBUG: Log('No Production Year Found, RelaseDate Movie returned: %s' % str(moviename))
        else:
          if DEBUG: Log('Prod Year Movie returned: %s' % str(moviename))
      else:
        moviename = entryRelName
        if (re.search('\(\d{4}\)', entryYearName)) and (not re.search('\[\d{4}-\d{2}-\d{2}\]', entryRelName)):
          moviename = entryYearName
          if DEBUG: Log('No Release Date Found, Year Movie returned: %s' % str(moviename))
        else:
          if DEBUG: Log('ReleaseDate Movie returned: %s' % str(moviename))

      entryScore = int(entryScore)
      if moviename.lower().count(title.lower()):
        results.Append(MetadataSearchResult(id = entryID, name = moviename, score = entryScore, lang = lang))
      elif (entryScore >= GOOD_SCORE):
        results.Append(MetadataSearchResult(id = entryID, name = moviename, score = entryScore, lang = lang))
    
    results.Sort('score', descending=True)
    

  def update(self, metadata, media, lang):
    if DEBUG: Log('Beginning Update...')
    html = HTML.ElementFromURL(ADE_MOVIE_INFO % metadata.id)
    metadata.title = media.title
    metadata.title = re.sub(r'\ \[\d{4}-\d{2}-\d{2}\]','',metadata.title).strip()
    metadata.title = re.sub(r'\ \(\d{4}\)','',metadata.title).strip()
    if DEBUG: Log('Title Metadata Key: [Movie Title]   Value: [%s]', metadata.title)

    #This strips the format type returned in the "curName += "  (VOD)" style lines above
    #You can uncomment them and this to make it work, I jsut thought it was too busy with
    #The dates listed as well, not to mention that formats are sorted by type with the score
    #DVD = 91-100, Blu-Ray = 71-80, VOD = 31-40
    #metadata.title = re.sub(titleFormats,'',metadata.title).strip()

    # Thumb and Poster
    try:
      if DEBUG: Log('Looking for thumb and poster')
      img = html.xpath('//*[@id="front-cover"]/img')[0]
      thumbUrl = img.get('src')

      thumb = HTTP.Request(thumbUrl)
      posterUrl = img.get('src')
      metadata.posters[posterUrl] = Proxy.Preview(thumb)
    except Exception, e:
      Log('Got an exception while downloading posters %s' %str(e))

    # Tagline
    #try: metadata.tagline = html.xpath('//p[@class="Tagline"]')[0].text_content().strip()
    try: metadata.tagline = html.xpath('//h2[contains(@class, "test")]/text()')[0].strip()
    except: pass

    # Summary.
    try:
        #summary = html.xpath('//div[@class="col-xs-12 text-center p-y-2 bg-lightgrey"]/div/p')[0].text_content().strip()
        summary = html.xpath('//div[@class="synopsis-content"]/p')[0].text_content().strip()
        #summary = re.sub('<[^<]+?>', '', summary)
        Log('Summary Found: %s' %str(summary))
        metadata.summary = summary
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Product info div
    data = {}

    # Match diffrent code, some titles are missing parts -- Still fails and needs to be refined.
    if DEBUG: Log('Detecting Product info...')
    if DEBUG: Log('Trying xpath 1...')
    if html.xpath('//*[@id="content"]/div[2]/div[3]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[3]/div/div[1]/ul')[0])
      if DEBUG: Log('Match on xpath 1...')
    if DEBUG: Log('Trying xpath 2...')
    if html.xpath('//*[@id="content"]/div[2]/div[4]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[4]/div/div[1]/ul')[0])
      if DEBUG: Log('Match on xpath 2...')
    if DEBUG: Log('Trying xpath 3...')
    if html.xpath('//*[@id="content"]/div[2]/div[2]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[2]/div[2]/div/div[1]/ul')[0])
      if DEBUG: Log('Match on xpath 3...')
    if DEBUG: Log('Trying xpath 4...')
    if html.xpath('//*[@id="content"]/div[3]/div[3]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[3]/div[3]/div/div[1]/ul')[0])
      if DEBUG: Log('Match on xpath 4...')
    if DEBUG: Log('Trying xpath 5...')
    if html.xpath('//*[@id="content"]/div[3]/div[4]/div/div[1]/ul'):
      productinfo = HTML.StringFromElement(html.xpath('//*[@id="content"]/div[3]/div[4]/div/div[1]/ul')[0])
      if DEBUG: Log('Match on xpath 5...')
    if DEBUG: Log('Trying NEW xpath 6...')
    if html.xpath('//ul[@class="list-unstyled m-b-2"]'):
      productinfo = HTML.StringFromElement(html.xpath('//ul[@class="list-unstyled m-b-2"]/li')[0])
      if DEBUG: Log('Match on xpath 6...')

    productinfo = productinfo.replace('<small>', '|')
    productinfo = productinfo.replace('</small>', '')
    productinfo = productinfo.replace('<li>', '').replace('</li>', '')
    productinfo = productinfo.replace('Features', '|')
    #productinfo = re.sub('Features *', '', productinfo, flags=re.M)
    productinfo = HTML.ElementFromString(productinfo).text_content()
    #if DEBUG: Log ('text_content: %s', productinfo)
    for div in productinfo.split('|'):
      if ':' in div:
        name, value = div.split(':')
        data[name.strip()] = value.strip()
        if DEBUG: Log('Title Metadata Key: [%s]   Value: [%s]', name.strip(), value.strip())
        if name.strip() == "Studio": break

    if DEBUG: Log('Parsing of product info complete...')
    # Rating
    if data.has_key('Rating'):
      if DEBUG: Log('Rating Present...')
      metadata.content_rating = data['Rating']

    # Studio
    if data.has_key('Studio'):
      if DEBUG: Log('Studio Present...')
      metadata.studio = data['Studio']
      studio = data['Studio']

    # Release
    if data.has_key('Released'):
      if DEBUG: Log('Release Present...')
      try:
        metadata.originally_available_at = Datetime.ParseDate(data['Released']).date()
        metadata.year = metadata.originally_available_at.year
      except: pass

    # Production Year
    # If the user preference is set, then we want to replace the 'Release Date' with a created date
    # based off of the Production Year that is returned.  Don't want to do it unless the difference
    # is greater than one year however, to allow for production at the end of the year with first of
    # year release
    if preference['useproductiondate']:
        if data.has_key('Production Year'):
          productionyear = int(data['Production Year'])
          if productionyear > 1900:
              if DEBUG: Log('Release Date Year for Title: %i' % metadata.year)
              if DEBUG: Log('Production Year for Title: %i' % productionyear)
              if (metadata.year > 1900) and ((metadata.year - productionyear) >1):
                  metadata.year = productionyear
                  metadata.originally_available_at = Datetime.ParseDate(str(productionyear) + "-01-01")
                  if DEBUG: Log('Production Year earlier than release, setting date to: %s' % (str(productionyear) + "-01-01"))

    # Cast - added updated by Briadin / 20190320
    try:
      metadata.roles.clear()
      if html.xpath('//div[@class="hover-popover-detail"]'):
        htmlcast = html.xpath('//div[@class="hover-popover-detail"]/img')

        upperlist = []
        for htmlcastUpper in htmlcast:
            uppername = htmlcastUpper.xpath('./@title')[0]
            upperurl = htmlcastUpper.xpath('./@src')[0]
            upperurl = upperurl.replace("h.jpg",".jpg")
            if DEBUG: Log('Upper Star Data: %s     %s' % (uppername, upperurl))
            upperlist.append(uppername)
            role = metadata.roles.new()
            role.name = uppername
            role.photo = upperurl

        # Bottom List: doesn't have photo links available, so only uses to add names to the ones from the upper
        if html.xpath('//a[contains(@class,"PerformerName")][not(ancestor::small)]'):
          htmlcastLower = html.xpath('//a[contains(@class,"PerformerName")][not(ancestor::small)]')
          lowerlist = []
          for removedupestar in htmlcastLower:
            # I realize there has to be a cleaner way to do this, but essentially this takes them
            # name and bio page url, strips the star id from the url, then hooks the name and id
            # together in a pseudo dictionary to be split back out later
            lowername = removedupestar.xpath('./text()')[0]
            lowerurl = removedupestar.xpath('./@href')[0]
            lowerurlre = re.search('\d{3,8}',lowerurl)
            lowerentry = lowername.strip() + '|' + lowerurlre.group(0).strip()
            lowerlist.append(lowerentry)
          lowerlist = list(set(lowerlist))
          for lowerstar in lowerlist:
            if (len(lowerstar) > 0):
              lowerstarname, lowerstarurl = lowerstar.split("|")
              # There are different descriptors that will show up as a name, for now just adding them ad-hoc
              # to following statement with "and lowerstar.lower() != 'bio'"
              if (lowerstarname not in upperlist and lowerstarname.lower() != 'bio' and lowerstarname.lower() != 'interview'):
                role = metadata.roles.new()
                role.name = lowerstarname
                if len(lowerstarurl) > 1:
                  photourl = "https://imgs1cdn.adultempire.com/actors/" + lowerstarurl + ".jpg"
                  if self.file_exists(photourl):
                    role.photo = photourl
                  else:
                    photourl = "Image Not Available"
                else:
                  photourl = "Image Not Available"
                if DEBUG: Log('Added Lower List Star: %s    URL: %s' % (lowerstarname, photourl))

    except Exception, e:
      Log('Got an exception while parsing cast %s' %str(e))

    # Director
    try:
      metadata.directors.clear()
      if html.xpath('//a[contains(@label, "Director - details")]'):
        if DEBUG: Log('Director Label Found...')
        #htmldirector = HTML.StringFromElement(html.xpath('//a[contains(@label, "Director - details")]/text()'))
        #htmldirector = HTML.ElementFromString(htmldirector).text_content().strip()
        htmldirector = html.xpath('//a[contains(@label, "Director - details")]/text()')
        #htmldirector = htmldirector.replace('\t', '')
        if DEBUG: Log('Director is: %s', htmldirector[0])
        if (len(htmldirector) > 0):
          directorstring = htmldirector
          director = metadata.directors.new()
          director.name = htmldirector[0]
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
    if studioascollection: metadata.collections.add(studio)

    # Genres

    try:
      genrelist = []
      metadata.genres.clear()
      ignoregenres = [x.lower().strip() for x in preference['ignoregenres'].split('|')]
      if html.xpath('//ul[@class="list-unstyled m-b-2"]//a[@label="Category"]'):
        genres = html.xpath('//ul[@class="list-unstyled m-b-2"]//a[@label="Category"]/text()')
        for genre in genres:
            genre = genre.strip()
            genrelist.append(genre)
            if not genre.lower().strip() in ignoregenres: metadata.genres.add(genre)
        if DEBUG: Log('Found Genres: %s' % (' | '.join(genrelist)))

    except Exception, e:
      Log('Got an exception while parsing genres %s' %str(e))

    # 2019-01-17:
    # The following code for Ratings, Background Art and Gallery images were copied From
    # macr0dev's repository at https://github.com/macr0dev/AdultDVDEmpire.bundle then
    # modified to work with user preferences and updated for the current website.
    # However it is still Macr0dev's code in use
    #
    # Adapted fom Macr0dev's code
    # Check for Average Rating
    if html.xpath('//span[@class="rating-stars-avg"]/text()'):
      averagerating = html.xpath('//span[@class="rating-stars-avg"]/text()')
      averagerating = averagerating[0].strip()
      averagerating = re.findall( r'\d+\.*\d*',averagerating)
      if DEBUG: Log('Found an Average Rating of: %s' % str(averagerating[0]))
      try:
        metadata.rating = float(averagerating[0]) * 2
      except: pass
    else:
      if DEBUG: Log('No Media Rating was Located')
      metadata.rating = float(0)

    # Adapted fom Macr0dev's code
    # Background Art From Page
    if preference['pullscreens']:
        pullscreenscount = int(preference['pullscreenscount'])
        if not (pullscreenscount > 0 and pullscreenscount < 50):
            pullscreenscount = 3
        try:
          imgs = html.xpath('//a[contains(@rel, "scenescreenshots")]')
          if len(imgs):
            screencount = 0
            imagelist = self.Rand(1,len(imgs),pullscreenscount)
            if DEBUG: Log('Pulling Screenshot Images: %s' % ', '.join(str(e) for e in imagelist))
            for img in imgs:
              screencount += 1
              if screencount in imagelist:
                thumbUrl = img.attrib['href']
                if DEBUG: Log('Writing Screen Image # %s: %s' % (str(screencount), str(thumbUrl)))
                thumb = HTTP.Request(thumbUrl)
                metadata.art[thumbUrl] = Proxy.Media(thumb)
          else:
            if DEBUG: Log('No Screenshot Images were found for media')
        except Exception, e:
          Log('Got an exception while parsing screenshot images %s' %str(e))

    # Adapted fom Macr0dev's code
    # Background Art From Gallery if it exists
    if preference['pullgallery']:
        pullgallerycount = int(preference['pullgallerycount'])
        if not (pullgallerycount > 0 and pullgallerycount < 50):
            pullgallerycount = 3
        try:
          galleryurl = None
          gallery = html.xpath('//div[@class="user-action"]/a[contains(@class, "gallery")]')
          for url in gallery:
            galleryurl = ADE_BASEURL + url.attrib['href']
            if DEBUG: Log('Gallery URL for Media: %s' % galleryurl)

          if galleryurl is not None:
            gallery = HTML.ElementFromURL(galleryurl)
            imagelist = gallery.xpath('//div/a[contains(@class, "thumb fancy")]')
            if len(imagelist):
              gallerycount = 0
              screenlist = self.Rand(1,len(imagelist),pullgallerycount)
              if DEBUG: Log('Pulling Gallery Images: %s' % ', '.join(str(e) for e in screenlist))
              for imgs in imagelist:
                gallerycount += 1
                if gallerycount in screenlist:
                  imageurl = imgs.attrib['href']
                  if DEBUG: Log('Writing Gallery Image # %s: %s' % (str(gallerycount),str(imageurl)))
                  image = HTTP.Request(imageurl)
                  metadata.art[imageurl] = Proxy.Media(image)
            else:
              if DEBUG: Log('No Gallery Images were found for media')
          else:
            if DEBUG: Log('No Gallery was found for media')
        except Exception, e:
            Log('Got an exception while parsing gallery images %s' %str(e))

  def Rand(self, start, end, num):
    res = []
    for j in range(num):
      res.append(random.randint(start, end))
    return res

  #Just a function to check to see if a url (image here) exists
  def file_exists(self, url):
    request = urllib2.Request(url)
    request.get_method = lambda : 'HEAD'
    try:
        response = urllib2.urlopen(request)
        #Log('Response for File Exist check: %s' % str(response.getcode()))
        #Log('URL Actually retrieved: %s' % str(response.geturl()))
        #Log('Headers retrieved from pull: %s' % str(response.info()))
        return True
    except:
        return False
