"""Local-only nine-frame sticker preparation; no generation API calls."""
import argparse, csv, hashlib, json, re, shutil, zipfile
from pathlib import Path
from statistics import median
from PIL import Image, ImageSequence, ImageDraw, ImageChops
from pack_wechat import package_album, save_transparent_gif

def split_sheet(path):
    sheet = Image.open(path).convert('RGBA')
    w, h = sheet.size
    if abs(w-h)>1:
        raise ValueError('Expected a square 3x3 sheet; inspect layout or supply a corrected sheet')
    frames = []
    for row in range(3):
        for col in range(3):
            box = (round(col*w/3), round(row*h/3), round((col+1)*w/3), round((row+1)*h/3))
            f = sheet.crop(box)
            if f.size != (418, 418):
                f = f.resize((418, 418), Image.Resampling.LANCZOS)
            frames.append(f)
    return frames


def torso_center_x(frame):
    """Track the hip band, avoiding moving hands and the tilting head."""
    alpha=frame.getchannel('A')
    start=85
    box=alpha.crop((0,start,frame.width,frame.height)).point(lambda a:255 if a>=145 else 0).getbbox()
    if box is None:
        raise ValueError('No character pixels found for horizontal alignment')
    top,bottom=start+box[1],start+box[3]
    centers=[]
    for y in range(round(top+(bottom-top)*.80),round(top+(bottom-top)*.88)):
        xs=[x for x in range(frame.width) if alpha.getpixel((x,y))>=145]
        if len(xs)>25:
            centers.append((xs[0]+xs[-1])/2)
    if not centers:
        raise ValueError('No stable hip band found for horizontal alignment')
    return median(centers)


