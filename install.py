from setuptools import setup
import os
import platform
import shutil
import sys

try:
    import py2app, py2app.build_app
    import objc, AppKit
except:
    sys.stderr.write('MailWrap requires the py2app and pyobjc modules\n')
    sys.stderr.write('Try: pip3 install --user py2app pyobjc\n')
    sys.exit(1)

def copystat(src, dst, **kw):
    st = os.stat(src, **kw)
    mode = shutil.stat.S_IMODE(st.st_mode)
    os.utime(dst, (st.st_atime, st.st_mtime))
    os.chmod(dst, mode, **kw)
shutil.copystat = copystat

install_path = os.environ['HOME'] + '/Library/Mail/Bundles'
if os.path.exists('/System/Applications/Mail.app'):
    mail_path = '/System/Applications/Mail.app/Contents/Info'
else:
    mail_path = '/Applications/Mail.app/Contents/Info'

command = 'defaults read %s CFBundleShortVersionString' % mail_path
if tuple(map(int, os.popen(command).read().strip().split('.'))) < (10, 0):
    sys.stderr.write('MailWrap requires Apple Mail 10.0 or later\n')
    sys.exit(1)

command = 'defaults read %s PluginCompatibilityUUID' % mail_path
compatibility_uuids = [ os.popen(command).read().strip() ]
version = '.'.join(platform.mac_ver()[0].split('.')[:2])

if version == '10.16':
    sys.stderr.write('Please run with SYSTEM_VERSION_COMPAT=0\n')
    sys.exit(1)

sys.argv[1:] = ['py2app'] + sys.argv[1:]
sys.stdout = open(os.devnull, 'w')
if os.path.dirname(__file__):
    os.chdir(os.path.dirname(__file__))
py2app.build_app.py2app.may_log_missing = lambda *args: False
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
            'semi_standalone': True,
            'strip': False
        }
    },
    setup_requires = ['py2app']
)
sys.stdout.close()
sys.stdout = sys.__stdout__
print('Installed compatible MailWrap.mailbundle in %s' % install_path)

os.system('defaults write com.apple.mail EnableBundles -bool true')
os.system('rm -f -r ~/Library/Mail/Bundles\\ \\(Disabled\\)/MailWrap.*')
os.system('rmdir ~/Library/Mail/Bundles\\ \\(Disabled\\) 2>/dev/null')
print('Enabled Apple Mail plugin bundles')
