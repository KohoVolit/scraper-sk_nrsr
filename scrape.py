#!/usr/bin/env python3

import re
from datetime import date, datetime, timedelta
import os.path
import argparse
import logging
import unittest
import sys
import io
import lxml.html
import json

import vpapi
import parse
import scrapeutils
import test

LOGS_PATH = 'logs'
scrapeutils.USE_WEBCACHE = True

SK_MONTHS = {
	'január': 1, 'januára': 1,
	'február': 2, 'februára': 2,
	'marec': 3 , 'marca': 3,
	'apríl': 4, 'apríla': 4,
	'máj': 5, 'mája': 5,
	'jún': 6, 'júna': 6,
	'júl': 7, 'júla': 7,
	'august': 8, 'augusta': 8,
	'september': 9, 'septembra': 9,
	'október': 10, 'októbra': 10,
	'november': 11, 'novembra': 11,
	'december': 12, 'decembra': 12
}

def sk_to_iso(datestring):
	"""Converts date(-time) string in SK format (d. m. YYYY or
	d. month YYYY) to ISO format (YYYY-mm-dd).
	"""
	sk_months_pattern = r'\b|'.join(SK_MONTHS.keys()) + r'\b'
	m = re.search(sk_months_pattern, datestring)
	if m:
		month = m.group(0)
		datestring = datestring.replace(month, '%s.' % SK_MONTHS[month])
	datestring = datestring.replace('. ', '.')
	try:
		return datetime.strptime(datestring, '%d.%m.%Y').date().isoformat()
	except ValueError:
		try:
			return datetime.strptime(datestring, '%d.%m.%Y %H:%M:%S').isoformat(' ')
		except ValueError:
			return datetime.strptime(datestring, '%d.%m.%Y %H:%M').isoformat(' ')


def datestring_add(datestring, days):
	"""Returns the date specified as string in ISO format with given number of days added.
	"""
	return (datetime.strptime(datestring, '%Y-%m-%d') + timedelta(days=days)).date().isoformat()


class Person:
	@staticmethod
	def _guess_gender(name):
		given_name, family_name = name.split(' ', 1)
		if family_name[-1] == 'á' or given_name in ('Edit', 'Ágnes', 'Klára', 'Anna', 'Erzsébet', 'Erzébet', 'Edita'):
			return 'female'
		else:
			return 'male'

	@staticmethod
	def scrape(id, term):
		source = parse.mp(id, term)

		p = Person()
		p.name = source['meno'] + ' ' + source['priezvisko']
		p.identifiers = [{'identifier': str(id), 'scheme': 'nrsr.sk'}]
		p.family_name = source['priezvisko']

		s = source['meno'].split(' ', 1)
		p.given_name = s[0]
		if len(s) > 1:
			p.additional_name = s[1]

		if source['titul']:
			s = source['titul'].split(',')
			p.honorific_prefix = s[0].strip()
			if len(s) > 1:
				p.honorific_suffix = s[1].strip()

		p.sort_name = source['priezvisko'] + ', ' + source['meno']

		if source['e-mail']:
			p.email = source['e-mail']

		p.gender = Person._guess_gender(p.name)

		if source[r'narodený(á)']:
			p.birth_date = sk_to_iso(source[r'narodený(á)'])

		if source['fotka']:
			p.image = source['fotka']

		if source['národnosť']:
			p.national_identity = source['národnosť']

		if source['bydlisko'] or source['kraj']:
			cd = {
				'label': 'Bydlisko',
				'type': 'address',
			}
			cd['value'] = source['bydlisko'] if source['bydlisko'] else '?'
			if source['kraj']:
				cd['note'] = source['kraj'] + ('' if source['kraj'].endswith('kraj') else ' kraj')
			p.contact_details = [cd]

		if source['www']:
			p.links = [{
				'url': source['www'],
				'note': 'Osobná webstránka'
			}]

		p.sources = [{
			'url': source['url'],
			'note': 'Profil na webe NRSR'
		}]
		return p

	def save(self):
		scraped = self.__dict__
		resp = vpapi.get('people', where={'identifiers': {'$elemMatch': self.identifiers[0]}})
		if not resp['_items']:
			resp = vpapi.post('people', scraped)
		else:
			# update by PUT is preferred over PATCH to correctly remove properties that no longer exist now
			existing = resp['_items'][0]
			resp = vpapi.put('people/%s' % existing['id'], scraped, effective_date=effective_date)

		if resp['_status'] != 'OK':
			raise Exception(self.name, resp)
		return resp['id']


