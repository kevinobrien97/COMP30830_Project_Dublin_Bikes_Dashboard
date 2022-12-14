import os
import json
import numpy as np
import pandas as pd
from traceback import print_tb
from sqlalchemy import create_engine
from flask_cors import CORS, cross_origin
from flask import Flask, jsonify, render_template, g
from apscheduler.schedulers.background import BackgroundScheduler
import day_means
import hour_means
import pickle

SQLPW = os.environ['SQLPW']
GMAPS_KEY = os.environ['GMAPS_KEY']

app = Flask(__name__, static_url_path='')
CORS(app, supports_credentials=True)


# Configure the scheduler for updating the mean data json files 
sched = BackgroundScheduler()

# The job function to be called by the scheduler
def job_function():
    # Call the two functions that update the json files
    day_means.main()
    hour_means.main()
    return

# Add the job to the scheduler and start
# Run at 2am every sunday
sched.add_job(job_function, 'cron', day_of_week='sun', hour='2')
sched.start()

days_of_week = ["Sunday","Monday", "Tuesday","Wednesday", "Thursday", "Friday", "Saturday"]

@app.route("/login")
@cross_origin(supports_credentials=True)
def login():
    return jsonify({'success':'ok'})

def connect_to_database():
    engine=create_engine("mysql+mysqlconnector://softies:" + SQLPW + "@db-bikes.ck7tnbvjxsza.eu-west-1.rds.amazonaws.com:3306/db-bikes")
    return engine.connect()

def get_stations():
    engine = get_db()
    stations = []
    rows = engine.execute("SELECT * from static")

    for row in rows:
        stations.append(dict(row))

    for station in stations:
        station["title"], station["id"] = station["address"], station["address"]
        station['coords'] =  {'lat': station['lat'], 'lng': station['lng']}
        
    return stations

def get_db():
    db = getattr(g, '_database', None)                                                                                                                                                                                                                               
    if db is None:                                                                                                                                                                                                                                                   
        db = g._database = connect_to_database()                                                                                                                                                                                                                     
    return db

def get_hour_means():
    jsonfile = open('./../web/hour_means_json.json', "r")
    # jsonfile = open('web/hour_means_json.json', "r")
    hour_data = json.load(jsonfile)
    res = hour_data
    jsonfile.close()
    return res

@app.route("/get-hour-means")
def get_hour_means_route():
    jsonfile = open('./../web/hour_means_json.json', "r")
    # jsonfile = open('web/hour_means_json.json', "r")
    hour_data = json.load(jsonfile)
    res = hour_data
    jsonfile.close()
    return res

def get_day_means():
    jsonfile = open('./../web/day_means_json.json', "r")
    # jsonfile = open('web/day_means_json.json', "r")
    day_data = json.load(jsonfile)
    res = day_data
    jsonfile.close()
    return res

@app.route("/get-day-means")
def get_day_means_route():
    jsonfile = open('./../web/day_means_json.json', "r")
    # jsonfile = open('web/day_means_json.json', "r")
    day_data = json.load(jsonfile)
    res = day_data
    jsonfile.close()
    return res

@app.teardown_appcontext                                                                                                                                                                                                                                             
def close_connection(exception):                                                                                                                                                                                                                                     
    db = getattr(g, '_database', None)                                                                                                                                                                                                                               
    if db is not None:                                                                                                                                                                                                                                               
        db.close()

@app.route('/')
def root():
    stations = get_stations()
    hour_means = get_hour_means()
    day_means = get_day_means()
    weather = get_weather()
    recentbike = bike_occupancy()
    return render_template('index.html', static_data=stations, hour_means=hour_means, day_means=day_means, recentWeather = weather, recentbike=recentbike, GMAPS_KEY=GMAPS_KEY)

@app.route("/occupancy/<station_id>")
def get_occupancy(station_id):
    engine = get_db()
    dfrecentbike = pd.read_sql_query(f"SELECT dynamic.available_bike_stands, dynamic.available_bikes, dynamic.last_update FROM dynamic JOIN static ON static.address=dynamic.address WHERE static.number='{station_id}' order by dynamic.last_update desc limit 1;" , engine)
    dfrecentbike = dfrecentbike.iloc[0].to_json()
    return dfrecentbike

@app.route("/stations")
def get_all_stations():
    engine = get_db()
    stations = []
    rows = engine.execute("select * from static")
    for row in rows:
        stations.append(dict(row))
    return jsonify(stations)

def bike_occupancy():
    engine = get_db()
    colourbikes = []
    recentbike = engine.execute(
    """select * from (select max(last_update) AS last_update, static.number, dynamic.address 
    FROM dynamic JOIN static ON static.address=dynamic.address GROUP BY dynamic.address) as t1, 
    (select * from dynamic) as t2 
    where t1.last_update=t2.last_update and t1.address=t2.address;""")
    for row in recentbike:
        colourbikes.append(dict(row))
    return colourbikes

def get_weather():
    engine = get_db()
    dfrecentweather = pd.read_sql_query(f"SELECT * FROM weather order by date desc LIMIT 1;", engine)
    dfrecentweather = dfrecentweather.iloc[0].to_json()
    return dfrecentweather

@app.route("/weather")
def get_weather_info():
    engine = get_db()
    weather = []
    rows = engine.execute("SELECT * FROM weather order by date desc LIMIT 1;")
    for row in rows:
        weather.append(dict(row))
    return jsonify(weather)

@app.route("/predictor/<hour>/<day>/<station_number>")
def predict_available_bikes(day, hour, station_number):
    print(day, hour, station_number)
    # Access day value as string
    day = days_of_week[int(day)]
    print(day, hour, station_number)

    with open(f'./../web/models/model_{station_number}.pkl', 'rb') as handle:
    # with open(f'web/models/model_{station_number}.pkl', 'rb') as handle:
        model = pickle.load(handle)

        # Column names for model
        cols = ['time_01', 'time_02', 'time_03', 'time_04', 'time_05', 'time_06',
        'time_07', 'time_08', 'time_09', 'time_10', 'time_11', 'time_12',
        'time_13', 'time_14', 'time_15', 'time_16', 'time_17', 'time_18',
        'time_19', 'time_20', 'time_21', 'time_22', 'time_23', 'day_Monday',
        'day_Saturday', 'day_Sunday', 'day_Thursday', 'day_Tuesday',
        'day_Wednesday']

        # Create dataframe of 0's
        params = pd.DataFrame(0, index=np.arange(1), columns=cols)

        hour = 'time_0' + hour if  int(hour) < 10 else 'time_' + hour
        day = 'time_' + day
        print(day, hour, station_number)

        # Reassign 0 to 1 for input values
        if day in params:
            params[day] = 1
        if hour in params:
            params[hour] = 1

        # Predict
        res = model.predict(params)
        # print(res)

    # Take out bike number
    bikes, = res

    # If negative
    if bikes < 0:
        bikes = 0

    prediction = [round(bikes)]
    return jsonify(prediction)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000,debug=True)
