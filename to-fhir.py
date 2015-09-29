#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import sys
import csv
import json
import uuid
import jinja2
import logging
import datetime
try:
	import requests
except ImportError as e:
	pass

from random import random as rand, seed as seed

tpl_suffix = '-dstu2'

names_family = ["Ackerman", "Adams", "Bachmann", "Belson", "Berger", "Cannon", "Chen", "Dunbar", "Ebert", "Fallon", "Gregory", "Grey", "Haynes", "Hendricks", "Hoover", "Jackson", "Klever", "Logan", "McConnell", "Mueller", "Newman", "Oppenheimer", "Peterson", "Petrich", "Richards", "Russo", "Santiago", "Savel", "Schmutzhauser", "Tessler", "Urciuoli", "Williams", "Zafran", "Zhou"]
names_females = ["Anne", "Beryl", "Brittany", "Christy", "Deborah", "Elizabeth", "Emilie", "Hannah", "Jeanine", "Julie", "Lindsay", "Magda", "Monica", "Nancy", "Paulene", "Rachel", "Renee", "Rita", "Shae", "Tess", "Trudy", "Vanessa", "Zoe"]
names_males = ["Ehrlich", "Gavin", "Joseph", "Peter", "Richard", "Ted"]

with io.open('map-condition-hca.json', 'r') as h:
	map_conditions = json.load(h)

with io.open('map-procedure-hca.json', 'r') as h:
	map_procedures = json.load(h)

with io.open('map-medication-hca.json', 'r') as h:
	map_medications = json.load(h)


def rand_id():
	return str(uuid.uuid4())[-12:]

def ucfirst(string):
	return string[:1].upper() + string[1:]

def parse_int(string):
	try:
		return int(string)
	except ValueError:
		return None

def populate_demographics(data, seed_num):
	data['pat_id'] = 'hca-pat-' + data['PtID']
	days = 365*int(data['age']) + round(364*rand())
	data['bday'] = datetime.date.today() - datetime.timedelta(days=days)
	data['name'] = {}
	if 'male' == data['Sex']:
		seed(seed_num)
		data['name']['given'] = names_males[int(round(rand()*(len(names_males)-1)))]
	else:
		seed(seed_num)
		data['name']['given'] = names_females[int(round(rand()*(len(names_females)-1)))]
	seed((seed_num + 3) * seed_num)
	data['name']['family'] = names_family[int(round(rand()*(len(names_family)-1)))]
	return data

def populate_conditions(data):
	data['cond_id'] = 'hca-con-' + rand_id()
	if 'Diagnosis name' in data:
		mapped = map_conditions[data['Diagnosis name'].lower()]
		data['condition'] = {
			'text': data['Diagnosis name'],
			'snomed': mapped['snomed'],
			'display': mapped['display'],
		}
	return data

def populate_mutations(data):
	obs = []
	obs.append({
		'gene_expression': True,
		'code': "HGNC:3430",
		'system': "http://www.genenames.org",
		'display': "erb-b2 receptor tyrosine kinase 2",
		'text': "Her2Neu FISH",
		'result': ucfirst(data['Her2Neu FISH']),
		'quantity': parse_int(data['Her2Neu FISH']),
		'string': data['Her2Neu FISH'],
		'ucum': '%',
	})
	obs.append({
		'gene_expression': True,
		'code': "HGNC:3467",
		'system': "http://www.genenames.org",
		'display': "estrogen receptor 1",
		'text': "ER Pct",
		'result': ucfirst(data['Receptors ER']),
		'quantity': parse_int(data['rlReceptorsER Pct']),
		'string': data['rlReceptorsER Pct'],
		'ucum': '%',
	})
	obs.append({
		'gene_expression': True,
		'code': "HGNC:8910",
		'system': "http://www.genenames.org",
		'display': "progesterone receptor",
		'text': "PR Pct",
		'result': ucfirst(data['Receptors PR']),
		'quantity': parse_int(data['rlReceptorsPR Pct']),
		'string': data['rlReceptorsPR Pct'],
		'ucum': '%',
	})
	if len(obs) > 0:
		data['mutations'] = obs
	return data

def populate_labs(data):
	labs = []
	labval = data.get('Abs Neutrophil Count (x10*3/uL)')
	if labval:
		labs.append({
			'code': "26499-4",
			'system': "http://loinc.org",
			'display': "Neutrophils [#/volume] in Blood",
			'text': "Abs Neutrophil Count (x10*3/uL)",
			'quantity': labval,
			'ucum': "10*3/uL",
		})
	
	labval = data.get('Platelets (x10*3)')
	if labval:
		labs.append({
			'code': "26515-7",
			'system': "http://loinc.org",
			'display': "Platelets [#/volume] in Blood",
			'text': "Platelets (x10*3)",
			'quantity': labval,
			'ucum': "10*3/uL",
		})
	
	labval = data.get('eGFR (ml/min)')
	if labval:
		low = None
		high = None
		if '<' == labval[:1]:
			high = labval[1:]
		elif '>' == labval[:1]:
			low = labval[1:]
		elif '-' in labval:
			low, high = labval.split('-')
		labs.append({
			'code': "69405-9",
			'system': "http://loinc.org",
			'display': "Glomerular filtration rate/1.73 sq M.predicted",
			'text': "eGFR (ml/min)",
			'low': low,
			'high': high,
			'string': labval,
			'ucum': "mL/min",
		})
	
	data['labs'] = labs
	return data

