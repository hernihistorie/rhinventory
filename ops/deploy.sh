#!/bin/bash
ssh -t retroherna.org "cd /var/www/rhinventory && git pull && sudo systemctl restart www_rhinventory"