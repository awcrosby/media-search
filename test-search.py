temp_apikey = 'yh7JUQD5rcNN9VVzjp6ovcTna1581H'
moviequery =  'clueless' #need to triple encode this

##create guidebox api search url
apikey = temp_apikey
region = 'US'
baseapiurl = 'http://api-public.guidebox.com/v1.43/' + region + '/' + apikey
url = baseapiurl + '/search/movie/title/' + moviequery + '/exact'

print url
