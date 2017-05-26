#!/usr/bin/env python
import json
import guidebox

''' print monthly api quota to command line '''

guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
guidebox.Quota.retrieve()
