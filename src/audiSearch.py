 # encoding: utf-8

import sys, json, ast, shutil, os, re
from workflow import Workflow3, ICON_ERROR, ICON_INFO, web
from workflow.notify import notify
from lxml import html

def addErrorItem(title, subtitle=""):
	wf.add_item(
		title=title,
		subtitle=subtitle,
		valid=True,
		icon=ICON_ERROR
	)

# Parses and caches product cover art given the image container.
# Returns the fully qualified path to the cached image.
def parseCoverArt(imageContainer):
	# Parse product image URL
	prodImage = imageContainer[0].xpath("a/img[@class='adbl-prod-image']")
	if len(prodImage):
		prodImageURL = prodImage[0].get("src")
		if prodImageURL is not None:
			# Save image to local cache
			imgName = os.path.basename(prodImageURL)
			basePath = prodImageURL.replace(imgName, "")
			
			img = open(coverArtDir + imgName, "wb")
			img.write(web.get(basePath + imgName).content)
			img.close()

			return coverArtDir + imgName

# Parses product metadata given the metadata container.
# Returns a dictionary representing the product's metadata.
def parseMetadata(metadataContainer):
	metadata = {}

	# Parse product title and ASIN
	prodTitle = metadataContainer[0].xpath("div[@class='adbl-prod-title']/a")
	if len(prodTitle):
		metadata["title"] = prodTitle[0].text_content()

		titleLinkURL = prodTitle[0].get("href")
		asinRegexMatch = re.search("B\d{2}\w{7}|\d{9}(X|\d)$", titleLinkURL)
		
		if asinRegexMatch is not None:
			metadata["asin"] = asinRegexMatch.group(0)

	# Parse product edition if it exists
	prodVersion = metadataContainer[0].xpath("div[@class='adbl-prod-version']")
	if len(prodVersion):
		metadata["version"] = prodVersion[0].text_content().replace("\n", "")

	# Parse product author(s) and ASIN (if not previously processed)
	prodAuthors = metadataContainer[0].xpath("div[@class='adbl-prod-meta']/ul/li/span[@class='adbl-prod-author']")
	if len(prodAuthors):
		authors = []
		authorEls = prodAuthors[0].findall("input[@name='authorName']")
		
		if len(authorEls):
			for authorEl in authorEls:
				authors.append(authorEl.get("value"))

			metadata["authors"] = ", ".join(authors)

		if "asin" not in metadata:
			asinEls = prodAuthors[0].findall("input[@name='productAsin']")

			if len(asinEls):
				metadata["asin"] = asinEls[0].get("value")

	# Parse product narrator(s)
	prodNarrators = metadataContainer[0].xpath("div[@class='adbl-prod-meta']/ul/li/span[@class='adbl-label-an' and contains(text(), 'Narrated By')]/following-sibling::span[@class='adbl-prod-author']")
	if len(prodNarrators):
		narrators = []
		narratorEls = prodNarrators[0].findall("a")

		if len(narratorEls):
			for narratorEl in narratorEls:
				narrators.append(narratorEl.text_content())

			metadata["narrators"] = ", ".join(narrators) 

	# Parse product length
	prodLength = metadataContainer[0].xpath("div[@class='adbl-prod-meta']/ul/li/span[@class='adbl-label' and contains(text(), 'Length')]/following-sibling::span[@class='adbl-label']")
	if len(prodLength):
		metadata["length"] = prodLength[0].text_content()

	return metadata

