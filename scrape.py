#!/usr/bin/env python3

import re
from datetime import date, datetime, timedelta
import os.path
import argparse
import logging
import unittest
import sys
import io

import vpapi
import parse
import scrapeutils
import test

LOGS_PATH = 'logs'
scrapeutils.USE_WEBCACHE = True

def sk_to_iso(datestring):
	"""Converts date(-time) string in SK format (dd. mm. YYYY.) to ISO
	format (YYYY-mm-dd).
	"""
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
	"""Scrape and save motions that are not scraped yet
	starting from the oldest ones. At most 1000 motions are scraped at
	a time. One Motion item, one VoteEvent item and many Vote items
	are created for each scraped motion detail page.

	Returns number of scraped motions.
	"""
	logging.info('Scraping motions of term `%s`' % term)

	# prepare mappings from source identifier to id for MPs and caucuses
	resp = vpapi.get('organizations',
		where={'identifiers': {'$elemMatch': {'identifier': term, 'scheme': 'nrsr.sk/chamber'}}})
	chamber_id = resp['_items'][0]['id']
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

	# scrape motions (at most 1000 at a time) from those sessions
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
					resp = vpapi.post('votes', votes)

			# insertion of the motion, vote event or votes failed
			except:
				if motion_id:
					vpapi.delete('motions/%s' % motion_id)
				if vote_event_id:
					vpapi.delete('vote-events/%s' % vote_event_id)
				raise

			scraped_motions_count += 1
			if scraped_motions_count >= 1000:
				logging.info('Scraped %s motions of term `%s`' % (scraped_motions_count, term))
				return scraped_motions_count

	logging.info('Scraped %s motions of term `%s`' % (scraped_motions_count, term))
	return scraped_motions_count


def main():
	# read command-line arguments
	ap = argparse.ArgumentParser('Scrapes data from Slovak parliament website http://nrsr.sk')
	ap.add_argument('--people', choices=['initial', 'recent', 'none'], default='recent', help='scrape of people, organizations and memberships')
	ap.add_argument('--motions', choices=['initial', 'incremental', 'recent', 'none'], default='recent', help='scrape of motions and votes')
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

		global effective_date
		if args.people == 'initial':
			# initial scrape of all history of people and organizations
			logging.info('Initial scrape - deleting people, organizations and memberships')
			vpapi.delete('memberships')
			vpapi.delete('organizations')
			vpapi.delete('people')
			for term in sorted(parse.terms.keys()):
				effective_date = parse.terms[term]['end_date'] or date.today().isoformat()
				scrape_people(term)

		elif args.people == 'recent':
			# incremental scrape of people and organizations since last scrape
			effective_date = date.today().isoformat()
			term = parse.current_term()
			if term not in parse.terms:
				raise Exception('A new term has started. Scrape canceled. Adjust the terms list in parse.py an rerun for the finished term once more.')
			scrape_people(term)

		if args.motions in ('initial', 'incremental'):
			# scrape of motions from all terms (max 1000 motions at a time)
			if args.motions == 'initial':
				logging.info('Initial scrape - deleting motions, vote-events and votes')
				vpapi.delete('votes')
				vpapi.delete('vote-events')
				vpapi.delete('motions')
			for term in sorted(parse.terms.keys()):
				if scrape_motions(term) > 0: break

		elif args.motions == 'recent':
			# scrape of motions from the current term
			term = parse.current_term()
			scrape_motions(term)

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
