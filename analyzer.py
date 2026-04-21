import csv
import os
from collections import defaultdict

FILE_RISULTATI = "statistiche_zola.csv"


def mostra_statistiche():
    if not os.path.exists(FILE_RISULTATI):
        print(f"Errore: Il file '{FILE_RISULTATI}' non esiste.")
        print("Esegui prima il file 'tournament.py' per generare dei dati.")
        return

    totale_tornei = 0
    totale_partite = 0
    tempo_totale = 0.0

    # Statistiche globali per ogni strategia: { 'giocate': 0, 'vinte': 0, 'perse': 0, 'pareggi': 0 }
    stats_globali = defaultdict(lambda: {'giocate': 0, 'vinte': 0, 'perse': 0, 'pareggi': 0})

    # Scontri diretti (Testa a Testa)
    scontri_diretti = defaultdict(lambda: {'giocate': 0, 'vinte_A': 0, 'vinte_B': 0, 'pareggi': 0})

    try:
        with open(FILE_RISULTATI, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                totale_tornei += 1

                rosso = row.get("Strategia Rosso", "Sconosciuto")
                blu = row.get("Strategia Blu", "Sconosciuto")
                giocate = int(row.get("Partite Giocate", 0))
                vinte_rosso = int(row.get("Vittorie Rosso", 0))
                vinte_blu = int(row.get("Vittorie Blu", 0))
                pareggi = int(row.get("Pareggi", 0))
                tempo = float(row.get("Tempo Totale (s)", 0.0))

                totale_partite += giocate
                tempo_totale += tempo

                # Aggiorna statistiche Rosso
                stats_globali[rosso]['giocate'] += giocate
                stats_globali[rosso]['vinte'] += vinte_rosso
                stats_globali[rosso]['perse'] += vinte_blu
                stats_globali[rosso]['pareggi'] += pareggi

                # Aggiorna statistiche Blu
                stats_globali[blu]['giocate'] += giocate
                stats_globali[blu]['vinte'] += vinte_blu
                stats_globali[blu]['perse'] += vinte_rosso
                stats_globali[blu]['pareggi'] += pareggi

                # Aggiorna Scontri Diretti (ordinamento alfabetico per raggruppare A vs B e B vs A)
                strat_A, strat_B = sorted([rosso, blu])
                chiave_scontro = f"{strat_A} VS {strat_B}"

                is_rosso_A = (rosso == strat_A)

                scontri_diretti[chiave_scontro]['giocate'] += giocate
                scontri_diretti[chiave_scontro]['pareggi'] += pareggi
                if is_rosso_A:
                    scontri_diretti[chiave_scontro]['vinte_A'] += vinte_rosso
                    scontri_diretti[chiave_scontro]['vinte_B'] += vinte_blu
                else:
                    scontri_diretti[chiave_scontro]['vinte_A'] += vinte_blu
                    scontri_diretti[chiave_scontro]['vinte_B'] += vinte_rosso

    except Exception as e:
        print(f"Errore durante la lettura del CSV: {e}")
        return

    if totale_partite == 0:
        print("Il file CSV è vuoto o non contiene dati validi.")
        return

    # --- STAMPA DEL REPORT ---
    print("\n" + "=" * 50)
    print(" 📊 REPORT STATISTICHE TORNEI ZOLA")
    print("=" * 50)
    print(f"Totale Tornei elaborati: {totale_tornei}")
    print(f"Totale Partite giocate : {totale_partite}")
    print(f"Tempo di calcolo totale: {tempo_totale:.2f} s")
    print(f"Tempo medio per partita: {(tempo_totale / totale_partite):.2f} s")

    print("\n" + "-" * 50)
    print(" 🏆 WINRATE GLOBALE (Tutte le partite)")
    print("-" * 50)

    # Ordiniamo le strategie per numero di vittorie decrescente
    strategie_ordinate = sorted(stats_globali.items(), key=lambda x: x[1]['vinte'], reverse=True)

    for strat, dati in strategie_ordinate:
        giocate = dati['giocate']
        vinte = dati['vinte']
        perse = dati['perse']
        winrate = (vinte / giocate) * 100 if giocate > 0 else 0

        print(f"🤖 {strat.upper()}")
        print(f"   Vittorie: {vinte} | Sconfitte: {perse} | Pareggi: {dati['pareggi']} | Partite: {giocate}")
        print(f"   Winrate : {winrate:.1f}%")
        print()

    print("-" * 50)
    print(" ⚔️  SCONTRI DIRETTI (Testa a Testa)")
    print("-" * 50)

    for scontro, dati in scontri_diretti.items():
        strat_A, strat_B = scontro.split(" VS ")
        vinte_A = dati['vinte_A']
        vinte_B = dati['vinte_B']
        giocate = dati['giocate']

        winrate_A = (vinte_A / giocate) * 100 if giocate > 0 else 0
        winrate_B = (vinte_B / giocate) * 100 if giocate > 0 else 0

        print(f"🔸 {scontro} ({giocate} partite)")
        print(f"   {strat_A}: {vinte_A} vittorie ({winrate_A:.1f}%)")
        print(f"   {strat_B}: {vinte_B} vittorie ({winrate_B:.1f}%)")
        if dati['pareggi'] > 0:
            print(f"   Pareggi: {dati['pareggi']}")
        print()

    print("=" * 50 + "\n")


if __name__ == "__main__":
    mostra_statistiche()