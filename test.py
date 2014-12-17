#!/usr/bin/env python3

import json
import unittest

import parse
import scrapeutils

scrapeutils.USE_WEBCACHE = True

def load_samples(filename):
	"""Return JSON data from file with the given filename."""
	with open('fixtures/%s.json' % filename, encoding='utf-8') as f:
		return json.load(f)


class ParseMpList(unittest.TestCase):
	def test_sample_mp_lists(self):
		"""parse.mp_list should give expected result on sample MP lists"""
		for sample in load_samples('mp_list'):
			result = parse.mp_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.mp_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.mp_list, '999')


class ParseMp(unittest.TestCase):
	def test_sample_mp(self):
		"""parse.mp should give expected result on sample MPs"""
		for sample in load_samples('mp'):
			result = parse.mp(sample['id'], sample['term'])
			if sample.get('memb_index') is not None:
				result['členstvo'] = result['členstvo'][sample['memb_index']:sample['memb_index']+1]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_mp_id(self):
		"""parse.mp should fail for an id that does not exist"""
		self.assertRaises(RuntimeError, parse.mp, '9999', '6')

	def test_not_member_in_term(self):
		"""parse.mp should fail if MP was not a member of parliament in given term"""
		self.assertRaises(RuntimeError, parse.mp, '226', '2')

	def test_nonexistent_term(self):
		"""parse.mp should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.mp, '226', '999')


class ParseGroupList(unittest.TestCase):
	def test_sample_group_lists(self):
		"""parse.group_list should give expected result on sample group lists"""
		for sample in load_samples('group_list'):
			result = parse.group_list(sample['type'], sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_group_type(self):
		"""parse.group_list should fail for an unknown type"""
		self.assertRaises(ValueError, parse.group_list, 'foo', '1')

	def test_nonexistent_term(self):
		"""parse.group_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.group_list, 'committee', '999')


class ParseGroup(unittest.TestCase):
	def test_sample_groups(self):
		"""parse.group should give expected result on sample groups"""
		for sample in load_samples('group'):
			result = parse.group(sample['type'], sample['id'])
			result['členovia'] = result['členovia'][0:1]
			if 'opis' in result:
				result['opis'] = result['opis'][:50]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_group_type(self):
		"""parse.group should fail for an unknown type"""
		self.assertRaises(ValueError, parse.group, 'foo', '1')

	def test_nonexistent_group_id(self):
		"""parse.group should fail for an id that does not exist"""
		self.assertRaises(RuntimeError, parse.group, 'committee', '9999')


class ParseChangeList(unittest.TestCase):
	def test_sample_changes(self):
		"""parse.change_list should give expected result on sample changes"""
		for sample in load_samples('change_list'):
			result = parse.change_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.change_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.change_list, 'abc')


@unittest.skip("Speaker is not used in scraping.")
class ParseSpeaker(unittest.TestCase):
	def test_sample_speaker(self):
		"""parse.speaker should give expected result on sample speaker"""
		for sample in load_samples('speaker'):
			result = parse.speaker()
			if 'životopis' in result:
				result['životopis'] = result['životopis'][:50]
			self.assertEqual(result, sample['expected'])


@unittest.skip("Deputy speakers are not used in scraping.")
class ParseDeputySpeakers(unittest.TestCase):
	def test_sample_deputy_speakers(self):
		"""parse.deputy_speakers should give expected result on sample deputy speakers"""
		for sample in load_samples('deputy_speakers'):
			result = parse.deputy_speakers()
			result = result[sample['index']]
			self.assertEqual(result, sample['expected'])


class ParseSessionList(unittest.TestCase):
	def test_sample_session_lists(self):
		"""parse.session_list should give expected result on sample session lists"""
		for sample in load_samples('session_list'):
			result = parse.session_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.session_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.session_list, '999')


class ParseSession(unittest.TestCase):
	def test_sample_sessions(self):
		"""parse.session should give expected result on sample session"""
		for sample in load_samples('session'):
			result = parse.session(sample['session_number'], sample['term'])
			result = result[sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_invalid_session_number(self):
		"""parse.session should fail for a session number that is not integer"""
		self.assertRaises(ValueError, parse.session, 'abc')

	def test_nonexistent_session_number(self):
		"""parse.session should return empty result for a session number that does not exist"""
		result = parse.session('999')
		self.assertEqual(result, [])

	def test_nonexistent_term(self):
		"""parse.session should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.session, '1', '999')


class ParseMotion(unittest.TestCase):
	def test_sample_motions(self):
		"""parse.motion should give expected result on sample motions"""
		for sample in load_samples('motion'):
			result = parse.motion(sample['id'])
			if sample.get('mp_index') is not None:
				result['hlasy'] = result['hlasy'][sample['mp_index']:sample['mp_index']+1]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_motion_id(self):
		"""parse.motion should fail for an id that does not exist"""
		self.assertRaises(RuntimeError, parse.motion, '0')


class ParseNewDebatesList(unittest.TestCase):
	def test_sample_lists(self):
		"""parse.new_debates_list should give expected result on sample debate lists"""
		for sample in load_samples('new_debates_list'):
			result = parse.new_debates_list(sample['term'],
				since_date=sample['since_date'], until_date=sample['until_date'])
			self.assertEqual(result[sample['index']], sample['expected'])

	def test_wrong_term(self):
		"""parse.new_debates_list should fail for a term before 5th one"""
		self.assertRaises(ValueError, parse.new_debates_list, '4')


class ParseDebateOfTerms56(unittest.TestCase):
	def test_sample_debates(self):
		"""parse.debates_of_terms56 should give expected result on sample debates"""
		for sample in load_samples('debate_of_terms_56'):
			result = parse.debate_of_terms56(sample['id'])
			result['riadky'] = [result['riadky'][sample['line_index']]]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_debate(self):
		"""parse.debates_of_terms56 should fail for debate that does not exist"""
		self.assertRaises(RuntimeError, parse.debate_of_terms56, '1')


# no tests for scraping of old debates as they are no more scraped after initial load


if __name__ == '__main__':
	unittest.main()
