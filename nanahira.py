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
SOCKET_LOCATION = "/tmp/nanahira.sock"

# Remove socket if it exists.
if os.path.exists(SOCKET_LOCATION):
    os.remove(SOCKET_LOCATION)

# Initialize socket.
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

# Maximum amount of data we will accept.
MAX_FILESIZE = 1024 # MB

# Array of supported filetypes.
UNSUPPORTED_FILETYPES = ["virus"] # xd

# Length of randomly generated filenames.
FILENAME_LENGTH = 12

# Location to save uploads to.
SAVE_LOCATION = "/home/cmyui/nanahira/uploads/"

# Generate a random FILENAME_LENGTH string.
def generate_filename(length=FILENAME_LENGTH): # Generate using all lowercase, uppercase, and digits.
    return "".join(random.choice(string.ascii_letters + string.digits) for i in range(length))

# Initialize our socket and begin the listener.
print(f"{Fore.CYAN}\nBooting up nanahira.")

# Create the socket file.
sock.bind(SOCKET_LOCATION)

# Since the socket has been removed, we have to give it's privileges back.
os.chmod(SOCKET_LOCATION, 0o777)

# Begin listening for requests.
# Param is the amount of queued connections.
sock.listen(2)

print(f"{Fore.CYAN}Waiting for requests..\n")\

# Every possible HTTP code!
HTTP_CODES = {
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing",
    #2xx: Success
    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    207: "Multi-Status",
    208: "Already Reported",
    226: "IM Used",
    #300x: Redirection
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    #4××: "Client Error"
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Payload Too Large",
    414: "Request-URI Too Long",
    415: "Unsupported Media Type",
    416: "Requested Range Not Satisfiable",
    417: "Expectation Failed",
    418: "I'm a teapot",
    421: "Misdirected Request",
    422: "Unprocessable Entity",
    423: "Locked",
    424: "Failed Dependency",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    444: "Connection Closed Without Response",
    451: "Unavailable For Legal Reasons",
    499: "Client Closed Request",
    #5××: "Server Error"
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
    506: "Variant Also Negotiates",
    507: "Insufficient Storage",
    508: "Loop Detected",
    510: "Not Extended",
    511: "Network Authentication Required",
    599: "Network Connect Timeout Error"
}

def HTTP_RESPOND(conn, HTTP_STATUS, user="", reason="Invalid request. Nanahira only supports ShareX!"):
    # Print error.
    print(f"{Fore.RED}{HTTP_STATUS}{Fore.CYAN} | {user}")

    # Grab the readable version of the HTTP status code.
    HTTP_STATUS_READABLE = HTTP_CODES.get(HTTP_STATUS)

    if reason:
        reason = f"Nanahira Response: {reason}".encode()
    else:
        reason = b"Great job! You have potential!"

    # Set the response headers.
    response_headers = {
        'Content-Type': 'text/html; encoding=utf-8',
        'Content-Length': len(reason),
        'Connection': 'close',
    }

    # Combine the response headers.
    response_headers_raw = "".join("%s: %s\n" % (k, v) for k, v in response_headers.items())

    # Send back status code / readable.
    conn.send(f"HTTP/1.1 {HTTP_STATUS} {HTTP_STATUS_READABLE}".encode())

    # Send the response headers.
    conn.send(response_headers_raw.encode())

    # Separate headers from body
    conn.send(b"\n")

    conn.send(reason)

    conn.close()
    return


