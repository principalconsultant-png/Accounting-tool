"""Styled Excel and print-ready PDF heatmaps sharing one Business Pulse snapshot."""
import html,io,os
from pathlib import Path
from decimal import Decimal
from . import business_pulse as bp,report_branding


def _label(row,pack):
    return row['label']+(' (INR 000)' if row['unit']=='money' and pack['scale']=='INR thousands' else ' (INR lakh)' if row['unit']=='money' and pack['scale']=='INR lakh' else ' (INR)' if row['unit'] in ('money','ratio') else ' (#)')


def export_xlsx(pack,path):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    w=Workbook();ws=w.active;ws.title='Monthly performance';report_branding.excel_header(ws,pack,13)
    def caption(text,height=24):
        ws.append([text]);r=ws.max_row;ws.merge_cells(start_row=r,start_column=1,end_row=r,end_column=13);ws.cell(r,1).data_type='s';ws.cell(r,1).alignment=Alignment(wrap_text=True,vertical='center');ws.row_dimensions[r].height=height;return r
    r=caption(pack['entity']+' | '+pack['title'],34);ws.cell(r,1).font=Font(size=19,bold=True,color=bp.PALETTE[0][1:])
    caption(f"FY {pack['year']}–{str(pack['year']+1)[-2:]} | {pack['scope']} | Through {pack['through']} | Money: {pack['scale']}; ARPP: INR; counts: #")
    caption('Colour: Q1 highest, Q2 upper-middle, Q3 lower-middle, Q4 lowest within each metric’s own observed history through that month. Not good/bad scoring.',30)
    caption('N/A = unavailable, unmapped, future or zero ARPP denominator. Pale blue = fewer than 4 observations / no variation. Provisional months are not certified complete.',30)
    ws.append(['Metric',*[__import__('datetime').datetime.strptime(m,'%Y-%m').strftime('%b %y') for m in pack['months']]]);header=ws.max_row
    for c in ws[header]:c.fill=PatternFill('solid',fgColor=bp.PALETTE[0][1:]);c.font=Font(bold=True,color='FFFFFF');c.alignment=Alignment(horizontal='center')
    ws.append(['Month coverage',*pack['coverage']])
    for c in ws[ws.max_row]:c.font=Font(size=9,color='526477');c.alignment=Alignment(wrap_text=True,horizontal='center')
    group=None
    for row in pack['rows']:
        if row['group']!=group:
            group=row['group'];r=caption(group.upper(),24);ws.cell(r,1).fill=PatternFill('solid',fgColor='DEE7F0');ws.cell(r,1).font=Font(bold=True,color=bp.PALETTE[0][1:])
        ws.append([_label(row,pack),*[bp.numeric(v,row['unit'],pack['scale']) for v in row['values']]])
        for i,c in enumerate(ws[ws.max_row]):
            c.alignment=Alignment(wrap_text=True,vertical='center',horizontal='left' if i==0 else 'right');c.border=Border(bottom=Side(style='hair',color='FFFFFF'));c.font=Font(size=10,color=bp.INK[1:],bold=i==0)
            if i:
                band=row['bands'][i-1];c.fill=PatternFill('solid',fgColor=bp.colour(band)[1:]);c.font=Font(size=10,color='FFFFFF' if band==0 else bp.INK[1:]);c.number_format='#,##0' if row['unit']=='count' else '#,##0.00;[Red](#,##0.00)'
                if c.value is None:c.value='N/A';c.data_type='s'
        ws.row_dimensions[ws.max_row].height=29
    caption(pack['note'],62)
    for warning in pack['warnings'][:8]:caption('REVIEW: '+warning,30)
    ws.column_dimensions['A'].width=39
    for c in range(2,14):ws.column_dimensions[get_column_letter(c)].width=14
    ws.freeze_panes=f'B{header+2}';ws.print_title_rows=f'1:{header+1}';ws.sheet_properties.pageSetUpPr.fitToPage=True;ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A3;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=1;ws.print_options.horizontalCentered=True;ws.oddFooter.center.text='Business Pulse | Page &P of &N'
    details=w.create_sheet('Sources and definitions');details.append(['Month','Metric','Actual INR / count','Unit','Source basis','Voucher IDs','Month review basis','Coverage'])
    for d in pack['details']:
        value=d['value'] if d['unit']=='count' or d['value'] is None else Decimal(d['value'])/100
        details.append([d['month'],d['metric'],value,d['unit'],d['source'],', '.join(d['vouchers']),d['review_basis'],d['coverage']])
    for row in details:
        for c in row:
            if isinstance(c.value,str):c.data_type='s'
            c.alignment=Alignment(wrap_text=True,vertical='top')
    for col in 'ABCDEFGH':details.column_dimensions[col].width=32 if col not in 'FG' else 65
    details.freeze_panes='C2';details.auto_filter.ref=details.dimensions
    definitions=w.create_sheet('Mapping review');definitions.append(['Setting','Value'])
    for k,v in pack['policy'].items():definitions.append([k,', '.join(v) if isinstance(v,list) else str(v)])
    definitions.append(['Prepared India',pack['prepared']]);definitions.append(['Heatmap method','Expanding history, including current observation; tied values use midrank. At least 4 observations and variation required. No future months enter earlier colours.'])
    for row in definitions:
        for c in row:c.data_type='s';c.alignment=Alignment(wrap_text=True,vertical='top')
    definitions.column_dimensions['A'].width=32;definitions.column_dimensions['B'].width=115
    w.save(path);w.close()


