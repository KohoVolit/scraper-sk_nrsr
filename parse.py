"""
	Parsers for official website of National Council of Slovak Republic
	http://www.nrsr.sk
"""

import re
import lxml.html
import os.path
import subprocess

import scrapeutils

terms = {
	'1': {'start_date': '1994-10-01', 'end_date': '1998-09-25'},
	'2': {'start_date': '1998-09-26', 'end_date': '2002-09-21'},
	'3': {'start_date': '2002-09-22', 'end_date': '2006-06-16'},
	'4': {'start_date': '2006-06-17', 'end_date': '2010-06-12'},
	'5': {'start_date': '2010-06-13', 'end_date': '2012-03-10'},
	'6': {'start_date': '2012-03-11', 'end_date': None},
}


def current_term():
	url = 'http://www.nrsr.sk/web/default.aspx?sid=poslanci'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	option = html.find('.//select[@id="_sectionLayoutContainer_ctl01__currentTerm"]/option[@selected]')
	return option.get('value')


def mp_list(term=None):
	"""Parse list of MPs."""
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)
	term = term or max(terms.keys())

	url = 'http://www.nrsr.sk/web/Default.aspx?sid=poslanci/zoznam_abc&ListType=0&CisObdobia=%s' % term
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	result = {
		'url': url,
		'_items': [{
			'id': re.search(r'PoslanecID=(\d+)', mp.get('href')).group(1),
			'meno': mp.text,
		} for mp in html.findall('.//div[@class="mps_list"]//li/a')]
	}

	return scrapeutils.plaintext(result)


def mp(id, term):
	"""Parse MP from his profile webpage."""
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)

	url = 'http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=%s&CisObdobia=%s' % (id, term)
	content = scrapeutils.download(url)
	if 'Unexpected error!' in content:
		raise RuntimeError("MP with id '%s' does not exist in term '%s'" % (id, term))
	html = lxml.html.fromstring(content)

	result = {
		'id': str(id),
		'url': url
	}
	for div in html.findall('.//div[@class="mp_personal_data"]//div[strong]'):
		label = div.findtext('strong')
		value = div.find('span')
		result[label.lower()] = value.text_content() if value is not None else ''

	result['fotka'] = html.find('.//div[@class="mp_foto"]/img').get('src')

	result['členstvo'] = []
	ul = html.find('.//span[@id="_sectionLayoutContainer_ctl01_ctlClenstvoLabel"]').getparent().getnext()
	for li in ul.findall('li'):
		m = re.search(r'(.*?)\s*\((.*?)\)', li.text)
		result['členstvo'].append({'meno': m.group(1), 'rola': m.group(2)})

	return scrapeutils.plaintext(result)


def group_list(type, term=None):
	"""Parse list of groups of a given type (committee, caucus, delegation, friendship group)."""
	types = {
		'committee': {
			'url': 'http://www.nrsr.sk/web/default.aspx?SectionId=77',
			'term_param_name': '_sectionLayoutContainer$ctl02$_currentTerm',
		},
		'caucus': {
			'url': 'http://www.nrsr.sk/web/default.aspx?SectionId=69',
			'term_param_name': '_sectionLayoutContainer$ctl02$_currentTerm',
		},
		'delegation': {
			'url': 'http://www.nrsr.sk/web/default.aspx?sid=eu/delegacie/zoznam',
			'term_param_name': '_sectionLayoutContainer$ctl01$_currentTerm',
		},
		'friendship group': {
			'url': 'http://www.nrsr.sk/web/default.aspx?sid=eu/sp/zoznam',
			'term_param_name': '_sectionLayoutContainer$ctl01$_currentTerm',
		},
	}

	if type not in types:
		raise ValueError("unknown type of group '%s'" % type)
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)

	content = scrapeutils.download(types[type]['url'])
	html = lxml.html.fromstring(content)

	# scraping for older terms requires another POST request to emulate selectbox choice
	if term:
		data = {
			types[type]['term_param_name']: term,
			'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
			'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
		}
		ext = '|%s' % term
		content = scrapeutils.download(types[type]['url'], 'POST', data, ext)
		html = lxml.html.fromstring(content)

	# pick list items
	result = {
		'url': types[type]['url'],
		'_items': []
	}
	for li in html.findall('.//ul[@class="longlist"]//li'):
		a = li.find('a')
		group = {
			'id': re.search(r'(ID|SkupinaId)=(\d+)', a.get('href')).group(2),
			'názov': a.text,
		}
		line = li.text_content()
		info = re.search(group['názov'] + r'\s*(\((.+?) - (.+?)\))?\s*(\S.*)?$', line, re.DOTALL)
		if info:
			if info.group(2):
				group['od'] = info.group(2)
				group['do'] = info.group(3)
			if info.group(4):
				group['poznámka'] = info.group(4)
		result['_items'].append(group)

	return scrapeutils.plaintext(result)


