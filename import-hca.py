#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import csv
import json
import uuid
import jinja2
import logging
import datetime

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

def populate_observations(data):
	obs = []
	obs.append({
		'hgnc': "HGNC:3430",
		'display': "erb-b2 receptor tyrosine kinase 2",
		'text': "Her2Neu FISH",
		'result': ucfirst(data['Her2Neu FISH']),
	})
	obs.append({
		'hgnc': "HGNC:3467",
		'display': "estrogen receptor 1",
		'text': "ER Pct",
		'result': ucfirst(data['Receptors ER']),
		'quantity': data['rlReceptorsER Pct'],
	})
	obs.append({
		'hgnc': "HGNC:8910",
		'display': "progesterone receptor",
		'text': "PR Pct",
		'result': ucfirst(data['Receptors PR']),
		'quantity': data['rlReceptorsPR Pct'],
	})
	if len(obs) > 0:
		data['observations'] = obs
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

def render(template, **args):
	print(template.render(rand_id=rand_id, **args))
	

print('->  Reading "import-hca.csv"')
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
			logging.debug("Processing row {}".format(row[0]))
			data = dict(zip(head, row))
			data = populate_demographics(data)
			data = populate_conditions(data)
			data = populate_observations(data)
			data = populate_procedures(data)
			data = populate_meds(data)
			
			render(tpl_patient, **data)
			render(tpl_condition, **data)
			for obs in data.get('observations', []):
				data['observation'] = obs
				render(tpl_observation, **data)
			if data.get('procedure'):
				render(tpl_procedure, **data)
			for med in data.get('medications', []):
				data['medication'] = med
				render(tpl_medpresc, **data)
			
			break

print('->  Done')
