from microdot import Microdot, send_file
from microdot.websocket import with_websocket
import json
import network
import qwiic_tmp117
import time

# defines
kDoAlerts = True # Set to False to disable checking alerts. This will speed up temperature reads.
kApSsid = "iot_redboard_tmp117"
kApPass = "sparkfun"

# fahrenheit to celcius
def f_to_c(degreesF):
    return (degreesF - 32) * 5/9

def c_to_f(degreesC):
    return (degreesC * 9/5) + 32

# Set up the AP
print("Formatting WIFI")
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=kApSsid,  password=kApPass)

while ap.active() == False:
    pass

config = ap.ifconfig()
print("WiFi Configured!")
# print("Active config: ", config)

# Set up the TMP117
print("Setting up TMP117")
# Create instance of device
myTMP117 = qwiic_tmp117.QwiicTMP117()

# Check if it's connected
if myTMP117.is_connected() == False:
    print("The TMP117 device isn't connected to the system. Please check your connection")

print("TMP117 device connected!")
    
# Initialize the device
myTMP117.begin()

if kDoAlerts:
    myTMP117.set_high_limit(25.50)
    myTMP117.set_low_limit(25)

    # Set to kAlertMode or kThermMode
    myTMP117.set_alert_function_mode(myTMP117.kAlertMode)

print("TMP117 Configured!")

print("\nNavigate to http://" + config[0] + ":5000/ to view the TMP117 temperature readings\n")

# Use the Microdot framework to create a web server
app = Microdot()

# Route our root page to the index.html file
@app.route('/')
async def index(request):
    return send_file('static/index.html')

# Create server-side coroutine for websocket to receive changes to the high and low temperature limits from the client
@app.route('/limits')
@with_websocket
async def limits(request, ws):
    while True:
        # print("-------------------READY TO RECEIVE LIMIT DATA!!!!-----------------")
        data = await ws.receive()
        # await ws.send(data)
        print("Received new limit: " + data)
        limitJson = json.loads(data)
        if 'low_input' in limitJson:
            toSet = f_to_c(limitJson['low_input'])
            print("setting low limit to: " + str(toSet))
            myTMP117.set_low_limit(toSet)
            print("New low limit: " + str(myTMP117.get_low_limit()))
        if 'high_input' in limitJson:
            toSet = f_to_c(limitJson['high_input'])
            print("setting high limit to: " + str(toSet))
            myTMP117.set_high_limit(toSet)
            print("New high limit: " + str(myTMP117.get_high_limit()))
 
# Create server-side coroutine for websocket to send temperature data to the client
@app.route('/temperature')
@with_websocket
async def temperature(request, ws):
    while True:
        if myTMP117.data_ready():
            # We'll store all our results in a dictionary so it's easy to dump to JSON
            data = {"tempF": 0, "tempC": 0, "limitH": 75, "limitL": 65, "alertH": False, "alertL": False} 
            data['tempC'] = myTMP117.read_temp_c()
            data['tempF'] = myTMP117.read_temp_f()

            if kDoAlerts:
                time.sleep(1.5) # This delay between reads to the config register is necessary. see qwiic_tmp117_ex2
                alertFlags = myTMP117.get_high_low_alert() # Returned value is a list containing the two flags
                data['alertL'] = bool(alertFlags[myTMP117.kLowAlertIdx])
                data['alertH'] = bool(alertFlags[myTMP117.kHighAlertIdx])
                data['limitL'] = c_to_f(myTMP117.get_low_limit())
                data['limitH'] = c_to_f(myTMP117.get_high_limit())

            data = json.dumps(data) # Convert to a json string to be parsed by client
            await ws.send(data)
            time.sleep(0.5)

# Route to the static folder to serve up the HTML and CSS files
@app.route('/static/<path:path>')
async def static(request, path):
    if '..' in path:
        # directory traversal is not allowed
        return 'Not found', 404
    return send_file('static/' + path)
        
app.run()