def export_pdf(pack,path):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='Helvetica'
    for candidate in (Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')):
        if candidate.is_file():
            font='BusinessPulseFont'
            if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(font,str(candidate)))
            break
    style=ParagraphStyle('Pulse',fontName=font,fontSize=6.2,leading=8,textColor=colors.HexColor(bp.INK));title=ParagraphStyle('PulseTitle',parent=style,fontSize=18,leading=23,textColor=colors.HexColor(bp.PALETTE[0]));sub=ParagraphStyle('PulseSub',parent=style,fontSize=8,leading=11)
    p=lambda s,colour=bp.INK:Paragraph(html.escape(str(s)),ParagraphStyle('Cell',parent=style,textColor=colors.HexColor('#'+colour.lstrip('#'))))
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=22,rightMargin=22,topMargin=87 if pack.get('logos') else 22,bottomMargin=30,title=pack['title'],author=pack['entity']);story=[]
    story += [Paragraph(html.escape(pack['entity']),sub),Paragraph(html.escape(pack['title']),title),Paragraph(html.escape(f"FY {pack['year']}–{str(pack['year']+1)[-2:]} | {pack['scope']} | Through {pack['through']} | Money: {pack['scale']} · ARPP: INR · counts: #"),sub),Spacer(1,8)]
    legend=Table([[p('Q1 Highest','FFFFFF'),p('Q2 Upper-middle'),p('Q3 Lower-middle'),p('Q4 Lowest'),p('N/A / unavailable'),p('Short / flat history')]],colWidths=[doc.width/6]*6)
    commands=[('BACKGROUND',(i,0),(i,0),colors.HexColor(c)) for i,c in enumerate([*bp.PALETTE,bp.MISSING,bp.NEUTRAL])];legend.setStyle(TableStyle(commands+[('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story += [legend,Spacer(1,7)]
    from datetime import datetime
    data=[[p('METRIC','FFFFFF'),*[p(datetime.strptime(m,'%Y-%m').strftime('%b %y'),'FFFFFF') for m in pack['months']]]];commands=[('BACKGROUND',(0,0),(-1,0),colors.HexColor(bp.PALETTE[0])),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.3,colors.white),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]
    group=None
    for row in pack['rows']:
        if row['group']!=group:
            group=row['group'];idx=len(data);data.append([p(group.upper()),*['']*12]);commands.extend([('SPAN',(0,idx),(-1,idx)),('BACKGROUND',(0,idx),(-1,idx),colors.HexColor('#DEE7F0'))])
        idx=len(data);data.append([p(_label(row,pack)),*[p(bp.display(v,row['unit'],pack['scale']),'FFFFFF' if row['bands'][i]==0 else bp.INK) for i,v in enumerate(row['values'])]])
        for i,b in enumerate(row['bands'],1):commands.append(('BACKGROUND',(i,idx),(i,idx),colors.HexColor(bp.colour(b))))
    widths=[doc.width*.23]+[doc.width*.77/12]*12;table=Table(data,colWidths=widths,repeatRows=1);table.setStyle(TableStyle(commands));story.append(table)
    notes='Coverage: '+' | '.join(__import__('datetime').datetime.strptime(m,'%Y-%m').strftime('%b')+': '+c for m,c in zip(pack['months'],pack['coverage']) if c!='Future')
    story += [Spacer(1,7),p(notes),p(pack['note'])]
    for warning in pack['warnings'][:5]:story.append(p('REVIEW: '+warning))
    def footer(canvas,d):
        canvas.saveState();report_branding.draw_pdf(canvas,d,pack.get('logos',{}));canvas.setFont(font,6);canvas.drawString(22,15,'Prepared India '+pack['prepared']+' | Business Pulse');canvas.drawRightString(d.pagesize[0]-22,15,'Page '+str(d.page));canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
