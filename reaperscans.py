#!/bin/env python3
import requests
from bs4 import BeautifulSoup
import base64
import time
import os
import errno
import argparse
from urllib.parse import urljoin
import concurrent.futures
import re

import argparse

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--pagenum', type=int, default=1)
args = p.parse_args()

pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' - Reaper Scans', '')

firstLink = parse.find('a', text=re.compile('.*Read First.*'))

nextUrl = parse.find('a', text=re.compile('.*Read First.*')).get('href')

def fetchImage(url: str):
    print('Fetching image', url)
    for i in range(5):
        try:
            with requests.get(url) as response:
                return f'<img src=\"data:image/jpg;base64, {base64.b64encode(response.content).decode()}\">\n'
        except:
            pass

try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
while nextUrl is not None:
    errCnt = 0
    try:
        with open(os.path.join(title, f'page{args.pagenum:03d}.html'), "wb") as dstFile:
            dstFile.write('<html>\n<head><style>\nimg {width: 50vh; display: block; max-width: 100%; margin: auto;}\n</style></head><body>\n'.encode())
            print(nextUrl)
            with requests.get(nextUrl, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
                parse = BeautifulSoup(pageDump.text, 'html.parser')
                siw = parse.find('p', {'class':'py-4'})
                # We can use a with statement to ensure threads are cleaned up promptly
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    imgTasks = [executor.submit(fetchImage, urljoin(nextUrl, img.get('src'))) for img in siw.find_all('img')]
                    for task in imgTasks:
                        dstFile.write(task.result().encode())
                dstFile.write('''
<script>
function checkKey(e) {
    e = e || window.event;
    if (e.keyCode == '39')
        document.getElementById('nextLink').click();
    else if (e.keyCode == '37')
        document.getElementById('prevLink').click();
}
document.onkeydown = checkKey;
</script>
    '''.encode())
                nextList = [a for a in parse.find_all(name='a') if any(['Next' in c for c in a.contents])]
                if nextList:
                    next=nextList[0]
                    dstFile.write(f'<a id=\"nextLink\" href=\"page{(args.pagenum+1):03d}.html\">Next</a>\n<br/>\n'.encode())
                    nextUrl = urljoin(nextUrl, next.get('href'))
                else:
                    nextUrl = None
                if args.pagenum > 1:
                    dstFile.write(f'<a id=\"prevLink\" href=\"page{(args.pagenum-1):03d}.html\">Prev</a>\n<br/>\n'.encode())
            dstFile.write('</body>\n</html>\n'.encode())
            args.pagenum += 1
            print('New Page', args.pagenum)
            time.sleep(2)
    except Exception as err:
        errCnt += 1
        if errCnt > 5:
            print(err)
            exit(1)
    else:
        errCnt = 0
    
