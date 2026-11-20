import sumolib

def charge(fichier):
    net = sumolib.net.readNet(fichier, withPrograms=True)
    lanes, conns = {}, set()
    for e in net.getEdges():
        for l in e.getLanes():
            lanes[l.getID()] = (frozenset(l.getPermissions()), round(l.getLength(), 1),
                                round(l.getSpeed(), 2))
            for c in l.getOutgoing():
                                conns.add((c.getFromLane().getID(), c.getToLane().getID(), c.getTLSID()))
    tls = {}
    for t in net.getTrafficLights():
        try:
            tls[t.getID()] = str([str(p.getPhases()) for p in t.getPrograms().values()])
        except Exception:
            tls[t.getID()] = "?"
    return lanes, conns, tls

la, ca, ta = charge("../hassan.net.xml")
lb, cb, tb = charge("hassan_voie_reservee_v2.net.xml")

print("voies :", len(la), "->", len(lb))
print("voies absentes d'un côté :", len(set(la) ^ set(lb)))

perm = [k for k in la if k in lb and la[k][0] != lb[k][0]]
print("\nvoies dont les classes autorisées changent :", len(perm))
for k in perm:
    print("  ", k)

geo = [k for k in la if k in lb and la[k][1:] != lb[k][1:]]
print("\nvoies dont la longueur ou la vitesse change :", len(geo))
for k in geo[:10]:
    print("  ", k, la[k][1:], "->", lb[k][1:])

print("\nconnexions ajoutées :", len(cb - ca))
for c in sorted(cb - ca):
    print("  ", c)
print("connexions supprimées :", len(ca - cb))
for c in sorted(ca - cb)[:10]:
    print("  ", c)

print("\nfeux : ", len(ta), "->", len(tb))
diff_tls = [k for k in ta if k in tb and ta[k] != tb[k]]
print("feux dont le programme change :", len(diff_tls))
for k in diff_tls[:10]:
    print("  ", k)