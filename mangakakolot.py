#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import argparse
import os
import errno
import logging
import queue
import zipfile
import threading
import concurrent.futures
import io
import time
from PIL import Image
import traceback
from urllib.parse import urljoin
import re

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--pagenum', type=int, default=1)
p.add_argument('--start', type=int, default=0)
p.add_argument('--end', type=int, default=-1)
p.add_argument('--verbose', '-v', action='count', default=0)
p.add_argument('--vscode', action='store_true')
args = p.parse_args()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))

requestHeader = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Referer': 'https://mangakakalot.com/'
}

#GET /img/tab_33/04/77/92/vo999149/chapter_1/2-o.jpg HTTP/1.1
#Host: v13.mkklcdnv6tempv4.com
#User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0
#Accept: image/avif,image/webp,*/*
#Accept-Language: en-US,en;q=0.5
#Accept-Encoding: gzip, deflate, br


pd = requests.get(args.url, requestHeader)
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' Manga Online Free - Manganato', '').replace('Manga Online Free - Manganato', '')
title = re.sub("Read (.*) Manga on Mangakakalot *", "\\1", title)
try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
Finished = "This task is finished. No, really."



def fetchImage(imgUrl):
    logger.debug(f'fetchImage {imgUrl}')
    for _ in range(5):
        try:
            response = requests.get(imgUrl, headers=requestHeader)
            response.raise_for_status()
            with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                with Image.open(image_bytes) as img:
                    format = {'jpg': 'JPEG', 'webp': 'JPEG'}.get(img.format.lower(), img.format)
                    logger.debug(f'format {format}')
                    img.save(img_dst, format=format, quality=20, optimize=True)
                    return (format, img_dst.getvalue())
        except Exception as err:
            logger.error(f'fetchImage({imgUrl} failed)')
            traceback.print_exception(err)
            logger.error(err)
            time.sleep(2)
    raise Exception(f"Failed to fetch {imgUrl}")

def writeToCbr(writeQueue, path):
    logger.debug(f'writeToCbr(queue, {path})')
    with open(path, 'wb') as zipdst:
        with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
            imgNum = 1
            while True:
                task = writeQueue.get()
                if task == Finished:
                    writeQueue.task_done()
                    return
                try:
                    format, content = task.result()
                    logger.info(f"writing {imgNum}")
                    dstFile.writestr(f'{imgNum:03d}.{format}', content)
                    imgNum += 1
                except Exception as err:
                    logger.error(err)
                writeQueue.task_done()

with concurrent.futures.ThreadPoolExecutor(max_workers=1 if args.vscode else None) as downloadExecutor:
    def downloadChapter(url, num):
        try:
            logger.debug(f'downloadChapter({url}, {num})')
            writeQueue = queue.Queue(maxsize=8)
            threading.Thread(target=writeToCbr, args=(writeQueue, os.path.join(title, f'chapter_{num:03d}.cbr'),)).start()
            with requests.get(url, headers=requestHeader) as pageDump:
                parse = BeautifulSoup(pageDump.text, 'html.parser')
                siw = parse.find('div', {'class':'container-chapter-reader'})
                for img in siw.find_all('img'):
                    writeQueue.put(downloadExecutor.submit(fetchImage, (img.get('data-src') or img.get('src')).strip()))
                writeQueue.put(Finished)
        except Exception as err:
            logger.error(err)
            traceback.print_exception(err)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if args.vscode else None) as executor:
        aList = [urljoin(args.url, a.get('href')) for a in parse.find('div', {'class': 'chapter-list'}).findAll('a')[::-1]]
        if args.end > 0:
            aList = aList[args.start:args.end]
        else:
            aList = aList[args.start:]
        for num, chapterUrl in enumerate(aList, args.start):
            executor.submit(downloadChapter, chapterUrl, num)
