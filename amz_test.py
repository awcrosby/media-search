#!/usr/bin/env python
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException)

def main():
    driver = webdriver.PhantomJS(service_log_path='log/phantomjs.log')
    driver.set_window_size(1920, 1080)
    driver.get('https://www.amazon.com/Cold-Mountain-Jude-Law/dp/B006T9Y278')
    print('testing')
    driver.save_screenshot('static/screenshot.png')

if __name__ == "__main__":
    main()
