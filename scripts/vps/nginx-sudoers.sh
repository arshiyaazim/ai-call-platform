#!/bin/bash
# Allow azim to run nginx commands without password (for rolling deploys)
echo 'azim ALL=(root) NOPASSWD: /usr/sbin/nginx -t, /usr/sbin/nginx -s reload' | sudo tee /etc/sudoers.d/azim-nginx > /dev/null
sudo chmod 440 /etc/sudoers.d/azim-nginx
sudo visudo -cf /etc/sudoers.d/azim-nginx && echo "SUDOERS_OK" || echo "SUDOERS_FAIL"
# Verify
sudo -n nginx -t 2>&1 && echo "NGINX_SUDO_OK" || echo "NGINX_SUDO_FAIL"
