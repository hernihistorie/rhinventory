#!/bin/bash
ssh -t retroherna.org "cd /var/www/rhinventory && sudo -u flask git pull && sudo systemctl restart www_rhinventory"