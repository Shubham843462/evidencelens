"""Generate three ORIGINAL, clearly synthetic instructional clips for UI testing.
These are NOT HoloAssist videos and must never be reported as experimental data.
Usage: python scripts/generate_demo_data.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SIZE=(960,540)
FPS=8
DURATION=12
CASES=["case_01","case_02","case_03"]


def font(size,bold=False):
    paths=(["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"] if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"])
    for path in paths:
        try: return ImageFont.truetype(path,size)
        except OSError: pass
    return ImageFont.load_default()
F12=font(23)
F10=font(18)
F20=font(34,True)

def pill(d,x,y,s,fill):
    bounds=d.textbbox((0,0),s,font=F10)
    w=bounds[2]+26
    d.rounded_rectangle((x,y,x+w,y+34),radius=16, fill=fill)
    d.text((x+13,y+7),s,font=F10,fill="white")

def draw(t,which):
    im=Image.new('RGB',SIZE,(10,19,31))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((46,38,915,493),radius=26,fill=(26,42,56),outline=(75,104,116),width=3)
    d.text((70,57),"SYNTHETIC DEMO / NOT HOLOASSIST",font=F10,fill=(143,211,202))
    d.text((70,98),["Board assembly — hole selection","Bracket installation — orientation","Obstructed view — uncertain evidence"][which],font=F20,fill="white")
    d.rounded_rectangle((105,174,842,418),radius=20,fill=(216,196,158),outline=(158,139,110),width=4)
    d.text((115,438),f"TIME  {int(t):02d}s  /  CLIP ENDS AT DECISION CUTOFF",font=F10,fill=(196,207,213))
    if which==0:
        # Board with clear A and B positions. Screw approaches the wrong A position.
        for x,label in [(315,'A'),(610,'B')]:
            d.ellipse((x-30,280,x+30,340),fill=(85,83,83),outline=(80,75,65),width=2)
            d.ellipse((x-19,291,x+19,329),fill=(29,47,53))
            d.text((x-11,244),f"{label}",font=F12,fill=(22,34,35))
        d.line((615,200,615,250), fill=(26,109,84), width=9)
        d.polygon([(598,238),(632,238),(615,261)],fill=(26,109,84))
        d.text((660,207),"Target: B",font=F12,fill=(24,85,69))
        # screw initially held above board and then moves toward A
        y=205+min(1,max(0,(t-3)/5))*110
        d.rounded_rectangle((298,y-46,332,y+12),radius=7,fill=(103,114,121),outline=(44,51,58),width=3)
        d.line((305,y-32,325,y-32),fill=(30,41,48),width=4)
        if t>8: pill(d,110,370,"Screw visibly at A; type cannot be inferred",(117,75,38))
    elif which==1:
        d.text((145,202),"Guide mark: arrow should point RIGHT",font=F12,fill=(31,75,66))
        d.line((240,254,570,254),fill=(24,105,82),width=13)
        d.polygon([(570,232),(625,254),(570,276)],fill=(24,105,82))
        d.rounded_rectangle((370,300,570,387),radius=12,fill=(71,94,104),outline=(33,40,49),width=4)
        if t<5:
            d.polygon([(410,345),(470,311),(470,330),(530,330),(530,360),(470,360),(470,380)],fill=(230,235,234))
        else:
            d.polygon([(530,345),(470,311),(470,330),(410,330),(410,360),(470,360),(470,380)],fill=(230,235,234))
        pill(d,110,370,"Orientation changes after 5s",(30,88,104))
    else:
        d.rounded_rectangle((302,245,630,371),radius=12,fill=(71,94,104))
        d.ellipse((415,280,465,330),fill=(125,130,140))
        d.rounded_rectangle((260,206,716,419),radius=30,fill=(34,42,53))
        d.text((355,310),"OBJECT OCCLUDED",font=F20,fill=(208,212,216))
        pill(d,110,370,"Cannot inspect the component reliably",(103,61,82))
    # progress
    d.rounded_rectangle((75,475,875,484),radius=4,fill=(71,81,92))
    d.rounded_rectangle((75,475,75+int(800*t/DURATION),484),radius=4,fill=(39,190,160))
    return im

def main():
    for i,case in enumerate(CASES):
        out=ROOT/'media'/'clips'/f'{case}.mp4'
        out.parent.mkdir(parents=True, exist_ok=True)
        e_dir=ROOT/'media'/'frames'/case
        e_dir.mkdir(parents=True, exist_ok=True)
        writer=cv2.VideoWriter(str(out),cv2.VideoWriter_fourcc(*'mp4v'),FPS,SIZE)
        if not writer.isOpened(): raise RuntimeError(f'VideoWriter failed: {out}')
        for n in range(FPS*DURATION):
            image=draw(n/FPS,i)
            writer.write(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR))
        writer.release()
        for id,t in [('E01',2),('E02',6),('E03',10)]:
            draw(t,i).save(e_dir/f'{id}.jpg',quality=92)
        print(out,out.stat().st_size)

if __name__=='__main__': main()
