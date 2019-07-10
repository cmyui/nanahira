import socket
import string
import random
import json
import os
import psutil
import mysql.connector
from mysql.connector import errorcode
import time

# TODO: stop using these!
from colorama import init
from colorama import Fore, Back, Style

# Initialize colorama.
# autoreset ensures colors are ended at the end of strings where colors are used..
init(autoreset=True)

SQL_HOST, SQL_USER, SQL_PASS, SQL_DB = [None] * 4

# Config
config = open('config.ini', 'r')
config_contents = config.read().split("\n")
for line in config_contents:
    line = line.split("=")
    if line[0].strip() == "SQL_HOST": # IP Address for SQL.
        SQL_HOST = line[1].strip()
    elif line[0].strip() == "SQL_USER": # Username for SQL.
        SQL_USER = line[1].strip()
    elif line[0].strip() == "SQL_PASS": # Password for SQL.
        SQL_PASS = line[1].strip()
    elif line[0].strip() == "SQL_DB": # DB name for SQL.
        SQL_DB = line[1].strip()

# MySQL
try:
    cnx = mysql.connector.connect(
        user       = SQL_USER,
        password   = SQL_PASS,
        host       = SQL_HOST,
        database   = SQL_DB,
        autocommit = True)
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print(f"{Fore.RED}Something is wrong with your username or password.")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print(f"{Fore.RED}Database does not exist.")
    else:
        print(f"{Fore.RED}{err}")
    os.exit()
else:
    SQL = cnx.cursor()

# Host IP. Blank string = localhost
SOCKET_LOCATION = "/tmp/tohru.sock"

# Remove socket if it exists.
if os.path.exists(SOCKET_LOCATION):
    os.remove(SOCKET_LOCATION)

# Initialize socket.
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

# Maximum amount of data we will accept.
MAX_PACKET = 1024000 # 1024MB

# Array of supported filetypes.
UNSUPPORTED_FILETYPES = ["virus"] # xd

# Length of randomly generated filenames.
FILENAME_LENGTH = 12

# Location to save uploads to.
SAVE_LOCATION = "/home/cmyui/tohru/uploads/"

# Generate a random FILENAME_LENGTH string.
def generate_filename(length=FILENAME_LENGTH): # Generate using all lowercase, uppercase, and digits.
    return "".join(random.choice(string.ascii_letters + string.digits) for i in range(length))


def handle_request(data):
    # Split the data into headers, content headers, and body.
    split = data.split(b"\r\n\r\n")
    # Assign the headers and content headers from split[0] and split[1].
    headers, content_headers = split[0].decode().split("\r\n"), split[1].decode().split("\r\n")
    # Assign body from split[2].
    body = split[2]

    # Set request values to None.
    request_IP, request_UAgent, request_token = [None] * 3

    # Iterate through content headers to assign keys and values.
    for header in headers:
        # Split up the header into keys and values.
        current_header = header.split(": ")

        # Check if the header has been properly split into key and value.
        if len(current_header) > 1:
            # Assign the key and value for the header.
            header_key, header_value = current_header

            # Check if the header is the CF-Connecting-IP header.
            # This header is the user's IP address, passed through cloudflare to us.
            if header_key == "CF-Connecting-IP":
                request_IP = header_value

            # Check if the header is the token header.
            # This is the token used in the user's ShareX config, for toh.ru.
            elif header_key == "token":
                request_token = header_value

            # Check if the header is the User-Agent header.
            # This header essentially shows what application the request was sent from.
            # Since toh.ru only allows for ShareX to be used for uploads, that is what we check for.
            elif header_key == "User-Agent":
                request_UAgent = header_value

    # The user has SOMEHOW managed to not provide an IP. Cursed?
    if not request_IP:
        print(f"{Fore.RED}400{Fore.CYAN} - No IP provided? What?")
        return False

    # Select UserID and username from DB based on the token they provided.
    SQL.execute("SELECT id, username FROM users WHERE token = %s", [request_token])
    resp = SQL.fetchone()

    if resp is None:
        print(f"{Fore.RED}400{Fore.CYAN} {request_IP} - Invalid token provided: {request_token}")
        return False

    userid = resp[0]
    username = resp[1]

    # Only submit ShareX for the time being.
    if not request_UAgent.startswith("ShareX"):
        print(f"{Fore.RED}400{Fore.CYAN} {request_IP} - Invalid HTTP Header (User-Agent): {request_UAgent}")
        return

    # Content headers include Content-Type and Content-Disposition.
    request_ContentDisposition, request_ContentType, extension_type = [None] * 3

    # Iterate through content headers to assign keys and values.
    for header in content_headers:
        # Split up the header into keys and values.
        current_header = header.split(": ")

        # Check if the header has been properly split into key and value.
        if len(current_header) > 1:
            # Assign the key and value for the header.
            header_key, header_value = current_header

            # Check if the header is the Content-Disposition header.
            # This header is made up of three segments; two of which (1, 2) are useful for us.
            # Index 1: name="files". If it is not this, they have an incorrect sharex config.
            # Index 2: This index contains the filename they are uploading, and more importantly, the extension.
            if header_key == "Content-Disposition":
                cd = header_value.split("; ")
                if len(cd) == 3:
                    if cd[1] != 'name="files[]"':
                        return False # They did not send files[]?
                    extension_type = cd[2].split(".")[-1].replace('"', "")
                else:
                    return False # User sent an invalid Content-Disposition header.

            # Check if the header is the Content-Type header.
            # At the moment, we only check that this header exists.
            elif header_key == "Content-Type":
                request_ContentType = header_value

    # Extension type is not allowed.
    if extension_type in UNSUPPORTED_FILETYPES:
        return False

    # One of the required headers was not recieved.
    if request_ContentType is None or request_IP is None or request_UAgent is None or request_token is None:
        print(f"{Fore.RED}400{Fore.CYAN} | {request_IP} - A required header was not recieved.")
        return False

    # Passed checks! Generate filename and save the png/serve the filename back.
    filename = generate_filename() + "." + extension_type

    # Write to file
    f = open(f'{SAVE_LOCATION}{filename}', 'wb+')
    f.write(body)
    f.close()

    # Insert into uploads.
    SQL.execute("INSERT INTO uploads (id, user, filename, filesize, time) VALUES (NULL, %s, %s, %s, %s)", [userid, filename, len(data), time.time()])

    print(f"{Fore.GREEN}200{Fore.CYAN} | {username} - {filename}")

    # Return the filename with extension.
    return filename


