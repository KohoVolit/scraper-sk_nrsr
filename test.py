#!/usr/bin/env python3

import parse
import unittest
import scrapeutils

scrapeutils.USE_WEBCACHE = True

class ParseMpList(unittest.TestCase):
	samples = [
		# MP list of current term
		{
			"term": None,
			"index": 1,
			"expected":
			{
				"id": "872",
				"meno": "Andreánsky, Ladislav"
			}
		},
		# MP list of a former term
		{
			"term": "4",
			"index": 1,
			"expected":
			{
				"id": "644",
				"meno": "Andruskó, Imre"
			}
		},
	]

	def test_sample_mp_lists(self):
		"""parse.mp_list should give expected result on sample MP lists"""
		for sample in self.samples:
			result = parse.mp_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.mp_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.mp_list, '999')


class ParseMp(unittest.TestCase):
	samples = [
		# MP of current term
		{
			"id": "773",
			"term": "6",
			"memb_index": 1,
			"expected":
			{
				"id": "773",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=773&CisObdobia=6",
				"meno": "Jozef",
				"priezvisko": "Viskupič",
				"titul": "Mgr.",
				"kandidoval(a) za": "OĽaNO",
				"narodený(á)": "8. 2. 1976",
				"národnosť": "slovenská",
				"bydlisko": "Trnava",
				"kraj": "Trnavský",
				"e-mail": "jozef_viskupic@nrsr.sk",
				"www": "www.jozefviskupic.sk",
				"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=773&ImageWidth=140",
				"členstvo": [
					{
						"meno": "Výbor NR SR pre európske záležitosti", 
						"rola": "overovateľ"
					}
				]
			},
		},
		# MP of a former term
		{
			"id": "226",
			"term": "4",
			"memb_index": None,
			"expected":
			{
				"id": "226",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=226&CisObdobia=4",
				"meno": "Pavol",
				"priezvisko": "Abrhan",
				"titul": "Ing.",
				"kandidoval(a) za": "KDH",
				"narodený(á)": "25. 7. 1959",
				"národnosť": "slovenská",
				"bydlisko": "Nové Zámky",
				"kraj": "Nitriansky",
				"e-mail": "pavol_abrhan@nrsr.sk",
				"www": "",
				"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=226&ImageWidth=140",
				"členstvo": [],
			},
		},
	]

	def test_sample_mp(self):
		"""parse.mp should give expected result on sample MPs"""
		for sample in self.samples:
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
	samples = [
		# group lists of current term
		{
			"type": "committee",
			"term": None,
			"index": 0,
			"expected":
			{
				"id": "115",
				"názov": "Mandátový a imunitný výbor NR SR"
			}
		},
		{
			"type": "caucus",
			"term": None,
			"index": 0,
			"expected":
			{
				"id": "41",
				"názov": "Klub SMER – SD",
				"od": "4. 4. 2012",
				"do": "..."
			}
		},
		{
			"type": "delegation",
			"term": None,
			"index": 0,
			"expected":
			{
				"id": "35",
				"názov": "Stála delegácia NR SR v Parlamentnom zhromaždení Rady Európy"
			}
		},
		{
			"type": "friendship group",
			"term": None,
			"index": 0,
			"expected":
			{
				"id": "73",
				"názov": "Skupina priateľstva s Českou republikou"
			}
		},
		# group lists of a former term
		{
			"type": "committee",
			"term": "4",
			"index": 0,
			"expected":
			{
				"id": "74",
				"názov": "Mandátový a imunitný výbor NR SR"
			}
		},
		{
			"type": "caucus",
			"term": "4",
			"index": 1,
			"expected":
			{
				"id": "28",
				"názov": "Klub SDKÚ – DS",
				"od": "4. 7. 2006",
				"do": "12. 6. 2010",
				"poznámka": "NR SR vzala na vedomie utvorenie Klubu SDKÚ Uznesením NR SR č. 11."
			}
		},
		{
			"type": "delegation",
			"term": "4",
			"index": 0,
			"expected":
			{
				"id": "19",
				"názov": "Stála delegácia NR SR v Parlamentnom zhromaždení Rady Európy"
			}
		},
		{
			"type": "friendship group",
			"term": "4",
			"index": 0,
			"expected":
			{
				"id": "25",
				"názov": "Skupina priateľstva s Albánskom, Bosnou a Hercegovinou, Bulharskom, Chorvátskom, Srbskom a Čiernou horou, Macedónskom a Rumunskom"
			}
		},
	]

	def test_sample_group_lists(self):
		"""parse.group_list should give expected result on sample group lists"""
		for sample in self.samples:
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
	samples = [
		# groups of current term
		{
			"type": "committee",
			"id": "116",
			"expected":
			{
				"id": "116",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=vybory/vybor&ID=116",
				"názov": "Výbor NR SR pre nezlučiteľnosť funkcií",
				"podnadpis": "Základné informácie o výbore",
				"opis": "<div align=\"justify\">Výbor NR SR pre nezlučiteľnos",
				"tel": "5972 1490",
				"fax": "5441 5468",
				"email": "vnf@nrsr.sk",
				"ďalšie dokumenty": "http://www.nrsr.sk/dl/Browser/Committee?committeeExternalId=116",
				"členovia": [
					{
						"id": "326",
						"meno": "Novotný, Viliam",
						"klub": "Klub SDKÚ – DS",
						"obdobia": [
							{
								"rola": "predseda",
							}
						],
						"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=326&ImageWidth=44",
					}
				]
			},
		},
		{
			"type": "caucus",
			"id": "41",
			"expected":
			{
				"id": "41",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/kluby/klub&ID=41",
				"názov": "Klub SMER – SD",
				"tel": "02/5972 - 1395",
				"fax": "02/5441 - 4255, 02/5441 - 3708",
				"email": "klubsmer@nrsr.sk",
				"členovia": [
					{
						"id": "278",
						"meno": "Laššáková, Jana",
						"obdobia": [
							{
								"rola": "predsedníčka",
							}
						],
						"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=278&ImageWidth=44",
					}
				]
			},
		},
		{
			"type": "delegation",
			"id": "35",
			"expected":
			{
				"id": "35",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=eu/delegacie/delegacia&ID=35",
				"názov": "Stála delegácia NR SR v Parlamentnom zhromaždení Rady Európy",
				"opis": "<div align=\"justify\">\r\n<p>\xa0</p>\r\n<p>Rada Európy je",
				"členovia": [
					{
						"id": "679",
						"meno": "Nachtmannová Oľga",
						"klub": "Klub SMER – SD",
						"obdobia": [
							{
								"rola": "vedúca",
							}
						],
						"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=679&ImageWidth=44",
					}
				]
			},
		},
		{
			"type": "friendship group",
			"id": "73",
			"expected":
			{
				"id": "73",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=eu/sp/sp&SkupinaId=73",
				"názov": "Skupina priateľstva s Českou republikou",
				"kontakt": "Jarmila Nováková, Odbor zahraničných vzťahov a agendy EÚ Kancelárie Národnej rady Slovenskej republiky",
				"tel": "+421 59 72 25 12",
				"fax": "+421 54 41 53 24",
				"email": "jarmila.novakova@nrsr.sk",
				"členovia": [
					{
						"id": "721",
						"meno": "Jasaň, Viliam",
						"klub": "Klub SMER – SD",
						"obdobia": [
							{
								"rola": "predseda",
							}
						],
						"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=721&ImageWidth=44",
					}
				]
			},
		},
		# groups of a former term
		{
			"type": "committee",
			"id": "75",
			"expected":
			{
				"id": "75",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=vybory/vybor&ID=75",
				"názov": "Výbor NR SR pre nezlučiteľnosť funkcií",
				"členovia": [
					{
						"id": "645",
						"meno": "Belásová Milada",
						"obdobia": [
							{
								"rola": "členka",
								"od": "4. 7. 2006",
								"do": "12. 6. 2010",
							}
						]
					}
				]
			},
		},
		{
			"type": "caucus",
			"id": "28",
			"expected":
			{
				"id": "28",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/kluby/klub&ID=28",
				"názov": "Klub SDKÚ – DS",
				"podnadpis": "NR SR vzala na vedomie utvorenie Klubu SDKÚ Uznesením NR SR č. 11.",
				"členovia": [
					{
						"id": "647",
						"meno": "Cibulková, Katarína",
						"obdobia": [
							{
								"rola": "členka",
								"od": "4. 7. 2006",
								"do": "12. 6. 2010",
							}
						]
					}
				]
			},
		},
		{
			"type": "delegation",
			"id": "19",
			"expected":
			{
				"id": "19",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=eu/delegacie/delegacia&ID=19",
				"názov": "Stála delegácia NR SR v Parlamentnom zhromaždení Rady Európy",
				"členovia": [
					{
						"id": "228",
						"meno": "Angyalová Edita",
						"obdobia": [
							{
								"rola": "členka",
								"od": "7. 9. 2006",
								"do": "30. 4. 2007",
							}
						]
					}
				]
			},
		},
		{
			"type": "friendship group",
			"id": "27",
			"expected":
			{
				"id": "27",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=eu/sp/sp&SkupinaId=27",
				"názov": "Skupina priateľstva s Českou republikou",
				"členovia": [
					{
						"id": "226",
						"meno": "Abrhan, Pavol",
						"obdobia": [
							{
								"rola": "Člen",
								"od": "4. 7. 2006",
								"do": "12. 6. 2010"
							}
						]
					}
				]
			},
		},
	]

	def test_sample_groups(self):
		"""parse.group should give expected result on sample groups"""
		for sample in self.samples:
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
	samples = [
		{
			"term": "5",
			"index": 51,
			"expected":
			{
				"dátum": "10. 3. 2012",
				"poslanec": {
					"meno": "Jarjabek, Dušan",
					"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=61&CisObdobia=5",
					"id": "61",
					"klub": "-",
				},
				"zmena": "Mandát zaniknutý",
				"dôvod": "Jeho mandát zanikol ukončením volebného obdobia.",
			},
		},
		{
			"term": None,
			"index": -2,
			"expected":
			{
				"dátum": "11. 3. 2012",
				"poslanec": {
					"meno": "Mikuš, Jozef",
					"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=317&CisObdobia=6",
					"id": "317",
					"klub": "SDKÚ – DS",
				},
				"zmena": "Mandát nadobudnutý vo voľbách",
				"dôvod": "Stal sa poslancom NR SR.",
			},
		},
	]

	def test_sample_changes(self):
		"""parse.change_list should give expected result on sample changes"""
		for sample in self.samples:
			result = parse.change_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.change_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.change_list, 'abc')


