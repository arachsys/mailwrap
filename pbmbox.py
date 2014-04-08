#!/usr/bin/python

from AppKit import NSPasteboard
import errno
import getopt
import re
import sys

try:
    opts, args = getopt.getopt(sys.argv[1:], "n", ["no-quote-from"])
    assert len(args) == 0
except:
    sys.stderr.write('''\
Usage: %s [-n]
Options:
  -n, --no-quote-from   disable mbox From_ quoting
''' % sys.argv[0])
    sys.exit(64)

quote_from = True
for opt, arg in opts:
    if opt in ("-n", "--no-quote-from"):
        quote_from = False

pasteboard = NSPasteboard.generalPasteboard()
if not pasteboard:
    sys.exit(1)

items = pasteboard.propertyListForType_('RFC822MessageDatasPboardType')
if not items:
    sys.exit(1)

for item in items:
    data = bytearray(item['message'])
    if quote_from:
        data = re.sub(r'\n(>*From )', r'\n>\1', data)
    try:
        sys.stdout.write(data)
        if data[-1] == ord('\n'):
            sys.stdout.write('\n')
        else:
            sys.stdout.write('\n\n')
    except IOError as error:
        if error.errno != errno.EPIPE:
            raise
