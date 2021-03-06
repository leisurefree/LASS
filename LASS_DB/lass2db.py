#!/usr/bin/env python
#
# Version: 0.3.0
#
# Objctive: This program will do the followings:
#	1. work as a MQTT subscriber of LASS
#	2. convert the MQTT messages into BSON format and insert into MongoDB
#	3. convert the MQTT messages into BSON format and insert into Couchbase
#
# Parameters to change:
#	MongoDB_SERVER: the host address of your own MongoDB server
#	MongoDB_PORT: the port number of your own MongoDB server
#	Couchbase_SERVER: the host address and the data bucket name of 
#                         your own Couchbase DB
#
# Input Format:
#	LASS version 0.7.1+ (LASS data format version 2.0+)
#
# Requirements:
# 	Paho: The Paho Python Client provides a client class with support 
#	      for both MQTT v3.1 and v3.1.1 on Python 2.7 or 3.x. It also 
#	      provides some helper functions to make publishing one off 
#	      messages to an MQTT server very straightforward.
#	      URL: https://eclipse.org/paho/clients/python/
#
#	PyMongo: PyMongo is a Python distribution containing tools for 
#                working with MongoDB, and is the recommended way to work 
#                with MongoDB from Python. 
#	         URL: https://api.mongodb.org/python/current/
#
#	Couchbase: Python client for Couchbase
#	           URL: https://pypi.python.org/pypi/couchbase

import paho.mqtt.client as mqtt
import pymongo
import re
import json
import sys
import math
from couchbase.bucket import Bucket

################################################################
# Please configure the following settings for your environment
USE_MongoDB = 1
USE_CouchbaseDB = 0

MQTT_SERVER = "gpssensor.ddns.net"
MQTT_PORT = 1883
MQTT_ALIVE = 60
MQTT_TOPIC = "LASS/Test/#"

MongoDB_SERVER = "localhost"
MongoDB_PORT = 27017
MongoDB_DB = "LASS"

Couchbase_SERVER = "couchbase://localhost/LASS"
################################################################

