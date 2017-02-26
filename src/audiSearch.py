 # encoding: utf-8

import sys, json, ast, shutil, os
from workflow import Workflow3, ICON_ERROR, ICON_INFO, ICON_SYNC, web

intervals = (
	('hrs', 3600),
	('mins', 60),
	('secs', 1)
)
numResultsPerPage = 10
coverArtSize = 64
defaultCoverArtUrl = "http://g-ecx.images-amazon.com/images/G/01/Audible/en_US/images/generic/no_image_s_150_image.jpg"

def addErrorItem(title, subtitle=""):
	wf.add_item(
		title=title,
		subtitle=subtitle,
		valid=True,
		icon=ICON_ERROR
	)

def displayVersion(productVersion):
	return {
		"abridged": "Abridged",
		"unabridged": "Unabridged",
		"highlights": "Highlights",
		"original_recording": "Original"
	}[productVersion]

def displayTime(seconds, granularity=2):
	result = []

	for name, count in intervals:
		value = seconds // count
		if value:
			seconds -= value * count
			if value == 1:
				name = name.rstrip('s')
			result.append("{} {}".format(value, name))
	return ' and '.join(result[:granularity])

def cacheCoverArt(imageUrl):
	imgName = os.path.basename(imageUrl)
	basePath = imageUrl.replace(imgName, "")
	pathToImg = coverArtDir + imgName
	
	if os.path.isfile(pathToImg) == False:
		img = open(pathToImg, "wb")
		img.write(web.get(imageUrl, stream=True).content)
		img.close()

	return pathToImg

def parseSearchResults(results):
	if "products" in results:
		# Clear out any previously stored cover art
		shutil.rmtree(coverArtDir, True)
		os.mkdir(coverArtDir)

		# Parse total result count
		if "total_results" in results:
			totalResultCount = results["total_results"]

		# Parse each result
		for result in results["products"]:
			product = {}

			# Parse asin
			if ("asin" in result and len(result["asin"])):
				product["asin"] = result["asin"]
			else:
				wf.logger.error("Failed to process asin.")

			# Parse title
			if ("title" in result and len(result["title"])):
				titleComponents = [result["title"]]
				if ("subtitle" in result and len(result["subtitle"])):
					titleComponents.append(result["subtitle"])
				product["title"] = ": ".join(titleComponents)

			# Cache cover art
			if "product_images" in result:
				coverArtUrl = result["product_images"][str(coverArtSize)]
				if (coverArtUrl is not None and len(coverArtUrl)):
					product["icon"] = cacheCoverArt(coverArtUrl)
				else:
					product["icon"] = cacheCoverArt(defaultCoverArtUrl)
			else:
				product["icon"] = cacheCoverArt(defaultCoverArtUrl)

			# Parse authors
			authors = []
			if ("authors" in result and len(result["authors"])):
				for author in result["authors"]:
					authors.append(author["name"])
				product["authors"] = "By: " + ", ".join(authors)
			else:
				wf.logger.error("Failed to process authors.")

			# Parse narrators
			narrators = []
			if ("narrators" in result and len(result["narrators"])):
				for narrator in result["narrators"]:
					narrators.append(narrator["name"])
				product["narrators"] = "Narrated By: " + ", ".join(narrators)
			else:
				wf.logger.error("Failed to process narrators.")

			# Parse version
			if ("format_type" in result and len(result["format_type"])):
				product["version"] = result["format_type"]
			else:
				wf.logger.error("Failed to process product type.")

			# Parse length
			if "runtime_length_min" in result:
				product["length"] = result["runtime_length_min"]
			else:
				wf.logger.error("Failed to process running time.")

			# Build subtitles for result items
			defaultSubtitleComponents = []
			if "version" in product:
				defaultSubtitleComponents.append(displayVersion(product["version"]))
			if "authors" in product:
				defaultSubtitleComponents.append(product["authors"])
			if "length" in product:
				lengthSecs = product["length"] * 60
				defaultSubtitleComponents.append(displayTime(lengthSecs))
			defaultSubtitleStr = " | ".join(defaultSubtitleComponents)

			altSubtitleComponents = []
			if "version" in product:
				altSubtitleComponents.append(displayVersion(product["version"]))
			if "narrators" in product:
				altSubtitleComponents.append(product["narrators"])
			if "length" in product:
				lengthSecs = product["length"] * 60
				altSubtitleComponents.append(displayTime(lengthSecs))
			altSubtitleStr = " | ".join(altSubtitleComponents)

			# Display result
			if "asin" in product:
				asin = product["asin"]
			else:
				asin = ""

			result = wf.add_item(
				title=product["title"],
				subtitle=defaultSubtitleStr,
				arg="asin:" + asin,
				valid=True,
				icon=product["icon"],
				copytext=asin,
				quicklookurl="https://www.audible.com/pd/" + asin 
			)
			result.add_modifier(key="alt", subtitle=altSubtitleStr)

		# Pagination

		# Pages are a zero-based index
		currentPage = int(os.getenv("currentPage")) + 1

		if (currentPage * numResultsPerPage) < totalResultCount:
			nextPage = str(int(os.getenv("currentPage"))+1)
			wf.add_item(
				title="Show more results...",
				subtitle="Load the next " + str(numResultsPerPage) + " results",
				arg="setpg:",
				valid=True,
				icon=ICON_SYNC
			).setvar("currentPage", nextPage)
	else:
		addErrorItem("No results found.")
		return None

def loadSearchResults(query):
	requestParams = {
		"keywords": query,
		"num_results": numResultsPerPage,
		"language": "en",
		"products_sort_by": "Relevance",
		"image_sizes": coverArtSize,
		"response_groups": "media,product_desc,contributors,product_attrs",
		"page": os.getenv("currentPage")
	}

	try:
		results = web.get("https://api.audible.com/1.0/catalog/products", requestParams)
	except:
		addErrorItem("Failed to retrieve search results.", "Please try again later.")
		return None
	else:
		if results.status_code is not 200:
			addErrorItem("Failed to retrieve search results.", "Please try again later.")
			return None
		else:
			try:
				return results.json()
			except:
				addErrorItem("Failed to parse search results.", "If this error continues please reach out.")
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

def parseSuggestions(suggestions):
	for suggestion in suggestions[1]:
		wf.add_item(
			title=suggestion,
			arg=suggestion,
			valid=True,
			icon="blank.png"
		)

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
				parseSuggestions(suggestions)

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