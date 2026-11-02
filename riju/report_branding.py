"""Book-local embedded report logos; no dependency on the original image path."""
import base64
import copy
import hashlib
import io
import warnings
from pathlib import Path
from PIL import Image
from . import core

SLOTS={'client':'Client logo (left)','axiom':'AXIOM logo (right)'}


def snapshot(state):return copy.deepcopy(state['settings'].get('report_logos',{}))


def image_bytes(record):
    return base64.b64decode(record['png'],validate=True)


def set_logo(state,slot,path):
    if slot not in SLOTS:raise ValueError('Choose the client or AXIOM logo slot.')
    path=Path(path)
    if path.stat().st_size>5*1024*1024:raise ValueError('Choose a PNG or JPEG logo smaller than 5 MB.')
    raw=path.read_bytes()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as im:
                if im.format not in ('PNG','JPEG'):raise ValueError('Choose a PNG or JPEG logo.')
                if im.width*im.height>16000000:raise ValueError('Logo exceeds 16 million pixels; resize it first.')
                im.load();im=im.convert('RGBA');im.thumbnail((1200,600));out=io.BytesIO();im.save(out,format='PNG')
    except (OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:
        raise ValueError('Cannot read this logo. Choose a valid PNG or JPEG image.') from error
    data=out.getvalue();record=dict(filename=path.name,png=base64.b64encode(data).decode('ascii'),sha256=hashlib.sha256(data).hexdigest())
    state['settings'].setdefault('report_logos',{})[slot]=record
    core.add_audit(state,'REPORT_LOGO_CHANGED',dict(slot=slot,filename=path.name,sha256=record['sha256']))


def remove_logo(state,slot):
    if slot not in SLOTS:raise ValueError('Choose the client or AXIOM logo slot.')
    state['settings'].setdefault('report_logos',{}).pop(slot,None)
    core.add_audit(state,'REPORT_LOGO_REMOVED',dict(slot=slot))


def excel_header(ws,pack,columns):
    from openpyxl.drawing.image import Image as ExcelImage
    logos=pack.get('logos',{})
    if not logos:return
    for _ in range(3):ws.append([''])
    ws.row_dimensions[1].height=48;ws.row_dimensions[2].height=10;ws.row_dimensions[3].height=10
    for slot,record in logos.items():
        im=ExcelImage(io.BytesIO(image_bytes(record)));scale=min(145/im.width,60/im.height);im.width*=scale;im.height*=scale
        from openpyxl.utils import get_column_letter
        im.anchor='A1' if slot=='client' else get_column_letter(max(2,columns-1))+'1';ws.add_image(im)


def draw_pdf(canvas,doc,logos):
    from reportlab.lib.utils import ImageReader
    for slot,record in logos.items():
        image=ImageReader(io.BytesIO(image_bytes(record)));w,h=image.getSize();scale=min(145/w,52/h);w*=scale;h*=scale
        x=doc.leftMargin if slot=='client' else doc.pagesize[0]-doc.rightMargin-w
        canvas.drawImage(image,x,doc.pagesize[1]-24-h,width=w,height=h,mask='auto')
