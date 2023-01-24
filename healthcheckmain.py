import requests
from requests.auth import HTTPBasicAuth
import getpass
import socket
import paramiko
import re
import reprlib  #used for the repr function to debug
from colorama import init, Fore, Back, Style
import configparser


def error_checker(access_exists, cloud_exists, client):  #check for high error rates comparatively among the total errors
    # client.connect(hostname=each,username=sshun,passphrase=sshpw) # TODO: MAC-compatible format? Does it even need username/pw? https://gist.github.com/mlafeldt/841944 & https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
    for line in access_exists:
        if line == "exists\n":
            errors_dict = {}
            for line in cloud_exists:
                if line == 'exists\n':  #cloud site
                    stdin, stdout, stderr = client.exec_command('/bin/grep -E \"(ERROR|FATAL|SEVERE) (com|org)\" /usr/local/jive/var/logs/sbs.log | /bin/cut -d \' \' -f5,6 | /bin/sort -d | /usr/bin/uniq -c | /bin/sort -g -r', timeout=20)
                    errors_output = stdout.readlines()
                    for line2 in errors_output:
                        match = re.search(r"(\s+)(\d+)(\s)(\S+)(\s)(\S+)(\s)", line2)
                        errors_dict[int(match.group(2))] = match.group(6)
                else:  # hosted site
                    hosted_log = ""
                    stdin, stdout, stderr = client.exec_command('ls /usr/local/jive/var/logs/ | grep .log | grep \'-\' | egrep -v \'.log(.+)|sql|session|realtime|profiling|pageview|latency|docverse|dev-metrics|context|httpd|newrelic|container|appmarket\'',timeout=20)
                    errors_output = stdout.readlines()
                    for line2 in errors_output:
                        hosted_log = line2.rstrip()
                        break
                    stdin, stdout, stderr = client.exec_command('/bin/grep -E \"(ERROR|FATAL|SEVERE) (com|org)\" /usr/local/jive/var/logs/' + hosted_log + ' | /bin/cut -d \' \' -f5,6 | /bin/sort -d | /usr/bin/uniq -c | /bin/sort -g -r',timeout=20)
                    errors_output = stdout.readlines()
                    for line3 in errors_output:
                        match = re.search(r"(\s+)(\d+)(\s)(\S+)(\s)(\S+)(\s)", line3)
                        if match is not None:
                            errors_dict[int(match.group(2))] = match.group(6)
                        else:
                            continue
            for key, value in errors_dict.items():
                if key > int(round(sum(errors_dict.keys())))*.2:  # Grabs highest 20% of all errors
                    print("| " + Style.BRIGHT + errors_dict[key] + Style.RESET_ALL + " has a high amount of errors in the log")
        else:
            break


def access_ip_checker(access_exists, client):  #print IPs accessing that are > the anonymous user (possibly needing blacklisting)
    # client.connect(hostname=each,username=sshun,passphrase=sshpw) # TODO: MAC-compatible format? Does it even need username/pw? https://gist.github.com/mlafeldt/841944 & https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
    for line in access_exists:
        if line == "exists\n":
            stdin, stdout, stderr = client.exec_command('cat /usr/local/jive/var/logs/jive-httpd-access.log | awk \'{print $1}\' | sort -n | uniq -c | sort -nr | head -10', timeout=20)
            access_stdout = stdout.readlines()
            for line2 in access_stdout:
                match = re.search(r"(\s+)(\d+)(\s)(.+)", line2)
                if match and match.group(4) == '-':
                    break
                else:
                    print("| " + Style.BRIGHT + match.group(4) + Style.RESET_ALL + " has more accesses in the log than the anonymous user")
            break
        elif line == "not exists\n":
            break
        else:
            print("You should never hit here [access_exists]")
            exit(1)