def group(type, id):
	"""Parse group of a given type (committee, caucus, delegation, friendship group)
	from its profile webpage."""
	types = {
		'committee': {
			'url': 'http://www.nrsr.sk/web/Default.aspx?sid=vybory/vybor&ID=',
			'members_xpath': './/table[@class="tab_zoznam"]//tr',
			'name_xpath': 'td[1]/a/strong',
		},
		'caucus': {
			'url': 'http://www.nrsr.sk/web/Default.aspx?sid=poslanci/kluby/klub&ID=',
			'members_xpath': './/table[@class="tab_zoznam"]//tr',
			'name_xpath': 'td[1]/a/strong',
		},
		'delegation': {
			'url': 'http://www.nrsr.sk/web/Default.aspx?sid=eu/delegacie/delegacia&ID=',
			'members_xpath': './/table[@class="tab_details"]//tr',
			'name_xpath': 'td[1]/strong/a',
		},
		'friendship group': {
			'url': 'http://www.nrsr.sk/web/Default.aspx?sid=eu/sp/sp&SkupinaId=',
			'members_xpath': './/table[@class="tab_details"]//tr',
			'name_xpath': 'td[1]/strong/a',
		},
	}

	if type not in types:
		raise ValueError("unknown type of group '%s'" % type)
	url = types[type]['url'] + str(id)

	content = scrapeutils.download(url)
	if 'Unexpected error!' in content:
		raise RuntimeError("group of type '%s' with id '%s' not found")

	content = content.replace('member_vez', 'member')	# exception in committee with id=119
	html = lxml.html.fromstring(content)

	result = {
		'id': str(id),
		'url': url
	}
	result['názov'] = html.findtext('.//h1')
	podnadpis = html.find('.//h2/span')
	if podnadpis is not None:
		p = podnadpis.text_content()
		if p not in ('', 'Zoznam členov'):
			result['podnadpis']  = p
	opis = html.find('.//div[@align="justify"]')
	if opis is not None:
		result['opis'] = lxml.html.tostring(opis, encoding='unicode', with_tail=False)

	# current term and older terms are displayed differently
	if 'Zoznam členov' in content:
		# scraping current term - contact information and member cards
		for tr in html.findall('.//table[@class="tab_details"]//tr'):
			label = tr.findtext('td[1]/span')
			if not label: continue
			value = tr.find('td[2]/span')
			result[label.lower().rstrip('.:')] = value.text_content() if value is not None else ''

		other_docs = html.find('.//a[@id="_sectionLayoutContainer_ctl01__otherDocumentsLink"]')
		if other_docs is not None:
			result['ďalšie dokumenty'] = other_docs.get('href')

		result['členovia'] = []
		for div in html.findall('.//div[@class="member"]'):
			member = {
				'id': re.search(r'PoslanecID=(\d+)', div.find('.//a').get('href')).group(1),
				'fotka':  'http://www.nrsr.sk/web/' + div.find('.//img').get('src'),
				'meno': div.findtext('.//a/strong'),
				'obdobia': [{'rola': div.findtext('.//span[1]').lower()}],
			}
			if type != 'caucus':
				member['klub'] = div.findtext('.//em')[1:-1]
				if member['klub'] in ('-', 'nie je členom poslaneckého klubu'):
					member['klub'] = None
				elif not member['klub'].startswith('Klub '):
					member['klub'] = 'Klub ' + member['klub']
			result['členovia'].append(member)

	else:
		# scraping older terms - list of members with membership roles and durations
		result['členovia'] = []
		for i, tr in enumerate(html.findall(types[type]['members_xpath'])):
			if type in ('caucus', 'committee') and i < 2: continue
			member = {
				'id': re.search(r'PoslanecID=(\d+)', tr.find('td[1]//a').get('href')).group(1),
				'meno': tr.findtext(types[type]['name_xpath']),
				'obdobia': [],
			}
			for period in tr.findtext('td[2]').split(', '):
				membership = re.search(r'([^\(]*)\((.+?) - (.+?)\)', period, re.DOTALL)
				if membership:
					member['obdobia'].append({
						'rola': membership.group(1),
						'od': membership.group(2),
						'do': membership.group(3),
					})
			result['členovia'].append(member)

	return scrapeutils.plaintext(result, ['opis'])


