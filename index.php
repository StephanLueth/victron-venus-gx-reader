<?php
require_once 'includes/wifi_functions.php';
require_once 'includes/config.php';

function DisplayWPAConfig()
{
	///// getWifiInterface needs to defined beforw getting any Wifi Stations
    getWifiInterface();    
    $iface = escapeshellarg($_SESSION['wifi_client_interface']);
	echo "<p><b>iface:</b> " . $iface . "<p><p>";  

	///// nearby Wifi Stations
    $nearby = [];
	nearbyWifiStations($nearby, False);
	echo "<p><b>nearbyWifiStations:</b><p>";  
	foreach ($nearby as $network) :
	    foreach($network as $item) :
		  echo $item .", ";
		endforeach;
		echo "<p>";
	endforeach;

	/////// known Wifi Stations
    $networks = [];
	knownWifiStations($networks);
	echo "<p><b>knownWifiStations:</b><p>";  
	foreach ($networks as $network) :
		echo $network['ssid'] .', '. $network['psk'] . "index: " .$network['index'] . ", passphrase: ". $network['passphrase'] ."<p>";
	endforeach;
    
	////// setKnown Wifi Stations
	setKnownStationsWPA($networks);
	echo "<p><b>setKnownStationsWPA:</b><p>";  
	 foreach ($networks as $network) :
		echo $network['ssid'] .', '. $network['psk'] . "index: " .$network['index'] . ", passphrase: ". $network['passphrase'] ."<p>";
	 endforeach;
}
 // DisplayWPAConfig();
 $MACPattern = '"([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}"';
 exec('iw dev uap0 station dump | grep -oE ' . $MACPattern, $clients);
 foreach ($clients as $client) :
    //echo $client . "<p>";
 endforeach;
 $getdevices = 'cat /var/lib/misc/dnsmasq.leases| grep -E $(iw dev uap0 station dump | grep -oE ' . $MACPattern . ' | paste -sd "|")';
 // echo $getdevices;
 exec($getdevices, $devices);
 foreach($devices as $device) :
    $props = explode(' ', $device);
    //echo ">" . $props[0] . "<";
    //echo ">" .  $props[1] . "<<p>";
 endforeach;
 $hostname = "";
?>

<!DOCTYPE html lang="en">
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>macro Solar</title>
    <link rel="icon" type="image/png" sizes="32x32" href="/app/icons/macrosolar-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/app/icons/macrosolar-16x16.png">
    <link rel="icon" type="image/png" href="/app/icons/macrosolar-16x16.png" />

<style>
table {
  border-collapse: collapse;
  width: 33%;
}

th, td {
  text-align: left;
  padding: 8px;

}

/*
tr:nth-child(even) {
  background-color: #D6EEEE;
*/

body {
  font-family: Arial, Helvetica, sans-serif;
}


/* The Modal (background) */
.modal {
  display: none;
  /* Hidden by default */
  position: fixed;
  /* Stay in place */
  z-index: 1;
  /* Sit on top */
  padding-top: 100px;
  /* Location of the box */
  left: 0;
  top: 0;
  width: 100%;
  /* Full width */
  height: 100%;
  /* Full height */
  overflow: auto;
  /* Enable scroll if needed */
  background-color: rgb(0, 0, 0);
  /* Fallback color */
  background-color: rgba(0, 0, 0, 0.4);
  /* Black w/ opacity */
}

/* Modal Content */
.modal-content {
  background-color: #fefefe;
  margin: auto;
  padding: 20px;
  border: 1px solid #888;
  width: 80%;
}

/* The Close Button */

.close {
  color: #aaaaaa;
  float: right;
  font-size: 28px;
  font-weight: bold;
}

.close:hover,
.close:focus {
  color: #000;
  text-decoration: none;
  cursor: pointer;
}

    #hiddenSection {
      display: none; /* Initially hidden */
      padding: 10px;
      background-color: #f0f0f0;
      border: 1px solid #ccc;
    }
    button {
      margin-top: 10px;
    }

