import os, sys
import socket
from datetime import datetime


import wifi_functions as wf

# Get the current date and time
def Now():
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


# some initalizations
homedir = os.path.join((os.path.dirname(os.path.realpath(__file__))), '')
picdir = os.path.join(homedir, 'pic')
libdir = os.path.join(homedir, 'lib')
hostname = socket.gethostname() + ".local" # mDNS convention
statustext = ""


iface = "wlan0"
device = None
venus_wifi = ""
client = None

# URL of the web service
urlstatus = "http://macrosolar.local/app.php?status"

# URL of the web service getting the venus acccess point name
urlvenus_ap = "http://macrosolar.local/app.php?venus"

# Headers
headers = { 'Content-Type': 'application/json' }


# States of automated configuration and detection of venus wifi
STAT_UNDEFINED = -1
STAT_NOT_INIT = 0		# (1st time access to zero device) Show info about instructions to connect with macrSOLAR AP
STAT_RUN_CHECK_AP = 1		# check, if any devices are connected with macroSOLAR AP
STAT_AP_CONNECTED = 2		# (a device is connected with macroSOLAR AP), show info about success and about now scanning for Venus
STAT_SHOW_SCAN_INFO = 3		# show scanning info
STAT_RUN_SCANNING = 4		# call get_venus_cebro()
STAT_VENUS_FOUND = 5		# Venus Wifi found, show info to open http://macrosolar.local and enter Wifi password
STAT_ENTER_WIFI_PWD = 6		# on web page ask and submit Wifi password or submit reset
STAT_VERIFY_PASSWORD = 7	# call connect_to_venus_Wifi()
STAT_SHOW_BATTERY_DATA = 8  # call Get_and_Show_Battery_Data()
STAT_REFRESH_DATA = 12      # call Get_and_Show_Battery_Data() w/o init display
STAT_MODBUS_ERROR = 9		# output Show Modbus Error and advice to re-init or contact support
STAT_RESET_TO_NOT_INIT = 10	# call setstatus(STAT_NOT_INIT)
STAT_WRONG_PASSWORD = 11	# cannot ping venus.local. Show error and request re-enter Password
STAT_ERROR_GETSTATUS = -2	# we have a problem with the web service or mysql
STAT_ERROR_SETSTATUS = -3	#     ----"----

# init status and l(ast)status variables
status = STAT_UNDEFINED
lstatus = status

# we have to bitmaps, one with qrcode for connection to macrosolar AP, the other only with macrSOLAR at the top
BMP_not_init = "not initialized macrosolar.local.bmp"
BMP_macrosolar = 'macrosolar.bmp'
BMP_batterydata = 'batterydata.bmp'

# append local sub directory lib to the library path
# this local lib directory conatins waveshare library
# for  printing to e-paper display
if os.path.exists(libdir):
    sys.path.append(libdir)

import pymodbus.client as modbusClient

import logging
from waveshare_epd import epd2in13_V4
import time
from PIL import Image,ImageDraw,ImageFont
import subprocess		# running cmdline app
import re			# regular expression module
import traceback
import requests			# for consuming the custom web service
import json			# just for data representation when using web service

# set the logging level
logging.basicConfig(level=logging.INFO)


#####################################################################################
# venus.local modbus registers
#####################################################################################
# UNITS for System and VE direct connected MQQT
SYSTEM = 100
CHARGER = 245

HOST = "venus.local"
PORT = 502


# Battery State of Charge (System)
# or 266 in dbus battery
ADR_BATTERY_SOC = (843, SYSTEM, 1)

# AC output power (System)
ADR_AC_Consumption_L1 = (817, SYSTEM, 1)
ADR_AC_Consumption_L2 = (818, SYSTEM, 1)
ADR_AC_Consumption_L3 = (819, SYSTEM, 1)

# Solar Power in Watt (System)
ADR_PV_coupled_power = (789, CHARGER, 10) # (850, SYSTEM, 1)