def change_list(term=None):
	"""Parse list of chamber membership changes."""
	term = term or max(terms.keys())
	if term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)

	url = 'http://www.nrsr.sk/web/default.aspx?sid=poslanci/zmeny'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	result = {
		'url': url,
		'_items': []
	}
	ctl = 'ctl00'
	page = 1
	while True:
		# scraping of individual pages requires POST request to emulate pager click
		data = {
			'__EVENTTARGET': '_sectionLayoutContainer$ctl01$_ResultGrid$ctl01$' + ctl,
			'_sectionLayoutContainer$ctl01$_currentTerm': term,
			'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
			'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
		}
		ext = '|%s|%s' % (term, page)
		content = scrapeutils.download(url, 'POST', data, ext)
		html = lxml.html.fromstring(content)

		# extract all changes from the current page
		for tr in html.findall('.//table[@id="_sectionLayoutContainer_ctl01__ResultGrid"]//tr'):
			if tr.get('class') in ('pager', 'tab_zoznam_header'): continue
			date = tr.findtext('td[1]')
			poslanec = tr.find('td[2]')
			text = re.search(r'(\S.*?)\s*\((.*?)\)', poslanec.text_content())
			link = poslanec.find('a').get('href')
			id = re.search(r'PoslanecID=(\d+)', link)
			result['_items'].append({
				'dátum': tr.findtext('td[1]'),
				'poslanec': {
					'meno': text.group(1),
					'url': 'http://www.nrsr.sk/web/' + link,
					'id': id.group(1),
					'klub': text.group(2),
				},
				'zmena': tr.findtext('td[3]'),
				'dôvod': tr.findtext('td[4]'),
			})

		current_page = html.find('.//table[@id="_sectionLayoutContainer_ctl01__ResultGrid"]//tr[1]//span')
		if current_page is None: break
		next_page = current_page.getnext()
		if next_page is None: break
		ctl = next_page.get('href')[-10:-5]
		page += 1

	return scrapeutils.plaintext(result)


def speaker():
	"""Parse current speaker (predseda) of the chamber."""
	url = 'http://www.nrsr.sk/web/default.aspx?sid=predseda'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	div = html.find(".//div[@id='_sectionLayoutContainer__panelContent']")
	result = {
		'url': url,
		'meno': div.find(".//h1").text_content(),
	}

	image = div.find('.//img')
	if image is not None:
		result['fotka'] = 'http://www.nrsr.sk/web/' + image.get('src')

	born = div.find("div[@class='article']")
	if born is not None:
		result['narodený'] = re.search(r'Narodený: (.*)', born.text_content()).group(1)

	bio = div.find('table')
	if bio is not None:
		result['životopis'] = lxml.html.tostring(bio, encoding='unicode', with_tail=False)

	return scrapeutils.plaintext(result)


