# This program is modified for Envilink and AWS Lambda
from datetime import datetime
from random import randint
import math
import json

# Return CLO based on current date
def decideCLO():
    currMonth = int(datetime.now().month)
    if (currMonth == 1):
        clo = 1.34
    if (currMonth == 2):
        clo = 1.18
    if (currMonth == 3):
        clo = 0.83
    if (currMonth == 4):
        clo = 0.59
    if (currMonth == 5):
        clo = 0.41
    if (currMonth == 6):
        clo = 0.33
    if (currMonth == 7):
        clo = 0.31
    if (currMonth == 8):
        clo = 0.31
    if (currMonth == 9):
        clo = 0.44
    if (currMonth == 10):
        clo = 0.51
    if (currMonth == 11):
        clo = 0.76
    if (currMonth == 12):
        clo = 1.26
    return clo


# Take temperature T in C
# Return saturated vapour pressure, in kPa
def FNPS(T):
    # Note: Missing '(' in document
    return math.exp(16.6536 - 4030.183 / (T + 235.0))

def computePPD(PMV):
    PPD = 100.0 - 95.0 * math.exp(-0.03353 * pow(PMV, 4.0) - 0.2179 * pow(PMV, 2.0))
    return PPD

def computeAPMV(PMV):
    if(PMV >= 0):
        coefficient = 0.21
    else:
        coefficient = -0.49
    APMV = PMV / (1.0 + coefficient * PMV)
    return APMV

# Clothing, clo,                     CLO
# Metabolic rate, met,               MET
# External work, met,                WME
# Air temperature, C,                TA
# Mean radiant temperature, C,       TR
# Relative air velocity, m/s,        VEL
# Relative humidity, %,              RH
# Partial water vapour pressure, Pa, PA
def computePMV(CLO, MET, WME, TA, TR, VEL, RH, PA):
    if PA == 0:
        PA = RH * 10 * FNPS(TA) # water vapour pressure, Pa
    ICL = 0.155 * CLO # thermal insulation of the clothing in m2K/W
    M = MET * 58.15 # external work in W/m2
    W = WME * 58.15
    MW = M - W #  internal heat production in the human body
    if (ICL <= 0.078):
        FCL = 1 + 1.29 * ICL
    else:
        FCL = 1.05 + 0.645 * ICL # clothing area factor
    HCF = 12.1 * math.sqrt(VEL) #  heat transf. coeff. by forced convection
    TAA = TA + 273 # air temperature in Kelvin
    TRA = TR + 273 # mean radiant temperature in Kelvin

    TCLA = TAA + (35.5 - TA) / (3.5 * ICL + 0.1) # first guess for surface temperature of clothing
    P1 = ICL * FCL
    P2 = P1 * 3.96
    P3 = P1 * 100
    P4 = P1 * TAA
    # Note: P5 = 308.7 - 0.028 * MW + P2 * (TRA / 100) * 4  in document
    P5 = (308.7 - 0.028 * MW) + (P2 * math.pow(TRA / 100, 4))
    # Note: TLCA in document
    XN = TCLA / 100
    # Note: XF = XN in document
    XF = TCLA / 50
    N = 0 # number of iterations
    EPS = 0.00015 # stop criteria in iteration
    # Note: HC must be defined before use
    HC = HCF

    while (abs(XN-XF) > EPS):
        XF = (XF + XN) / 2
        HCN = 2.38 * math.pow(abs(100.0 * XF - TAA), 0.25)
        if (HCF > HCN):
            HC = HCF
        else:
            HC = HCN
        # Note: should be '-' in document
        XN = (P5 + P4 * HC - P2 * math.pow(XF, 4)) / (100 + P3 * HC)
        N = N + 1
        if (N > 150):
            print 'Max iterations exceeded'
            return 999999
    TCL = 100 * XN - 273

    HL1 = 3.05 * 0.001 * (5733 - 6.99 * MW - PA) # heat loss diff. through skin
    if MW > 58.15:
        HL2 = 0.42 * (MW - 58.15)
    else:
        HL2 = 0
    HL3 = 1.7 * 0.00001 * M * (5867 - PA) # latent respiration heat loss
    HL4 = 0.0014 * M * (34 - TA) # dry respiration heat loss
    # Note: HL5 = 3.96 * FCL * (XN^4 - (TRA/100^4)   in document
    HL5 = 3.96 * FCL * (math.pow(XN, 4) - math.pow(TRA / 100, 4)) # heat loss by radiation
    HL6 = FCL * HC * (TCL - TA)

    TS = 0.303 * math.exp(-0.036 * M) + 0.028
    PMV = TS * (MW - HL1 - HL2 - HL3 - HL4 - HL5 - HL6)
    return PMV

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


# Entry point of AWS lambda
def handler(event, context):
    print(json.dumps(event))
    # TODO
    if ('queryStringParameters' in event and
        'ta' in event['queryStringParameters'] and
        'rh' in event['queryStringParameters']):
        # We have enough info
        TA = float(event['queryStringParameters']['ta'])
        RH = float(event['queryStringParameters']['rh'])
        # Check if we have more info
        if ('clo' in event['queryStringParameters']):
            CLO = float(event['queryStringParameters']['clo'])
        else:
            CLO = decideCLO()
        if ('met' in event['queryStringParameters']):
            MET = float(event['queryStringParameters']['met'])
        else:
            MET = 1.2
        if ('wme' in event['queryStringParameters']):
            WME = float(event['queryStringParameters']['wme'])
        else:
            WME = 0.0
        if ('tr' in event['queryStringParameters']):
            TR = float(event['queryStringParameters']['tr'])
        else:
            TR = TA
        if ('vel' in event['queryStringParameters']):
            VEL = float(event['queryStringParameters']['vel'])
        else:
            VEL = randint(7, 12) / 100.0
        if ('pa' in event['queryStringParameters']):
            PA = float(event['queryStringParameters']['pa'])
        else:
            PA = 0

        pmv = computePMV(CLO, MET, WME, TA, TR, VEL, RH, PA)
        apmv = computeAPMV(pmv)
        ppd = computePPD(pmv)
        responseBody = {
            'PMV': pmv,
            'APMV': apmv,
            'PPD': ppd
        }
        return respond(None, responseBody)

    else:
        # no
        respond(ValueError('Unsupported parameters'))