def populate_procedures(data):
	if 'Surgery detail' in data:
		mapped = map_procedures[data['Surgery detail'].lower()]
		data['procedure'] = {
			'snomed': mapped['snomed'],
			'display': mapped['display'],
			'text': data['Surgery detail'],
		}
	return data

def populate_meds(data):
	meds = []
	for med in [data.get('Chemo drug 1'), data.get('Chemo drug 2'), data.get('Chemo drug 3'), data.get('Endocrine therapy')]:
		if med:
			meds.append(map_medications[med])
	data['medications'] = meds
	return data

def render(template, data, **args):
	d = data.copy()
	d.update(args)
	return template.render(rand_id=rand_id, **d)

def fhir_post_bundle(base_url, bundle):
	try:
		res = requests.post(base_url, headers={'Content-Type': 'application/json+fhir'}, data=bundle)
		res.raise_for_status()
	except Exception as e:
		logging.error("Failed; failing Bundle was:\n{}".format(bundle))
		raise e
	
def fhir_update(base_url, resource_type, resource):
	try:
		parsed = json.loads(resource)
		url = '{}/{}/{}'.format(base_url, resource_type, parsed['id'])
		res = requests.put(url, headers={'Content-Type': 'application/json+fhir'}, data=resource)
		res.raise_for_status()
	except Exception as e:
		logging.error("Failed; failing resource \"{}\" was:\n{}".format(resource_type, resource))
		raise e


if '__main__' == __name__:
	logging.basicConfig(level=logging.DEBUG)
	push_to = sys.argv[1] if len(sys.argv) > 1 else None
	bundle_per_patient = False
	
	# read CSV
	logging.debug('Reading "import-hca.csv"')
	with io.open('import-hca.csv', 'r') as csvfile:
		f = csv.reader(csvfile)
		head = None
		bundles = []
		resources = []
		
		# Jinja2
		tplenv = jinja2.Environment(loader=jinja2.PackageLoader(__name__, 'templates'))
		tpl_bundle = tplenv.get_template('Bundle{}.json'.format(tpl_suffix))
		tpl_patient = tplenv.get_template('hca-patient{}.json'.format(tpl_suffix))
		tpl_condition = tplenv.get_template('hca-condition{}.json'.format(tpl_suffix))
		tpl_observation = tplenv.get_template('hca-observation{}.json'.format(tpl_suffix))
		tpl_procedure = tplenv.get_template('hca-procedure{}.json'.format(tpl_suffix))
		#tpl_medpresc = tplenv.get_template('hca-medicationprescription{}.json'.format(tpl_suffix))
		tpl_medpresc = tplenv.get_template('hca-medicationorder{}.json'.format(tpl_suffix))
		
		# loop
		for row in f:
			if head is None:
				head = row
			
			# one row, one patient
			else:
				logging.debug("Processing row {}".format(row[0]))
				data = dict(zip(head, row))
				data = populate_demographics(data, int(row[0]))
				data = populate_conditions(data)
				data = populate_mutations(data)
				data = populate_labs(data)
				data = populate_procedures(data)
				data = populate_meds(data)
				
				resources.append(('Patient', render(tpl_patient, data)))
				resources.append(('Condition', render(tpl_condition, data)))
				for obs in data.get('mutations', []):
					resources.append(('Observation', render(tpl_observation, data, lab=obs)))
				for obs in data.get('labs', []):
					resources.append(('Observation', render(tpl_observation, data, lab=obs)))
				if 'procedure' in data:
					resources.append(('Procedure', render(tpl_procedure, data)))
				for med in data.get('medications', []):
					resources.append(('MedicationPrescription', render(tpl_medpresc, data, medication= med)))
				
				# bundle up
				bundle = tpl_bundle.render(bundle={'type': 'transaction', 'entries': [r[1] for r in resources]})
				bundles.append(bundle)
				
				if push_to is not None:
					logging.debug("Pushing bundle for row {} to {}".format(row[0], push_to))
					fhir_post_bundle(push_to, bundle)
				elif bundle_per_patient:
					print(bundle)
				#break
		
		# create a master Bundle
		if not bundle_per_patient:
			bundle = tpl_bundle.render(bundle={'type': 'transaction', 'entries': [r[1] for r in resources]})
			print(bundle)
	
	logging.debug('Done')

