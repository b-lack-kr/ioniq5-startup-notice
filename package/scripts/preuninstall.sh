#!/system/bin/sh
# NEMESIS stops the registered service before running this hook.
rm -f /data/local/tmp/neev-consent.session
echo 'Startup notice monitor removed; future automatic calls stopped.'
echo 'No inverse factory command is known or issued.'
exit 0
