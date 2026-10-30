"""Printable, read-only bank reconciliation handover reports."""
import csv
import html
from pathlib import Path
from .ledgers import number,safe_csv

SUMMARY=(('bank_closing','Bank statement closing balance'),('deposits_in_transit','+ Book receipts/deposits not yet credited by bank'),('unpresented_payments','− Book payments/cheques not yet debited by bank'),('unrecorded_bank_credits','− Bank credits not in books at statement date'),('unrecorded_bank_debits','+ Bank debits not in books at statement date'),('adjusted_bank_balance','Adjusted bank statement balance'),('book_balance','Balance as per bank ledger'),('variance','Unexplained difference: book less adjusted bank'))


def _n(value):return 'Not supplied' if value is None else number(value,True)


def _status(r):return 'VOID — import cancelled' if r['status']=='VOID' else 'RECONCILED' if r['status']=='RECONCILED' else 'READY FOR REVIEW' if r['ready'] else 'DRAFT — incomplete / unrecorded items'


def export_csv(r,path):
    with open(path,'w',newline='',encoding='utf-8-sig') as stream:
        w=csv.writer(stream);s=r['statement']
        for row in [('Entity',r['entity']),('Bank ledger',s['bank_account']+' '+r['account_name']),('Scope',r['scope_name']),('Statement',s['filename']),('Period',s['start'],s['through']),('Status',_status(r)),('Statement checks',s['coverage']),('Prepared India',r['prepared'])]:w.writerow([safe_csv(v) for v in row])
        w.writerow(['Amounts in INR; positive balance = funds, negative = overdraft'])
        for key,label in SUMMARY:w.writerow([safe_csv(label),'' if r[key] is None else number(r[key])])
        w.writerow([]);w.writerow(['Outstanding book items']);w.writerow(['Date','Voucher','Reference','Branch','Narration','Signed amount INR'])
        for b in r['books']:w.writerow([safe_csv(b[k]) for k in ('date','voucher','reference','branch','narration')]+[number(b['remaining'])])
        w.writerow([]);w.writerow(['Outstanding bank items']);w.writerow(['Date','Reference','Narration','Signed amount INR','Reviewed reason / cutoff'])
        for b in r['banks']:w.writerow([safe_csv(b['date']),safe_csv(b['reference']),safe_csv(b['narration']),number(b['remaining']),safe_csv(b['exception'])])


def html_document(r):
    e=lambda v:html.escape(str(v),quote=True)
    s=r['statement'];summary=''.join('<tr><td>'+e(label)+'</td><td class="amount">'+e(_n(r[key]))+'</td></tr>' for key,label in SUMMARY)
    books=''.join('<tr>'+''.join('<td>'+e(b[k])+'</td>' for k in ('date','voucher','reference','branch','narration'))+'<td class="amount">'+e(_n(b['remaining']))+'</td></tr>' for b in r['books'])
    banks=''.join('<tr><td>'+e(b['date'])+'</td><td>'+e(b['reference'])+'</td><td>'+e(b['narration'])+'</td><td class="amount">'+e(_n(b['remaining']))+'</td><td>'+e(b['exception'])+'</td></tr>' for b in r['banks'])
    registration=' | '.join(e(k.upper()+': '+v) for k,v in r['registration'].items() if v)
    return '''<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"><title>Bank reconciliation</title><style>
body{font:12px Arial,sans-serif;color:#111;margin:20px}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #999;padding:6px;vertical-align:top;overflow-wrap:anywhere}th{background:#eee}.amount{text-align:right;white-space:nowrap}thead{display:table-header-group}.no-print{background:#f9e5d1;padding:12px}h1{font-size:20px}h2{font-size:16px}p{margin:6px 0}@page{size:A4 landscape;margin:12mm}@media print{body{margin:0;font-size:10px}.no-print{display:none}tr{break-inside:avoid}}
</style></head><body><div class="no-print"><button onclick="window.print()">Print / Save as PDF</button> Offline report preview</div><h1>'''+e(r['entity'])+'</h1><p>'+registration+'</p><h2>Bank Reconciliation Statement — '+e(_status(r))+'</h2><p>'+e(s['bank_account']+' '+r['account_name'])+' | '+e(r['scope_name'])+'</p><p>'+e(s['start']+' to '+s['through'])+' | '+e(s['filename'])+'</p><p>Checks: '+e(s['coverage'])+'</p><p>Amounts in INR. Positive balance = funds; negative balance = overdraft.</p><table>'+summary+'</table><h2>Book items outstanding at '+e(s['through'])+'</h2><table><thead><tr><th>Date</th><th>Voucher</th><th>Reference</th><th>Branch</th><th>Narration</th><th>Signed INR</th></tr></thead><tbody>'+books+'</tbody></table><h2>Bank items not recorded in books at statement date</h2><table><thead><tr><th>Date</th><th>Reference</th><th>Narration</th><th>Signed INR</th><th>Reviewed reason / cutoff</th></tr></thead><tbody>'+banks+'</tbody></table><p>Prepared India: '+e(r['prepared'])+'</p><p>Prepared by: ____________________ &nbsp; Reviewed by / CEO: ____________________</p></body></html>'


