# media-search

Project to create a watchlist of movies and tv shows, allows search for media and displays streaming sources. Watchlist media can be filtered on the front end.

## Setting up the project

Locally use ansible to configure a remote Ubuntu 16.04 box
```
$ ssh-agent bash
$ ssh-add /path/to/private/key
$ ansible-playbook -i inventory site.yml -e "githubpw=XXXXXXXXX"
```

On remote box copy config and creds, and edit to change secret key and add credentials
```
$ cp ~/media-search/config/config.py ~/media-search/config.py
$ cp ~/media-search/config/creds.json ~/media-search/creds.json
```

Follow [Let's Encrypt](https://letsencrypt.org/getting-started/) instructions

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