class Organization:
	@staticmethod
	def make_chamber(term):
		o = Organization()
		o.classification = 'chamber'

		o.founding_date = parse.terms[term]['start_date']
		if parse.terms[term]['end_date']:
			o.dissolution_date = parse.terms[term]['end_date']

		o.name = 'Národná rada %s-%s' % (o.founding_date[:4], getattr(o, 'dissolution_date', '')[:4])
		o.identifiers = [{'identifier': term, 'scheme': 'nrsr.sk/chamber'}]

		o.contact_details = [
			{
				'type': 'address',
				'value': 'Národná rada Slovenskej republiky, Námestie Alexandra Dubčeka 1, 812 80 Bratislava 1',
			},
			{
				'label': 'Ústredňa',
				'type': 'tel',
				'value': '+421 2 59721111',
			},
			{
				'label': 'Informácie pre verejnosť',
				'type': 'tel',
				'value': '+421 2 59722463, +421 2 59722460',
			},
			{
				'type': 'email',
				'value': 'info@nrsr.sk',
			},
		]

		o.sources = [{
			'url': 'http://www.nrsr.sk/web/default.aspx?SectionId=152',
			'note': 'Kontaktné informácie na webe NRSR'
		}]
		return o

	@staticmethod
	def scrape(type, id):
		source = parse.group(type, id)

		o = Organization()
		o.name = source['názov']
		o.identifiers = [{'identifier': str(id), 'scheme': 'nrsr.sk/'+type}]
		o.classification = type

		cds = []
		for ctype in ('tel', 'fax', 'email', 'kontakt'):
			if ctype in source:
				cds.append({'type': ctype if ctype != 'kontakt' else 'person', 'value': source[ctype]})
		if cds:
			o.contact_details = cds

		if 'ďalšie dokumenty' in source:
			o.links = [{'url': source['ďalšie dokumenty'], 'note': 'Ďalšie dokumenty'}]

		o.sources = [{
			'url': source['url'],
			'note': 'Profil na webe NRSR'
		}]
		return o

	def set_dates(self, group):
		if group.get('od', '') not in ('', '...', '1. 1. 0001'):
			self.founding_date = sk_to_iso(group['od'])
		if group.get('do', '') not in ('', '...', '1. 1. 0001'):
			self.dissolution_date = sk_to_iso(group['do'])

	def save(self):
		scraped = self.__dict__
		resp = vpapi.get('organizations', where={'identifiers': {'$elemMatch': self.identifiers[0]}})
		if not resp['_items']:
			resp = vpapi.post('organizations', scraped)
		else:
			# update by PUT is preferred over PATCH to correctly remove properties that no longer exist now
			existing = resp['_items'][0]
			resp = vpapi.put('organizations/%s' % existing['id'], scraped, effective_date=effective_date)

		if resp['_status'] != 'OK':
			raise Exception(self.name, resp)
		return resp['id']


