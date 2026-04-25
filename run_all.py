import concurrent
import subprocess
import itertools

# Inserire nella lista i nomi dei file contenenti le strategie, senza il ".py"
strategie_da_testare = [
    "playerStrategyImplPasqualeOG",
    "playerStrategyImplPasqualeRandom",
    "playerStrategyImplPasqualeMAX",
    "playerExampleAlphaImplGiuseppe",
    "GiuseppeImp2",
]

NUM_PARTITE = "15"
TIMEOUT = "3"
NUMERO_MASSIMO_TORNEI_IN_PARALLELO = 5

# due agenti si affrontano una volta sola, cambiare "combinations" con "permutations" per fare "andata e ritorno"
combinazioni = list(itertools.combinations(strategie_da_testare, 2))

# avvia lo script python e tournament_2 farà il parsing degli argomenti
def esegui_torneo(giocatori):
    rosso, blu = giocatori
    print(f"[AVVIO] {rosso} VS {blu}")
    subprocess.run([
        "python", "tournament_2.py",
        "--rosso", rosso,
        "--blu", blu,
        "--partite", NUM_PARTITE,
        "--timeout", TIMEOUT
    ])
    print(f"[FINE] {rosso} VS {blu}")

with concurrent.futures.ThreadPoolExecutor(max_workers=NUMERO_MASSIMO_TORNEI_IN_PARALLELO) as executor:
    executor.map(esegui_torneo, combinazioni)

print("TUTTI I TORNEI IN PARALLELO SONO FINITI!")