def deputy_speakers():
	"""Parse current deputy speakers (podpredsedovia) of the chamber."""
	url = 'http://www.nrsr.sk/web/default.aspx?sid=podpredsedovia'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	result = []
	for div in html.findall(".//div[@class='vicechairman_bigbox']"):
		name = div.find('.//a')
		link = name.get('href')
		id = re.search(r'PoslanecID=(\d+)', link)
		description = div.find(".//div[@class='vicechairman_description']")

		result.append({
			'fotka': 'http://www.nrsr.sk/web/' + div.find('.//img').get('src'),
			'meno': name.text,
			'url': 'http://www.nrsr.sk/web/' + link,
			'id': id.group(1),
			'kandidoval(a) za': description.find('div[1]/strong').tail,
			'narodený(á):': description.find('div[2]/strong').tail,
			'národnosť': description.find('div[3]/strong').tail,
		})

	return scrapeutils.plaintext(result)


def session_list(term=None):
	"""Parse list of sessions in one term of office of the parliament."""
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)

	url = 'http://www.nrsr.sk/web/default.aspx?sid=schodze/hlasovanie/schodze'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	# scraping for older terms requires another POST request to emulate selectbox choice
	if term:
		data = {
			'_sectionLayoutContainer$ctl01$_termsCombo': term,
			'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
			'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
		}
		ext = '|%s' % term
		content = scrapeutils.download(url, 'POST', data, ext)
		html = lxml.html.fromstring(content)

	# pick list items
	result = {
		'url': url,
		'_items': []
	}
	for li in html.findall('.//div[@id="_sectionLayoutContainer__panelContent"]//ul//li'):
		a = li.find('a')
		link = a.get('href')
		session = {
			'číslo': re.search(r'CisSchodze=(\d+)', link).group(1),
			'názov': a.text,
			'trvanie': re.search(r'\((.+?)\)', li.text_content()).group(1),
			'url': 'http://www.nrsr.sk/web/' + link,
		}
		result['_items'].append(session)

	return scrapeutils.plaintext(result)


def session(session_number, term=None):
	"""Parse a session, i.e. the list of voted motions."""
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)
	term = term or max(terms.keys())
	if not session_number.isdigit() or int(session_number) == 0:
		raise ValueError("Invalid session number '%s'" % session_number)

	url = 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok' + \
		'&ZakZborID=13&CisObdobia=%s&CisSchodze=%s&ShowCisloSchodze=False' % \
		(term, session_number)
	content = scrapeutils.download(url)
	if 'V systéme nie sú evidované žiadne hlasovania vyhovujúce zadanej požiadavke.' in content:
		return []
	html = lxml.html.fromstring(content)

	result = []
	ctl = 'ctl00'
	page = 1
	while True:
		# scraping of individual pages requires POST request to emulate pager click
		data = {
			'__EVENTTARGET': '_sectionLayoutContainer$ctl01$_resultGrid$ctl01$' + ctl,
			'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
			'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
		}
		ext = '|%s|%s' % (term, page)
		content = scrapeutils.download(url, 'POST', data, ext)
		html = lxml.html.fromstring(content)

		# extract all motions from the current page
		for tr in html.findall('.//table[@id="_sectionLayoutContainer_ctl01__resultGrid"]//tr'):
			if tr.get('class') in ('pager', 'tab_zoznam_header'): continue
			date = tr.find('td[1]')
			vote_event = tr.find('td[2]/a')
			vote_event_link = vote_event.get('href')
			id = re.search(r'ID=(\d+)', vote_event_link)
			motion = {
				'dátum': date.text_content(),
				'číslo': vote_event.text_content(),
				'názov': tr.findtext('td[4]'),
				'id': id.group(1),
				'url': {
					'výsledok': 'http://www.nrsr.sk/web/' + vote_event_link,
				}
			}
			object = tr.find('td[3]/a')
			if object is not None:
				motion['čpt'] = {
					'číslo': object.text_content(),
					'url': 'http://www.nrsr.sk/web/' + object.get('href')
				}
			vote_link2 = tr.find('td[5]/a').get('href')
			if vote_link2:
				motion['url']['kluby'] = 'http://www.nrsr.sk/web/' + vote_link2
			result.append(motion)

		current_page = html.find('.//table[@id="_sectionLayoutContainer_ctl01__resultGrid"]//tr[1]//span')
		if current_page is None: break
		next_page = current_page.getnext()
		if next_page is None: break
		ctl = next_page.get('href')[-10:-5]
		page += 1

	return scrapeutils.plaintext(result)


