#!/usr/bin/env python3
import requests, urllib, os
from bs4 import BeautifulSoup
import zipfile
import time
import concurrent.futures
import io
from PIL import Image
import argparse
import queue
import threading

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)



p = argparse.ArgumentParser()
p.add_argument('userName', default='slaveryartwork')
p.add_argument('--num', type=int, default=1)
p.add_argument('--verbose', '-v', action='count', default=0)
p.add_argument('--nodl', action="store_true")
args = p.parse_args()
userName = args.userName
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))

dstPath = f'hfsite/{userName}'
os.makedirs(dstPath, exist_ok=True)
baseUrl = 'https://hentai-foundry.com'
session = requests.Session()
session.get('https://hentai-foundry.com')
res = session.get('https://www.hentai-foundry.com/?enterAgree=1&size=1000')
filterData = {
    'YII_CSRF_TOKEN': urllib.parse.unquote(session.cookies['YII_CSRF_TOKEN']).split('"')[1],
    'rating_nudity': '3',
    'rating_violence': '3',
    'rating_profanity': '3',
    'rating_racism': '3',
    'rating_sex': '3',
    'rating_spoilers': '3',
    'rating_yaoi': '1',
    'rating_yuri': '1',
    'rating_teen': '1',
    'rating_guro': '1',
    'rating_furry': '1',
    'rating_beast': '1',
    'rating_male': '1',
    'rating_female': '1',
    'rating_futa': '1',
    'rating_other': '1',
    'rating_scat': '1',
    'rating_incest': '1',
    'rating_rape': '1',
    'filter_media': 'A',
    'filter_order': 'date_old',
    'filter_type': '0'
}
session.post('https://www.hentai-foundry.com/site/filters', data=filterData)
imgNum = 1
nextUrl = f'https://www.hentai-foundry.com/pictures/user/{userName}/page/{args.num}'

def fetch(link, session: requests.Session):
    imgPage = session.get(baseUrl + '/' + link.get('href'))
    imgSoup = BeautifulSoup(imgPage.text, 'html.parser')
    tagImg = imgSoup.find(name='img', attrs={'class': 'center'})
    imgPath = tagImg.get('src')
    
    try:
        imgPath = 'https:' + tagImg.get('onclick').split('\'')[1]
    except:
        pass
    if not imgPath.startswith('http'):
        imgPath = 'http://' + imgPath
    imgPath = imgPath.replace('////', '//')
    for i in range(5):
        try:
            with session.get(imgPath, headers={'User-Agent': 'Mozilla/5.0', 'referer': 'https://readmanganato.com/'}) as response:
                response.raise_for_status()
                with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                    with Image.open(image_bytes) as img:
                        format = {}.get(img.format.lower(), img.format)
                        img.save(img_dst, format=format, quality=20, optimize=True)
                        return (format, img_dst.getvalue())
        except Exception as err:
            logger.error(err)
            time.sleep(2)

writeQueue = queue.Queue(maxsize=8)

Finished = "Work is finished! Close now"

def writeToCbr():
    imgNum = 1
    with open(f'hfsite/{userName}.cbr', 'wb') as zipdst:
        with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
            while True:
                print(f"writing {imgNum}")
                task = writeQueue.get()
                if task == Finished:
                    writeQueue.task_done()
                    return
                format, content = task.result()
                dstFile.writestr(f'{imgNum:03d}.{format}', content)
                imgNum += 1
                writeQueue.task_done()
threading.Thread(target=writeToCbr).start()
    
with concurrent.futures.ThreadPoolExecutor() as executor:    
    while nextUrl is not None:
        page = session.get(nextUrl)
        soup = BeautifulSoup(page.text, 'html.parser')
        for link in soup.findAll(name='a', attrs={"class":"thumbLink"}):
            if args.nodl:
                continue
            writeQueue.put(executor.submit(fetch, link, session))
            
        nextSoup = soup.find(name='a', string='Next >')
        if nextSoup and nextSoup != nextUrl and nextUrl != baseUrl + "/" + nextSoup.get('href'):
            nextUrl = baseUrl + '/' + nextSoup.get('href')
        else:
            nextUrl = None
writeQueue.put(Finished)
print("writeQ join")
writeQueue.join()