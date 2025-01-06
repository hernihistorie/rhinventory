#!/bin/bash
echo "retroherna.org: "
ssh -t retroherna.org "\
    cd /var/www/rhinventory && \
    sudo -u flask git pull && \
    sudo -u flask poetry install && \
    sudo systemctl restart www_rhinventory && \
    sudo systemctl restart www_rhinventory_api \
"
echo "https://inventory.herniarchiv.cz/"