# Iterate through connections indefinitely.
while True:
    # Set our niceness of the program to 10.
    # Nanahira is not very intensive CPU-wise whatsoever.
    # It's also very unimportant to the other things running on our machine.
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

            # Overshoot on the headers, and give the extra data back to the body.
            _full_headers = conn.recv(750)

            # Somehow the request is not even 750 bytes.
            # This is very wrong and should never happen.
            if len(_full_headers) != 750:
                HTTP_RESPOND(conn, 418)
                break

            full_headers = _full_headers.split(b"\r\n\r\n")

            # Could not be split into 3 parts.
            # This COULD be headers being too long, but very unlikely?
            if len(full_headers) != 3:
                HTTP_RESPOND(conn, 418)
                break

            headers = full_headers[0].decode().split("\r\n")
            content_headers = full_headers[1].decode().split("\r\n")

            delimiter = content_headers[0].encode()

            data = full_headers[2]

            """ BEGIN HEADER CHECKS BEFORE EVEN GETTING THE DATA! """

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
                    # This is the token used in the user's ShareX config, for nanahira.life.
                    elif header_key == "token":
                        request_token = header_value

                    # Check if the header is the User-Agent header.
                    # This header essentially shows what application the request was sent from.
                    # Since nanahira.life only allows for ShareX to be used for uploads, that is what we check for.
                    elif header_key == "User-Agent":
                        request_UAgent = header_value

            # The user has SOMEHOW managed to not provide an IP. Cursed?
            if not request_IP:
                HTTP_RESPOND(conn, 405, request_IP)
                break

            # Select UserID and username from DB based on the token they provided.
            SQL.execute("SELECT id, username FROM users WHERE token = %s", [request_token])
            resp = SQL.fetchone()

            if resp is None:
                HTTP_RESPOND(conn, 400, request_IP, reason="Invalid token.")
                break

            userid = resp[0]
            username = resp[1]

            # Only submit ShareX for the time being.
            if not request_UAgent.startswith("ShareX"):
                HTTP_RESPOND(conn, 405, username)
                break

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
                                HTTP_RESPOND(conn, 400, username)
                                break
                            extension_type = cd[2].split(".")[-1].replace('"', "")
                        else:
                            HTTP_RESPOND(conn, 400, username)
                            break

                    # Check if the header is the Content-Type header.
                    # At the moment, we only check that this header exists.
                    elif header_key == "Content-Type":
                        request_ContentType = header_value

            # Extension type is not allowed.
            if extension_type in UNSUPPORTED_FILETYPES:
                HTTP_RESPOND(conn, 400, username, reason=f"Unsupported filetype: {extension_type}.")
                break

            # One of the required headers was not recieved.
            if request_ContentType is None or request_IP is None or request_UAgent is None or request_token is None:
                HTTP_RESPOND(conn, 405, username)
                break


            """ HEADER CHECKS COMPLETE! LETS CHECK THE DATA! """


            # Take a small sample of the data so we can tell if we can just get it in one scoop.
            # This happens more frequently than you'd think, even small images can be picked up this way.
            # It also gives some protection against CURSED shit.
            primary = conn.recv(1024)

            # Add primary to our data.
            data += primary

            if len(primary) == 1024 and delimiter not in primary:
                for iteration in range (0, (MAX_FILESIZE // 1024) * 1000): # Cap it out at our MAX_FILESIZE amt
                    data += conn.recv(1024)

                    # I'm still 99% sure this can theoretically break and inf loop crash!
                    if delimiter in data: break

            # 2x2 black pixels with shareX = 167 len.
            # If they specify less than this, literally what are they doing.
            if len(data) < 167:
                HTTP_RESPOND(conn, 403, username, reason=f"Not enough data provided - {len(data)}.")
                break

            # Passed checks! Generate filename and save the png/serve the filename back.
            filename = generate_filename() + "." + extension_type

            # Write to file
            f = open(SAVE_LOCATION + filename, 'wb+')
            f.write(data)
            f.close()

            # Insert into uploads.
            SQL.execute("INSERT INTO uploads (id, user, filename, filesize, time) VALUES (NULL, %s, %s, %s, %s)", [userid, filename, len(data), time.time()])

            # Print success.
            print(f"{Fore.GREEN}200{Fore.CYAN} | {username} - {filename}")

            # We've successfully saved the image and all data was correct. Prepare to send back 200.
            # Set the response body to a successful request, and return required params.
            _response_body = {
                "success": "true",
                "files": [
                    {
                        "name": filename,
                        "size":"4", # ?
                        "url":"https://nanahira.life/uploads/" + filename
                    }]
                }

            # JSONify the response body.
            response_body = json.dumps(_response_body)

            # Set the response headers.
            response_headers = {
                'Content-Type': 'text/html; encoding=utf-8',
                'Content-Length': len(filename) + len(response_body),
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