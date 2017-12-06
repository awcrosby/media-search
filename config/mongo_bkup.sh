#!/bin/bash
mongodump -d MediaData -o ~/media-search/db_backups/"MediaData_bkup_$(date +"%Y%m%d-%H%M")"