# Power, negativ: into net, positiv: from net (Grid)
# may be 2638, 2640, 2642, if power is larger than 16 Bit (>32768 W)
ADR_GRID_Power_L1 = (2600, SYSTEM, 1)
ADR_GRID_Power_L2 = (2601, SYSTEM, 1)
ADR_GRID_Power_L3 = (2602, SYSTEM, 1)

# battery voltage (System) - 840, scale factor=10!!!!
# or address=259 in dbus Battery, Scale focator=100!!!
# or address=260 for starter battery, scale factor=100!!!
# or per VE direct connected MQQT: address 771, unit=245, scale factor=100!!!
ADR_BATTERY_Voltage = (771, CHARGER, 100) #840


# battery current (System) - 841, scale factor=10!!!!
# or be 261 in dbus Battery, Scale foctor=10!!!
# or per VE direct connected MQQT: address 772, unit=245 Scale factor 10
ADR_BATTERY_Current = (772, CHARGER, 10) # 841




#####################################################################################
# find venus access point . SSID starts with "venus-"
#####################################################################################
def getstatus()-> tuple:
    maxRetries = 3
    while maxRetries:
        try:
            response = requests.get(urlstatus, headers=headers)
            if response.status_code == 200:
                state = json.loads(response.content)
                logging.debug('DEBUG getstatus',state["value"], state["status"])
                return (int(state["value"]), state["status"])
            else:
                return(ERROR_GETSTATUS, "Cannot get status")
        except Exception as e:
            print(f"Exception {e} occurred in getstatus")
            maxRetries -= 1 
            time.sleep(5)
    return(ERROR_GETSTATUS, "Cannot get status")

#####################################################################################
# read status of automated configuration and detection
#####################################################################################
def getVenusAP()-> str:
    global venus_wifi
    try:
        response = requests.get(urlvenus_ap, headers=headers)
        if response.status_code == 200:
            data = json.loads(response.content)
            venus_wifi = data["venus"]
            logging.debug('DEBUG getVenusAP', venus_wifi)
            return venus_wifi
        else:
            return(ERROR_GETSTATUS, "Cannot get venus access point")
    except Exception as e:
        print(f"Exception {e} occurred in getstatus")

#####################################################################################
# set the status code and text
#####################################################################################
def setstatus(statuscode: int, statustext: str)->dict:
    try:
        new_status = {'value': statuscode, 'status': statustext }
        response = requests.put(urlstatus, data=json.dumps(new_status), headers=headers)
        # Check the response
        if response.status_code == 200:
            # successfully: return statuscode and statustext
            return (statuscode, statustext)
        else:
            return(STAT_ERROR_SETSTATUS, f"cannot set status ({statuscode}, '{statustext}')")
    except Exception as e:
        print(f"Exception {e} occurred in setstatus")

#####################################################################################
# ping hostname, return True, if available else False
#####################################################################################
def ping_host(hostname):
    try:
        output = subprocess.check_output(["/usr/bin/ping", "-c", "4", hostname], universal_newlines=True)
        logging.info(output)
        return True
    except subprocess.CalledProcessError as e:
        logging.info(f"Failed to ping {hostname}. Error: {e}")
        return False

