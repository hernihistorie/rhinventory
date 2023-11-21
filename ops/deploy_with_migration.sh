#!/bin/bash
ssh -t retroherna.org "\
    cd /var/www/rhinventory && \
    sudo -u flask git pull && \
    sudo -u flask poetry run alembic upgrade head && \
    sudo systemctl restart www_rhinventory \
"
echo "https://inventory.retroherna.org"