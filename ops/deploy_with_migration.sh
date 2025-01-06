#!/bin/bash
# TODO merge this into deploy.sh with a CLI argument
echo "retroherna.org: "
ssh -t retroherna.org "\
    cd /var/www/rhinventory && \
    sudo -u flask git pull && \
    sudo -u flask poetry install && \
    sudo -u flask poetry run alembic upgrade head && \
    sudo systemctl restart www_rhinventory && \
    sudo systemctl restart www_rhinventory_api \
"
echo "https://inventory.herniarchiv.cz/"