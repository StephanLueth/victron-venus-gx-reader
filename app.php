<?php
require_once 'includes/wifi_functions.php';
require_once 'includes/config.php';

$servername = "localhost";
$username = "sqluser";
$password = "T,X.xNYHd#tfP7cB<!rLW8";
$dbname = "macrosolar";

$filename_ = '/var/www/html/status.json';
// Create connection
$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

function findVenusWifi() {
    getWifiInterface();    
    $iface = escapeshellarg($_SESSION['wifi_client_interface']);
    $nearby = [];
	nearbyWifiStations($nearby, False);
	$result = "";
	foreach ($nearby as $network) {
		$ssid = $network["ssid"];
		if (preg_match("/^venus-/", $ssid)) {
			$result=$ssid;
			break;
		}
	}
	return $result;
}

// get venus Access Point SSID
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['venus'])) {
	$venus = findVenusWifi();
	$data = array( "venus" => $venus);
    $jsonData = json_encode($data);
    echo $jsonData;
}
// get Status
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['status'])) {
    $sql = "SELECT value, status FROM tblStatus;";
    $result = $conn->query($sql);
    if ($result->num_rows > 0) {
        $row = $result->fetch_assoc(); 
        $value = $row["value"];
	$status = $row["status"];
	$data = array( "value" => $value, "status" => $status);

        $jsonData = json_encode($data);
        echo $jsonData;
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['run'])) {
	$run = $_GET['run'];
    $netid = trim(shell_exec("sudo wpa_cli -i wlan0 add_network"));
	$ssid = "venus-HQ1728BHSWF-584";
    $run1 = 'sudo wpa_cli -i wlan0 set_network ' . $netid . ' ssid "' .$ssid .'"';
	$psk  = "f7x8yj4r";
    $run2 = 'sudo wpa_cli -i wlan0 set_network ' . $netid . ' psk "' .$psk . '"';
    $run3 = 'sudo wpa_cli -i wlan0 enable_network ' . $netid;
	$ret1 = shell_exec($run1);
	$ret2 = shell_exec($run1);
	$ret3 = shell_exec($run1);
	$data = array( "value" => $ret1 . $ret2 . $ret3 . $netid, "status" => $run1);
    $jsonData = json_encode($data);
    echo $jsonData;
}

if ($_SERVER['REQUEST_METHOD'] === 'PUT' && isset($_GET['status'])) {
    $sql = "SELECT value FROM tblStatus;";
    $result = $conn->query($sql);
    if ($result->num_rows > 0) {
        $row = $result->fetch_assoc(); 
	$content = file_get_contents('php://input');
	echo $content;
    	$newdata = json_decode($content, true);
	echo $newdata;
        // get the value of the row
	$value = $row["value"];
	$newvalue= $newdata['value'];
	$newstatus = $newdata['status'];
	$sql = "UPDATE tblStatus SET value=$newvalue, status='$newstatus' WHERE value=$value";
        echo  $sql;
        if ($conn->query($sql) === TRUE) { 
	    echo "Record updated successfully"; 
        } else { 
            echo "Error updating record: " . $conn->error; 
        }
    }
}
$conn->close();
/*
$filename_ = '/var/www/html/status.json';
$filename = '/home/stephan/victron_small/status.json';
$current_state = '{"value": 1, "status": "Stephans Handy"}';


// Update status
if ($_SERVER['REQUEST_METHOD'] === 'PUT' && isset($_GET['status'])) {
    global $current_state;
    // read the body which contains json formatted new value and new status
    $newdata = json_decode(file_get_contents('php://input'), true);
    // read the cjson formatted current value and status
    $current = json_decode(file_get_contents($filename), true); 
    // file_put_contents($filename, json_encode($current_state)); 
    //$value = $newdata->value;
    //$status = $newdata->status;
    //$json_state = json_decode($current_state);
    //$current->value = $value;
    //$current->status = $status;
    //$current_state = json_encode($current);
 }

****/
?>
