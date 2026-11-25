"""Compose an album's delivered GIFs into a synchronized promotional overview."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageSequence

def compose(source, dest, font_path):
    paths=sorted((source/'main').glob('*.gif'))
    if len(paths)!=16:
        raise ValueError('Expected sixteen delivered GIFs')
    animations=[]
    for path in paths:
        with Image.open(path) as im:
            frames=[f.convert('RGBA') for f in ImageSequence.Iterator(im)]
            durations=[]
            for i in range(im.n_frames):
                im.seek(i);durations.append(im.info.get('duration',120))
        if len(frames)!=9:
            raise ValueError('Expected nine frames per GIF')
        animations.append((frames,durations))
    if any(a[1]!=animations[0][1] for a in animations):
        raise ValueError('Synchronized overview requires matching frame durations')
    dest.mkdir(parents=True,exist_ok=True)
    title=ImageFont.truetype(str(font_path),42)
    small=ImageFont.truetype(str(font_path),20)
    output=[]
    for step in range(9):
        canvas=Image.new('RGB',(1000,1160),'#f7f2e9')
        d=ImageDraw.Draw(canvas)
        d.text((32,24),'表情工坊 · Sticker Studio',font=title,fill='#24251f')
        d.text((34,87),'三花猫的日常营业  /  16 张动态表情 · 9 帧循环',font=small,fill='#68685d')
        for index,(frames,_) in enumerate(animations):
            x=20+(index%4)*245;y=137+(index//4)*245
            d.rounded_rectangle((x,y,x+234,y+234),radius=16,fill='#ffffff')
            f=frames[step].resize((226,226),Image.Resampling.LANCZOS)
            canvas.paste(f,(x+4,y+4),f)
        d.text((32,1128),'Codex 内置生图 + 本地合成  /  github.com/homxuwang/sticker-studio-skill',font=small,fill='#68685d')
        output.append(canvas)
    output[4].save(dest/'calico-overview.png')
    palette=output[4].quantize(colors=256,method=Image.Quantize.MEDIANCUT)
    encoded=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in output]
    encoded[0].save(dest/'calico-overview.gif',save_all=True,append_images=encoded[1:],duration=animations[0][1],loop=0,disposal=2,optimize=False)
    cover=Image.new('RGB',(1200,675),'#f7f2e9');d=ImageDraw.Draw(cover)
    d.text((56,74),'表情工坊',font=ImageFont.truetype(str(font_path),68),fill='#24251f')
    d.text((60,170),'Sticker Studio',font=ImageFont.truetype(str(font_path),34),fill='#68685d')
    for n,line in enumerate(('一个角色，做成一整套动态表情','16 张表情  /  九帧循环  /  透明 GIF','从动作配字到对齐、检查与打包')):
        d.text((60,290+n*58),line,font=ImageFont.truetype(str(font_path),27),fill='#24251f')
    with Image.open(source/'cover.png') as im:
        cat=im.convert('RGBA').resize((510,510),Image.Resampling.LANCZOS)
        cover.paste(cat,(665,80),cat)
    cover.save(dest/'cover.png')
    with Image.open(dest/'calico-overview.gif') as im:
        assert im.n_frames==9 and im.info.get('loop')==0
        assert len({f.convert('RGB').tobytes() for f in ImageSequence.Iterator(im)})==9

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--album',type=Path,required=True)
    p.add_argument('--dest',type=Path,required=True)
    p.add_argument('--font',type=Path,required=True,help='Font supporting Chinese, e.g. msyh.ttc or Noto Sans CJK')
    a=p.parse_args();compose(a.album,a.dest,a.font)