def parseSearchResults(results):
	resultItems = results.xpath("//ul[@class='adbl-search-results']/li/div[@class='adbl-prod-result adbl-search-result']")

	if len(resultItems):
		# Clear out any previously stored cover art
		shutil.rmtree(coverArtDir, True)
		os.mkdir(coverArtDir)

		# Parse each result
		for result in resultItems:
			product = {}

			# Parse image container
			imageContainer = result.xpath("div[contains(@class, 'adbl-prod-image-sample-cont')]")
			if len(imageContainer):
				coverArt = parseCoverArt(imageContainer)
				product["icon"] = coverArt
			else:
				wf.logger.error("Failed to process product image.")
				coverArt = None

			# Parse metadata
			metadataContainer = result.xpath("div[@class='adbl-prod-meta-data-cont']")
			if len(metadataContainer):
				metadata = parseMetadata(metadataContainer)
				product["metadata"] = metadata
			else:
				wf.logger.error("Failed to process product metadata.")
				metadata = None

			# Build subtitles for result items
			if "authors" in product["metadata"]:
				authorStr = "By: " + product["metadata"]["authors"]
			else:
				authorStr = None

			if "narrators" in product["metadata"]:
				narratorStr = "Narrated By: " + product["metadata"]["narrators"]
			else:
				narratorStr = None

			defaultSubtitleComponents = []
			if "version" in product["metadata"]:
				defaultSubtitleComponents.append(product["metadata"]["version"])
			if (authorStr is not None and len(authorStr)):
				defaultSubtitleComponents.append(authorStr)
			if "length" in product["metadata"]:
				defaultSubtitleComponents.append(product["metadata"]["length"])
			defaultSubtitleStr = " | ".join(defaultSubtitleComponents)

			altSubtitleComponents = []
			if "version" in product["metadata"]:
				altSubtitleComponents.append(product["metadata"]["version"])
			if (narratorStr is not None and len(narratorStr)):
				altSubtitleComponents.append(narratorStr)
			if "length" in product["metadata"]:
				altSubtitleComponents.append(product["metadata"]["length"])
			altSubtitleStr = " | ".join(altSubtitleComponents)

			# Display result
			if "asin" not in product["metadata"]:
				asin = None
			else:
				asin = product["metadata"]["asin"]

			result = wf.add_item(
				title=product["metadata"]["title"],
				subtitle=defaultSubtitleStr,
				arg="asin:" + (asin if asin is not None else ""),
				valid=True,
				icon=product["icon"],
				copytext=asin if asin is not None else "",
				quicklookurl="https://www.audible.com/pd/" + (asin if asin is not None else "") 
			)
			result.add_modifier(key="alt", subtitle=altSubtitleStr)
	else:
		addErrorItem("No results found.")
		return None

def loadSearchResults(query):
	requestParams = {
		"advsearchKeywords": query,
		"searchSize": 10,
		"filterby": "field-keywords"
	}

	try:
		results = web.get("https://www.audible.com/search", requestParams)
	except:
		addErrorItem("Failed to retrieve search results.", "Please try again later.")
		return None
	else:
		if results.status_code is not 200:
			addErrorItem("Failed to retrieve search results.", "Please try again later.")
			return None
		elif len(results.content):
			return html.fromstring(results.content)
		else:
			return None

def loadSuggestions(query):
	requestParams = {
		"method": "completion",
		"q": query,
		"search-alias": "marketplace",
		"client": "audible-search@amazon.com",
		"mkt": "91470",
		"x": "updateACCompletion",
		"sc": "1"
	}

	try:
		suggestions = web.get("https://completion.amazon.com/search/complete", requestParams)
	except:
		addErrorItem("Failed to retrieve auto-complete suggestions.", "Please try again later.")
		return None
	else:
		if suggestions.status_code is not 200:
			addErrorItem("Failed to retrieve auto-complete suggestions.", "Please try again later.")
			return None
		elif len(suggestions.text):
			suggestions = suggestions.text.replace("completion = ", "")
			suggestions = suggestions.replace(";updateACCompletion();", "")
			suggestions = ast.literal_eval(suggestions)

			return suggestions
		else:
			return None 

def main(wf):
	if len(wf.args):
		query = wf.args[0]
	else:
		query = None

	if query is not None:
		if (os.getenv("activeQuery") is not None and os.getenv("activeQuery") == query):
			results = loadSearchResults(query)

			if results is not None:
				parseSearchResults(results)
		else:
			suggestions = loadSuggestions(query)

			wf.add_item(
				title=query,
				arg=query,
				valid=True,
				icon="blank.png"
			)

			if (suggestions is not None and len(suggestions[1])):
				for suggestion in suggestions[1]:
					wf.add_item(
						title=suggestion,
						arg=suggestion,
						valid=True,
						icon="blank.png"
					)

	wf.send_feedback()

if __name__ == u"__main__":
	wf = Workflow3(update_settings={"github_slug": "snewman205/audisearch-for-alfred"})
	coverArtDir = wf.cachedir + "/coverart/"
	if wf.update_available:
		wf.add_item(
			title="New version available",
			subtitle="Click to install the update now.",
			autocomplete="workflow:update",
			icon=ICON_INFO
		)

	sys.exit(wf.run(main))