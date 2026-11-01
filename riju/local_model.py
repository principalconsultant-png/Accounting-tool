"""Small, authored offline multinomial Naive Bayes topic model. No downloads/network.
Model/training phrase data below: CC0-1.0; runtime follows project terms.
This is a statistical intent classifier, not a generative language model.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import re

VERSION='riju-intents-1'
PHRASES={
 '4530':('premises rental monthly lease','building rent office rental','rent expense landlord accommodation lease','monthly rental premises landlord','rented office building payment'),
 '4540':('electricity power utility bill','water utility waterworks','electric meter energy charges','utilities broadband telephone bill','power supply electricity utilities'),
 '4550':('repairs maintenance servicing','repair equipment maintenance expense','plumbing repair maintenance','air conditioner servicing upkeep','fixing building repair'),
 '4520':('staff wages salary payroll','employee salaries monthly payroll','staff remuneration wages','salary employee benefits','payroll wages employees'),
 '4510':('doctor professional fees','physician consultation professional fee','medical consultant honorarium','visiting physician remuneration','doctor consultancy charges'),
 '4560':('bank processing charges','bank fee transfer commission','merchant processing fee','bank service charge','payment processing bank commission'),
 '1030':('medical equipment machine acquisition','bought diagnostic equipment','purchased medical apparatus','medical machinery acquisition','new clinical equipment'),
 '1040':('furniture fixtures purchase','bought office chairs desks','purchased furniture cabinet','office desk furnishings','new furniture acquisition'),
 'service:treatment':('therapy treatment','panchakarma therapy services','therapeutic session','ayurveda therapy treatment','treatment procedure session'),
 'service:consultation':('outpatient consultation opd','consultation appointment outpatient','opd consultation service','outpatient consult fee','medical consultation outpatient'),
 'service:eye_check':('eye check examination','eye checkup screening','vision examination eye','ophthalmic screening vision','eye examination checkup'),
 'service:registration':('registration patient enrolment','new patient registration','enrolment registration fee','patient registration charge','enrollment patient registration'),
 'service:medicine_retail':('pharmacy retail medicines','medicine retail sale','pharmacy medicine sale','retail prescription drugs','medicine pharmacy'),
 'service:medicine_treatment':('treatment medicines','medicine for treatment','treatment medicine charges','therapy medicine provided','medicines treatment'),
 'service:consumables':('consumables patient supplies','consumable charges','patient consumables','consumables supply charge','patient consumable supply'),
 'service:room_rent':('room rent inpatient ipd','inpatient accommodation room','hospital room charges','ipd room service','room inpatient stay'),
 'service:nursing':('nursing care','nursing charges','nursing services','nurse care service','nursing fee'),
 'service:duty_doctor':('duty doctor charges','duty physician rounds','duty doctor fee','duty medical officer','duty doctor services'),
 'service:food':('patient food diet meals','patient meals food','food charges patient','diet kitchen meals','meal service food'),
 'service:swarnaprashna':('swarnaprashna','swarnaprashana','suvarnaprashana','swarnaprashan','swarnaprashna service'),
 'service:kalari':('kalari sessions','kalari service','kalari class','kalari training','kalari therapy'),
 'service:treatment_receipt':('treatment receipt earned','trtmt pymt recd','earned treatment payment','treatment payment received','treatment receipts'),
 'service:misc':('miscellaneous patient charges','misc charges','miscellaneous service','misc patient charge','miscellaneous charges'),
 '4040':('resort accommodation revenue','resort service','resort stay charges','resort hospitality','resort room service'),
}
STOP=set('a an the for of our we by from to on at in paid received settled collected remitted payment receipt money cash bank upi card rs inr through via rupees and was is'.split())


def tokens(text):return [w for w in re.findall('[a-z]+',text.lower()) if w not in STOP and len(w)>1]


def digest():return hashlib.sha256(json.dumps(PHRASES,sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def model():
    counts={label:Counter(tokens(' '.join(rows))) for label,rows in PHRASES.items()};vocab=set(w for c in counts.values() for w in c)
    return counts,vocab


def predict(text):
    counts,vocab=model();features=Counter(w for w in tokens(text) if w in vocab)
    if not features:return dict(intent=None,confidence=0,margin=0,evidence=[],version=VERSION,digest=digest())
    weights={w:1+math.log((len(counts)+1)/(1+sum(w in c for c in counts.values()))) for w in features}
    scores={label:sum(n*weights[w]*math.log((c[w]+1)/(sum(c.values())+len(vocab))) for w,n in features.items()) for label,c in counts.items()};ordered=sorted(scores,key=scores.get,reverse=True);top=ordered[0];peak=scores[top];prob=1/sum(math.exp(v-peak) for v in scores.values());margin=math.exp(min(20,peak-scores[ordered[1]]))
    accepted=prob>=.24 and margin>=1.8
    return dict(intent=top if accepted else None,proposed=top,confidence=round(prob,4),margin=round(margin,4),evidence=sorted(features),version=VERSION,digest=digest())