# Initialize our socket and begin the listener.
print(f"{Fore.CYAN}\nBooting up tohru.")

# Create the socket file.
sock.bind(SOCKET_LOCATION)

# Since the socket has been removed, we have to give it's privileges back.
os.chmod(SOCKET_LOCATION, 0o777)

# Begin listening for requests.
# Param is the amount of queued connections.
sock.listen(2)

print(f"{Fore.CYAN}Waiting for requests..\n")

# Iterate through connections indefinitely.
while True:
    # Set our niceness of the program to 10.
    # Tohru is not very intensive CPU-wise whatsoever.
    # It's also very unimportant to the other things running on our machine.
    print("how often does this run test", int(time.time()))
    psutil.Process(os.getpid()).nice(10)

    # Accept incoming connection.
    conn, addr = sock.accept()
    with conn:
        while True:
            # We have a connection.
            # This has some intensity, bring up the niceness level again.
            # NOTE: This will only work if we're running on root!
            # This is not advised, but optimal in the situation of the developer.
            os.nice(-5)

            data = bytes()
            i = 0
            print("assigned empty bytes thing")
            while True: # TODO: ShareX delimiter? Unsure if it exists.
                print("running! - ", i)
                addition = conn.recv(1024)
                print(addition)
                if not addition:
                    print("braek")
                    break
                print("made it further than expected!")

                data += addition
                i += 1
                print(data)
            print(data)

            # The user has not specified much data at all.
            # They are almost definitely visiting from the HTML page (/api/upload).
            if len(data) < 800:
                conn.send(b"No?")
                conn.close()
                break

            # Handle the request, and retrieve the file name w/ extension back.
            file = handle_request(data)

            # An exception was raised while handling the request.
            # Send back a 400 Bad Request response, and close the connection.
            if not file:
                conn.send(b"HTTP/1.1 400 Bad Request")
                conn.send(b"\n")
                conn.send(b'Bad request, incorrect parameters.')
                conn.close()
                break

            # We've successfully saved the image and all data was correct. Prepare to send back 200.
            # Set the response body to a successful request, and return required params.
            _response_body = {
                "success": "true",
                "files": [
                    {
                        "name": file,
                        "size":"4", # ?
                        "url":"https://toh.ru/uploads/" + file
                    }]
                }

            # JSONify the response body.
            response_body = json.dumps(_response_body)

            # Set the response headers.
            response_headers = {
                'Content-Type': 'text/html; encoding=utf-8',
                'Content-Length': len(file) + len(response_body),
                'Connection': 'close',
            }

            # Combine the response headers.
            response_headers_raw = "".join("%s: %s\n" % (k, v) for k, v in response_headers.items())

            # Send the HTTP status 200 OK.
            conn.send(b"HTTP/1.1 200 OK")

            # Send the response headers.
            conn.send(response_headers_raw.encode())

            # Send a newline so we separate headers from the body.
            conn.send(b"\n")

            # Send the response body.
            conn.send(response_body.encode())

            # Finally, close the connection and break the loop.
            conn.close()
            break