</style>
</head>

<body>
<h2>
<?php if (count($clients) == 0) {
          echo "no device connected.</h2><br>Please connect your laptop or mobile phone with the access point macroSOLAR-AP<br> and refresh this page!";
      } else {
          echo "Your connected device(s)</h2>";
          echo "<table><tr bgcolor='#D6EEEE'><th>" . "Host name" .  "</th>";
          echo "<th>" . "IP Address" . "</th>";
          echo "<th>" . "MAC Address" . "</th></tr>";
          foreach ($devices as $device) :
            echo "<tr>";
            $props = explode(' ', $device);
            $hostname =  htmlspecialchars($props[3], ENT_QUOTES);
            echo "<td>" . $hostname ."</td>";
            echo "<td>" . htmlspecialchars($props[2], ENT_QUOTES) ."</td>";
            echo "<td>" . htmlspecialchars($props[1], ENT_QUOTES) ."</td></tr>";
          endforeach;
          echo "</table>";
      } ?>
<br><br>

<!--- here the password input -->
<form method "post">
Please check your Venus GX/Cerbo GX. You will find the WiFi KEY printed on a label <br>
<label for="password">enter WiFi KEY of venus:</label>
<input type="text" id="password" name="password">
<input type="submit"  id="btnPassword" value="submit"><br>
    <script>
        // Define the function to be called
        function funcPassword() {
           var password = document.getElementById("password").value;
    	   const data = {value: 7, status:  password }
        return fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
           }).then(response => response.json())
        }
        // Add an event listener to the button
        document.getElementById('btnPassword').addEventListener('click', funcPassword);
    </script>
</form>

<!-- Trigger/Open The Modal -->
<button id="myBtn">re-initialize</button>

<!-- The Modal -->
<div id="myModal" class="modal">
  <!-- Modal content -->
  <div class="modal-content">
    <span class="close">&times;</span>
    <p>Would you like to reinitialize macroSOLAR device?</p>
    <button id="btn-Yes">Yes</button><button  id="btn-No">No</button>
<script>
  document.getElementById("myBtn").onclick = function() {  modal.style.display = "none"; }
  btnNo = document.getElementById("btn-No");
  btnNo.onclick = function() { modal.style.display = "none"; }
</script>
  </div>
</div>

<div>
  <div id="LicenseSection">
<p>
macrosolar viewer is a tool which requires victron GX device. It provides information about photovoltaic system, battery and load 
</p>
<p>
Copyright (C) 2025  Tilo Ritz
</p>
<p>
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <a href="https://www.gnu.org/licenses" target="_blank">GNU licenses</a>.
</p>
 </div>
  <button id="ShowLicense">License information</button>
</div>

<script>
   const toggleButton = document.getElementById('ShowLicense');
   const hiddenSection = document.getElementById('LicenseSection');

   hiddenSection.style.display = 'none';

    toggleButton.addEventListener('click', () => {
      if (hiddenSection.style.display === 'none') {
        hiddenSection.style.display = 'block';
        toggleButton.textContent = 'You can hide license information';
      } else {
        hiddenSection.style.display = 'none';
        toggleButton.textContent = 'License information';
      }
    });
</script>

<script>
const url = 'http://macrosolar.local/app.php?status'
// Get the modal
var modal = document.getElementById("myModal");

// Get the button that opens the modal
var btn = document.getElementById("myBtn");

// Get the <span> element that closes the modal
var span = document.getElementsByClassName("close")[0];

// When the user clicks the button, open the modal
btn.onclick = function() {
  modal.style.display = "block";
}

// When the user clicks on <span> (x), close the modal
span.onclick = function() {
  modal.style.display = "none";
}

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
}


// Close modal when button with id "yes-button" is clicked
 btnYes = document.getElementById("btn-Yes");
 btnYes.onclick = function() {
   modal.style.display = "none";
   const data = {value: 10, status:  "reset and reboot" }
   fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
           }).then(response => response.json())
        }
</script>
</p>
</body>
</html>
