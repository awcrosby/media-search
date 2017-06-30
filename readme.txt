This is a demo project that searches movies and tv shows via themoviedb api,
and displays streaming sources based on cached data. Data is rich but outdated,
therefore for demonstation purposes only. Also supports creating an account
for a personalized watchlist.

# -----System Pieces-----
# Hosting: Digital Ocean, ubuntu
# Networking: ufw firewall port access, and iptables port redirect
# Application: site to resolve media query and display data from db or api
# Webframework: flask with jinja templates
# Dev Environment: python2.7, git, vim, tmux, virtualenv, mobaxterm ssh
# APIs: Guidebox
# Database: mongodb
# Script: daily crontab run python script to write api updates to db
# UI: bootstrap css/js framework, flash messaging, wtforms
# Logging: python built-in logging for flaskapp and db_update
