 # encoding: utf-8

import sys, json, ast, shutil, os
from workflow import Workflow3, ICON_ERROR, ICON_INFO, web
from workflow.notify import notify

def addErrorItem(title, subtitle=""):
	wf.add_item(
		title=title,
		subtitle=subtitle,
		valid=True,
		icon=ICON_ERROR
	)

def cacheCoverArt(imageUrl):
	imgName = os.path.basename(imageUrl)
	basePath = imageUrl.replace(imgName, "")
			
	img = open(coverArtDir + imgName, "wb")
	img.write(web.get(basePath + imgName).content)
	img.close()

	return coverArtDir + imgName

def parseSearchResults(results):
	if "products" in results:
		# Clear out any previously stored cover art
		shutil.rmtree(coverArtDir, True)
		os.mkdir(coverArtDir)

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
			coverArtUrl = result["product_images"]["256"]
			if (coverArtUrl is not None and len(coverArtUrl)):
				product["icon"] = cacheCoverArt(coverArtUrl)
			else:
				wf.logger.error("Failed to process cover art.")

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
				defaultSubtitleComponents.append(product["version"])
			if "authors" in product:
				defaultSubtitleComponents.append(product["authors"])
			if "length" in product:
				defaultSubtitleComponents.append(str(product["length"]))
			defaultSubtitleStr = " | ".join(defaultSubtitleComponents)

			altSubtitleComponents = []
			if "version" in product:
				altSubtitleComponents.append(product["version"])
			if "narrators" in product:
				altSubtitleComponents.append(product["narrators"])
			if "length" in product:
				altSubtitleComponents.append(str(product["length"]))
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
	else:
		addErrorItem("No results found.")
		return None

def loadSearchResults(query):
	requestParams = {
		"keywords": query,
		"num_results": 10,
		"language": "en",
		"products_sort_by": "Relevance",
		"image_sizes": "256",
		"response_groups": "media,product_desc,contributors,product_attrs"
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