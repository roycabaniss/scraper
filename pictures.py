#!/usr/bin/env python3

from PIL import ImageDraw, Image, ImageFont
import math

def addTitle(image: Image, title: str, textColor=(0,0,0)) -> Image:
    titleHeight = int(image.height*0.05) # TODO - currently hardcoded to 5%
    backColor = tuple([int(sum(col)/len(col)) for col in zip(*[image.getpixel((x,0)) for x in range(image.width)])])
    lightenBackColor = tuple([int((255-x)/2+x) for x in backColor])
    newImg = Image.new('RGB', (image.width, image.height+titleHeight), lightenBackColor)
    newImg.paste(image, (0, titleHeight))
    font = ImageFont.truetype("FreeSerif.ttf", 16)
    box = (10, 10, image.width-10, titleHeight - 10)
    size = None
    font_size = 100
    while (size is None or size[0] > box[2] - box[0] or size[1] > box[3] - box[1]) and font_size > 0:
        font = ImageFont.truetype("FreeSerif.ttf", font_size)
        size = font.getsize(title)
        font_size -= 1
    
    ImageDraw.Draw(newImg).text((int((image.width-size[0])/2), int((titleHeight-size[1])/2)), title, textColor, font=font)
    return newImg

def addCaption(image: Image, text: str, textColor=(0,0,0)) -> Image:
    # The Caption height is slightly tricky. First, it can never exceed 20% of the original
    # image's height. Trim extra space, since if the font size is appreciably large it will
    # result in too large an area. 
    textLines = text.splitlines()
    captionHeight = int(image.height*0.2) # TODO - currently hardcoded to 5%
    font = ImageFont.truetype("FreeSerif.ttf", 16)
    box = (10, 10, image.width-10, captionHeight - 10)
    size = None
    font_size = 100
    minFontSize = 0
    maxFontSize = 100
    while minFontSize + 1 < maxFontSize:
        font_size = math.floor((minFontSize+maxFontSize)/2)
        #print('font size', font_size)
        font = ImageFont.truetype("FreeSerif.ttf", font_size)
        testTextLines = []
        for line in textLines:
            
            if font.getlength(line) > box[3]-box[1]:
                while len(line) > 0:
                    # Figure out how many characters to reach the end of the line
                    minEOL = 0
                    maxEOL = len(line)+1
                    while minEOL+1 < maxEOL:
                        testEOL = math.floor((minEOL + maxEOL) / 2)
                        if font.getlength(text[:testEOL]) > box[2]-box[0]:
                            maxEOL = testEOL
                        else:
                            minEOL = testEOL
                    
                    eol = minEOL
                    while eol < len(line) and line[eol] not in (' ', '-', '\t') and eol > 0:
                        eol -= 1
                    if eol == 0:  # If there's no place to break, just break as best you can
                        eol = minEOL
                    testTextLines.append(line[:eol].strip())
                    line = line[eol:].strip()
            else:
                testTextLines.append(line)
        # Now, newTextLines is the newly-breaked caption. We need to get the size of it!
        boxes = [font.getbbox(line) for line in testTextLines]
        testSize = (
            max([b[2] for b in boxes]),  #Width
            sum([b[3] for b in boxes]) + 20 #Height, including 10 top and bottom
        )
        if (testSize[0] > box[2] - box[0] or testSize[1] > box[3] - box[1]):
            maxFontSize = font_size
        else:
            size=testSize
            minFontSize = font_size
            newTextLines = testTextLines
    font_size = minFontSize
    if not size:
        size = testSize
    if not newTextLines:
        newTextLines = testTextLines
    backColor = tuple([int(sum(col)/len(col)) for col in zip(*[image.getpixel((x,image.height-1)) for x in range(image.width)])])
    lightenBackColor = tuple([int((255-x)/2+x) for x in backColor])
    newImg = Image.new('RGB', (image.width, image.height+size[1]), lightenBackColor)
    newImg.paste(image, (0, 0))
    yPos = image.height+10
    for line in newTextLines:
        ImageDraw.Draw(newImg).text((10, yPos), line, textColor, font=font)
        box = font.getbbox(line)
        yPos += box[3]
    return newImg
    
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('infile')
    parser.add_argument('outfile')
    parser.add_argument('title')
    captionBlock = '''Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.'''
    args = parser.parse_args()
    addCaption(addTitle(Image.open(args.infile), args.title), captionBlock).save(args.outfile)