class ParseSpeaker(unittest.TestCase):
	samples = [
		{
			"expected":
			{
				"url": "http://www.nrsr.sk/web/default.aspx?sid=predseda",
				"meno": "Mgr. Pavol Paška",
				"fotka": "http://www.nrsr.sk/web/img/Paska_Pavol-w-207x266.jpg",
				"narodený": "23. 2. 1958 v Košiciach",
				"životopis": "<table>\r\n\r\n<tr>\r\n<td> </td>\r\n<td width=\"1%\"> </td>",
			}
		},
	]

	def test_sample_speaker(self):
		"""parse.speaker should give expected result on sample speaker"""
		for sample in self.samples:
			result = parse.speaker()
			result['životopis'] = result['životopis'][:50]
			self.assertEqual(result, sample['expected'])


class ParseDeputySpeakers(unittest.TestCase):
	samples = [
		{
			"index": 1,
			"expected":
			{
				"fotka": "http://www.nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID=297&ImageWidth=130",
				"meno": "JUDr. Zmajkovičová Renáta",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=297",
				"id": "297",
				"kandidoval(a) za": "SMER – sociálna demokracia",
				"narodený(á):": "09. 05. 1962",
				"národnosť": "slovenská",
			}
		},
	]

	def test_sample_deputy_speakers(self):
		"""parse.deputy_speakers should give expected result on sample deputy speakers"""
		for sample in self.samples:
			result = parse.deputy_speakers()
			result = result[sample['index']]
			self.assertEqual(result, sample['expected'])


