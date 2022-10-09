#!/bin/env python3
import requests
from bs4 import BeautifulSoup
import base64
import time
import os
import errno
import argparse
from urllib.parse import urljoin

pageNum = 1

import argparse

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
args = p.parse_args()

pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.strip(' Manga Online Free - Manganato')

nextUrl = parse.find('ul', {'class': 'row-content-chapter'}).find_all('li')[-1].a.get('href')

try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
while nextUrl is not None:
    errCnt = 0
    try:
        with open(os.path.join(title, f'page{pageNum}.html'), "wb") as dstFile:
            dstFile.write('<html>\n<head><style>\nimg {width: 300px; margin-bottom: -5px;}\n</style></head><body>\n'.encode())
            print(nextUrl)
            with requests.get(nextUrl, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
                parse = BeautifulSoup(pageDump.text, 'html.parser')
                siw = parse.find('div', {'class':'container-chapter-reader'})
                for img in siw.findAll('img'):
                    imgPath = img.get('src')
                    srcPath = urljoin(nextUrl, imgPath)

                    print('img ', srcPath)
                    for i in range(5):
                        try:
                            with requests.get(srcPath, headers={'User-Agent': 'Mozilla/5.0', 'referer': 'https://readmanganato.com/'}) as response:
                                dstFile.write('<img src=\"data:image/jpg;base64,'.encode())
                                dstFile.write(base64.b64encode(response.content))
                                dstFile.write('\">\n<br/>\n'.encode())
                        except:
                            pass
                        else:
                            break
                next = parse.find(name='a', attrs={'class':'navi-change-chapter-btn-next'})
                if next:
                    dstFile.write('''
    <script>
    function checkKey(e) {
        e = e || window.event;
        if (e.keyCode == '39')
            document.getElementById('nextLink').click();
        else if (e.keyCode == '37)
            document.getElementById('prevLink').click();
    }
    document.onkeydown = checkKey;
    </script>
    '''.encode())
                    dstFile.write(f'<a id=\"nextLink\" href=\"page{pageNum+1}.html\">Next</a>\n<br/>\n'.encode())
                    nextUrl = urljoin(nextUrl, next.get('href'))
                else:
                    nextUrl = None
                if pageNum > 1:
                    dstFile.write(f'<a id=\"prevLink\" href=\"page{pageNum-1}.html\">Prev</a>\n<br/>\n'.encode())
            dstFile.write('</body>\n</html>\n'.encode())
            pageNum += 1
            print('New Page', pageNum)
            time.sleep(2)
    except Exception as err:
        errCnt += 1
        if errCnt > 5:
            print(err)
            exit(1)
    else:
        errCnt = 0
    