def motion(id):
	"""Parse a motion/vote-event with individual votes cast by MPs."""
	url = 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=%s' % id
	content = scrapeutils.download(url)
	if 'Unexpected error!' in content:
		raise RuntimeError("Motion with id '%s' does not exist" % id)
	html = lxml.html.fromstring(content)

	panel = html.find('.//div[@id="_sectionLayoutContainer__panelContent"]')
	motion = panel.find('.//div[@class="voting_stats_summary_full"]')
	session_link = motion.find('div[1]//a').get('href')
	counts = panel.find('.//div[@id="_sectionLayoutContainer_ctl01_ctl00__resultsTablePanel"]/div')

	result = {
		'url': url,
		'schôdza': {
			'číslo': re.search(r'CisSchodze=(\d+)', session_link).group(1),
			'obdobie': re.search(r'CisObdobia=(\d+)', session_link).group(1),
			'url': 'http://www.nrsr.sk/web/' + session_link,
		},
		'dátum': motion.findtext('div[2]/span'),
		'číslo': motion.findtext('div[3]/span'),
		'názov': motion.findtext('div[4]/span'),
	}
	res = motion.findtext('div[5]/span')
	if res:
		result['výsledok'] = res
	if counts is not None:
		result['súčty'] = {
			'prítomní': counts.findtext('div[1]/span'),
			'hlasujúcich': counts.findtext('div[2]/span'),
			'[z] za': counts.findtext('div[3]/span'),
			'[p] proti': counts.findtext('div[4]/span'),
			'[?] zdržalo sa': counts.findtext('div[5]/span'),
			'[n] nehlasovalo': counts.findtext('div[6]/span'),
			'[0] neprítomní': counts.findtext('div[7]/span'),
		}

	mps = panel.find('.//div[@id="_sectionLayoutContainer_ctl01__bodyPanel"]')
	if mps is not None:
		result['hlasy'] = []
		for td in mps.findall('.//td'):
			if td.get('class') == 'hpo_result_block_title':
				caucus = td.text.strip()
			else:
				if not td.text: continue
				vote = td.text[1].lower()
				a = td.find('a')
				family_name, _, given_name = a.text.partition(',')
				link = a.get('href')
				id = re.search(r'PoslanecID=(\d+)', link)
				mp = {
					'meno': given_name.strip() + ' ' + family_name.strip(),
					'klub': caucus,
					'hlas': vote,
					'id': id.group(1),
					'url': 'http://www.nrsr.sk/web/' + link
				}
				result['hlasy'].append(mp)

	related_docs = panel.findall('./ul/li[img]/a')
	if related_docs:
		result['dokumenty'] = [{
			'názov': a.text.strip(),
			'url': 'http://www.nrsr.sk/web/' + a.get('href')
		} for a in related_docs]

	return scrapeutils.plaintext(result)


def old_debates_list(term):
	"""Parse list of debates for the given term of office from NRSR
	Digital Library.
	Appropriate for older terms (1.-4.) where debates are not split
	by speaker."""
	if term not in ['1', '2', '3', '4']:
		raise ValueError("Old style transcripts are not available for term '%s'" % term)

	result = []
	page = 0
	while True:
		url = 'http://www.nrsr.sk/dl/Browser/Grid?nodeType=DocType&legId=13&chamberId=0' + \
			'&categoryId=1&committeeId=0&documentTypeId=5&folderId=0&meetingNr=' + \
			'&termNr=%s&pageIndex=%s' % (term, page)
		content = scrapeutils.download(url)
		html = lxml.html.fromstring(content)

		# extract all debates from the current page
		for tr in html.findall('.//table[@class="resultTable"]//tr'):
			sequence_number = tr.findtext('td[1]/a')
			title = tr.find('td[2]/a')
			doc_id = re.search(r'documentId=(\d+)', title.get('href'))
			debate = {
				'časť': sequence_number,
				'názov': title.text,
				'url': 'http://www.nrsr.sk' + title.get('href'),
				'id': doc_id.group(1)
			}
			result.append(debate)

		page += 1
		pages = html.findtext('.//div[@class="pager"]/span[last()]')
		if page >= int(pages): break

	return scrapeutils.plaintext(result)