def gc_checker(is_cloud, client):  #checks if GC is > 1 second
    patt1 = re.compile(r"(\\n)$")
    # client.connect(hostname=each,username=sshun,passphrase=sshpw) # TODO: MAC-compatible format? Does it even need username/pw? https://gist.github.com/mlafeldt/841944 & https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
    for line in is_cloud:
        if line == 'exists\n':  # cloud site
            stdin, stdout, stderr = client.exec_command('cat /usr/local/jive/var/logs/`ls -flarth /usr/local/jive/var/logs/ | grep sbs-gc-20 | tail -1 | awk {\'print $9\'}` | grep real= | tail -1 | awk \'{print $11}\' | cut -c6-', timeout=20)
            gc_output = stdout.readlines()
            for line2 in gc_output:
                if float(line2) > 1:
                    line2 = line2.rstrip()
                    print("| GC is " + Style.BRIGHT + line2 + Style.RESET_ALL + " seconds")
                else:
                    break
        else:  # hosted site
            stdin, stdout, stderr = client.exec_command('cat /usr/local/jive/var/logs/`ls -flarth /usr/local/jive/var/logs/ | grep .*-gc-20 | tail -1 | awk {\'print $9\'}` | grep real= | tail -1 | awk \'{print $11}\' | cut -c6-', timeout=20)
            gc_output = stdout.readlines()
            for line2 in gc_output:
                if line2 != "\n" and (patt1.match(line2)):
                    try:
                        if float(line2) > 1:
                            line2 = line2.rstrip()
                            print("| GC is " + Style.BRIGHT + line2 + Style.RESET_ALL + " seconds")
                    except ValueError:
                        print(line2 + " is not a float")
                else:
                    break


def load_checker(client):  #checks if the load average over 1 minute is > 1
    # client.connect(hostname=each,username=sshun,passphrase=sshpw) # TODO: MAC-compatible format? Does it even need username/pw? https://gist.github.com/mlafeldt/841944 & https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
    stdin, stdout, stderr = client.exec_command('w | head -1 | awk {\'print $10+0\'}', timeout=20)
    load_output = stdout.readlines()
    for line in load_output:
        if float(line) > 1:
            line = line.rstrip()
            print("| Load is " + Style.BRIGHT + line + Style.RESET_ALL)


init()
config = configparser.ConfigParser()
config.read('params.txt')
version = "0.64"
print(Back.BLUE + Fore.WHITE + Style.BRIGHT + "\n+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+")
print(''.join("| Running NOC Healthchecker v%s |" % version))
print(''.join("+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+%s" % Style.RESET_ALL))

if config.has_option('JCA', 'email'):  #login to API and check if API is functioning as expected
    email = config.get('JCA', 'email')
else:
    config['JCA'] = {'email': ''}
    email = input("Enter your JCA email address: ")
    match = re.search(r"(.+)[@](\S+)(\.com)", email)
    if not match:
        print(Style.BRIGHT + Fore.RED + "Not a valid email" + Style.RESET_ALL)
        exit(1)
    config['JCA']['email'] = email

jcapw = getpass.getpass('JCA Password: ')

resp = requests.get('https://scrubbed_hostname/admin/api/cloud/v1/users/current', auth=HTTPBasicAuth(email, jcapw))
if resp.status_code != 200:
    print("Received non-200 status code [%s] (likely incorrect pw)\nABORTING!" % resp.status_code)
    exit(1)
else:
    resp_formatted = resp.json()
    if resp_formatted['id'] == 0:
        print("ID == 0\nABORTING!")
        exit(1)

jcaid = input("Enter the InstallationID to check: ")

# grab hosts for that JCA id
resp = requests.get('https://scrubbed_hostname/admin/api/cloud/v1/vm/installation/' + jcaid, auth=HTTPBasicAuth(email, jcapw))
containers = resp.json()
servers = []
for each in containers:
    servers.append(each['hostname'])
servers = list(set(servers))
servers.sort(reverse=True)
if config.has_option('SSH', 'username'):
    sshun = config.get('SSH', 'username')
else:
    config['SSH'] = {'username': ''}
    sshun = input("Enter your SSH username: ")
    config['SSH']['username'] = sshun
#sshpw = getpass.getpass('SSH passphrase: ')
with open('params.txt', 'w') as configfile:
    config.write(configfile)