#####################################################################################
# connect to the venus CX/Cerbo CX wifi by given SSID and password
#####################################################################################
def do_run_connect_to_venus(ssid, password):
    global venus_wifi
    # Erstellen Sie eine Konfigurationsdatei für wpa_supplicant
    print(f"### ssid:{ssid}, venus_wifi:{venus_wifi}")
    header = f"""
    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    update_config=1
    """
    # wegen problemen mit der Verbindung zum zero device nach der Anpassung,
    # wird der folgende code zunächst nicht ausgeführt
    if True: #try:
        known = dict()
        wf.knownWifiStations(known, iface)
        for network in known:
            # disconnect/remove possibly existing network from interface
            knownNetwork = known[network]
            netID = knownNetwork['index']
            print(knownNetwork)
            if knownNetwork['ssid'] == ssid:
               print(f'disconnect  {ssid}')
               sh_disconnect = f'sudo /usr/sbin/wpa_cli -i {iface} disconnect {netID}'
               subprocess.run( sh_disconnect.split())
               print(f'remove {ssid}')
               sh_remove = f'sudo /usr/sbin/wpa_cli -i {iface} remove_network {netID}'
               subprocess.run(sh_remove.split())
            else:
               ssid = f'"{knownNetwork["ssid"]}"'
               psk  = f'"{knownNetwork["passkey"]}"'
               print(f'add_network {ssid}')
               sh_add = f'sudo /usr/sbin/wpa_cli -i {iface} add_network'
               netID = subprocess.check_output(sh_add.split()).decode('utf-8')
               if netID:
                  print(f'set_network {netID} ssid {ssid}')
                  subprocess.run(f'sudo /usr/sbin/wpa_cli -i {iface} set_network {netID} ssid {ssid}'.split())
                  print(f'set_network {netID} psk {psk}')
                  subprocess.run(f'sudo /usr/sbin/wpa_cli -i {iface} set_network {netID} psk {psk}'.split())
                  print(f'enable_network {netID}')
                  subprocess.run(f'sudo /usr/sbin/wpa_cli -i {iface} enable_network {netID}'.split())
        # Speichern Sie die Konfigurationsdatei
        with open("/tmp/wpa_supplicant.conf", "w") as file:
            file.write(f'{header}\n')
            for network in known:
                knownNetwork = known[network]
                ssid = knownNetwork['ssid']
                passkey =knownNetwork['passkey']
                if (len(passkey)<=63):
                   wpa_passphrase = subprocess.check_output(f'wpa_passphrase {ssid} "{passkey}"'.split()).decode('utf-8')
                   lines=wpa_passphrase.split('\n')
                   for line in lines:
                       file.write(line)
                else:
                   file.write(f'network={{\n')
                   file.write(f'\tssid="{knownNetwork["ssid"]}"\n')
                   file.write(f'\tpsk={knownNetwork["passkey"]}\n')
                   file.write(f'}}\n')
        # subprocess.run(["sudo", "cp", "/tmp/wpa_supplicant.conf", "/etc/wpa_supplicant/wpa_supplicant.conf"])

        # Starten Sie den wpa_supplicant-Dienst neu
        ### testing temporarely commented out STEPHAN subprocess.run(f'sudo /usr/sbin/wpa_cli -i {iface} reconfigure'.split())

        # Verbinden Sie sich mit dem Netzwerk
        ### subprocess.run("sudo /usr/sbin/ifconfig wlan0 up".split())
        ### subprocess.run("sudo /usr/sbin/dhclient wlan0".split())
    # except Exception as e:
    #    print(f"Exception {e} occurred in connect_to_wifi, adding{ssid} and {password}")
    if not ping_host("venus.local"):
       setstatus(STAT_WRONG_PASSWORD, password)
    else:
       setstatus(STAT_SHOW_BATTERY_DATA, 'show battery data')

#####################################################################################
# scan for any wifi SSID which matches with venus*
#####################################################################################
def do_run_scan_venus_cerbo_gx():
    global venus_wifi
    try:
        venus_wifi = getVenusAP()
        if venus_wifi != "":
            logging.info(f"found venus wifi {venus_wifi}")
            setstatus(STAT_VENUS_FOUND, venus_wifi)
            return
    #
    #        sh_get_hotspots = "/usr/bin/nmcli -c no -f SSID d wifi list ifname uap0"
    #        text  = subprocess.check_output(sh_get_hotspots.split()).decode('utf-8')
    #        victron_hotspots =  []
    #        lines=text.split("\n")
    #        for line in lines:
    #            if line.find("venus") == 0:
    #                victron_hotspots.append(line)
    #                logging.info(f"found venus wifi {line}")
    #                setstatus(STAT_VENUS_FOUND, line)
    #                break
    #        return
    except Exception as e:
        print(f"Exception {e} occurred in do_run_scan_venus_cerbo_gx")