def debate_of_term1(id):
	"""Parse a debate transcript in term 1 format and return list of
	its paragraphs' text content."""
	# download the debate transcript or use a local fixed debate if there is one
	filename = os.path.join('fixed_debates', 'debate_%s.html' % id)
	if os.path.exists(filename):
		with open(filename, 'r') as f:
			content = f.read()
	else:
		url = 'http://www.nrsr.sk/dl/Browser/Document?documentId=%s' % id
		content = scrapeutils.download(url)
		if 'Unexpected error!' in content:
			raise RuntimeError("Debate with id '%s' does not exist" % id)

	# fix markup and parse to HTML tree
	content = content.replace('12. 9. 1995<o:p></o:p>', '12. septembra 1995')
	content = content.replace('<o:p></o:p>', '')
	html = lxml.html.fromstring(content)

	# extract paragraph texts, use blank line as paragraph separator
	result = []
	text = ''
	for par in html.findall('.//p'):
		line = scrapeutils.plaintext(par.text_content())
		if len(line) > 0 and not re.match(r'\w+ deň rokovania', line):
			text += '\n%s' % line
		else:
			if text:
				result.append(scrapeutils.clear_hyphens(text, '\n'))
			text = line

	return scrapeutils.plaintext(result)


def debate_of_terms234(id):
	"""Parse a debate transcript in terms 2-4 format and return list of
	its paragraphs' text content."""
	# download RTF file or use a local fixed debate if there is one
	filename = os.path.join('fixed_debates', 'debate_%s.rtf' % id)
	if not os.path.exists(filename):
		url = 'http://www.nrsr.sk/dl/Browser/Document?documentId=%s' % id
		rtf = scrapeutils.download(url)
		filename = os.path.join(scrapeutils.WEBCACHE_PATH, 'debate_%s.rtf' % id)
		with open(filename, 'w') as f:
			f.write(rtf)

	# convert from RTF to HTML using unoconv using LibreOffice
	content = subprocess.check_output(['unoconv', '-f', 'html', '--stdout', filename])

	html = lxml.html.fromstring(content)
	result = []
	for par in html.findall('./body/p'):
		result.append(par.text_content())

	return scrapeutils.plaintext(result)