class Membership:
	@staticmethod
	def scrape_chamber_changes_and_save(term):
		"""Scrape list of changes of memberships in the parliament chamber
		and save (or update) the respective memberships.
		If an MP referred by the membership does not exist, scrape and save him/her.
		"""
		change_list = parse.change_list(term)

		chamber = vpapi.get('organizations', where={'identifiers': {'$elemMatch': {'identifier': term, 'scheme': 'nrsr.sk/chamber'}}})
		oid = chamber['_items'][0]['id']

		# collect specific roles in the chamber
		roles = {}
		if term == '6':
			roles = {ds['id']: 'deputy speaker' for ds in parse.deputy_speakers()}
			roles['286'] = 'speaker'

		for change in reversed(change_list['_items']):
			logging.info('Scraping mandate change of `%s` at %s' % (change['poslanec']['meno'], change['dátum']))

			# if MP is not scraped yet, scrape and save him
			resp = vpapi.get('people',
				where={'identifiers': {'$elemMatch': {'identifier': change['poslanec']['id'], 'scheme': 'nrsr.sk'}}},
				projection={'id': 1})
			if resp['_items']:
				pid = resp['_items'][0]['id']
			else:
				p = Person.scrape(change['poslanec']['id'], term)
				pid = p.save()

			# create or update the membership
			m = Membership()
			m.label = 'Poslanec Národnej rady SR'
			m.role = roles.get(pid, 'member')
			m.person_id = pid
			m.organization_id = oid
			m.sources = [{
				'url': change_list['url'],
				'note': 'Zmeny v poslaneckom zbore na webe NRSR'
			}]

			if change['zmena'] in ('Mandát vykonávaný (aktívny poslanec)', 'Mandát náhradníka vykonávaný'):
				m.start_date = sk_to_iso(change['dátum'])
				m.save()
			elif change['zmena'] in ('Mandát zaniknutý', 'Mandát sa neuplatňuje', 'Mandát náhradníka zaniknutý'):
				m.end_date = sk_to_iso(change['dátum'])
				# only close an existing membership (counterexample: Érsek, Árpád, 27. 9. 2010 - 10. 3. 2012)
				m.save(False)
			elif change['zmena'] in ('Mandát nadobudnutý vo voľbách', 'Mandát náhradníka získaný'):
				pass
			else:
				raise RuntimeError("unknown change '%s' of a membership in chamber" % change['zmena'])

		logging.info('Scraped %s mandate changes' % len(change_list['_items']))

	@staticmethod
	def scrape_from_group_and_save(group_type, id, term):
		"""Scrape memberships in a given group and save (or update) them.
		If group or MP referred by the membership does not exist, scrape
		and save it/him/her.
		"""
		group = parse.group(group_type, id)

		# if group is not scraped yet, scrape and save it
		g = vpapi.get('organizations',
			where={'identifiers': {'$elemMatch': {'identifier': id, 'scheme': 'nrsr.sk/'+group_type}}},
			projection={'id': 1})
		if g['_items']:
			oid = g['_items'][0]['id']
		else:
			o = Organization.scrape(group_type, id)
			oid = o.save()

		roles = {
			'člen': 'member',
			'členka': 'member',
			'predseda': 'chairman',
			'predsedníčka': 'chairwoman',
			'podpredseda': 'vice-chairman',
			'podpredsedníčka': 'vice-chairwoman',
			'vedúci': 'chairman',
			'vedúca': 'chairwoman',
			'náhradník': 'substitute',
			'náhradníčka': 'substitute',
			'overovateľ': 'verifier',
			'overovateľka': 'verifier',
			'poverený vedením klubu': 'chairman',
			'podpredseda poverený vedením výboru': 'vice-chairman',
			'náhradný člen': 'substitute',
			'náhradná členka': 'substitute',
		}

		for member in group['členovia']:
			logging.info('Scraping membership of `%s`' % member['meno'])

			# if member MP is not scraped yet, scrape and save him
			resp = vpapi.get('people',
				where={'identifiers': {'$elemMatch': {'identifier': member['id'], 'scheme': 'nrsr.sk'}}},
				projection={'id': 1})
			if resp['_items']:
				pid = resp['_items'][0]['id']
			else:
				p = Person.scrape(member['id'], term)
				pid = p.save()

			m = Membership()
			m.person_id = pid
			m.organization_id = oid
			m.sources = [{
				'url': group['url'],
				'note': 'Profil na webe NRSR'
			}]
			# create or update all periods of the membership
			for period in member['obdobia']:
				if period.get('rola'):
					m.label = period['rola'].capitalize() + ' v skupine ' + group['názov']
					m.role = roles[period['rola'].lower()]
				else:
					m.label = 'V skupine ' + group['názov']
				if period.get('od'):
					m.start_date = sk_to_iso(period.get('od'))
				if period.get('do'):
					m.end_date = sk_to_iso(period.get('do'))
				m.save()
				for attr in ('role', 'start_date', 'end_date'):
					if hasattr(m, attr):
						delattr(m, attr)
		logging.info('Scraped %s memberships' % len(group['členovia']))

		# close all open memberships in this group that were not updated
		logging.info('Closing not updated open memberships')
		present = datetime.now() - timedelta(minutes=10)
		query = {
			'organization_id': oid,
			'$or': [{'end_date': {'$exists': False}}, {'end_date': {'$in': [None, '']}}],
			'updated_at': {'$lt': present.isoformat()}
		}
		resp = vpapi.get('memberships', where=query)
		for m in resp['_items']:
			vpapi.patch('memberships/%s' % m['id'], {'end_date': datestring_add(effective_date, -1)})

	def save(self, create_new=True):
		"""If a compatible membership already exists, update it. Otherwise,
		create a new one. If `create_new` is False, only existing memberships
		are updated, no new one is created.
		Memberships are compatible if their fields `start_date`, `role` and `post`
		are compatible. Field 'end_date' is not checked to allow for later corrections
		of guessed end dates used when a member disappears from a group profile.
		"""
		resp = vpapi.get('memberships',
			where={'person_id': self.person_id, 'organization_id': self.organization_id},
			sort=[('start_date', -1)])
		to_save = self.__dict__
		id = None
		for existing in resp['_items']:
			if self._merge_values('start_date', to_save, existing) \
					and self._merge_values('role', to_save, existing) \
					and self._merge_values('post', to_save, existing):
				id = existing['id']
				break
		if id:
			resp = vpapi.put('memberships/%s' % id, to_save)
		else:
			if not create_new: return
			resp = vpapi.post('memberships', self.__dict__)

		if resp['_status'] != 'OK':
			raise Exception(self.name, resp)

	@staticmethod
	def _merge_values(key, candidate, existing):
		"""Check for compatibility of values candidate[key] and existing[key]
		and store the more specific value into candidate[key].
		Values are compatible if at least one of them is empty
		(ie. None, "", or key is not present) or they are equal.
		A more specific value is the non-empty one.
		"""
		c = candidate.get(key)
		e = existing.get(key)
		if c and e and c != e:
			return False
		if key in candidate or key in existing:
			candidate[key] = e or c
		return True


def scrape_people(term):
	"""Scrape and save people, organizations and memberships for the
	given term.
	"""
	logging.info('Scraping people, organizations and memberships of term `%s`' % term)

	global effective_date
	effective_date = date.today().isoformat() if term == parse.current_term() else parse.terms[term]['end_date']

	# get or make chamber
	chamber = vpapi.get('organizations', where={'identifiers': {'$elemMatch': {'identifier': term, 'scheme': 'nrsr.sk/chamber'}}})
	if chamber['_items']:
		chamber_id = chamber['_items'][0]['id']
	else:
		chamber_id = Organization.make_chamber(term).save()

	# scrape MPs
	mps = parse.mp_list(term)
	for mp in mps['_items']:
		logging.info('Scraping person `%s` (id=%s)' % (mp['meno'], mp['id']))
		p = Person.scrape(mp['id'], term)
		p.save()
	logging.info('Scraped %s people' % len(mps['_items']))

	# scrape memberships of MPs in the chamber
	logging.info('Scraping mandate changes')
	Membership.scrape_chamber_changes_and_save(term)

	# scrape groups and memberships in them
	for type in ('committee', 'caucus', 'delegation', 'friendship group'):
		groups = parse.group_list(type, term)
		for group in groups['_items']:
			logging.info('Scraping %s `%s` (id=%s)' % (type, group['názov'], group['id']))
			o = Organization.scrape(type, group['id'])
			o.set_dates(group)
			o.parent_id = chamber_id
			o.save()
			logging.info('Scraping its memberships')
			Membership.scrape_from_group_and_save(type, group['id'], term)
		logging.info('Scraped %s %s' % (len(groups['_items']), type + ('es' if type == 'caucus' else 's')))


