#-----------------------------------------------------------------------------------
# Name:        wifi_functions
# Purpose:
#
# Author:      Steph
#
# Created:     08.03.2025
# Copyright:   (c) Steph 2025
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import subprocess
import time

#####################################################################################
# get known Wifi Stations
#####################################################################################
networks = dict()

WPA_SUPPLICANT_CONFIG = '/etc/wpa_supplicant/wpa_supplicant.conf'
HOSTAPD_CONFIG = '/etc/hostapd/hostapd.conf'

def getNetworkIdBySSID(ssid, iface):
    sh_cmd = f'sudo wpa_cli -i {iface} list_networks'
    output = subprocess.check_output(sh_cmd.split()).decode('utf-8')
    lines= output.split('\n')
    lines.pop(0)
    # print('************ get Network Id by SSID ************')
    for line in lines:
        columns = line.split('\t')
        # if len(columns) > 1:
        #     print(f'{columns[0]} is Network Id for {columns[1]}')
        if len(columns) >= 4 and (columns[1].strip() == ssid.strip()):
            # print(f'found matching SSID {ssid} in list_networks')
            return columns[0]
    # print('************ get Network Id by SSID END ************')
    return None


def getSSID(iface):
    sh_iwgetid = f'sudo iwgetid {iface} -r'
    SSID = ''
    try:
        SSID = subprocess.check_output(sh_iwgetid.split()).decode('utf-8').strip()
    except:
        SSID = ''
    return SSID


def knownWifiStations(networks, iface):
    def set_ssid(network, value):
        value = value.strip('"')
        network['ssid'] = value
        index = getNetworkIdBySSID(value, iface)
        network['index'] = index
        return 'ssid'

    def set_psk(network, value):
        network['passkey'] = value.strip()
        network['protocol'] = 'WPA'
        return 'psk'

    def set_passphrase(network, value):
        network['passphrase'] = value.strip()
        return 'passphrase'

    def set_hashpsk(network, value):
        network['protocol'] = 'WPA'
        return '#psk'

    def set_wepkey0(network, value):
        network['passphrase'] = value.strip('"')
        return 'wep_key0'

    def set_keymgmt(network, value):
        if not ('passphrase' in network) and (value == 'NONE'):
            network['protocol'] = 'Open'
        return 'key_mgmt'

    def set_priority(network, value):
        network['priority'] = value.strip('"')
        return 'priority'

    def set_default(network, value):
        return 'undefined'

    switch = {
        'ssid': set_ssid, 'psk': set_psk, '#psk': set_hashpsk, 
        'key_mgmt': set_keymgmt, 'wep_key0': set_wepkey0, 'priority': set_priority}

    def select_case(case, network, value):
        return switch.get(case, set_default)(network, value)

    sh_cat_wpa_supplicant =f'sudo cat {WPA_SUPPLICANT_CONFIG}'
    output = subprocess.check_output(sh_cat_wpa_supplicant.split()).decode('utf-8')
    lines  = output.split('\n')
    print(f'lines:{lines}')
    network = None
    ssid = None
    index = 0
    for line in lines:
        line = line.strip() # remove white spaces
        print(line)
        if line.startswith('network'):
            network = {
                "visible":False, "configured": True, "connected":False, "index":0
            }
            index+=1
        else:
            if network:
                if '}' in line:
                    ssid = network['ssid']
                    networks[ssid] = network
                    network = None
                    ssid = None
                else:
                    lineArr = line.split('=')
                    if len(lineArr) == 2:
                        name = lineArr[0].lower()
                        value = lineArr[1]
                        select_case(name, network, value)

def reinitializeWPA(iface):
    result = ''
    if False: # force: for now don't delete socket
        sh_cmd = f'sudo /bin/rm /var/run/wpa_supplicant/{iface}'
        output = subprocess.check_output(sh_cmd()).decode('utf-8')
        result = output
    sh_cmd = f'sudo wpa_supplicant -B -Dnl80211 -c/etc/wpa_supplicant/wpa_supplicant.conf -{iface}'
    output = subprocess.check_output(sh_cmd()).decode('utf-8')
    result = output
    return result

def setKnownStationsWPA(networks, iface):
    sh_cmd = f'sudo wpa_cli -i {iface} list_networks'
    output = subprocess.check_output(sh_cmd.split()).decode('utf-8')
    lines= output.split('\n')
    lines.pop(0)
    wpaCliNetworks = []

    for line in lines:
        line.strip()
        data = line.split('\t')
        if len(data) >= 2:
            id = data[0];
            ssid = data[1];
            item = {
                'id': id,
                'ssid': ssid
            }
            wpaCliNetworks.append(item)
    for network in networks:
        ssid = network['ssid']
        if (not networkExists(ssid, wpaCliNetworks)):
            ssid = f'"{network["ssid"]}"'
            psk  = f'"{network["passphrase"]}"'
            protocol = network['protocol']
            netid = subprocess.check_output(f"sudo wpa_cli -i {iface} add_network".split()).decode('utf-8')