#####################################################################################
# check if any device is connected to hotspot macroSOLAR-AP and return its MACs
#####################################################################################
def do_run_check_AP():

    def extract_mac_addresses(text):
        # retrieve all occcurances of MAC addresses
        # return string array of found MAC_addresses
        #
        # Regular expression pattern for MAC addresses
        # couldn't find a better pattern, but retrieves
        # also large numbers which needs to removed later by code
        mac_pattern = r'(?:[0-9a-fA-F]:?){12}'
        #mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
        # mac_addresses = re.search(mac_pattern, text).group()
        mac_addresses = re.findall(mac_pattern, text)
        logging.debug("xma mac_addr" + str(mac_addresses))
        macs=[]
        for mac in mac_addresses:
            if len(mac) ==  17:
               col_okay=True
               for col in range(1,6):
                  if mac[3*col-1] != ":":
                     col_okay=False
                     break
               if col_okay:
                  macs.append(mac)
        logging.info("xma" +  text)
        logging.info('xma' +  str(macs))
        return macs

    def extract_devices(text, mac_adresses):
        # retrieve IP, devicename from dnsmasq leases of given mac_addresses
        # returns array of tupels (MAC-address, IP, devicename)
        # used only by function get_connected devices
        lines = text.split("\n")
        result = []
        for line in lines:
            try:
               tokens = line.split()
               mac = tokens[1]
               name = tokens[3]
               ip = tokens[2]
               if mac in mac_adresses:
                  result.append((mac, ip, name))
            except:
               # probably empty line
               continue
        logging.info('xd' + str(len(result)))
        return result

    try:
        logging.info(f"get_connected_devices")
        sh_cat_dnsmasq ='cat /var/lib/misc/dnsmasq.leases'
        sh_station_dump ='/usr/sbin/iw dev uap0 station dump'
        iw_stations = subprocess.check_output(sh_station_dump.split()).decode('utf-8')
        MAC_adresses = ''
        if iw_stations:
            MAC_adresses = extract_mac_addresses(iw_stations)
            # get dnsmasq leases might be delayed, so we check 3 times
            retries = 3
            while retries:
               dnsmasq_leases = subprocess.check_output(sh_cat_dnsmasq.split()).decode('utf-8')
               MAC_adresses = extract_devices(dnsmasq_leases, MAC_adresses);
               if len(MAC_adresses) > 0:
                  break
               retries -= 1
               time.sleep(3)
            logging.info(f'MACs:{MAC_adresses}')
            setstatus(STAT_AP_CONNECTED, MAC_adresses[0][2])
        logging.info(f'found:{MAC_adresses}')
    except Exception as e:
        print(f"Exception {e} occurred in do_run_check_AP")
    return

#####################################################################################
# show on display: not initialied and connect infos about macroSOLAR-AP
#####################################################################################
def do_show_please_connect_to_macrosolar_ap():
    logging.info('DEBUG status == STAT_NOT_INIT')
    bitmap = BMP_not_init.format(hostname)
    logging.info(f"loading bitmap file '{bitmap}'")
    image = Image.open(os.path.join(picdir, bitmap))
    draw = ImageDraw.Draw(image)
    draw.text((110, 22), f'No configurado', font=font18, fill=0)
    draw.text((111, 22), f'No configurado', font=font18, fill=0)

    #draw.text(( 105, 46), f'Please connect to', font=font15, fill=0)
    draw.text(( 105, 46), f'Por favor conectar', font=font15, fill=0)
    #draw.text(( 105, 64), f'access point:', font=font15, fill=0)
    draw.text(( 105, 64), f'al WIFI:', font=font15, fill=0)
    draw.text(( 105, 82), f'macroSOLAR-AP', font=font15, fill=0)
    draw.text(( 106, 82), f'macroSOLAR-AP', font=font15, fill=0)
    #draw.text(( 105, 98), f'Password:',     font=font15, fill=0)
    draw.text(( 105, 98), f'Clave:',     font=font15, fill=0)
    draw.text(( 173, 98), f'12345678',      font=font15, fill=0)
    draw.text(( 174, 98), f'12345678',      font=font15, fill=0)
    epd.display(epd.getbuffer(image))
    print("STAT_NOT_INIT set status to STAT_RUN_CHECK_AP")
    setstatus(STAT_RUN_CHECK_AP, "scan for devices connected to macroSOLAR AP")
    print("STAT_NOT_INIT completed")
    return

