# EVERYTHING WRT BOLUS

import pandas as pd
import numpy as np
import sys
import os
import fnmatch
import datetime
from dateutil import parser
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

#root_dir = '/mnt/c/Users/xSix.SixAxiS/Documents/Stanford/Research/Buckingham/meal_analysis'
root_dir = '~/Desktop/Buckingham/meal_analysis'
predictions = 'Fiasp 670G Meal Scoring_MD Predictions.xlsx'
carelink = pd.read_excel('{}/{}'.format(root_dir, predictions), sheet_name='Sheet1', skiprows=1, parse_dates=[['Date', 'Time']])
carelink = carelink.loc[:, ~carelink.columns.str.contains('^Unnamed')]

results = []

for index, row in carelink.iterrows():
    # search for appropriate csv file in 'CSV Files'
    subject = row['Subject'][:5] + row['Subject'][6] + row['Subject'][8:]
    date_time = row['Date_Time']

    # VERY HACKY, CHANGE IF POSSIBLE
    if date_time <= datetime.datetime(2018, 8, 1, 0, 0, 0):
        date_time = datetime_end.replace(year=2019)

    pattern = '{}_Insulin[12]_*'.format(subject)
    
    #files = os.listdir('{}/CSV Files'.format(root_dir))
    files = os.listdir('CSV Files')
    possible = fnmatch.filter(files, pattern)
   
    datafile = None
    # match dates
    for f in possible:
        if len(f) <= 37:
            date_range = f[22:-4]
        else:
            date_range = f[27:-4]
        
        datetime_start = parser.parse(date_range[:3] + ' ' + date_range[3:5])

        datetime_end = None
        if len(date_range) == 11:
            datetime_end = parser.parse(date_range[6:9] + ' ' + date_range[9:])
        else:
            datetime_end = parser.parse(date_range[:3] + ' ' + date_range[6:])

        # HACKY METHOD, NEEDS TO BE REPLACED ONCE FILES ARE FIXED
        if datetime_start >= datetime.datetime(2019, 8, 1, 0, 0, 0):
            datetime_start = datetime_start.replace(year=2018)
        if datetime_end >= datetime.datetime(2019, 8, 1, 0, 0, 0):
            datetime_end = datetime_end.replace(year=2018)

        if date_time >= datetime_start and date_time <= datetime_end + datetime.timedelta(days=1):
            datafile = f

    u_cols = ['Date', 'Time', 'Timestamp', 'Sensor Glucose (mg/dL)']

    data = pd.read_csv(
                        'CSV Files/{}'.format(datafile), 
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

    meal = data[(data['Date'] == row['Date_Time'].date())
                 & (data['Timestamp'] >= row['Date_Time'] - datetime.timedelta(hours=1)) 
                 & (data['Timestamp'] <= row['Date_Time'] + datetime.timedelta(hours=3))]
    meal = meal.dropna(subset=['Sensor Glucose (mg/dL)'])
    meal['Time_delta'] = meal['Timestamp'] - row['Date_Time']
    #print(meal.head())

    possible_baseline_glucoses = meal[(meal['Timestamp'] >= row['Date_Time'] - datetime.timedelta(minutes=20)) & 
                                          (meal['Timestamp'] <= (row['Date_Time'] + datetime.timedelta(minutes=5))) & 
                                          ((meal['Sensor Glucose (mg/dL)']).isnull() == False)]
    
    baseline_glucose = 0
    bolus_time = row['Date_Time']
    min_time_diff = datetime.timedelta(hours=1)
    # for each possible baseline value, check which timestamp is closest to insulin bolus time
    for index, possible_baseline in possible_baseline_glucoses.iterrows():
        time_diff = abs(possible_baseline['Timestamp'] - row['Date_Time'])
        if time_diff < min_time_diff:
            min_time_diff = time_diff
            baseline_glucose = possible_baseline['Sensor Glucose (mg/dL)']
            bolus_time = possible_baseline['Timestamp']

    # within the next 1:30, we need to look for the maximum glucose level, minimum glucose level,
    # don't forget to record the T_max and T_1/2max
    glucose_max = 0
    delta_max = 0
    T_max = 0
    glucose_min = sys.maxsize
    delta_min = 0
    T_min = 0
    glucose_halfmax = 0
    T_halfmax = 0

    meal_period = meal[(meal['Timestamp'] <= (bolus_time + datetime.timedelta(hours=1, minutes=30))) &
                          (meal['Timestamp'] >= bolus_time)]

    for index, entry in meal_period.iterrows():
        if entry['Sensor Glucose (mg/dL)'] > glucose_max:
            glucose_max = entry['Sensor Glucose (mg/dL)']
            T_max = entry['Timestamp'] - bolus_time 
        if entry['Sensor Glucose (mg/dL)'] < glucose_min:
            glucose_min = entry['Sensor Glucose (mg/dL)']
            T_min = entry['Timestamp'] - bolus_time

    delta_max = glucose_max - baseline_glucose
    delta_min = glucose_min - baseline_glucose

    delta_diff = sys.maxsize
    for index, entry in meal_period.iterrows():
        # captures the first instance of a glucose reading at 1/2 max
        # TODO: FIGURE OUT WHY THE FOLLOWING IF STATEMENT ISN'T BEING FOLLOWED THROUGH!

        # find the entry where the difference between the max and x, and x and baseline are the closest
        # must be before glucose hits maximum
        if entry['Sensor Glucose (mg/dL)'] < glucose_max:
            baseline_to_x = entry['Sensor Glucose (mg/dL)'] - baseline_glucose
            x_to_max = glucose_max - entry['Sensor Glucose (mg/dL)']

            if abs(baseline_to_x - x_to_max) < delta_diff:
                glucose_halfmax = entry['Sensor Glucose (mg/dL)']
                T_halfmax = entry['Timestamp'] - bolus_time
                delta_diff = abs(baseline_to_x - x_to_max)
        else:
            break
    print(glucose_halfmax, T_halfmax)

    # add new columns 'Glucose_delta' and 'Time-delta' to plot later on
    meal_period['Time_delta'] = meal_period['Timestamp'] - bolus_time
    meal_period['Glucose_delta'] = meal_period['Sensor Glucose (mg/dL)'] - baseline_glucose

    # calculating area under curve with scaled glucose values using numpy.trapz(array/list, dx)
    # each glucose value isn't recorded at regular intervals, so how to deal with that?
    # just using dx=1 for now
    auc = np.trapz(list(meal_period['Glucose_delta'].dropna()), dx=1) 

    result = [bolus_time, baseline_glucose, glucose_max, delta_max, T_max, glucose_min, delta_min, T_min, glucose_halfmax, T_halfmax, auc]

    results.append(result)

    print(result)

    #plt.figure()

    #meal_period_graph = meal_period.dropna(subset=['Glucose_delta'])
    #ax = meal_period_graph.plot(kind='line', x='Time_delta', y='Glucose_delta')

df = pd.DataFrame(data=results, columns=['Bolus Time', 'Baseline Glucose', 'Glucose max', 'Delta max', 'T max',
    'Glucose min', 'Delta min', 'T min', 'Glucose halfmax', 'T halfmax', 'AUC'])

df.to_csv('result_metrics.csv')
