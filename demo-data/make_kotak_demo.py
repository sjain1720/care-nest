"""Generate fictional hospital documents; original policy wording is copied byte-for-byte.
Run with a Python runtime containing reportlab. No supplied patient data is copied.
"""
from hashlib import sha256
from pathlib import Path
import json
import shutil
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'demo-data'
PUBLIC = ROOT / 'frontend/public/demo'
POLICY = ROOT / 'policies-data-set/Kotak Group Health Assure.pdf'
TEAL = colors.HexColor('#087d6d')
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle('SmallDemo', fontName='Helvetica', fontSize=9, leading=13, spaceAfter=8))
STYLES.add(ParagraphStyle('DemoTitle', fontName='Helvetica-Bold', fontSize=21, leading=26, textColor=TEAL, spaceAfter=14))
STYLES.add(ParagraphStyle('DemoNote', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#526762'), spaceAfter=8))
ROWS = [
 ('Single A/C room', 'room', 2750, 7), ('Consultant visits', 'doctor', 20700, 1),
 ('Laboratory and radiology', 'investigations', 8450, 1), ('Medical records', 'admin', 500, 1),
 ('Admission processing', 'admin', 500, 1), ('Nursing care', 'nursing', 1450, 7),
 ('Urinary catheter procedure', 'procedure', 800, 1), ('Anaesthetist', 'anaesthesia', 10000, 1),
 ('C-arm equipment', 'equipment', 5000, 1), ('Surgeon', 'surgery', 25000, 1),
 ('Oxygen support', 'equipment', 1800, 1), ('Orthopaedic implant', 'implants', 71925, 1),
 ('Operation theatre', 'surgery', 15000, 1), ('Nebulisation', 'procedure', 150, 4),
 ('Bedside glucose test', 'investigations', 150, 1),
]
PREVIOUS = [('Radiology', 'investigations', 2004, 1), ('General ward', 'room', 1500, 4),
            ('Consultation', 'doctor', 2450, 1), ('Pathology', 'investigations', 10098, 1),
            ('Pharmacy and medicines', 'pharmacy', 52868, 1)]

def money(v):
 s=f'{v:.2f}';a,b=s.split('.');head=a[:-3];last=a[-3:]
 if head: last=','.join([head[max(0,i-2):i] for i in range(len(head),0,-2)][::-1])+','+last
 return 'Rs. '+last+'.'+b

def p(text, style='SmallDemo'): return Paragraph(text, STYLES[style])
def table(data,widths):
 cells=[[p(str(x)) for x in row] for row in data]
 t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f5f1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#dce6e2')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 return t

def header(title,sub): return [p('CARENEST SAMPLE HOSPITAL - FICTIONAL', 'DemoNote'),p(title,'DemoTitle'),p(sub),Spacer(1,10)]
def bill_rows(rows,start):return table([['No.','Charge','Rate','Qty','Amount']]+[[i,desc,money(rate),qty,money(rate*qty)] for i,(desc,cat,rate,qty) in enumerate(rows,start)], [30,198,95,38,138])
def build(name,pages):
 def foot(c,doc):
  c.setStrokeColor(TEAL);c.line(40,45,555,45);c.setFont('Helvetica',7)
  c.drawString(40,32,'SYNTHETIC DEMO - NOT A REAL PATIENT BILL OR INSURER DECISION')
  c.drawRightString(555,32,f'Page {doc.page} of {len(pages)}')
 story=[]
 for n,items in enumerate(pages):
  if n:story.append(PageBreak())
  story.extend(items)
 SimpleDocTemplate(str(OUT/name),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=60).build(story,onFirstPage=foot,onLaterPages=foot,canvasmaker=lambda *a,**k:canvas.Canvas(*a,**{**k,'invariant':1}))
 shutil.copyfile(OUT/name,PUBLIC/name)


def main():
 OUT.mkdir(exist_ok=True);PUBLIC.mkdir(exist_ok=True)
 # Source policy stays completely unchanged. Authoring affects only synthetic companion documents.
 for folder in [OUT,PUBLIC]:shutil.copyfile(POLICY,folder/'kotak_group_health_assure.pdf')
 current='Bill CN/IP/2026/1002 | Patient: _____, 58 | Stay: 12-19 September 2026 | Fictional fracture repair admission'
 pages=[]
 for n in range(3):
  items=header('Final hospital bill' if n==0 else 'Final bill - continuation',current)
  items += [bill_rows(ROWS[n*5:(n+1)*5],n*5+1)]
  if n==2:
   items += [Spacer(1,12),table([['Bill summary','Amount'],['Gross charges',money(189825)],['Hospital discount - implant only',money(4825)],['Net bill / amount claimed',money(185000)],['Family payment received',money(185000)],['Hospital balance due',money(0)]],[340,159]),p('The hospital discount is not an insurer deduction. Insurer payment is established separately by the simulated settlement.','DemoNote')]
  if n==0:items += [Spacer(1,16),p('Room: single A/C, Rs. 2,750/day, seven days. Differential normal-room tariffs apply to consultant visits, nursing, surgeon, anaesthetist and theatre charges. Implant/equipment/tests are separately priced.','DemoNote')]
  pages.append(items)
 build('hospital_bill.pdf',pages)
 prev='Bill CN/IP/2026/1001 | Patient: _____, 32 | Stay: 04-08 May 2026 | Fictional short medical admission'
 build('previous_bill.pdf',[header('Previous hospital bill',prev)+[bill_rows(PREVIOUS[:3],1)],header('Previous bill - final summary',prev)+[bill_rows(PREVIOUS[3:],4),Spacer(1,16),table([['Summary','Amount'],['Net amount',money(73420)],['Family payment',money(73420)],['Balance due',money(0)]],[340,159]),p('Whole-rupee fictional scenario based on the supplied sample layout; all names, dates and identifiers are invented.','DemoNote')]])
 build('settlement_letter.pdf',[
  header('Simulated claim decision','CARENEST FICTIONAL CLAIMS DESK - NOT ISSUED BY KOTAK')+[p('Claim: DEMO-2026-1002 | Policy: DEMO-KOTAK-1000000 | Decision date: 25 September 2026'),p('Patient: _____ | Hospital bill: CN/IP/2026/1002'),table([['Decision summary','Amount'],['Claimed - net hospital bill',money(185000)],['Approved and paid (fictional)',money(165000)],['Total deductions',money(20000)]],[340,159]),Spacer(1,16),p('The itemized reasons appear on page 2. This simulated decision deliberately contains a questionable implant deduction and an unexplained amount for investigation. It is not evidence of an actual insurer decision or practice.','DemoNote')],
  header('Itemized deduction record','Claim DEMO-2026-1002 - illustrative recorded reasons, not verified applicability')+[
   table([['Recorded deduction','Amount','Recorded reason'],['Room and associated charges',money(9100),'Selected normal-room limit exceeded. Applied benefit 13.'],['Proportionate reduction on implant',money(6100),'Applied the same room ratio to net implant charges.'],['Other deductions',money(4800),'-']],[165,100,234]),Spacer(1,12),p('Recorded room calculation: 7 x (2,750 - 2,500) = 1,750. Associated charge base: 20,700 + 10,150 + 25,000 + 10,000 + 15,000 = 80,850. Recorded proportional reduction: 80,850 x (1 - 2,500/2,750) = 7,350. Combined = 9,100.'),p('Recorded implant calculation: (71,925 - hospital discount 4,825) x (1 - 2,500/2,750) = 6,100. This is the simulated decision\'s calculation; the app must examine the policy exception, rather than assume it is valid.'),p('No itemization or policy clause is recorded for the remaining 4,800. Ask the fictional claims desk for the breakdown.'),p('Reconciliation: 1,85,000 - 9,100 - 6,100 - 4,800 = 1,65,000. Related wording does not confirm a deduction is justified.','DemoNote')]])
 build('previous_settlement.pdf',[header('Previous claim - simulated payment','CARENEST FICTIONAL CLAIMS DESK - NOT ISSUED BY KOTAK')+[p('Claim: DEMO-2026-1001 | Policy: DEMO-KOTAK-1000000 | Decision/payment date: 12 May 2026'),p('Patient: _____ | Bill CN/IP/2026/1001 | Hospital stay: 04-08 May 2026'),table([['Previous claim','Amount'],['Claimed',money(73420)],['Approved and paid (fictional)',money(73420)],['Deductions',money(0)]],[340,159]),p('For the fictional profile this claim is closed. Both hospitalisations fall in the assumed policy year 12 March 2026 to 11 March 2027. This document is not an insurer-issued record.','DemoNote')]])
 build('coverage_assumptions.pdf',[header('Example coverage assumptions','COMPANION TO ORIGINAL KOTAK WORDING - NOT AN INSURER-ISSUED SCHEDULE')+[
  table([['Fictional selection','Assumed value'],['Policy wording reference','Kotak Group Health Assure - KOTHLGP22168V012122'],['Demo policy reference','DEMO-KOTAK-1000000'],['Sum insured','Rs. 10,00,000 family floater'],['Continuous cover assumed from','12 March 2024, without breaks'],['Current renewal assumed','12 March 2026 to 11 March 2027'],['Members','Self: _____ (32); father: _____ (62); mother: _____ (58)'],['Selected room option','Benefit 13: normal-room cap with proportionate deduction'],['Normal room limit','Rs. 2,500 per day - fictional selected limit'],['Optional co-pay and deductible','Neither selected in this fictional scenario']],[190,309]),Spacer(1,12),p('Pages 6 and 29 allow a mother as an insured relationship. The example mother is assumed enrolled for this fictional story; an issued certificate is required in real use. The original wording does not supply these personal selections or numeric limits. They are invented demonstration inputs. The original PDF is unchanged. Benefit 14 is the alternative without proportionate deduction, not the option chosen for this story.'),p('Kotak wording page 17 contains important exceptions: medicines/pharmacy, medical consumables, implants and diagnostic costs are reimbursed based on actual amounts subject to policy terms. Differential-billing conditions and ICU exceptions also matter. Actual eligibility requires the issued schedule and claim facts.','DemoNote'),p('Demo figures: previous paid 73,420; current paid 1,65,000; total recorded 2,38,420; estimated base cover remaining 7,61,580. This is a demonstration ledger, not an insurer-confirmed balance.','DemoNote')]])
 names=['hospital_bill.pdf','previous_bill.pdf','settlement_letter.pdf','previous_settlement.pdf','coverage_assumptions.pdf','kotak_group_health_assure.pdf']
 manifest={'schema':2,'policySha256':sha256(POLICY.read_bytes()).hexdigest(),'files':{n:sha256((OUT/n).read_bytes()).hexdigest() for n in names},'current':{'gross':189825,'discount':4825,'net':185000,'approved':165000,'deducted':20000,'rows':15},'previous':{'net':73420,'approved':73420,'rows':5},'sumInsured':1000000,'estimatedRemaining':761580}
 for folder in [OUT,PUBLIC]:(folder/'kotak_demo_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
