"""Build the complete printable offline user/training guide and receipt templates."""
import argparse
import html
import os
from pathlib import Path
import re
import sys
import textwrap
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from riju import APP_VERSION,receipt_import


def build_pdf(source,target):
    from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,PageBreak,LongTable,TableStyle,Preformatted
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='Helvetica';bold='Helvetica-Bold'
    for normal,strong in [(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf',Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeuib.ttf'),(Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))]:
        if normal.is_file() and strong.is_file():
            font='RijuManual';bold='RijuManualBold'
            if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(font,str(normal)));pdfmetrics.registerFont(TTFont(bold,str(strong)));pdfmetrics.registerFontFamily(font,normal=font,bold=bold,italic=font,boldItalic=bold)
            break
    styles=getSampleStyleSheet();body=ParagraphStyle('ManualBody',fontName=font,fontSize=9.2,leading=14,spaceAfter=8,wordWrap='CJK');title=ParagraphStyle('ManualTitle',parent=body,fontName=bold,fontSize=22,leading=29,spaceAfter=20);chapter=ParagraphStyle('ManualChapter',parent=body,fontName=bold,fontSize=15,leading=21,spaceAfter=14);cell=ParagraphStyle('ManualCell',parent=body,fontSize=7.6,leading=11,spaceAfter=2);tocstyle=ParagraphStyle('ManualTOC',parent=body,fontSize=9,leading=14,leftIndent=8,firstLineIndent=-8,spaceBefore=5)
    class Manual(BaseDocTemplate):
        def afterFlowable(self,flowable):
            if isinstance(flowable,Paragraph) and flowable.style.name=='ManualChapter':
                text=flowable.getPlainText();key='chapter-'+re.sub('[^a-zA-Z0-9]','',text);self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,0,False);self.notify('TOCEntry',(0,text,self.page,key))
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);doc=Manual(str(target),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=45,bottomMargin=45,title='Riju Books '+APP_VERSION+' — User and Training Guide',author='Riju Books')
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,7);canvas.setFillColor(colors.HexColor('#596878'));canvas.drawString(42,25,'Riju Books '+APP_VERSION+' | Training and User Guide');canvas.drawRightString(A4[0]-42,25,'Page '+str(doc.page));canvas.restoreState()
    doc.addPageTemplates(PageTemplate(id='manual',frames=[Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='body')],onPage=footer));story=[];lines=Path(source).read_text(encoding='utf-8').splitlines();i=0;contents=False
    def formatted(text):
        out=html.escape(text);out=re.sub(r'`([^`]+)`',r'<font face="Courier">\1</font>',out);out=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',out);return out
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('# '):story.append(Paragraph(formatted(line[2:]),title));i+=1;continue
        if line.startswith('## '):
            if not contents:
                story.append(PageBreak());story.append(Paragraph('Contents',title));toc=TableOfContents();toc.levelStyles=[tocstyle];story.append(toc);contents=True
            story.append(PageBreak());story.append(Paragraph(formatted(line[3:]),chapter));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                values=[v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',v) for v in values):rows.append([Paragraph(formatted(v),cell) for v in values])
                i+=1
            cols=max(len(r) for r in rows);weights=[1.0]*cols
            if cols==3:weights=[1.1,1,2.2]
            if cols==4:weights=[1.1,1.2,1.2,1.8]
            table=LongTable(rows,colWidths=[doc.width*w/sum(weights) for w in weights],repeatRows=1,hAlign='LEFT',splitInRow=1);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E3EEDF')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CED8CF')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.extend([table,Spacer(1,12)]);continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):code.extend(textwrap.wrap(lines[i],90) or ['']);i+=1
            story.append(Preformatted('\n'.join(code),ParagraphStyle('ManualCode',fontName='Courier',fontSize=7,leading=10)));i+=1;continue
        if re.match(r'\d+\. ',line):
            story.append(Paragraph(formatted(line),body));i+=1;continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```')) and not re.match(r'\d+\. ',lines[i]):paragraph.append(lines[i].strip());i+=1
        story.append(Paragraph(formatted(' '.join(paragraph)),body))
    doc.multiBuild(story)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='dist/user-documents');args=p.parse_args();root=Path(__file__).resolve().parents[1];out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    build_pdf(root/'docs/USER_TRAINING_GUIDE.md',out/'RijuBooks-User-Training-Guide.pdf');(out/'USER_TRAINING_GUIDE.md').write_text((root/'docs/USER_TRAINING_GUIDE.md').read_text(encoding='utf-8'),encoding='utf-8')
    for kind in ('xlsx','csv'):receipt_import.template(out/('RijuBooks-Sales-Receipts-Template.'+kind))
    print('Created PDF, source guide and standard XLSX/CSV receipt templates in '+str(out))
if __name__=='__main__':main()