class ParseSessionList(unittest.TestCase):
	samples = [
		# session list of current term
		{
			"term": None,
			"index": -2,
			"expected":
			{
				"číslo": "2",
				"názov": "2. schôdza",
				"trvanie": "2. - 16. 5. 2012",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok&ZakZborID=13&CisObdobia=6&CisSchodze=2&ShowCisloSchodze=False", 
			}
		},
		# session list of a former term
		{
			"term": "4",
			"index": 1,
			"expected":
			{
				"číslo": "52",
				"názov": "52. schôdza",
				"trvanie": "25. - 26. 5. 2010",
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok&ZakZborID=13&CisObdobia=4&CisSchodze=52&ShowCisloSchodze=False",
			}
		},
	]

	def test_sample_session_lists(self):
		"""parse.session_list should give expected result on sample session lists"""
		for sample in self.samples:
			result = parse.session_list(sample['term'])
			result = result['_items'][sample['index']]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_term(self):
		"""parse.session_list should fail for a term that does not exist"""
		self.assertRaises(ValueError, parse.session_list, '999')


class ParseSession(unittest.TestCase):
	samples = [
		# session of the current term
		{
			"term": None,
			"session_number": "2",
			"index": 0,
			"expected":
			{
				"dátum": "02. 05. 2012 13:04:15", 
				"číslo": "1", 
				"názov": "Prezentácia.", 
				"id": "30051", 
				"url": {
					"výsledok": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasovanie&ID=30051", 
					"kluby": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=30051"
				}
			},
		},
		# session of a former term
		{
			"term": "4",
			"session_number": "11",
			"index": 5,
			"expected":
			{
				"dátum": "19. 06. 2007 17:10:25", 
				"číslo": "6", 
				"názov": "Správa o činnosti verejného ochrancu práv (tlač 243).\r\nHlasovanie o návrhu uznesenia.", 
				"id": "20995",
				"url": {
					"výsledok": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasovanie&ID=20995", 
					"kluby": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=20995"
				}, 
				"čpt": {
					"url": "http://www.nrsr.sk/web/Default.aspx?sid=zakony/cpt&ZakZborID=13&CisObdobia=4&ID=243", 
					"číslo": "243"
				}
			},
		},
	]

	def test_sample_sessions(self):
		"""parse.session should give expected result on sample session"""
		for sample in self.samples:
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
	samples = [
		{
			"id": "33841",
			"mp_index": 1,
			"expected":
			{
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=33841",
				"názov": "Hlasovanie o pozmeňujúcich a doplňujúcich návrhoch k programu 35. schôdze Národnej rady Slovenskej republiky.\r\nNávrh posl. Kollára.",
				"číslo": "7",
				"schôdza": {
					"číslo": "35",
					"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok&ZakZborID=13&CisObdobia=6&CisSchodze=35&ShowCisloSchodze=False",
					"obdobie": "6"
				},
				"dátum": "13. 5. 2014 13:19",
				"výsledok": "Návrh neprešiel",
				"súčty": {
					"prítomní": "141",
					"hlasujúcich": "138",
					"[z] za": "37",
					"[p] proti": "77",
					"[?] zdržalo sa": "24",
					"[n] nehlasovalo": "3",
					"[0] neprítomní": "9"
				},
				"hlasy": [
					{
						"meno": "Ján Babič",
						"id": "735",
						"url": "http://www.nrsr.sk/web/Default.aspx?sid=poslanci/poslanec&PoslanecID=735&CisObdobia=6",
						"klub": "Klub SMER – SD",
						"hlas": "p"
					},
				]
			},
		},
		{
			"id": "30297",
			"mp_index": None,
			"expected":
			{
				"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=30297",
				"názov": "Návrh na voľbu predsedu a člena Osobitného kontrolného výboru Národnej rady Slovenskej republiky na kontrolu činnosti Slovenskej informačnej služby (tlač 109).",
				"číslo": "0",
				"schôdza": {
					"číslo": "3",
					"url": "http://www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/vyhladavanie_vysledok&ZakZborID=13&CisObdobia=6&CisSchodze=3&ShowCisloSchodze=False",
					"obdobie": "6"
				},
				"dátum": "19. 6. 2012 17:30",
				"dokumenty": [
					{
						"názov": "Zápisnica o výsledku tajného hlasovania",
						"url": "http://www.nrsr.sk/web//web/Dynamic/Download.aspx?DocID=368031"
					}
				],
			},
		},
	]

	def test_sample_motions(self):
		"""parse.motion should give expected result on sample motion"""
		for sample in self.samples:
			result = parse.motion(sample['id'])
			if sample.get('mp_index') is not None:
				result['hlasy'] = result['hlasy'][sample['mp_index']:sample['mp_index']+1]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_motion_id(self):
		"""parse.motion should fail for an id that does not exist"""
		self.assertRaises(RuntimeError, parse.motion, '0')