def export_html(r,path):Path(path).write_text(html_document(r),encoding='utf-8')


def export_pdf(r,path):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import landscape,A4
    from reportlab.lib import colors
    # ASCII report labels avoid relying on a downloaded font.
    clean=lambda v:html.escape(str(v).replace('−','-').replace('—','-'))
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font='Helvetica'
    for candidate in (Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')):
        if candidate.is_file():
            font='RijuBRS'
            if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(font,str(candidate)))
            break
    style=ParagraphStyle('BRS',fontName=font,fontSize=8,leading=11,wordWrap='CJK')
    heading=ParagraphStyle('BRSHeading',parent=style,fontSize=13,leading=16,spaceAfter=8)
    p=lambda v:Paragraph(clean(v),style)
    s=r['statement'];story=[Paragraph(clean(r['entity']),heading),p('Bank Reconciliation Statement - '+_status(r)),p(s['bank_account']+' '+r['account_name']+' | '+r['scope_name']),p(s['start']+' to '+s['through']+' | '+s['filename']),p(s['coverage']),p('INR; positive balance = funds, negative = overdraft.'),Spacer(1,10)]
    for key,value in r['registration'].items():
        if value:story.append(p(key.upper()+': '+value))
    summary=LongTable([[p(label),p(_n(r[key]))] for key,label in SUMMARY],colWidths=[590,150])
    summary.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,colors.grey),('BACKGROUND',(0,-3),(-1,-1),colors.HexColor('#E3EEDF'))]));story.extend([summary,Spacer(1,15)])
    def section(title,headers,rows,widths):
        story.extend([Paragraph(clean(title),heading),LongTable([[p(h) for h in headers]]+[[p(v) for v in row] for row in rows],colWidths=widths,repeatRows=1,splitInRow=1,style=TableStyle([('GRID',(0,0),(-1,-1),.3,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E3EEDF')),('VALIGN',(0,0),(-1,-1),'TOP')])) ,Spacer(1,15)])
    section('Outstanding book items',['Date','Voucher','Reference','Branch','Narration','Signed INR'],[[b['date'],b['voucher'],b['reference'],b['branch'],b['narration'],_n(b['remaining'])] for b in r['books']],[65,120,90,55,300,110])
    section('Outstanding bank items / reviewed cutoff reasons',['Date','Reference','Narration','Signed INR','Reason'],[[b['date'],b['reference'],b['narration'],_n(b['remaining']),b['exception']] for b in r['banks']],[65,90,245,110,230])
    story.append(p('Prepared by: ____________________    Reviewed by / CEO: ____________________'))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,7);canvas.drawString(25,17,s['bank_account']+' | '+s['through']+' | Prepared India: '+r['prepared']);canvas.drawRightString(815,17,'Riju Books | Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=25,rightMargin=25,topMargin=25,bottomMargin=35,title='Bank reconciliation',author=r['entity']).build(story,onFirstPage=footer,onLaterPages=footer)