# Objective: converting GPS coordinates from DMS to DD format
#
# Note that the LASS DB has been changed to DD format since 2016/2/3 11:42am
def dms2dd(dms):
    try:
    	dms = float(dms)
    	d = math.floor(dms)
    	m = ((dms - d) / 60) * 100 * 100
    	s = (m - math.floor(m)) * 100
    	dd = d + math.floor(m) * 0.01 + s * 0.0001
    except:
	print "DMS2DD: Unexpected error:", sys.exc_info()[0]
	dd = 0;
	raise
    return str(dd)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("MQTT Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(MQTT_TOPIC)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    #print(msg.topic+" "+str(msg.payload))
    re.sub('\s+','',msg.payload)
    items = re.split('\|',msg.payload)
    lat = "000.000"
    lon = "000.000"
    db_msg = "{"
    flag = 0
    app = 0
    LASS_DEVICE_ID="non_device"
    FAKE_GPS = 0
    LASS_APP = ""
    LASS_SITE_ID = ""
    LASS_DEVICE_ID = ""
    LASS_SITE_NAME = ""
    for item in items:
        if item == '':
            continue 
        pairs = re.split('=',item)
	if len(pairs)==1:
            continue
        flag = 1
        if (pairs[0] == "time"):
            LASS_TIME = pairs[1]
        elif (pairs[0] == "date"):
            LASS_DATE = pairs[1]
        elif (pairs[0] == "app"):
            LASS_APP = pairs[1]
        elif (pairs[0] == "device_id"):
            LASS_DEVICE_ID = pairs[1]
        elif (pairs[0] == "SiteID"):
            LASS_SITE_ID = pairs[1]
	    pairs[0] = "device_id"  # make it compatible with the LASS devices
        elif (pairs[0] == "SiteName"):
            LASS_SITE_NAME = pairs[1]
        elif (pairs[0] == "ver_format"):
            if (float(pairs[1])<2.0):
                print("[Error] data format is outdated!")
                return
	elif (pairs[0] == "FAKE_GPS"):
	    try:
		FAKE_GPS = int(pairs[1])
	    except:
		print("[Error] FAKE_GPS string error")
		print(msg.payload)
		return


	if (pairs[0] == "gps_lat" or pairs[0] == "gps-lat"):
	    if (pairs[1]==""):
		lat = "0"
	    else:
		lat = pairs[1]
	elif (pairs[0] == "gps_lon" or pairs[0] == "gps-lon"):
	    if (pairs[1]==""):
		lon = "0"
	    else:
	    	lon = pairs[1]
	else:
            if (pairs[0] == "device_id"):
                db_msg = db_msg + "\"" + pairs[0] + "\":\"" + pairs[1] + "\",\n"
	    elif (num_re_pattern.match(pairs[1])):
                db_msg = db_msg + "\"" + pairs[0] + "\":" + pairs[1] + ",\n"
            else:
                db_msg = db_msg + "\"" + pairs[0] + "\":\"" + pairs[1] + "\",\n"

    if (LASS_APP == "EPA_COPY"):
	app = 2
    elif (LASS_APP == "WEBDUINO_COPY"):
	app = 3
    elif (LASS_APP == "ProbeCube_COPY"):
	app = 4
    else:
	app = 1

    if (flag==0):
        return
    if (app==1):
	if (FAKE_GPS==0):
	    lat = dms2dd(lat)
	    lon = dms2dd(lon)

    lat = float(lat)
    lon = float(lon)
    if (lat>90):
	lat = lat - 90
	lat = 0 - lat

    if (lon > 180):
	lon = lon - 180
	lon = 0 - lon

    if (USE_MongoDB==1):
        #mongodb_posts = mongodb_db.posts
        mongodb_posts = mongodb_db.posts2
	mongodb_latest = mongodb_db.latest
        mongodb_msg = db_msg + "\"loc\":{\"type\":\"Point\",\"coordinates\":["+ str(lat) + "," + str(lon) + "]}}"
        #print(mongodb_msg)

	try:
            mongodb_msg = json.loads(mongodb_msg)
            db_result = mongodb_posts.insert_one(mongodb_msg)
	    #print(db_result)
	    if (app==1):
	        r = mongodb_latest.delete_many({"device_id":LASS_DEVICE_ID})
	    elif (app==2):
	        r = mongodb_latest.delete_many({"SiteName":LASS_SITE_NAME})
	    elif (app==3):
	        r = mongodb_latest.delete_many({"device_id":LASS_SITE_ID})
	    elif (app==4):
	        r = mongodb_latest.delete_many({"device_id":LASS_DEVICE_ID})
            db_result = mongodb_latest.insert_one(mongodb_msg)
	except ValueError:
	    print("Exception ValueError: " + db_msg)
	except TypeError:
	    print("Exception TypeError: " + db_msg)
        except pymongo.errors.ServerSelectionTimeoutError:
            print("[ERROR] MongoDB insertion fails for the message: " + msg.payload)
        except pymongo.errors.ServerSelectionTimeoutError:
            print("[ERROR] MongoDB insertion fails for the message: " + msg.payload)
	except:
	    print "Unexpected error:", sys.exc_info()[0]
		
    if (USE_CouchbaseDB==1):
        couchbase_msg = db_msg + "\"loc\":["+ lat + "," + lon + "]}"
        couchbase_msg = json.loads(couchbase_msg)
        couchbase_key = LASS_DEVICE_ID + "-" + LASS_DATE + "-" + LASS_TIME
        db_result = couchbase_db.set(couchbase_key, couchbase_msg)
        #print(db_result)

if (USE_MongoDB==1):
    mongodb_client = pymongo.MongoClient(MongoDB_SERVER, MongoDB_PORT, serverSelectionTimeoutMS=0)
    mongodb_db = mongodb_client[MongoDB_DB]

if (USE_CouchbaseDB==1):
    try:
        couchbase_db = Bucket(Couchbase_SERVER)
    except:
        print("[ERROR] Cannot connect to Couchbase server. Skip the following Couchbase insertions.")
        USE_CouchbaseDB = 0

num_re_pattern = re.compile("^-?\d+\.\d+$|^-?\d+$")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_SERVER, MQTT_PORT, MQTT_ALIVE)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
mqtt_client.loop_forever()
