# media-search

Project to create a watchlist of movies and tv shows, allows search for media and displays streaming sources. Watchlist media can be filtered on the front end.

## Setting up the project

Create an Ubuntu 16.04 box with an `ubuntu` user with sudo privileges

Local - set the `ansible_ssh_host` variable in the `inventory` file
```
$ cd media-search/config/
$ vim inventory
```

Local - allow ssh to store key for ansible to use
```
$ ssh-agent bash
$ ssh-add /path/to/private/key
```

Local - test connection, then use ansible to configure the remote Ubuntu box
```
$ ansible myhost -i inventory -m shell -a "pwd"
$ ansible-playbook -i inventory site.yml --ask-become-pass
```

Remote - copy config and creds, and edit to change secret key and add credentials, then reboot
```
$ cp ~/media-search/config/config.py ~/media-search/config.py
$ cp ~/media-search/config/creds.json ~/media-search/creds.json
$ sudo reboot
```

Remote - follow [Let's Encrypt](https://letsencrypt.org/getting-started/) instructions

## Technical

### Stack
Linux, Nginx/Gunicorn, MongoDB, Python/Flask

### Additional Details
* Webserver + framework: Nginx/Gunicorn, Python/Flask
* Database: MongoDB
* DevOps: AWS, Ansible, ufw, fail2ban
* Other tools: flash messaging, wtforms, jinja, logging, REST API
* Dev Environment: Ubuntu, vim/tmux, github
* JavaScript framework: VueJS
* UI Presentation: Bootstrap, some custom CSS