class ParseNewDebatesList(unittest.TestCase):
	samples = [
		{
			"term": "6",
			"since_date": "2013-07-02",
			"until_date": "2013-07-02",
			"index": 1,
			"expected":
			{
				"schôdza": "21",
				"dátum": "2. 7. 2013",
				"trvanie": {
					"do": "9:16:59",
					"od": "9:04:58"
				},
				"druh": "Uvádzajúci uvádza bod",
				"osoba": {
					"id": "326",
					"url": "http://www.nrsr.sk/Default.aspx?sid=poslanci/poslanec&PoslanecID=326&CisObdobia=6",
					"meno": "Novotný, Viliam",
					"funkcia": "poslanec NR SR"
				},
				"video": {
					"id": "106774",
					"url": "http://mmserv2.nrsr.sk/NRSRInternet/Vystupenie/106774/video.html"
				},
				"video_rokovania": {
					"id": "724",
					"url": "http://mmserv2.nrsr.sk/NRSRInternet/Rokovanie/724/"
				},
				"prepis": {
					"id": "106774",
					"url": "http://mmserv2.nrsr.sk/NRSRInternet/indexpopup.aspx?module=Internet&page=SpeakerSection&SpeakerSectionID=106774&ViewType=content&"
				}
			},
		},
	]

	def test_sample_lists(self):
		"""parse.new_debates_list should give expected result on sample debate lists"""
		for sample in self.samples:
			result = parse.new_debates_list(sample['term'],
				since_date=sample['since_date'], until_date=sample['until_date'])
			self.assertEqual(result[sample['index']], sample['expected'])

	def test_wrong_term(self):
		"""parse.new_debates_list should fail for a term before 5th one"""
		self.assertRaises(ValueError, parse.new_debates_list, '4')


class ParseDebateOfTerms56(unittest.TestCase):
	samples = [
		# session of the current term
		{
			"id": "78454",
			"line_index": -1,
			"expected":
			{
				"nadpis": "1. schôdza NR SR ustanovujúca - 1. deň - streda - A. dopoludnia",
				"podnadpis": "Bugár, Béla, 2012.04.04 09:48 - 10:03",
				"riadky": [
					"(Hymna Slovenskej republiky.)"
				],
			},
		},
	]

	def test_sample_debates(self):
		"""parse.debates_of_terms56 should give expected result on sample session"""
		for sample in self.samples:
			result = parse.debate_of_terms56(sample['id'])
			result['riadky'] = [result['riadky'][sample['line_index']]]
			self.assertEqual(result, sample['expected'])

	def test_nonexistent_debate(self):
		"""parse.debates_of_terms56 should fail for debate that does not exist"""
		self.assertRaises(RuntimeError, parse.debate_of_terms56, '1')


if __name__ == '__main__':
	unittest.main()
