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
import requests

from random import random as rand

suffix = '-dstu2'

names_family = ["Bachmann", "Belson", "Berger", "Cannon", "Gregory", "Hendricks", "Schmutzhauser", "Weisman"]
names_females = ["Christy", "Elizabeth", "Emilie", "Jeanine", "Julie", "Magda", "Monica", "Rachel"]
names_males = ["Ehrlich", "Jerome", "Gavin", "Henry", "Peter", "Richard", "Ted", "Zhou"]

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

def populate_demographics(data):
	data['pat_id'] = 'hca-pat-' + data['PtID']
	days = 365*int(data['age']) + int(365*rand())
	data['bday'] = datetime.date.today() - datetime.timedelta(days=days)
	data['name'] = {}
	if 'male' == data['Sex']:
		data['name']['given'] = names_males[int(rand()*len(names_males))]
	else:
		data['name']['given'] = names_females[int(rand()*len(names_females))]
	data['name']['family'] = names_family[int(rand()*len(names_family))]
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

def fhir_update(base_url, resource_type, resource):
	try:
		parsed = json.loads(resource)
		url = '{}/{}/{}'.format(base_url, resource_type, parsed['id'])
		res = requests.put(url, headers={'Content-Type': 'application/json+fhir'}, data=resource)
		res.raise_for_status()
	except Exception as e:
		logging.error("Failing resource \"{}\" was:\n{}".format(resource_type, resource))
		raise e


if '__main__' == __name__:
	logging.basicConfig(level=logging.DEBUG)
	push_to = sys.argv[1] if len(sys.argv) > 1 else None
	
	# read CSV
	logging.debug('Reading "import-hca.csv"')
	with io.open('import-hca.csv', 'r') as csvfile:
		f = csv.reader(csvfile)
		head = None
		
		# Jinja2
		tplenv = jinja2.Environment(loader=jinja2.PackageLoader(__name__, 'templates'))
		tpl_patient = tplenv.get_template('hca-patient{}.json'.format(suffix))
		tpl_condition = tplenv.get_template('hca-condition{}.json'.format(suffix))
		tpl_observation = tplenv.get_template('hca-observation{}.json'.format(suffix))
		tpl_procedure = tplenv.get_template('hca-procedure{}.json'.format(suffix))
		tpl_medpresc = tplenv.get_template('hca-medicationprescription{}.json'.format(suffix))
		
		# loop
		for row in f:
			if head is None:
				head = row
			
			# one row, one patient
			else:
				resources = []
				logging.debug("Processing row {}".format(row[0]))
				data = dict(zip(head, row))
				data = populate_demographics(data)
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
				
				# push to FHIR server
				if push_to is not None:
					logging.debug("Pushing row {} to {}".format(row[0], push_to))
					for typ, resource in resources:
						fhir_update(push_to, typ, resource)
				else:
					for typ, resource in resources:
						print("-->  {}\n{}\n".format(typ, json.loads(resource)))
				
				#break
	
	logging.debug('Done')