def new_debates_list(term, since_date=None, until_date=None):
	"""Parse list of debate parts for the given term of office from
	NRSR web. Appropriate for newer terms (since 5th) where split
	debates are available. If `since_date` or `until_date` is given
	in ISO format only the debate parts since/until that date are
	returned.
	"""
	if term not in ['5', '6']:
		raise ValueError("Parsed transcripts are not available for term '%s'" % term)

	url = 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/rozprava'
	content = scrapeutils.download(url)
	html = lxml.html.fromstring(content)

	# a POST request to emulate choice of term in second selectbox and pressing the button
	data = {
		'_sectionLayoutContainer$ctl01$_termNr': term,
		'_sectionLayoutContainer$ctl01$_search': 'Vyhľadať',
		'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
		'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
	}
	base_ext = '|new|%s' % term
	if since_date:
		data['_sectionLayoutContainer$ctl01$_dateFrom$dateInput'] = since_date + '-00-00-00'
		base_ext += '|s%s' % since_date
	if until_date:
		data['_sectionLayoutContainer$ctl01$_dateTo$dateInput'] = since_date + '-00-00-00'
		base_ext += '|u%s' % since_date
	content = scrapeutils.download(url, 'POST', data, base_ext)
	html = lxml.html.fromstring(content)

	result = []
	page = 1
	while True:
		# extract all debate parts from the current page
		for tr in html.findall('.//table[@id="_sectionLayoutContainer_ctl01__newDebate"]/tr'):
			if tr.get('class') in ('pager', 'tab_zoznam_header'): continue
			session_number = tr.find('td[1]')
			date = tr.find('td[2]')
			time_interval = tr.find('td[3]')
			time = re.search(r'(.*?) - (.*)', time_interval.text)
			part_type = time_interval.find('em')
			speaker = tr.find('td[4]')
			speaker_label = speaker.find('br').tail.strip('( ')
			debate_part = {
				'schôdza': session_number.text.replace('.', ''),
				'dátum': date.text,
				'trvanie': {'od': time.group(1), 'do': time.group(2)},
				'druh': part_type.text or '',
				'osoba': {'meno': speaker.findtext('strong'), 'funkcia': speaker_label}
			}
			speaker_link = speaker.find('a')
			if speaker_link is not None:
				speaker_url = speaker_link.get('href')
				id = re.search(r'PoslanecID=(\d+)', speaker_url)
				debate_part['osoba']['url'] = speaker_url
				debate_part['osoba']['id'] = id.group(1)
			for a in tr.findall('td[5]/a'):
				link = a.get('href')
				if 'Vystupenie' in link:
					id = re.search(r'Vystupenie/(\d+)', link)
					debate_part['video'] = {'url': link, 'id': id.group(1)}
				elif 'Rokovanie' in link:
					id = re.search(r'Rokovanie/(\d+)', link)
					debate_part['video_rokovania'] = {'url': link, 'id': id.group(1)}
				elif 'SpeakerSection' in link:
					id = re.search(r'SpeakerSectionID=(\d+)', link)
					debate_part['prepis'] = {'url': link, 'id': id.group(1)}
				else:
					raise RuntimeError('Unrecognized link in section %s/%s/%s' %
						(session_number, date, time_interval))
			result.append(debate_part)

		# test if there is a link to next page
		current_page = html.find('.//table[@id="_sectionLayoutContainer_ctl01__newDebate"]//tr[1]//span')
		if current_page is None: break
		next_page = current_page.getparent().getnext()
		if next_page is None: break
		page += 1

		# a POST request to emulate pager click
		data = {
			'__EVENTTARGET': '_sectionLayoutContainer$ctl01$_newDebate',
			'__EVENTARGUMENT': 'Page$%s' % page,
			'_sectionLayoutContainer$ctl01$_termNr': term,
			'__VIEWSTATE': html.find('.//input[@id="__VIEWSTATE"]').get('value'),
			'__EVENTVALIDATION': html.find('.//input[@id="__EVENTVALIDATION"]').get('value'),
		}
		ext = base_ext + '|%s' % page
		content = scrapeutils.download(url, 'POST', data, ext)
		html = lxml.html.fromstring(content)

	return scrapeutils.plaintext(result)


def debate_of_terms56(id):
	"""Parse a debate transcript in terms 5-6 format and return its
	structure."""
	# download the debate transcript
	url = 'http://mmserv2.nrsr.sk/NRSRInternet/indexpopup.aspx?module=Internet&page=SpeakerSection&SpeakerSectionID=%s&ViewType=content&' % id
	content = scrapeutils.download(url)
	if 'Unexpected error!' in content:
		raise RuntimeError("Debate with id '%s' does not exist" % id)

	# parse to HTML tree
	html = lxml.html.fromstring(content)
	result = {
		'nadpis': html.findtext('.//h1'),
		'podnadpis': html.findtext('.//h2'),
	}

	# parse headings and individual lines used as paragraphs
	main_block = html.find('.//div[@style="text-align: justify;"]')
	if main_block is not None:
		main_content = lxml.html.tostring(main_block, encoding='unicode', with_tail=False)
		main_content = main_content[len('<div style="text-align: justify;">'):-len('</div>')]
		result['riadky'] = re.split('<br\s*/?>', main_content)

	return scrapeutils.plaintext(result)