#####################################################################################
# show on display: that connected to macroSOLAR-AP and start scanning venus wifi
#####################################################################################
def do_show_connected_to_AP():
    logging.info('DEBUG status == STAT_HOTSPOT_CONNECTED with '+ statustext)
    devicename = statustext
    bitmap = BMP_macrosolar
    logging.info(f"loading bitmap file '{bitmap}'")
    image = Image.open(os.path.join(picdir, bitmap))
    draw = ImageDraw.Draw(image)
    #draw.text((  0, 21), f'{devicename} is now connected', font=font15, fill=0)
    draw.text((  0, 21), f'{devicename} conectado', font=font15, fill=0)
    #draw.text((  1, 21), f'{devicename}', font=font15, fill=0)
    draw.text((  1, 21), f'{devicename} conectado', font=font15, fill=0)
    draw.text((  0, 41), f'con macroSOLAR-AP', font=font15, fill=0)
    #draw.text((  0, 61), 'Begin scanning for wifi of venus GX', font=font15, fill=0)
    draw.text((  0, 61), 'Buscando WIFI de Victron GX', font=font15, fill=0)
    epd.display(epd.getbuffer(image))
    setstatus(STAT_SHOW_SCAN_INFO, "start scanning...")
    return

#####################################################################################
# show on display: ask for patience & bring both devices close together
#####################################################################################
def do_show_scan_info():
    logging.info('DEBUG status == STAT_SCANNING')
    bitmap = BMP_macrosolar
    logging.info(f"loading bitmap file '{bitmap}'")
    image = Image.open(os.path.join(picdir, bitmap))
    draw = ImageDraw.Draw(image)
    #draw.text((  0, 21), 'Scanning Wifi of Venus/Cerbo GX', font=font15, fill=0)
    draw.text((  0, 21), 'Buscando WIFI de  Venus/Cerbo GX', font=font15, fill=0)
    #draw.text((  1, 21), 'Scanning Wifi of Venus/Cerbo GX', font=font15, fill=0)
    draw.text((  1, 21), 'Buscando WIFI de  Venus/Cerbo GX', font=font15, fill=0)
    draw.text((  0, 61), 'Esto puedo tardar 3 minutes.', font=font15, fill=0)
    # draw.text((  0, 81), 'Bring your macroSOLAR', font=font15, fill=0)
    draw.text((  0, 81), 'Acere su pantalla macroSOLAR', font=font15, fill=0)
    #draw.text((  0,101), 'device close to Venus/Cerbo GX', font=font15, fill=0)
    draw.text((  0,101), 'al Victron GX', font=font15, fill=0)
    epd.display(epd.getbuffer(image))
    setstatus(STAT_RUN_SCANNING, "scanning venus wifi")

#####################################################################################
# show on display: show found venus wifi name and request to open website
# http://macrosolar.local so that teh printed password can be enterer on web site
#####################################################################################
def do_show_venus_found():
    logging.info('DEBUG status == STAT_VENUS_FOUND')
    global venus_wifi
    # venus_wifi = statustext
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    #draw.text((  0, 21), 'found Wifi Venus GX/Cerbo GX', font=font15, fill=0)
    draw.text((  0, 21), 'WIFI Victron GX encontrado', font=font15, fill=0)
    #draw.text((  1, 21), 'found Wifi Venus GX/Cerbo GX', font=font15, fill=0)
    draw.text((  1, 21), 'WIFI Victron GX encontrado', font=font15, fill=0)
    draw.text((  0, 41),  f'WIFI:', font=font15, fill=0)
    draw.text(( 37, 41), f'{venus_wifi}', font=font15, fill=0)
    draw.text(( 38, 42), f'{venus_wifi}', font=font15, fill=0)
    draw.text((  0, 61), 'Abra http://macrosolar.local en', font=font15, fill=0)
    #draw.text((  0, 81), 'browser and enter the WiFi KEY', font=font15, fill=0)
    draw.text((  0, 81), 'Navegador e ingrese WIFI KEY', font=font15, fill=0)
    #draw.text((  0,101), 'labeled on your Venus/Cerbo GX', font=font15, fill=0)
    draw.text((  0,101), 'impreso al costado de  Victron GX', font=font15, fill=0)
    epd.display(epd.getbuffer(image))
    print(f"### venus_wifi before:{venus_wifi}")
    setstatus(STAT_ENTER_WIFI_PWD, venus_wifi)
    print(f"### venus_wifi after:{venus_wifi}")
    return