#            if (isset($netid) && !isset($known[$netid])) {
#                $commands = [
#                    "sudo wpa_cli -i $iface set_network $netid ssid $ssid",
#                    "sudo wpa_cli -i $iface set_network $netid psk $psk",
#                    "sudo wpa_cli -i $iface enable_network $netid"
#                ];
#                if ($protocol === 'Open') {
#                    $commands[1] = "sudo wpa_cli -i $iface set_network $netid key_mgmt NONE";
#                }
#                foreach ($commands as $cmd) {
#                    echo(" " . $cmd);
#                    exec($cmd);
#                    usleep(1000);
#                }
#            }
#        }
#    }
#}

def nearbyWifiStations(networks, iface):
    def ConvertToChannel(sFreq):
        freq = int(sFreq)
        if (freq >= 2412) and (freq <= 2404):
           return int((freq-2407)/5)
        if (freq >= 4915) and (freq <= 4980):
           return int((freq-4910)/5) + 182
        if (freq >= 5035) and (freq <= 5865):
           return int((freq-5030)/5) + 6
        return 'Invalid Channel'

    def ConvertToSecurity(security):
        props = security[1:-1].split('][')
        result = ''
        sep = ''
        for prop in props:
            if not prop.startswith('WPA'):
               continue
            flags = prop.split('-')
            if len(result) > 0:
               sep = ' / '
            result = result + f'{sep}{flags[0]} ({flags[2]})'
        return result

    special_chars = [ chr(digit) for digit in range(0,31)]
    special_chars.append(chr(127))

    #cachetime = int(os.path.getmtime(WPA_SUPPLICANT_CONFIG))
    #cacheKey = f'nearby_wifi_stations_{cachetime}'
    # scan for nearby wifi
    sh_cmd = f'sudo wpa_cli -i {iface} scan'
    subprocess.check_output(sh_cmd.split()).decode('utf-8')
    time.sleep(3)
    # retrieve found nearby networks into array
    sh_cmd = f'sudo wpa_cli -i {iface} scan_results'
    output = subprocess.check_output(sh_cmd.split()).decode('utf-8')
    scan_results  = output.split('\n')
    scan_results.pop(0)
    print(f'scan_results:{scan_results}')
    print('----------------------------------------------------------------')
    print(f'scan_results[0]:{scan_results[0]}')
    print('----------------------------------------------------------------')
    # get the name of the AP. Should be excluded from neabrby networks
    sh_cmd = f'cat {HOSTAPD_CONFIG} | sed -rn "s/ssid=(.*)\\s*$/\\1/p"'
    result = subprocess.run(sh_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Get the output and errors (if any)
    output = result.stdout.decode().split('\n')
    print(f'hostapd.conf: {output}')
    ap_ssid = output[0]
    print(f'ap_ssid: {ap_ssid}')
    index, lastnet  = 0, 0
    if len(networks):
        lastnet = list(networks.values())[-1]
        if 'index' in lastnet.keys():
            index = int(lastnet['index']) + 1
        print(scan_results)
        for network in scan_results:
            print(f'network: {network}')
            arrNetwork = network.split('\t')
            try:
                ssid = arrNetwork[4]
            except:
                ssid = ''
            if (ssid == '') or (ssid == ap_ssid):
               continue
            if any(char in ssid for char in special_chars):
               continue
            if ssid in networks.keys():
               networks[ssid]['visible'] = True
               networks[ssid]['channel'] = ConvertToChannel(arrNetwork[1])
            else:
               networks[ssid] = {
                   'ssid': ssid,
                   'configured': False,
                   'protocol': ConvertToSecurity(arrNetwork[3]),
                   'channel': ConvertToChannel(arrNetwork[1]),
                   'passphrase': '',
                   'visible': True,
                   'connected': False,
                   'index': str(index)
               }
               index += 1

def main():
    networks = dict()
    knownWifiStations(networks, 'wlan0')
    print('Known Wifi Stations:')
    print('====================')
    for kNetwork in networks:
        if kNetwork:
            network = networks[kNetwork]
            s = '[  '
            for param in network:
                s = s + f'{param} :{network[param]}, '
            s = s.rstrip(', ') +']'
            print(kNetwork + ">" + s)

    print('Nearby Wifi Stations:')
    print('=====================')
    nearbyWifiStations(networks, 'wlan0')
    for kNetwork in networks:
        if kNetwork:
            network = networks[kNetwork]
            s = '[  '
            for param in network:
                s = s + f'{param} :{network[param]}, '
            s = s.rstrip(', ') +']'
            print(kNetwork + "\n------------------------\n" + s + '\n\n')

if __name__ == '__main__':
    main()
