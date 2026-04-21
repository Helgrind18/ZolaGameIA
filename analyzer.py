import csv
import os
from collections import defaultdict

# Tentiamo di importare matplotlib per i grafici
try:
    import matplotlib.pyplot as plt
    import numpy as np

    GRAFICI_ABILITATI = True
except ImportError:
    GRAFICI_ABILITATI = False

FILE_RISULTATI = "statistiche_zola.csv"


def genera_grafici(stats_globali, scontri_diretti):
    """Genera e mostra i grafici a partire dalle statistiche calcolate."""

    # ---------------------------------------------------------
    # GRAFICO 1: Winrate Globale
    # ---------------------------------------------------------
    strategie = []
    winrates = []
    colori = []

    # Prepariamo i dati ordinati per winrate
    ordinate = sorted(stats_globali.items(),
                      key=lambda x: (x[1]['vinte'] / x[1]['giocate'] if x[1]['giocate'] > 0 else 0), reverse=True)

    for strat, dati in ordinate:
        strategie.append(strat)
        wr = (dati['vinte'] / dati['giocate']) * 100 if dati['giocate'] > 0 else 0
        winrates.append(wr)
        colori.append('skyblue' if wr > 50 else 'lightcoral')

    plt.figure(figsize=(10, 6))
    barre = plt.bar(strategie, winrates, color=colori, edgecolor='black')
    plt.title('Winrate Globale per Strategia', fontsize=14, fontweight='bold')
    plt.ylabel('Percentuale di Vittoria (%)', fontsize=12)
    plt.ylim(0, 105)
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Aggiungiamo i valori sopra le barre
    for rect in barre:
        altezza = rect.get_height()
        plt.text(rect.get_x() + rect.get_width() / 2.0, altezza + 1, f'{altezza:.1f}%', ha='center', va='bottom',
                 fontweight='bold')

    plt.tight_layout()

    # ---------------------------------------------------------
    # GRAFICO 2: Scontri Diretti (Stacked Bar Chart)
    # ---------------------------------------------------------
    matchups = []
    perc_A = []
    perc_B = []
    perc_pareggi = []

    for scontro, dati in scontri_diretti.items():
        g = dati['giocate']
        if g == 0: continue

        matchups.append(scontro)
        perc_A.append((dati['vinte_A'] / g) * 100)
        perc_B.append((dati['vinte_B'] / g) * 100)
        perc_pareggi.append((dati['pareggi'] / g) * 100)

    fig, ax = plt.subplots(figsize=(12, 7))

    # Creiamo le barre impilate
    p1 = ax.bar(matchups, perc_A, color='lightgreen', edgecolor='black', label='Vittorie Strategia A (Sinistra)')
    p2 = ax.bar(matchups, perc_B, bottom=perc_A, color='salmon', edgecolor='black',
                label='Vittorie Strategia B (Destra)')

    bottom_pareggi = [i + j for i, j in zip(perc_A, perc_B)]
    p3 = ax.bar(matchups, perc_pareggi, bottom=bottom_pareggi, color='lightgray', edgecolor='black', label='Pareggi')

    ax.set_title('Esito Scontri Diretti (Testa a Testa)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Distribuzione Esiti (%)', fontsize=12)
    ax.set_ylim(0, 105)
    ax.legend(loc='upper right', bbox_to_anchor=(1, 1.15), ncol=3)

    # Etichette diagonali per non farle accavallare
    plt.xticks(rotation=30, ha='right')

    plt.tight_layout()

    # Mostra entrambi i grafici
    plt.show()


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

                # Aggiorna Scontri Diretti (ordinamento alfabetico)
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

    # --- STAMPA DEL REPORT TESTUALE ---
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

    # --- CHIAMATA AI GRAFICI ---
    if GRAFICI_ABILITATI:
        print("📈 Apertura delle finestre con i grafici in corso...")
        genera_grafici(stats_globali, scontri_diretti)
    else:
        print("💡 SUGGERIMENTO: Vuoi vedere i grafici visuali?")
        print("   Apri il terminale e digita:")
        print("   pip install matplotlib numpy")
        print("   Quindi riavvia questo script.\n")


if __name__ == "__main__":
    mostra_statistiche()