def get_chamber_id(term):
	"""Return chamber id of the given term."""
	resp = vpapi.get('organizations',
		where={'identifiers': {'$elemMatch': {'identifier': term, 'scheme': 'nrsr.sk/chamber'}}})
	return resp['_items'][0]['id']


def get_all_items(resource, **kwargs):
	"""Read all items from the resource without paging."""
	result = []
	page=1
	while True:
		resp = vpapi.get(resource, page=page, **kwargs)
		result.extend(resp['_items'])
		if 'next' not in resp['_links']: break
		page += 1
	return result


def scrape_motions(term):
	"""Scrape and save motions from the given term that are not scraped
	yet starting from the oldest ones. One Motion item, one VoteEvent
	item and many Vote items are created for each scraped motion detail
	page.

	Returns number of scraped motions.
	"""
	logging.info('Scraping motions of term `%s`' % term)

	# prepare mappings from source identifier to id for MPs and caucuses
	chamber_id = get_chamber_id(term)
	resp = get_all_items('people', projection={'identifiers': 1})
	mps = {mp['identifiers'][0]['identifier']: mp['id'] for mp in resp}
	resp = vpapi.get('organizations', where={'classification': 'caucus', 'parent_id': chamber_id})
	caucuses = {c['name']: c['id'] for c in resp['_items']}

	# prepare list of sessions that are not completely scraped yet
	sessions_to_scrape = []
	session_list = parse.session_list(term)
	for s in session_list['_items']:
		session = parse.session(s['číslo'], term)
		if len(session) == 0: continue
		last_motion_id = session[-1]['id']
		m = vpapi.get('motions',
			where={'sources.url': 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=%s' % last_motion_id})
		if m['_items']: break
		sessions_to_scrape.append((s['názov'], session))

	# scrape motions from those sessions
	scraped_motions_count = 0
	for session_name, session in reversed(sessions_to_scrape):
		logging.info('Scraping session `%s`' % session_name)
		for i, m in enumerate(session):
			m_id = re.search(r'ID=(\d+)', m['url']['výsledok']).group(1)
			m_url = 'http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=%s' % m_id
			resp = vpapi.get('motions', where={'sources.url': m_url})
			if resp['_items']: continue

			try:
				motion_id, vote_event_id = None, None

				# insert motion
				logging.info('Scraping motion %s of %s (voted at %s)' % (i+1, len(session), m['dátum']))
				parsed_motion = parse.motion(m['id'])
				motion = {
					'organization_id': chamber_id,
					'legislative_session': {'name': session_name},
					'text': parsed_motion['názov'],
					'date': sk_to_iso(m['dátum']),
					'sources': [{
						'url': parsed_motion['url'],
						'note': 'Hlasovanie na webe NRSR'
					}],
				}
				if 'výsledok' in parsed_motion:
					motion['result'] = 'pass' if parsed_motion['výsledok'] == 'Návrh prešiel' else 'fail'
				resp = vpapi.post('motions', motion)
				motion_id = resp['id']

				# insert vote event
				vote_event = {
					'identifier': parsed_motion['číslo'],
					'motion_id': motion_id,
					'organization_id': chamber_id,
					'legislative_session': {'name': session_name},
					'start_date': motion['date'],
					'sources': [{
						'url': parsed_motion['url'],
						'note': 'Hlasovanie na webe NRSR'
					}],
				}
				if 'výsledok' in parsed_motion:
					vote_event['result'] = motion['result']
				if 'súčty' in parsed_motion:
					options = {
						'yes': '[z] za',
						'no': '[p] proti',
						'abstain': '[?] zdržalo sa',
						'absent': '[0] neprítomní',
						'not voting': '[n] nehlasovalo'
					}
					vote_event['counts'] = [
						{'option': o, 'value': int(parsed_motion['súčty'][s])}
						for o, s in options.items() if parsed_motion['súčty'][s] != ''
					]
					if len(vote_event['counts']) == 0:
						del vote_event['counts']
				resp = vpapi.post('vote-events', vote_event)
				vote_event_id = resp['id']

				# insert votes
				if 'hlasy' in parsed_motion and len(parsed_motion['hlasy']) > 0:
					vote_options = {
						'z': 'yes',
						'p': 'no',
						'?': 'abstain',
						'n': 'not voting',
						'0': 'absent'
					}
					votes = []
					for v in parsed_motion['hlasy']:
						# skip MPs not applying their mandate
						if v['hlas'] == '-': continue
						votes.append({
							'vote_event_id': vote_event_id,
							'option': vote_options[v['hlas']],
							'voter_id': mps.get(v['id']),
							'group_id': caucuses.get(v['klub']),
						})
					if len(votes) > 0:
						resp = vpapi.post('votes', votes)

			# delete incomplete data if insertion of the motion, vote event or votes failed
			except:
				if motion_id:
					vpapi.delete('motions/%s' % motion_id)
				if vote_event_id:
					vpapi.delete('vote-events/%s' % vote_event_id)
				raise

			scraped_motions_count += 1

	logging.info('Scraped %s motions of term `%s`' % (scraped_motions_count, term))
	return scraped_motions_count


def scrape_old_debates(term):
	"""Scrape and save speeches from debates of the given term, one
	of those older terms where transcripts of debates are stored in
	RTF files.

	Returns number of scraped speeches.
	"""

	def insert_speech(type):
		"""Insert a speech entity with the given type and data
		from parent scope variables."""
		speech = {
			'organization_id': chamber_id,
			'legislative_session': {'name': session_name},
			'section': {'name': section_name},
			'start_date': date + ' 00:00:00',
			'number': len(speeches),
			'type': type,
			'text': text.strip().replace('[', '(').replace(']', ')'),
			'sources' : [{
				'url': debate['url'],
				'note': 'Prepis debaty v Digitálnej knižnici na webe NRSR'
			}]
		}
		if type != 'scene':
			speech['speaker_id'] = speaker_id
			speech['speaker_label'] = label.strip()
		speeches.append(speech)

	logging.info('Scraping debates of term `%s`' % term)
	chamber_id = get_chamber_id(term)

	# prepare mapping from MP's name to id
	resp = get_all_items('people', projection={'given_name': 1, 'additional_name': 1, 'family_name': 1})
	mps = {}
	for mp in resp:
		if 'additional_name' in mp:
			name = '%s. %s. %s' % (mp['given_name'][0], mp['additional_name'][0], mp['family_name'])
		else:
			name = '%s. %s' % (mp['given_name'][0], mp['family_name'])
		mps[name] = mp['id']

	# load name corrections
	with open('name_corrections.json', 'r') as f:
		name_corrections = json.load(f)

	# scrape list of debates
	debates = parse.old_debates_list(term)

	# add the debate missing in the list
	if term == '4':
		debates.append({
			'názov': 'Autorizovaná rozprava, 48. schôdza NR SR, 3. 2. 2010',
			'id': '2010_02_03',
			'url': 'http://www.nrsr.sk/dl/Browser/DsDocument?documentId=391413'
		})

	speech_count = 0
	session_name = ''
	for debate in debates:
		# skip obsolete debates in the list
		if term == '1':
			if (debate['názov'] == 'Stenozáznam' and debate['id'] != '198550' or
					debate['id'] in ('65890', '65945', '65949')):
				continue
		elif term == '2':
			if debate['názov'].startswith('Stenografická') and debate['id'] != '92098':
				continue

		logging.info('Scraping debate `%s` (id=%s)' % (debate['názov'], debate['id']))
		if term == '1':
			paragraphs = parse.debate_of_term1(debate['id'])
		else:
			paragraphs = parse.debate_of_terms234(debate['id'])

		# normalize header of the debate transcript
		if term == '2':
			# join first 4 paragraphs and add trailing underscores to mark the header
			paragraphs = ['%s %s %s %s\n___' % (paragraphs[0], paragraphs[1], paragraphs[2],
				paragraphs[3])] + paragraphs[4:]
		elif term in ('3', '4'):
			# join first paragraphs until " hodine" ending is found
			# and add trailing underscores to mark the header
			p = ''
			while True:
				p += ' ' + paragraphs.pop(0)
				if p.endswith('hodine'): break
			if paragraphs[0].startswith('___'):
				paragraphs.pop(0)
			paragraphs.insert(0, p + '\n___')

		# extract speeches from the debate
		speeches = []
		text = ''
		within_scene = False
		for par in paragraphs:
			par = par.replace('\n', ' ').strip()
			if not par: continue

			# fix last scene
			if re.match(r'Rokovanie.*? schôdze .*?\s+(sa skončilo|skončené)\s+o\s+.*?\s+hodine', par):
				if not par.startswith('('):
					par = '(%s)' % par

			# convert slash pairs and brackets to parentheses
			par = re.sub(r'(^|[^\d])/(.*?)/', r'\1(\2)', par)
			par = re.sub(r'\[(.*?)\]', r'(\1)', par)
			# convert all inner nested parentheses to brackets
			n = 1
			while n >= 1:
				(par, n) = re.subn(r'\((.*?)\((\.*?)\)(.*?)\)', r'(\1[\2]\3)', par, flags=re.DOTALL)

			# process eventual multiparagraph scene
			if par.startswith('(') and par.count('(') > par.count(')'):
				if text:
					insert_speech('speech')
				text = '<p>%s</p>' % par[1:]
				within_scene = True
				continue
			if within_scene:
				if par.endswith(')') and par.count(')') > par.count('('):
					text += '\n\n<p>%s</p>' % par[:-1]
					insert_speech('scene')
					text = ''
					within_scene = False
				else:
					text += '\n\n<p>%s</p>' % par
				continue

			# process eventual header
			header_pattern = r'((\(?(\d+)\.\)?\s+schôdz)|slávnostn).*?(\d+)\..*\b(\w{3,})\s+(\d{4}).*?_{3,}$'
			hd = re.search(header_pattern, par, re.DOTALL)
			if hd:
				date = '%s. %s %s' % (hd.group(4), hd.group(5), hd.group(6))
				old_session_name = session_name
				session_name = ('Slávnostné zasadnutie %s' % date
					if hd.group(1).startswith('sláv')
					else '%s. schôdza' % hd.group(3))
				if session_name != old_session_name:
					section_count = 0
				section_count += 1
				section_name = '%s. deň rokovania, %s' % (section_count, date)
				date = sk_to_iso(date)
				continue

			# process eventual start of a speech
			if date < '2001-09-04':
				# format `Foreign minister J. Doe:`
				speech_start_pattern = r'(.*?)\b([^\W\d])\.[\s_]+((\w)\.[\s_]+)?(\w+):$'
			else:
				# format `J. Doe, foreign minister: speech`
				speech_start_pattern = r'([^\W\d])\.[\s_]+((\w)\.[\s_]+)?(\w+),\s+(.+?):(.+)$'
			sp = re.match(speech_start_pattern, par, re.DOTALL)
			if sp:
				# save previous speech
				if text:
					insert_speech('speech')

				# identify speaker
				if date < '2001-09-04':
					name = '%s. %s' % (sp.group(2), sp.group(5))
					if (sp.group(4)):
						name = name.replace(' ', ' %s. ' % sp.group(4))
					label = sp.group(1)
					par = ''
				else:
					name = '%s. %s' % (sp.group(1), sp.group(4))
					if (sp.group(3)):
						name = name.replace(' ', ' %s. ' % sp.group(3))
					label = sp.group(5)
					par = sp.group(6)

				if name in name_corrections:
					name = name_corrections[name]
				label = label[0].lower() + label[1:].strip()
				text = ''
				speaker_id = mps.get(name)

				# create unknown speakers
				if not speaker_id:
					logging.info('Speaker `%s, %s` not found, creating new Person' % (name, label))
					name_parts = re.match(r'(\w)\. ((\w)\. )?(\w+)', name)
					person = {
						'name': name,
						'family_name': name_parts.group(4),
						'given_name': name_parts.group(1)
					}
					person['sort_name'] = '%s, %s.' % (person['family_name'], person['given_name'])
					if name_parts.group(3):
						person['additional_name'] = name_parts.group(3)
						person['sort_name'] += ' %s.' % person['additional_name']
					resp = vpapi.post('people', person)
					speaker_id = resp['id']
					mps[name] = speaker_id

			# recognize date(-time) stamps in transcripts
			ds = re.match(r'^\s*(\d+\.\s\w+\s\d{4})(.*hodine)?\s*$', par)
			if ds:
				try:
					date = sk_to_iso(ds.group(1).strip())
					continue
				except ValueError:
					pass

			# process eventual scene in this paragraph
			scene_pattern = r'(.*?)\(([\d%s][^\(\)]{2,}[\.?!“])\s*\)(.*)$' % scrapeutils.CS_UPPERS
			while True:
				scene = re.match(scene_pattern, par, re.DOTALL)
				if not scene: break
				if scene.group(1):
					text += '\n\n<p>%s</p>' % scene.group(1).strip()
				if text:
					insert_speech('speech')
				text = '<p>%s</p>' % scene.group(2).strip()
				insert_speech('scene')
				text = ''
				par = scene.group(3)

			if par:
				text += '\n\n<p>%s</p>' % par

		if text:
			insert_speech('speech')

		vpapi.post('speeches', speeches)
		logging.info('Scraped %s speeches' % len(speeches))
		speech_count += len(speeches)

	logging.info('Scraped %s speeches in total' % speech_count)


def scrape_new_debates(term):
	"""Scrape and save speeches from debates of the given term, one
	of those newer terms where transcripts of debates are published
	in parts assigned to individual speakers.

	Returns number of scraped speeches.
	"""

	debate_part_kinds = {
		'Uvádzajúci uvádza bod': 'speech',
		'Vstup predsedajúceho': 'speech',
		'Vystúpenie spoločného spravodajcu': 'speech',
		'Vystúpenie': 'speech',
		'Vystúpenie v rozprave': 'speech',
		'Vystúpenie s faktickou poznámkou': 'speech',
		'Vystúpenie s procedurálnym návrhom': 'speech',
		'Prednesenie otázky': 'question',
		'Zodpovedanie otázky': 'answer',
		'Doplňujúca otázka / reakcia zadávajúceho': 'question',
		'Prednesenie interpelácie': 'question',
		'Odpoveď na interpeláciu': 'answer',
		'scene': 'scene'
	}

	def insert_speech(kind):
		"""Insert a speech entity for the given debate part kind
		and data from parent scope variables."""
		speech = {
			'organization_id': chamber_id,
			'legislative_session': {'name': session_name},
			'section': {'name': section_name},
			'start_date': start_datetime,
			'end_date': end_datetime,
			'number': len(speeches) + 1,
			'type': debate_part_kinds.get(kind, 'speech'),
			'text': text.strip().replace('[', '(').replace(']', ')'),
			'sources' : [{
				'url': dpart_url,
				'note': 'Prepis časti debaty na webe NRSR'
			}]
		}
		if kind != 'scene':
			speech['speaker_id'] = speaker_id
			speech['speaker_label'] = label.strip()
		speeches.append(speech)

	logging.info('Scraping debates of term `%s`' % term)
	chamber_id = get_chamber_id(term)

	# prepare mapping from MP's name to id
	resp = get_all_items('people', projection={'name': 1})
	mps = {mp['name']: mp['id'] for mp in resp}

	# load name corrections
	with open('name_corrections.json', 'r') as f:
		name_corrections = json.load(f)

	# scraping will start since the most recent debate date
	resp = vpapi.get('speeches',
		where={'organization_id': chamber_id},
		sort=[('start_date', -1)])
	since_date = resp['_items'][0]['start_date'][:10] if resp['_items'] else None

	# scrape list of debate parts
	debate_parts = parse.new_debates_list(term, since_date)

	speech_count = 0
	session_name = ''
	section_name = ''
	for dp in debate_parts:
		if 'prepis' not in dp: continue

		# skip already scraped debate parts
		resp = vpapi.get('speeches', where={'sources.url': dp['prepis']['url']})
		if resp['_items']: continue

		logging.info('Scraping debate part %s %s-%s (id=%s)' %
			(dp['dátum'], dp['trvanie']['od'], dp['trvanie']['do'], dp['prepis']['id']))
		dpart = parse.debate_of_terms56(dp['prepis']['id'])

		start_datetime = sk_to_iso('%s %s' % (dp['dátum'], dp['trvanie']['od']))
		end_datetime = sk_to_iso('%s %s' % (dp['dátum'], dp['trvanie']['do']))
		dpart_kind = dp['druh']
		dpart_url = dp['prepis']['url']
		sitting = re.search(r'(\d+)\.?\s*deň', dpart['nadpis'])
		if sitting is None:
			logging.info('Sitting number not found in the heading `%s`' % dpart['nadpis'])
			continue
		if not (session_name.startswith('%s. ' % dp['schôdza']) and
				section_name.startswith('%s. ' % sitting.group(1))):
			# start of a new sitting
			if section_name:
				if len(speeches) > 0:
					vpapi.post('speeches', speeches)
				logging.info('Scraped %s speeches' % len(speeches))
				speech_count += len(speeches)
			speeches = []
		session_name = '%s. schôdza' % dp['schôdza']
		section_name = '%s. deň rokovania, %s' % (sitting.group(1), dp['dátum'])

		# add the first speaker name that is sometimes missing
		first_speaker = '<strong>%s, %s</strong>' % (dp['osoba']['meno'], dp['osoba']['funkcia'])
		dpart['riadky'].insert(0, first_speaker)

		# extract speeches from the debate part
		text = ''
		within_scene = False
		for par in dpart['riadky']:
			if not par: continue
			par = par.replace('\n', ' ').strip()

			# skip eventual speech number
			if re.match('^(\d+)\.$', par): continue

			# convert slash pairs and brackets to parentheses
			par = re.sub(r'(^|[^\d])/(.*?)/', r'\1(\2)', par)
			par = re.sub(r'\[(.*?)\]', r'(\1)', par)
			# convert all inner nested parentheses to brackets
			n = 1
			while n >= 1:
				(par, n) = re.subn(r'\((.*?)\((\.*?)\)(.*?)\)', r'(\1[\2]\3)', par, flags=re.DOTALL)

			# process eventual multiparagraph scene
			if par.startswith('(') and par.count('(') > par.count(')'):
				if text:
					insert_speech(dpart_kind)
				text = '<p>%s</p>' % lxml.html.fromstring(par[1:]).text_content()
				within_scene = True
				continue
			if within_scene:
				if par.endswith(')') and par.count(')') > par.count('('):
					text += '\n\n<p>%s</p>' % lxml.html.fromstring(par[:-1]).text_content()
					insert_speech('scene')
					text = ''
					within_scene = False
				else:
					text += '\n\n<p>%s</p>' % lxml.html.fromstring(par).text_content()
				continue

			# process eventual new speaker
			# format `Doe, John, foreign minister`
			speech_start_pattern = r'<strong>(\w+), (\w+\.?)( (\w+\.?))?, (.*)</strong>'
			sp = re.match(speech_start_pattern, par, re.DOTALL)
			if sp:
				# save previous speech
				if text:
					insert_speech(dpart_kind)

				# identify speaker
				name = '%s %s' % (sp.group(2), sp.group(1))
				if (sp.group(4)):
					name = name.replace(' ', ' %s ' % sp.group(4))
				label = sp.group(5)
				text = ''
				if name in name_corrections:
					name = name_corrections[name]
				if len(name) == 0: continue
				speaker_id = mps.get(name)

				# create unknown speakers
				if not speaker_id:
					logging.info('Speaker `%s, %s` not found, creating new Person' % (name, label))
					name_parts = re.match(r'(\w+\.?)( (\w+\.?))? (\w+)', name)
					person = {
						'name': name,
						'family_name': name_parts.group(4),
						'given_name': name_parts.group(1)
					}
					person['sort_name'] = '%s, %s' % (person['family_name'], person['given_name'])
					if name_parts.group(3):
						person['additional_name'] = name_parts.group(3)
						person['sort_name'] += ' %s' % person['additional_name']
					resp = vpapi.post('people', person)
					speaker_id = resp['id']
					mps[name] = speaker_id
				continue

			# remove HTML tags
			par = lxml.html.fromstring(par).text_content()

			# process eventual scene in this paragraph
			scene_pattern = r'(.*?)\(([\d%s][^\(\)]{2,}[\.?!“])\s*\)(.*)$' % scrapeutils.CS_UPPERS
			while True:
				scene = re.match(scene_pattern, par, re.DOTALL)
				if not scene: break
				if scene.group(1):
					text += '\n\n<p>%s</p>' % scene.group(1).strip()
				if text:
					insert_speech(dpart_kind)
				text = '<p>%s</p>' % scene.group(2).strip()
				insert_speech('scene')
				text = ''
				par = scene.group(3)

			if par:
				text += '\n\n<p>%s</p>' % par

		if text:
			insert_speech(dpart_kind)

	if len(speeches) > 0:
		vpapi.post('speeches', speeches)
	logging.info('Scraped %s speeches' % len(speeches))
	speech_count += len(speeches)

	logging.info('Scraped %s speeches in total' % speech_count)


def main():
	# read command-line arguments
	ap = argparse.ArgumentParser('Scrapes data from Slovak parliament website http://nrsr.sk')
	ap.add_argument('--people', choices=['initial', 'recent', 'none'], default='recent', help='scrape of people, organizations and memberships')
	ap.add_argument('--votes', choices=['initial', 'recent', 'none'], default='recent', help='scrape of motions and votes')
	ap.add_argument('--debates', choices=['initial', 'recent', 'none'], default='recent', help='scrape of speeches from debates')
	ap.add_argument('--term', help='term to scrape recent data from; current term is used when omitted')
	args = ap.parse_args()

	# set-up logging to a local file
	if not os.path.exists(LOGS_PATH):
		os.makedirs(LOGS_PATH)
	logname = datetime.now().strftime('%Y-%m-%d-%H%M%S') + '.log'
	logname = os.path.join(LOGS_PATH, logname)
	logname = os.path.abspath(logname)
	logging.basicConfig(level=logging.DEBUG, format='%(message)s', handlers=[logging.FileHandler(logname, 'w', 'utf-8')])
	logging.getLogger('requests').setLevel(logging.ERROR)

	logging.info('Started')
	try:
		# set-up the API access
		vpapi.parliament('sk/nrsr')
		vpapi.authorize('scraper', os.environ['VPAPI_PWD_SK_NRSR'])

		# indicate that the scraper has started
		db_log = vpapi.post('logs', {'status': 'running', 'file': logname, 'params': args.__dict__})

		# clear cached source files
		logging.info('Clearing cached files')
		scrapeutils.clear_cache()

		# test parser functions
		logging.info('Testing parser functions')
		out = io.StringIO()
		suite = unittest.TestLoader().loadTestsFromModule(sys.modules['test'])
		result = unittest.TextTestRunner(stream=out).run(suite)
		logging.info(out.getvalue())
		if result.errors or result.failures:
			raise RuntimeError('Unit tests of parser functions failed, update canceled.')

		if args.people == 'initial':
			# initial scrape of all history of people and organizations
			logging.info('Initial scrape - deleting people, organizations and memberships')
			vpapi.delete('memberships')
			vpapi.delete('organizations')
			vpapi.delete('people')
			for term in sorted(parse.terms.keys()):
				scrape_people(term)

		elif args.people == 'recent':
			# incremental scrape of people and organizations since the last scrape
			term = args.term or parse.current_term()
			if term not in parse.terms:
				raise Exception('Unknown term `%s`. Scrape canceled. Add it to the terms list in parse.py an rerun for the recently finished term once more.' % term)
			scrape_people(term)

		if args.votes == 'initial':
			# initial scrape of votes from all terms
			logging.info('Initial scrape - deleting votes, vote-events and motions')
			vpapi.delete('votes')
			vpapi.delete('vote-events')
			vpapi.delete('motions')
			for term in sorted(parse.terms.keys()):
				scrape_motions(term)

		elif args.votes == 'recent':
			# incremental scrape of votes since the last scrape
			term = args.term or parse.current_term()
			if term not in parse.terms:
				raise Exception('Unknown term `%s`. Scrape canceled. Add it to the terms list in parse.py an rerun once more.' % term)
			scrape_motions(term)

		terms_with_old_debates = ('1', '2', '3', '4')
		if args.debates == 'initial':
			# initial scrape of debates from all terms
			logging.info('Initial scrape - deleting speeches')
			vpapi.delete('speeches')
			# newer terms are scraped first to get full names of unknown speakers
			for term in sorted(parse.terms.keys()):
				if term in terms_with_old_debates: continue
				scrape_new_debates(term)
			for term in terms_with_old_debates:
				scrape_old_debates(term)

		elif args.debates == 'recent':
			# incremental scrape of debates since the last scrape
			term = args.term or parse.current_term()
			if term not in parse.terms:
				raise Exception('Unknown term `%s`. Scrape canceled. Add it to the terms list in parse.py an rerun once more.' % term)
			if term in terms_with_old_debates:
				scrape_old_debates(term)
			else:
				scrape_new_debates(term)

		status = 'finished'
		logging.info('Finished')

	except Exception as e:
		logging.critical(e, exc_info=True)
		if hasattr(e, 'response'):
			logging.critical(e.response._content.decode('utf-8'))
		status = 'failed'
		logging.info('Failed')
	finally:
		if 'db_log' in locals():
			vpapi.patch('logs/%s' % db_log['id'], {'status': status})


if __name__ == '__main__':
	main()
