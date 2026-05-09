import subprocess
import itertools


strategie_da_testare = [
    "playerStrategyImplPasqualeRL",
    "playerStrategyImplPasqualeOG",
    "playerStrategyImplPasqualeRandom",
    "playerStrategyImplPasqualeMAX",
    "playerExampleAlphaImplGiuseppe",
    "GiuseppeImp2",
]


NUM_PARTITE = "20"
TIMEOUT = "3"
EPOCHE_DI_TRAINING = 5


tutte_le_combinazioni = list(itertools.product(strategie_da_testare, strategie_da_testare))

match_di_addestramento = [
    giocatori for giocatori in tutte_le_combinazioni
    if "playerStrategyImplPasqualeRL" in giocatori
]


def esegui_torneo(giocatori):
    rosso, blu = giocatori
    print(f"\n[START] {rosso} (ROSSO) VS {blu} (BLU)")
    subprocess.run([
        "python", "tournament_2.py",
        "--rosso", rosso,
        "--blu", blu,
        "--partite", NUM_PARTITE,
        "--timeout", TIMEOUT
    ])
    print(f"[END] {rosso} VS {blu}")


if __name__ == "__main__":
    print("=== AVVIO FASE DI ADDESTRAMENTO (REINFORCEMENT LEARNING) ===")
    print(f"Totale match per epoca: {len(match_di_addestramento)}")

    for epoca in range(1, EPOCHE_DI_TRAINING + 1):
        print(f"\n" + "=" * 40)
        print(f"  EPOCA DI TRAINING {epoca} / {EPOCHE_DI_TRAINING}")
        print("=" * 40)

        for giocatori in match_di_addestramento:
            esegui_torneo(giocatori)

    print("\n=== ADDESTRAMENTO COMPLETATO! ===")
    print("Controlla il file 'weights_rl.json' per vedere i pesi finali imparati dal tuo agente!")