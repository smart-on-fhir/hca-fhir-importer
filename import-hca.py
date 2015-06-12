#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import csv
import json
import uuid
import jinja2
import datetime

from random import random as rand

suffix = '-dstu2'

names_family = ["Bachmann", "Berger", "Cannon", "Schmidt", "Schmutzhauser", "Weizman"]
names_females = ["Christy", "Jeanine", "Julie", "Rachel", "Magda", "Marian"]
names_males = ["Ehrlich", "Jerome", "Henry", "Richard", "Ted", "Zhou"]

with io.open('map-condition-hca.json', 'r') as h:
	map_conditions = json.load(h)


def rand_id():
	return str(uuid.uuid4())[-12:]

def ucfirst(string):
	return string[:1].upper() + string[1:]

def populate_demographics(data):
	data['pat_id'] = 'hca' + data['PtID']
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
	data['cond_id'] = 'hcac' + rand_id()
	mapped = map_conditions[data['Diagnosis name']]
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

def render(row, template, observation=None):
	print(template.render(rand_id=rand_id, observation=observation, **row))
	

print('->  Reading "import-hca.csv"')
with io.open('import-hca.csv', 'r') as csvfile:
	f = csv.reader(csvfile)
	head = None
	
	# Jinja2
	tplenv = jinja2.Environment(loader=jinja2.PackageLoader(__name__, 'templates'))
	tpl_patient = tplenv.get_template('hca-patient{}.json'.format(suffix))
	tpl_condition = tplenv.get_template('hca-condition{}.json'.format(suffix))
	tpl_observation = tplenv.get_template('hca-observation{}.json'.format(suffix))
	
	# loop
	for row in f:
		
		# header
		if head is None:
			head = row
		
		# one row, one patient
		else:
			data = dict(zip(head, row))
			data = populate_demographics(data)
			data = populate_conditions(data)
			data = populate_observations(data)
			
			render(data, tpl_patient)
			render(data, tpl_condition)
			for obs in data['observations']:
				render(data, tpl_observation, obs)
			break

print('->  Done')
