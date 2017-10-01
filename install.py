from distutils.core import setup
import os
import platform
import py2app
import sys

install_path = os.environ["HOME"] + '/Library/Mail/Bundles'
mail_path = '/Applications/Mail.app/Contents/Info'

command = 'defaults read %s CFBundleShortVersionString' % mail_path
if tuple(map(int, os.popen(command).read().strip().split('.'))) < (10, 0):
    sys.stderr.write("MailWrap requires Apple Mail 10.0 or later\n")
    sys.exit(1)

command = 'defaults read %s PluginCompatibilityUUID' % mail_path
compatibility_uuids = [ os.popen(command).read().strip() ]
version = platform.mac_ver()[0]

sys.argv[1:] = ['py2app'] + sys.argv[1:]
sys.stdout = open(os.devnull, 'w')
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))
setup(
    name = 'MailWrap',
    plugin = ['MailWrap.py'],
    options = {
        'py2app': {
            'dist_dir': install_path,
            'extension': '.mailbundle',
            'plist': {
                'CFBundleIdentifier': 'uk.me.cdw.MailWrap',
                'CFBundleVersion': '1.0',
                'NSHumanReadableCopyright':
                    'Copyright (C) 2017 Chris Webb <chris@arachsys.com>',
                'Supported%sPluginCompatibilityUUIDs' % version:
                    compatibility_uuids
            },
            'semi_standalone': True
        }
    },
    setup_requires = ['py2app']
)
sys.stdout.close()
sys.stdout = sys.__stdout__
print 'Installed compatible MailWrap.mailbundle in %s' % install_path

os.system('defaults write com.apple.mail EnableBundles -bool true')
os.system('rm -f -r ~/Library/Mail/Bundles\\ \\(Disabled\\)/MailWrap.*')
os.system('rmdir ~/Library/Mail/Bundles\\ \\(Disabled\\) 2>/dev/null')

print 'Enabled Apple Mail plugin bundles'
