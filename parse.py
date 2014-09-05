"""
	Parsers for official website of National Council of Slovak Republic
	http://www.nrsr.sk
"""

import re
import lxml.html

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
		ext = '|' + term
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
		result['opis'] = lxml.html.tostring(opis, encoding='unicode')

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
		ext = '|' + term + '|' + str(page)
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
	narodeny = div.find("div[@class='article']").text_content()
	result = {
		'url': url,
		'meno': div.find(".//h1").text_content(),
		'fotka':  'http://www.nrsr.sk/web/' + div.find('.//img').get('src'),
		'narodený': re.search(r'Narodený: (.*)', narodeny).group(1),
		'životopis': lxml.html.tostring(div.find('table'), encoding='unicode'),
	}
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
		ext = '|' + term
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
	term = term or max(terms.keys())
	if term and term not in terms.keys():
		raise ValueError("unknown term '%s'" % term)
		
	url = 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok' + \
		'&ZakZborID=13&CisObdobia=%s&CisSchodze=%s&ShowCisloSchodze=False' % \
		(term, session_number)
	content = scrapeutils.download(url)
	if (not session_number.isdigit() or
			int(session_number) == 0 or
			'V systéme nie sú evidované žiadne hlasovania vyhovujúce zadanej požiadavke.' in content):
		raise RuntimeError("Session number '%s' does not exist in term '%s'" % (session_number, term))
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
		ext = '|' + term + '|' + str(page)
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
			if vote_link2 is not None:
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
