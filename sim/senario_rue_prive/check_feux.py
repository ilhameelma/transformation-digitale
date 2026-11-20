import sumolib

IDS = ["cluster_1152869978_11834868569_12488127526_5183882550_#1more",
       "cluster_12488127527_12488127528_1872110762_5766095503_#2more",
       "cluster_12498204248_21518203_5763861450_5763861451"]

def phase(p):
    try:
        return p.duration, p.state
    except AttributeError:
        return p[0], p[1]

def programmes(fichier):
    net = sumolib.net.readNet(fichier, withPrograms=True)
    res = {}
    for i in IDS:
        tls = net.getTLS(i)
        res[i] = {pid: [phase(p) for p in prog.getPhases()]
                  for pid, prog in tls.getPrograms().items()}
    return res

a = programmes("../hassan.net.xml")
b = programmes("hassan_voie_reservee_v2.net.xml")

for i in IDS:
    print("\n", i)
    for pid in a[i]:
        pa, pb = a[i][pid], b[i].get(pid, [])
        da, db = [d for d, _ in pa], [d for d, _ in pb]
        print(f"  programme {pid} | phases {len(pa)} -> {len(pb)}")
        print("   durées actuel :", da)
        print("   durées v2     :", db)
        print("   durées identiques :", da == db)
        print("   longueur état :", len(pa[0][1]), "->", len(pb[0][1]) if pb else "?")
        for k, ((d1, s1), (d2, s2)) in enumerate(zip(pa, pb)):
            print(f"   phase {k}: {s1}  ->  {s2}")