def stabilize_labels(frames, align="torso", anchors=None, label_mode="white_placard"):
    # Alpha threshold matches the existing GIF packer. Keep RGB unchanged.
    separated = []
    for f in frames:
        if label_mode == "none":
            separated.append((f.copy(), None))
            continue
        points = [(x,y) for y in range(85) for x in range(40,378)
                  if min(f.getpixel((x,y))[:3]) > 220 and f.getpixel((x,y))[3] >= 145]
        if not points:
            raise ValueError('No white placard panel found')
        bb = (max(0,min(x for x,y in points)-5),max(0,min(y for x,y in points)-5),
              min(418,max(x for x,y in points)+6),min(85,max(y for x,y in points)+6))
        sign = f.copy()
        body = f.copy()
        body.paste((0, 0, 0, 0), (max(0,bb[0]-3),0,min(f.width,bb[2]+3),bb[3]+3))
        separated.append((body, sign.crop(bb)))
    sign = separated[0][1]
    # A single generated sign is reused for all frames, so type never wobbles.
    if sign is not None:
        scale = min(300/sign.width, 60/sign.height)
        sign = sign.resize((round(sign.width*scale),round(sign.height*scale)),Image.Resampling.LANCZOS)
    bodies = [x[0] for x in separated]
    union = None
    for body in bodies:
        bb = body.getchannel('A').point(lambda a:255 if a>=145 else 0).getbbox()
        union = bb if union is None else (min(union[0],bb[0]),min(union[1],bb[1]),max(union[2],bb[2]),max(union[3],bb[3]))
    bw,bh=union[2]-union[0],union[3]-union[1]
    body_scale=min(380/bw,326/bh)
    size=(round(bw*body_scale),round(bh*body_scale))
    result=[]
    for index, body in enumerate(bodies):
        canvas=Image.new('RGBA',(418,418))
        if sign is not None:
            canvas.alpha_composite(sign,((418-sign.width)//2,8))
        crop=body.crop(union).resize(size,Image.Resampling.LANCZOS)
        body_layer=Image.new('RGBA',(418,418))
        body_layer.alpha_composite(crop,((418-size[0])//2,410-size[1]))
        if align == "manual":
            dx=round(209-((anchors[index]*418-union[0])*size[0]/bw+(418-size[0])//2))
        elif align == "torso":
            dx=round(209-torso_center_x(body_layer))
        else:
            dx=0
        bb=body_layer.getchannel('A').point(lambda a:255 if a>=145 else 0).getbbox()
        if bb[0]+dx<0 or bb[2]+dx>418:
            raise ValueError('Alignment would clip character or props')
        canvas.alpha_composite(body_layer,(dx,0))
        result.append(canvas)
    return result


def fit_full_body(frames, size, margin):
    boxes=[f.getchannel('A').point(lambda a:255 if a>=145 else 0).getbbox() for f in frames]
    if not all(boxes): raise ValueError('Empty animation frame')
    box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
    w,h=box[2]-box[0],box[3]-box[1]
    scale=min((size-2*margin)/w,(size-2*margin)/h)
    wh=(max(1,round(w*scale)),max(1,round(h*scale)))
    out=[]
    for f in frames:
        c=Image.new('RGBA',(size,size))
        c.alpha_composite(f.crop(box).resize(wh,Image.Resampling.LANCZOS),((size-wh[0])//2,(size-wh[1])//2))
        out.append(c)
    return out


def validate(out):
    meta=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    if len(meta)!=16: raise ValueError('Expected exactly 16 stickers')
    if len(list((out/'main').glob('*.gif')))!=16 or len(list((out/'thumb').glob('*.png')))!=16:
        raise ValueError('Unexpected main/thumbnail file count')
    records=[]
    for item in meta:
        p=out/'main'/f"{item['code']}.gif"
        with Image.open(p) as im:
            if im.size!=(240,240) or im.info.get('loop')!=0: raise ValueError(f'Invalid GIF size/loop: {p}')
            frames=[f.convert('RGBA') for f in ImageSequence.Iterator(im)]
        if len(frames)!=9 or p.stat().st_size>500*1024 or p.read_bytes()[:6]!=b'GIF89a': raise ValueError(f'Invalid GIF frames/size/format: {p}')
        if len({f.tobytes() for f in frames})<2: raise ValueError(f'Animation is frozen: {p}')
        for f in frames:
            box=f.getchannel('A').getbbox()
            if f.getchannel('A').getextrema()!=(0,255) or not box or min(box[0],box[1],240-box[2],240-box[3])<6: raise ValueError(f'Alpha/margin check failed: {p}')
        thumb=out/'thumb'/f"{item['code']}.png"
        with Image.open(thumb) as im:
            if im.size!=(120,120) or im.mode!='RGBA' or thumb.stat().st_size>200*1024: raise ValueError(f'Invalid thumbnail: {thumb}')
        records.append(dict(code=item['code'],frames=9,gif_kb=round(p.stat().st_size/1024,1)))
    for name,size,limit in [('cover.png',(240,240),500),('icon.png',(50,50),100),('banner.png',(750,400),500)]:
        p=out/name
        with Image.open(p) as im:
            if im.size!=size or p.stat().st_size>limit*1024: raise ValueError(f'Invalid auxiliary asset: {p}')
            extrema=im.convert('RGBA').getchannel('A').getextrema()
            if extrema!=((255,255) if name=='banner.png' else (0,255)): raise ValueError(f'Invalid auxiliary transparency: {p}')
    report=dict(status='passed',count=16,items=records,scope='Bundled packer technical profile; platform acceptance and visual quality require separate review')
    (out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def build(manifest, out):
    config=json.loads(manifest.read_text(encoding='utf-8'))
    items=config['items']
    if len(items)!=16: raise ValueError('Manifest must contain exactly 16 items')
    if len({x['slug'] for x in items})!=16: raise ValueError('Duplicate slugs')
    for item in items:
        if not re.fullmatch(r'[a-zA-Z0-9_-]+',item['slug']): raise ValueError('Unsafe slug')
        if item.get('align','torso') not in ('torso','manual','none'): raise ValueError('Unknown alignment mode')
        if item.get('label_mode','white_placard') not in ('white_placard','none'): raise ValueError('Unknown label mode')
        if item.get('align')=='manual' and (len(item.get('anchors',[]))!=9 or not all(0<=x<=1 for x in item['anchors'])): raise ValueError('Manual alignment requires 9 normalized horizontal anchors')
    def source(name):
        p=Path(name)
        return p if p.is_absolute() else manifest.parent/p
    inputs=[source(x['sheet']) for x in items]+[source(config['cover']),source(config['banner'])]
    if not all(p.is_file() for p in inputs): raise ValueError('Missing source sheet, cover, or banner')
    if out.exists(): raise ValueError('Output already exists; choose a new versioned directory')
    duration=config.get('duration_ms',120)
    if not isinstance(duration,int) or duration<20 or duration%10: raise ValueError('duration_ms must be a positive multiple of 10, at least 20')
    out.mkdir(parents=True)
    raw=out/'sources';raw.mkdir()
    prepared=[];motion=[]
    for item in items:
        original=split_sheet(source(item['sheet']))
        if any(f.getchannel('A').getextrema()[0]!=0 for f in original): raise ValueError('Source has no transparent pixels; generate true alpha, do not chroma-key')
        frames=stabilize_labels(original,item.get('align','torso'),item.get('anchors'),item.get('label_mode','white_placard'))
        prepared.append(frames)
        if item.get('align','torso')=='torso':
            centers=[torso_center_x(f) for f in frames]
            span=max(centers)-min(centers)
            if span>2: raise ValueError(f"Residual torso drift in {item['slug']}: {span}px")
            motion.append(dict(slug=item['slug'],span_px=span,space='418px normalized frame',method='hip-band heuristic; inspect visually'))
        save_transparent_gif(fit_full_body(frames,320,8),raw/f"{item['slug']}.gif",duration)
    shutil.copy2(source(config['cover']),raw/'cover_raw.png')
    shutil.copy2(source(config['banner']),raw/'banner_raw.png')
    upload=out/'wechat_upload'
    report=package_album(raw,upload,items,duration_ms=duration,album_title=config.get('title','微信动态表情包'),enlarge_mode=None)
    # Write final GIF once from RGBA, avoiding double palette loss and the
    # original packer's half-body heuristic misclassifying wide feet.
    contact=Image.new('RGB',(960,1040),'#444444');draw=ImageDraw.Draw(contact)
    for i,(entry,frames) in enumerate(zip(report,prepared)):
        final=fit_full_body(frames,240,6)
        entry['gif_kb'],_=save_transparent_gif(final,upload/'main'/f"{entry['code']}.gif",duration)
        fit_full_body([frames[4]],120,6)[0].save(upload/'thumb'/f"{entry['code']}.png",optimize=True)
        entry['thumb_kb']=round((upload/'thumb'/f"{entry['code']}.png").stat().st_size/1024,1)
        bg=Image.new('RGBA',(240,240),'#191919' if i%2 else '#EDEDED');bg.alpha_composite(final[4]);contact.paste(bg.convert('RGB'),(i%4*240,i//4*260+20));draw.text((i%4*240+8,i//4*260+4),entry['code'],fill='white')
    (upload/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    page=(upload/'preview.html').read_text(encoding='utf-8')
    for entry in report:
        pattern=r'(src="main/'+entry['code']+r'\.gif".*?\()([\d.]+)(KB\))'
        page=re.sub(pattern,lambda m:m[1]+str(entry['gif_kb'])+m[3],page,flags=re.S,count=1)
        path=upload/'main'/f"{entry['code']}.gif"
        page=page.replace(f'src="main/{entry["code"]}.gif"',f'src="main/{entry["code"]}.gif?v={hashlib.sha256(path.read_bytes()).hexdigest()[:10]}"')
    (upload/'preview.html').write_text(page,encoding='utf-8')
    contact.save(out/'contact_sheet.jpg',quality=95)
    (out/'motion_report.json').write_text(json.dumps(motion,indent=2),encoding='utf-8')
    shutil.copy2(manifest,out/'input_manifest.json')
    with (upload/'meanings.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['编号','配字','含义词'])
        writer.writerows((x['code'],x['caption'],x['meaning']) for x in report)
    result=validate(upload)
    with zipfile.ZipFile(out/'wechat_upload.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(upload.rglob('*')):
            if p.is_file(): z.write(p,Path('wechat_upload')/p.relative_to(upload))
    return result


def export_qa(upload, dest):
    """Decode delivered GIFs, not source sheets; expose all frames on both backgrounds."""
    if dest.exists():
        raise ValueError('QA output already exists; choose a new directory')
    paths=sorted((upload/'main').glob('*.gif'))
    if len(paths)!=16:
        raise ValueError('Expected 16 delivered GIFs for QA')
    dest.mkdir(parents=True)
    for path in paths:
        with Image.open(path) as im:
            frames=[f.convert('RGBA') for f in ImageSequence.Iterator(im)]
        if len(frames)!=9:
            raise ValueError(f'Expected nine frames: {path}')
        canvas=Image.new('RGB',(9*160,2*184),'#555555')
        draw=ImageDraw.Draw(canvas)
        for row,color in enumerate(('#EDEDED','#191919')):
            for col,frame in enumerate(frames):
                bg=Image.new('RGBA',frame.size,color)
                bg.alpha_composite(frame)
                canvas.paste(bg.convert('RGB').resize((160,160)),(col*160,row*184+24))
                draw.text((col*160+4,row*184+5),f'{path.stem} / {col+1}',fill='white')
        canvas.save(dest/f'{path.stem}.jpg',quality=95)
    status=dict(technical_validation='not_run_by_qa_command',frame_review='pending',
                playback_review='pending',platform_review='not_submitted',
                notes='Contact sheets do not verify real-time playback. Record observed review results separately.')
    (dest/'review_status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    return dict(count=16,output=str(dest),playback_review='pending')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--manifest',type=Path,required=True);b.add_argument('--out',type=Path,required=True)
    v=sub.add_parser('validate');v.add_argument('--out',type=Path,required=True,help='wechat_upload folder')
    q=sub.add_parser('qa');q.add_argument('--out',type=Path,required=True,help='wechat_upload folder');q.add_argument('--dest',type=Path,required=True)
    a=sub.add_parser('anchor');a.add_argument('--sheet',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--frame',type=int,choices=range(9),default=0)
    args=parser.parse_args()
    if args.command=='build':print(json.dumps(build(args.manifest.resolve(),args.out.resolve())))
    elif args.command=='validate':print(json.dumps(validate(args.out.resolve())))
    elif args.command=='qa':print(json.dumps(export_qa(args.out.resolve(),args.dest.resolve())))
    else:
        if args.out.exists():raise ValueError('Anchor already exists; use a new versioned path')
        args.out.parent.mkdir(parents=True,exist_ok=True)
        split_sheet(args.sheet)[args.frame].save(args.out)
        print(args.out.resolve())


if __name__=='__main__':main()