#####################################################################################
# show on display: show error message when exception occurred in getstatus
#####################################################################################
def do_show_error_getstatus():
    logging.info('DEBUG status == STAT_ERROR_GETSTATUS')
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    draw.text((  0, 21), 'INTERNAL ERROR', font=font15, fill=0)
    draw.text((  1, 21), 'INTERNAL ERROR', font=font15, fill=0)
    draw.text((  0, 41), statustext, font=font15, fill=0)
    draw.text((  0, 61), 'Try rebooting or resetting this device', font=font15, fill=0)
    draw.text((  0, 81), 'or  contact technical support', font=font15, fill=0)
    epd.display(epd.getbuffer(image))

#####################################################################################
# show on display: show error message when exception occurred in setstatus
#####################################################################################
def do_show_error_setstatus():
    logging.info('DEBUG status == STAT_ERROR_SETSTATUS')
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    draw.text((  0, 21), 'INTERNAL ERROR', font=font15, fill=0)
    draw.text((  1, 21), 'INTERNAL ERROR', font=font15, fill=0)
    draw.text((  0, 41), statustext, font=font15, fill=0)
    draw.text((  0, 61), 'Try rebooting this device (switch off/on)', font=font15, fill=0)
    draw.text((  0, 81), 'or  contact technical support', font=font15, fill=0)
    epd.display(epd.getbuffer(image))

#####################################################################################
# show on display: show error message when exception occurred in setstatus
#####################################################################################
def do_show_wrong_password():
    logging.info('DEBUG status == STAT_WRONG_PASSWORD')
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    draw.text((  0, 21), 'Unable to connect to venus/cebro GX', font=font15, fill=0)
    draw.text((  1, 21), 'Unable to connect to venus/cebro GX', font=font15, fill=0)
    draw.text((  0, 41), 'Your wifi key might be wrong', font=font15, fill=0)
    draw.text((  0, 61), 'You entered', font=font15, fill=0)
    draw.text(( 90, 61), f'{statustext}', font=font15, fill=0)
    draw.text(( 91, 61), f'{statustext}', font=font15, fill=0)
    draw.text((  0, 81), 'Open http://macrosolar.local and', font=font15, fill=0)
    draw.text((  0,101), 'verify/reenter WiFi KEY', font=font15, fill=0)
    epd.display(epd.getbuffer(image))

