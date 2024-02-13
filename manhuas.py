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

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--start', type=int, default=0)
p.add_argument('--end', type=int, default=4096)
p.add_argument('--verbose', '-v', action='count', default=0)
p.add_argument('--volume', type=int, default=1)
args = p.parse_args()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))


pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' - MANHUAUS.COM', '')
try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
Finished = "This task is finished. No, really."

def fetchImage(imgUrl):
    logger.debug(f'fetchImage {imgUrl}')
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Accept': 'image/avif,image/webp,*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://manhuaus.com/',
    }
    
    for _ in range(5):
        response = requests.get(imgUrl, headers=headers)
        response.raise_for_status()
        try:
            with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                with Image.open(image_bytes) as img:
                    format = {'jpg': 'JPEG', 'webp': 'JPEG'}.get(img.format.lower(), img.format)
                    img.save(img_dst, format=format, quality=20, optimize=True)
                    return (format, img_dst.getvalue())
        except Exception as err:
            logger.error(f'fetchImage({imgUrl} failed)')
            traceback.print_exception(err)
            logger.error(err)
            time.sleep(2)
    raise Exception(f"Failed to fetch {imgUrl}")
        

def writeToCbr(writeQueue, path):
    logger.debug(f'starting {path})')
    with open(path, 'wb') as zipdst:
        with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
            imgNum = 1
            while True:
                task = writeQueue.get()
                if task == Finished:
                    writeQueue.task_done()
                    logger.debug(f'finished {path})')
                    return
                try:
                    format, content = task.result()
                    logger.debug(f"writing image {zipdst}::{imgNum}")
                    dstFile.writestr(f'{imgNum:03d}.{format}', content)
                    imgNum += 1
                except Exception as err:
                    logger.error(err)
                writeQueue.task_done()

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as downloadExecutor:
    def downloadVolume(chunks, fName):
        writeQueue = queue.Queue(maxsize=8)
        threading.Thread(target=writeToCbr, args=(writeQueue, os.path.join(title, fName),)).start()
        for url in chunks:
            with requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
                parse = BeautifulSoup(pageDump.text, 'html.parser')
                siw = parse.find('div', {'class':'reading-content'})
                for img in siw.find_all('img'):
                    writeQueue.put(downloadExecutor.submit(fetchImage, (img.get('data-src') or img.get('src')).strip()))
        writeQueue.put(Finished)
            
    def chunk(arr, chunksize):
        for a in range(0, len(arr), chunksize):
            yield arr[a:a+chunksize]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        if args.volume > 1:
            for volNum, volChunk in enumerate(chunk([li.a.get('href') for li in parse.find('ul', {'class': 'version-chap'}).find_all('li')[::-1][args.start:args.end+1]], args.volume), start=args.start):
                executor.submit(downloadVolume, volChunk, f'volume_{volNum:03d}.cbr')
        else:
            for volNum, item in enumerate([li for li in parse.find('ul', {'class': 'version-chap'}).find_all('li')[::-1][args.start:args.end+1]], start=args.start):
                executor.submit(downloadVolume, [item.a.get('href')], f'chapter_{volNum:03d} - {item.a.text.strip()}.cbr')
