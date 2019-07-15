# EVERYTHING WRT BOLUS

import pandas as pd
import numpy as np
import sys
import os, re

root_dir = '/mnt/c/Users/xSix.SixAxiS/Documents/Stanford/Research/Buckingham/breakfast'
fo = 'Fiasp 670G Meal Scoring_MD Predictions.xlsx'
bolus = pd.read_excel('{}/{}'.format(root_dir, fo), sheetname='Sheet1', parse_dates=[['Date', 'Time']])
bolus = bolus.loc[:, ~bolus.columns.str.contains('^Unnamed')]

for index, row in bolus.iterrows():
	# search for appropriate csv file in 'CSV Files'
	subject = row['Subject'][:5] + row['Subject'][6] + row['Subject'][8:]
	date = row['Date'][:3] + row['Date'][4:]
	date = date.upper()
	regex = re.compile('{}_Insulin[12]_(Carelink|CSV)_(\S+)'.format(subject))

	for root, dirs, files in os.walk('{}/CSV\ Files'.format(root_dir)):
		for file in files:
			

u_cols = ['Date', 'Time', 'Timestamp','Bolus Type', 'Bolus Volume Selected (U)', 'Bolus Volume Delivered (U)', 'Sensor Glucose (mg/dL)']

data = pd.read_csv(
                    filename, 
                    skiprows=range(11),
                    usecols=u_cols,
                    )
data['Date'] = pd.to_datetime(data['Date'])
data['Timestamp'] = pd.to_datetime(data['Timestamp'])
begin_date = data.iloc[1]['Date']
end_date = data.iloc[-1]['Date']

# drop all the rows that don't give us any valuable information regarding blood glucose and insulin boluses
data = data.dropna(thresh=4)
data = data.reset_index()


import datetime
import matplotlib.pyplot as plt

meal = data[(data['Date'] == bolus.iloc[0]['Date_Time'].date())
             & (data['Timestamp'] >= bolus.iloc[0]['Date_Time'] - datetime.timedelta(hours=1)) 
             & (data['Timestamp'] <= bolus.iloc[0]['Date_Time'] + datetime.timedelta(hours=3))]
meal = meal.dropna(subset=['Sensor Glucose (mg/dL)'])
meal['Time_delta'] = meal['Timestamp'] - bolus.iloc[0]['Date_Time']
print(meal.head())

ax = meal.plot(kind='line', x ='Time_delta', y='Sensor Glucose (mg/dL)', color='red')
plt.ylim(0,300)
plt.show()


possible_baseline_glucoses = meal[(meal['Timestamp'] >= bolus.iloc[0]['Date_Time'] - datetime.timedelta(minutes=20)) & 
                                      (meal['Timestamp'] <= (bolus.iloc[0]['Date_Time'] + datetime.timedelta(minutes=5))) & 
                                      ((meal['Sensor Glucose (mg/dL)']).isnull() == False)]

baseline_glucose = 0
min_time_diff = datetime.timedelta(hours=1)
# for each possible baseline value, check which timestamp is closest to insulin bolus time
for index, possible_baseline in possible_baseline_glucoses.iterrows():
    time_diff = abs(possible_baseline['Timestamp'] - bolus.iloc[0]['Date_Time'])
    if time_diff < min_time_diff:
        min_time_diff = time_diff
        baseline_glucose = possible_baseline['Sensor Glucose (mg/dL)']


# within the next 1:30, we need to look for the maximum glucose level, minimum glucose level,
# don't forget to record the T_max and T_1/2max
bolus_time = meal.iloc[0]['Timestamp']
glucose_max = 0
delta_max = 0
T_max = 0
glucose_min = sys.maxsize
delta_min = 0
T_min = 0
T_halfmax = 0

meal_period = meal[(meal['Timestamp'] <= (bolus_time + datetime.timedelta(hours=1, minutes=30))) &
                      (meal['Timestamp'] >= bolus_time)]

for index, entry in meal_period.iterrows():
    if entry['Sensor Glucose (mg/dL)'] > glucose_max:
        glucose_max = entry['Sensor Glucose (mg/dL)']
        T_max = entry['Timestamp']
    if entry['Sensor Glucose (mg/dL)'] < glucose_min:
        glucose_min = entry['Sensor Glucose (mg/dL)']
        T_min = entry['Timestamp']

delta_max = glucose_max - baseline_glucose
delta_min = glucose_min - baseline_glucose

glucose_halfmax = baseline_glucose + delta_max / 2
for index, entry in meal_period.iterrows():
    # captures the first instance of a glucose reading at 1/2 max
    if (entry['Sensor Glucose (mg/dL)'] <= glucose_halfmax + 1) or (entry['Sensor Glucose (mg/dL)'] >= glucose_halfmax - 1):
        T_halfmax = entry['Timestamp']
        break

# add new columns 'Glucose_delta' and 'Time-delta' to plot later on
meal_period['Time_delta'] = meal_period['Timestamp'] - bolus_time
meal_period['Glucose_delta'] = meal_period['Sensor Glucose (mg/dL)'] - baseline_glucose

# calculating area under curve with scaled glucose values using numpy.trapz(array/list, dx)
# each glucose value isn't recorded at regular intervals, so how to deal with that?
# just using dx=1 for now
auc = np.trapz(list(meal_period['Glucose_delta'].dropna()), dx=1) 

result = [bolus, bolus_time, baseline_glucose, glucose_max, delta_max, T_max, glucose_min, delta_min, T_min, T_halfmax, auc]


plt.figure()

meal_period_graph = meal_period.dropna(subset=['Glucose_delta'])
ax = meal_period_graph.plot(kind='line', x='Time_delta', y='Glucose_delta')