#####################################################################################
# show on display: battery data
#####################################################################################
imageData = None
def do_show_battery_data(refreshOnly : bool):
    global imageData

    def drawBold(x, y, sLine):
        draw.rectangle((x, y, 250, y+19), fill=255)
        epd.displayPartial(epd.getbuffer(imageData))
        draw.text((x, y), sLine, font=font15, fill=0)
        draw.text((x+1, y), sLine, font=font15, fill=0)
        epd.displayPartial(epd.getbuffer(imageData))

    logging.info('DEBUG status == STAT_SHOW_BATTERY_DATA')
    epd.init()
    imageData = Image.open(os.path.join(picdir, BMP_batterydata))
    global client
    if refreshOnly:
        print('REFRESH_DATA')
    else:
        print('SHOW_DATA')
    try:
        if client is None:
            client = modbusClient.ModbusTcpClient(HOST, port=PORT)
            if client:
                print(f"connecting to venus GX")
                client.connect()
            else:
                draw = ImageDraw.Draw(imageData)
                drawBold(0, 21, "ERROR connecting to venus/cebro GX")
                epd.display(epd.getbuffer(imageData))
            return
    except Exception as e:
        print(f"connect to venus fails with exception: {e}")
        draw.text((  0, 21), "ERROR connecting to venus/cebro GX", font=font15, fill=0)

    if not refreshOnly:
        imageData = Image.open(os.path.join(picdir, BMP_batterydata))
        draw = ImageDraw.Draw(imageData)
        epd.displayPartial(epd.getbuffer(imageData))

    draw = ImageDraw.Draw(imageData)
    draw.rectangle((136, 21, 200, 120), outline=255, fill=255)
    try:
        #################################
        # Battery SOC (state of charge) #
        #################################
        #if not refreshOnly:
        #    draw.text((  0, 21), 'Carga de la batería', font=font15, fill=0)
        #    epd.displayPartial(epd.getbuffer(imageData))
        result = client.read_holding_registers(843, slave=100)
        sValue = str(result.registers[0])+ ' %' if result else 'ERROR'
        drawBold(136, 21, sValue)

        #################################
        # PV  power                     #
        #################################
        #if not refreshOnly:
        #    draw.text((  0, 41), 'potencia solar', font=font15, fill=0)
        #    epd.displayPartial(epd.getbuffer(imageData))
        (address, unit, scale) = ADR_PV_coupled_power
        result = client.read_holding_registers(address, slave=unit)
        sValue = "{:.1f} W".format(result.registers[0]/scale) if result else 'ERROR'
        drawBold(136, 41, sValue)

        #################################
        # AC output power               #
        #################################
        #if not refreshOnly:
        #    draw.text((  0, 61), 'consumo de casa', font=font15, fill=0)
        #    epd.displayPartial(epd.getbuffer(imageData))
        result = client.read_holding_registers(817, count=3, slave=100)
        sValue = ','.join(map(str, result.registers)) + " W" if result else 'ERROR'
        drawBold(136, 61, sValue)

        #################################
        # Battery current               #
        #################################
        #if not refreshOnly:
        #    draw.text((  0, 81), 'corriente de batería', font=font15, fill=0)
        #    epd.displayPartial(epd.getbuffer(imageData))
        (address, unit, scale) = ADR_BATTERY_Current
        result = client.read_holding_registers(address, slave=unit)
        sValue = "{:.1f} A".format(result.registers[0]/scale) if result else 'ERROR'
        drawBold(136, 81, sValue)

        #################################
        # Battery voltage               #
        #################################
        #if not refreshOnly:
        #    draw.text((  0, 101), 'voltaje de batería', font=font15, fill=0)
        #    epd.displayPartial(epd.getbuffer(imageData))
        (address, unit, scale) = ADR_BATTERY_Voltage
        result = client.read_holding_registers(address, slave=unit)
        sValue = "{:.1f} V".format(result.registers[0]/scale) if result else 'ERROR'
        drawBold(136, 101, sValue)

        epd.displayPartial(epd.getbuffer(imageData))
        #imageData.save('batterydata.png')  # Save as PNG
        #input()
    except Exception as e:
        print(f"read venus register fails with exception: {e}")
        rectangle_coords = (0, 21, 255, 40)
        # Draw a white rectangle
        draw.rectangle(rectangle_coords, fill=255)
        drawBold(  0, 21, "ERROR reading register from venus/cebro GX")
        client = None
        epd.display(epd.getbuffer(imageData))
    setstatus(STAT_REFRESH_DATA, 'refresh battery data')
    epd.sleep()

#####################################################################################
# show on display: show rebooting info and run sudo reboot
#####################################################################################
def do_run_reset():
    global lstatus
    lstatus =  STAT_UNDEFINED
    setstatus(STAT_NOT_INIT, "(Reboot) - not initialized")
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    draw.text((  0, 21), 'INICIANDO macroSOLAR aparato', font=font15, fill=0)
    draw.text((  1, 21), 'INICIANDO macroSOLAR aparato', font=font15, fill=0)
    draw.text((  1, 21), 'REBOOTING macroSOLAR device', font=font15, fill=0)
    draw.text((  0, 61), 'espere por favor ...', font=font15, fill=0)
    time.sleep(5)
    subprocess.run("sudo /usr/sbin/reboot".split())


