import bencodepy
import sys

if len(sys.argv) != 2:
    print("Usage: python script.py <torrent_file>")
    sys.exit(1)

file_name=sys.argv[1]

try:
    with open(file_name,"rb") as torrentFile:
        fileContent=torrentFile.read()
except FileNotFoundError:
    print(f"Error: file {file_name} not found!")
    sys.exit(1)
except Exception as E:
    print(f"Error : {E}")
    sys.exit(1)

try:
    decodedDict = bencodepy.decode(fileContent)
except Exception as E:
    print(f"Error : {E}")
    sys.exit(1)

try:
    trackerURL = decodedDict[b'announce'].decode('utf-8')
except Exception as E:
    print(f"Error : {E}")
    sys.exit(1)

print(trackerURL)