for each in servers:
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=each, username=sshun, key_filename=r"C:\Users\jared.vibert\Box Sync\Jared Vibert\docs\PHX_privatekey.ppk")  #, passphrase=sshpw)
        # client.connect(hostname=each,username=sshun,passphrase=sshpw) # TODO: MAC-compatible format? Does it even need username/pw? https://gist.github.com/mlafeldt/841944 & https://github.com/paramiko/paramiko/blob/master/demos/demo_simple.py
        print(Fore.GREEN + Style.BRIGHT + '++ ' + each + ' ++' + Style.RESET_ALL)
        stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive status', timeout=10)  #timeout in seconds
        status_stdout = stdout.readlines()  #can only be read once so needs to be stored at first read
        stdin, stdout, stderr = client.exec_command('sudo /sbin/service saasagent status', timeout=10)  #checks that saasagent is running
        saasagent_status = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('df -h', timeout=10)  #checks disk space
        diskspace_stdout = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('free | awk \'{print $4}\'', timeout=10)  #checks memory
        free_stdout = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('sar | awk \'FNR == NF-1 {print $9}\'', timeout=10)  #checks CPU
        cpu_stdout = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('[ -e "/usr/local/jive/var/logs/jive-httpd-access.log" ]&&echo "exists"||echo "not exists"', timeout=20)
        access_exists = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('[ -e "/usr/local/jive/var/logs/sbs.log" ]&&echo "exists"||echo "not exists"', timeout=10)  #checks if cloud site
        cloud_exists = stdout.readlines()
        stdin, stdout, stderr = client.exec_command('awk \'{print $9}\' /usr/local/jive/var/logs/jive-httpd-access.log | grep -w -v "5" | sort | uniq -c | sort -nr | head -30', timeout=10)  #checks for non-200 request responses
        access_request_stdout = stdout.readlines()
        if status_stdout == []:  #status checks for v6
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-application status', timeout=10)
            app_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-cache status', timeout=10)
            cache_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eae-service status', timeout=10)
            eae_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-httpd status', timeout=10)
            httpd_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-sbsdb status', timeout=10)
            sbsdb_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-analdb status', timeout=10)
            analdb_status = stdout.readlines()
            stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eaedb status', timeout=10)
            eaedb_status = stdout.readlines()
            for line2 in app_status:
                match = re.search(r"(stopped)", line2)
                if match is not None:
                    print(match.group(1))
                    if match.group(1) == 'stopped':
                        print("| " + Style.BRIGHT + "jive-application" + Style.RESET_ALL + " is stopped")
                        #answer = input("Start jive-application?: ")
                        #if answer.lower() == 'yes' or answer.lower() == 'y':
                            #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-application start',timeout=10)
                else:
                    continue
            for line3 in cache_status:
                match = re.search(r"(stopped)", line3)
                if match is not None:
                    if match.group(1) == 'stopped':
                        print("| " + Style.BRIGHT + "jive-cache" + Style.RESET_ALL + " is stopped")
                        #answer = input("Start jive-cache?: ")
                        #if answer.lower() == 'yes' or answer.lower() == 'y':
                            #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-cache start',timeout=10)
                else:
                    continue
            for line4 in eae_status:
                match = re.search(r"(eae01)", each)
                if match is not None:
                    match = re.search(r"(stopped)", line4)
                    if match is not None:
                        if match.group(1) == 'stopped':
                            print("| " + Style.BRIGHT + "jive-eae-service" + Style.RESET_ALL + " is stopped")
                            #answer = input("Start jive-eae-service?: ")
                            #if answer.lower() == 'yes' or answer.lower() == 'y':
                                #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eae-service start',timeout=10)
            for line5 in httpd_status:
                match = re.search(r"(stopped)", line5)
                if match is not None:
                    if match.group(1) == 'stopped':
                        print("| " + Style.BRIGHT + "jive-httpd" + Style.RESET_ALL + " is stopped")
                        #answer = input("Start jive-httpd?: ")
                        #if answer.lower() == 'yes' or answer.lower() == 'y':
                            #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-httpd start',timeout=10)
                else:
                    continue
        else:
            for line in status_stdout:  #check for enabled but stopped services
                if re.search(r"(\S+)(\s+)(stopped)(\s+)(enabled)", line):
                    match = re.search(r"(\S+)(\s+)(stopped)(\s+)(enabled)", line)
                    print("| " + Style.BRIGHT + match.group(1) + Style.RESET_ALL + " should be running but is not")
                    #answer = input("Start %s?: " % match.group(1))
                    #if answer.lower() == 'yes' or answer.lower() == 'y':
                        #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive start %s' % match.group(1), timeout=10)
        match = re.search(r"(db|-jd|-ed|-ad|-single)", each)  #grab only db nodes
        if match is not None:
            match = re.search(r"(-single)", each)
            if match is not None:
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-application status', timeout=10)
                app_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-cache status', timeout=10)
                cache_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eae-service status', timeout=10)
                eae_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-httpd status', timeout=10)
                httpd_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-sbsdb status', timeout=10)
                sbsdb_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-analdb status', timeout=10)
                analdb_status = stdout.readlines()
                stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eaedb status', timeout=10)
                eaedb_status = stdout.readlines()
            for line in sbsdb_status: #checks sbsdb service status
                match = re.search(r"(stopped)", line)
                if match is not None:
                    print("| " + Style.BRIGHT + "jive-sbsdb" + Style.RESET_ALL + " is stopped")
                    #answer = input("Start jive-sbsdb? (make sure you are on the correct node): ") #Bring back if wanted
                    #if answer.lower() == 'yes' or answer.lower() == 'y':
                        #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-sbsdb start', timeout=10)
            for line in analdb_status:  #checks analdb service status
                match = re.search(r"(stopped)", line)
                if match is not None:
                    print("| " + Style.BRIGHT + "jive-analdb" + Style.RESET_ALL + " is stopped")
                    #answer = input("Start jive-analdb? (make sure you are on the correct node): ") #Bring back if wanted
                    #if answer.lower() == 'yes' or answer.lower() == 'y':
                        #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-analdb start', timeout=10)
            for line in eaedb_status:  #checks eaedb service status
                match = re.search(r"(stopped)", line)
                if match is not None:
                    print("| " + Style.BRIGHT + "jive-eaedb" + Style.RESET_ALL + " is stopped")
                    #answer = input("Start jive-eaedb? (make sure you are on the correct node): ") #Bring back if wanted
                    #if answer.lower() == 'yes' or answer.lower() == 'y':
                        #stdin, stdout, stderr = client.exec_command('sudo /sbin/service jive-eaedb start', timeout=10)
        for line in saasagent_status:  #checks saasagent status
            match = re.search(r"(SaasAgent)(\s)(\S+)(\s)(\S+)", line)
            if match.group(5) == 'stopped':
                print("| " + Style.BRIGHT + "SaasAgent" + Style.RESET_ALL + " is stopped")
                answer = input("Start SaasAgent?: ")
                if answer.lower() == 'yes' or answer.lower() == 'y':
                    stdin, stdout, stderr = client.exec_command('sudo /sbin/service saasagent start',timeout=10)
        for line in diskspace_stdout:  #checks for high disk space
            if re.search(r"(\d+)([%])(\s+)(\S+)", line):
                match = re.search(r"(\d+)([%])(\s+)(\S+)", line)
                if int(match.group(1)) >= 90:
                    print("| " + Style.BRIGHT + match.group(4) + Style.RESET_ALL + " is at " + Style.BRIGHT + match.group(1) + Style.RESET_ALL + "% disk space")
        mem_var = ""
        for line in free_stdout:
            if line == 'shared\n':
                continue
            elif mem_var != "":
                break
            else:
                mem_var = line
        if int(mem_var) <= 100:
            print("| OS Free memory is <= 100KB")
        elif int(mem_var) == 0:
            print("| OS memory is 0!")
        for line in cpu_stdout:  #check for high CPU
            if 100 - float(line) >= 95:
                print("| CPU is " + Style.BRIGHT + str(round(100 - float(line), 2)) + Style.RESET_ALL + "%")
        error_checker(access_exists, cloud_exists, client)
        access_ip_checker(access_exists, client)
        for line in access_request_stdout:
            if re.search(r"(\d+) (\d\d\d)$", line):
                match = re.search(r"(\d+) (\d\d\d)$", line)
                numof_goodcalls = None
                if int(match.group(2)) == 200:
                    numof_goodcalls = int(match.group(1))
                elif numof_goodcalls is None:
                    print("| There is a high amount of " + Style.BRIGHT + Fore.WHITE + str(match.group(2)) + Style.RESET_ALL + " errors")
                else:
                    if float(match.group(1)) >= float(float(numof_goodcalls) * .1):
                        if int(match.group(2)) not in [302, 301]:
                            print("| There is a high amount of " + Style.BRIGHT + Fore.WHITE + str(match.group(2)) + Style.RESET_ALL + " errors")
        load_checker(client)
        gc_checker(cloud_exists, client)
        client.close()
    except socket.timeout as e:
        print(Fore.YELLOW + "Command timed out" + Style.RESET_ALL)
        client.close()
    except paramiko.SSHException:
        print(Style.BRIGHT + Fore.RED + "Failed to execute the command for some reason on " + Fore.GREEN + each + Style.RESET_ALL + Fore.RED + Style.BRIGHT + ". Look into this if hit" + Style.RESET_ALL)
        client.close()

        #v6 test https://[scrubbed_hostname]/admin/installation-custom-view.jspa?customerInstallationId=20097