#####################################################################################
# main program: basically init display and running loop for ever. In main loop ...
# ... different functions will be called according to current state
#####################################################################################
def main():
    global status, lstatus
    try:
        # on reboot/Power off/on, reset status
        # main loop automate for ever
        print('macroSOLAR starts running', Now())
        while True:
            logging.info(f"Status:{status} (before {lstatus}) {venus_wifi}")
            (status, statustext) = getstatus()
            logging.info(f"status:{status}, lstatus:{lstatus}, hit <enter>")
            if status != lstatus:
                lstatus = status
                if status == STAT_NOT_INIT:
                    # show logo/qrcode not init bitmap
                    do_show_please_connect_to_macrosolar_ap()
                if status == STAT_RUN_CHECK_AP:
                    # assure that check will be repeated until found
                    lstatus = STAT_UNDEFINED
                    do_run_check_AP()
                if status == STAT_AP_CONNECTED:
                    do_show_connected_to_AP()
                if status == STAT_SHOW_SCAN_INFO:
                    do_show_scan_info()
                if status == STAT_RUN_SCANNING:
                    # assure that check will be repeated until found
                    lstatus = STAT_UNDEFINED
                    do_run_scan_venus_cerbo_gx()
                if status == STAT_VENUS_FOUND:
                    do_show_venus_found()
                    print(f"### venus_wifi:{venus_wifi}")
                if status == STAT_REFRESH_DATA:
                    lstatus = STAT_UNDEFINED
                    do_show_battery_data(True)
                if status == STAT_VERIFY_PASSWORD:
                    do_run_connect_to_venus(venus_wifi, statustext)
                if status == STAT_SHOW_BATTERY_DATA:
                    lstatus = STAT_UNDEFINED
                    do_show_battery_data(False)
                if status == STAT_RESET_TO_NOT_INIT:
                   do_run_reset()
                if status == STAT_WRONG_PASSWORD:
                   do_show_wrong_password()
                if status == STAT_ERROR_GETSTATUS:
                   do_show_error_getstatus()
                if status == STAT_ERROR_SETSTATUS:
                   do_show_error_setstatus()
            time.sleep(5)
    except IOError as e:
        logging.info(e)
        print(f"macroSOLAR terminates with exception IOError at {Now()}")
        image = Image.open(os.path.join(picdir, BMP_macrosolar))
        draw = ImageDraw.Draw(image)
        draw.text((  0, 41), 'Exception IO Error', font=font15, fill=0)
        epd.display(epd.getbuffer(image))
    except KeyboardInterrupt as e:
        logging.info("ctrl + c:")
        epd2in13_V4.epdconfig.module_exit(cleanup=True)
        print(f"macroSOLAR terminates by user at {Now()}")
        exit()
    except Exception as e:
        print(f"macroSOLAR terminates at {Now()} with exception: {e}")
        image = Image.open(os.path.join(picdir, BMP_macrosolar))
        draw = ImageDraw.Draw(image)
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)

        draw.text((  0, 61), f'{exc_type} in {fname}', font=font15, fill=0)
        draw.text((  0, 81), f'line {exc_tb.tb_lineno}', font=font15, fill=0)
        epd.display(epd.getbuffer(image))


if __name__ == '__main__':
    #just init ePaper and status flag for main() program
    epd = epd2in13_V4.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear(0xFF)
    # Drawing on the image
    font15 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 15)
    # font24 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 24)
    font18 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)
    image = Image.open(os.path.join(picdir, BMP_macrosolar))
    draw = ImageDraw.Draw(image)
    # draw.text((  0, 21), 'Rebooting, please wait!', font=font15, fill=0)
    draw.text((  0, 21), 'Iniciando - espere por favor!', font=font15, fill=0)
    epd.display(epd.getbuffer(image))
    lstatus = STAT_UNDEFINED
    status = STAT_UNDEFINED
    # test()
    setstatus(STAT_NOT_INIT, "rebooted")
    main()
