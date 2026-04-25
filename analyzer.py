import os
import glob
from collections import defaultdict

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns

    LIBRERIE_AVANZATE = True
except ImportError:
    LIBRERIE_AVANZATE = False

PATTERN_FILE = os.path.join("risultati", "*.csv")

def mostra_statistiche():
    if not LIBRERIE_AVANZATE:
        print("⚠️  Librerie avanzate non trovate!")
        print("Per una reportistica completa e grafici avanzati, apri il terminale e digita:")
        print("pip install pandas matplotlib seaborn\n")
        return

    file_trovati = glob.glob(PATTERN_FILE)
    if not file_trovati:
        print(f"Errore: Nessun file corrispondente a '{PATTERN_FILE}' trovato.")
        return

    print(f"📂 Sto analizzando {len(file_trovati)} file CSV...")

    # Carica tutti i file CSV in un unico DataFrame
    df_list = []
    for f in file_trovati:
        try:
            temp_df = pd.read_csv(f)
            df_list.append(temp_df)
        except Exception as e:
            print(f"Errore nella lettura di {f}: {e}")

    if not df_list:
        print("Nessun dato valido trovato nei file.")
        return

    df = pd.concat(df_list, ignore_index=True)

    # Assicuriamoci che ci siano le nuove colonne, altrimenti le riempiamo con 0 (retrocompatibilità)
    nuove_colonne = ["Media Turni", "Timeouts Rosso", "Timeouts Blu",
                     "Mosse Illegali Rosso", "Mosse Illegali Blu",
                     "Tempo Medio Mossa Rosso (s)", "Tempo Medio Mossa Blu (s)"]
    for col in nuove_colonne:
        if col not in df.columns:
            df[col] = 0.0

    # Dizionari per aggregare i dati
    stats_agenti = defaultdict(lambda: {
        'giocate': 0, 'vinte': 0, 'perse': 0, 'pareggi': 0,
        'timeouts': 0, 'illegali': 0, 'somma_tempo': 0.0
    })

    matchups = defaultdict(lambda: {
        'giocate': 0, 'vinte_A': 0, 'vinte_B': 0, 'pareggi': 0, 'somma_turni': 0.0
    })

    tot_tornei = len(df)
    tot_partite = df['Partite Giocate'].sum()

    # Iteriamo riga per riga per smistare i dati (poiché un agente può essere Rosso o Blu)
    for _, row in df.iterrows():
        r = row['Strategia Rosso']
        b = row['Strategia Blu']
        g = row['Partite Giocate']

        # Aggiornamento ROSSO
        stats_agenti[r]['giocate'] += g
        stats_agenti[r]['vinte'] += row['Vittorie Rosso']
        stats_agenti[r]['perse'] += row['Vittorie Blu']
        stats_agenti[r]['pareggi'] += row['Pareggi']
        stats_agenti[r]['timeouts'] += row['Timeouts Rosso']
        stats_agenti[r]['illegali'] += row['Mosse Illegali Rosso']
        stats_agenti[r]['somma_tempo'] += row['Tempo Medio Mossa Rosso (s)'] * g

        # Aggiornamento BLU
        stats_agenti[b]['giocate'] += g
        stats_agenti[b]['vinte'] += row['Vittorie Blu']
        stats_agenti[b]['perse'] += row['Vittorie Rosso']
        stats_agenti[b]['pareggi'] += row['Pareggi']
        stats_agenti[b]['timeouts'] += row['Timeouts Blu']
        stats_agenti[b]['illegali'] += row['Mosse Illegali Blu']
        stats_agenti[b]['somma_tempo'] += row['Tempo Medio Mossa Blu (s)'] * g

        # Aggiornamento Scontri Diretti
        strat_A, strat_B = sorted([r, b])
        chiave = f"{strat_A} VS {strat_B}"
        matchups[chiave]['giocate'] += g
        matchups[chiave]['pareggi'] += row['Pareggi']
        matchups[chiave]['somma_turni'] += row['Media Turni'] * g

        if r == strat_A:
            matchups[chiave]['vinte_A'] += row['Vittorie Rosso']
            matchups[chiave]['vinte_B'] += row['Vittorie Blu']
        else:
            matchups[chiave]['vinte_A'] += row['Vittorie Blu']
            matchups[chiave]['vinte_B'] += row['Vittorie Rosso']

    # --- REPORT TESTUALE ---
    print("\n" + "=" * 60)
    print(" 📊 REPORT STATISTICHE AVANZATE TORNEI ZOLA")
    print("=" * 60)
    print(f"Totale File Analizzati : {len(file_trovati)}")
    print(f"Totale Tornei/Righe    : {tot_tornei}")
    print(f"Totale Partite Giocate : {tot_partite}")
    print("-" * 60)

    # Preparazione dati per i DataFrame e i Grafici
    dati_agenti = []
    for agente, s in stats_agenti.items():
        wr = (s['vinte'] / s['giocate']) * 100 if s['giocate'] > 0 else 0
        t_medio = s['somma_tempo'] / s['giocate'] if s['giocate'] > 0 else 0
        err_totali = s['timeouts'] + s['illegali']
        dati_agenti.append({
            'Agente': agente,
            'Winrate (%)': wr,
            'Giocate': s['giocate'],
            'Timeouts': s['timeouts'],
            'Illegali': s['illegali'],
            'Errori Totali': err_totali,
            'Tempo Medio (s)': t_medio
        })

    df_agenti = pd.DataFrame(dati_agenti).sort_values(by='Winrate (%)', ascending=False)

    print(" 🏆 LEADERBOARD AGENTI (Ordinati per Winrate)")
    for _, row in df_agenti.iterrows():
        print(f"🤖 {row['Agente'].upper()}")
        print(f"   Winrate: {row['Winrate (%)']:.1f}% ({row['Giocate']} partite)")
        print(f"   Tempo medio per mossa: {row['Tempo Medio (s)']:.3f} s")
        print(f"   Errori critici: {row['Errori Totali']} (Timeouts: {row['Timeouts']}, Illegali: {row['Illegali']})\n")

    print("-" * 60)
    print(" ⚔️  SCONTRI DIRETTI & DINAMICHE DI GIOCO")
    for scontro, m in matchups.items():
        A, B = scontro.split(" VS ")
        wr_A = (m['vinte_A'] / m['giocate']) * 100
        wr_B = (m['vinte_B'] / m['giocate']) * 100
        turni_medi = m['somma_turni'] / m['giocate'] if m['giocate'] > 0 else 0

        print(f"🔸 {scontro} ({m['giocate']} partite)")
        print(f"   Durata media partita: {turni_medi:.1f} turni")
        print(f"   Vittorie: {A} [{wr_A:.1f}%] - {B} [{wr_B:.1f}%]")
        print()

    # --- GENERAZIONE GRAFICI CON SEABORN E MATPLOTLIB ---
    print("📈 Generazione grafici in corso...")
    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(16, 10))

    # 1. Winrate
    ax1 = plt.subplot(2, 2, 1)
    sns.barplot(x='Winrate (%)', y='Agente', data=df_agenti, palette='viridis', ax=ax1)
    ax1.set_title('Winrate Globale per Agente', fontweight='bold')
    ax1.set_xlim(0, 100)

    # 2. Tempi di Pensiero
    ax2 = plt.subplot(2, 2, 2)
    df_tempi = df_agenti.sort_values(by='Tempo Medio (s)')
    sns.barplot(x='Tempo Medio (s)', y='Agente', data=df_tempi, palette='magma', ax=ax2)
    ax2.set_title('Efficienza: Tempo Medio per Mossa', fontweight='bold')

    # 3. Errori e Affidabilità (Stacked)
    ax3 = plt.subplot(2, 2, 3)
    df_agenti_err = df_agenti.sort_values(by='Errori Totali', ascending=False)
    ax3.bar(df_agenti_err['Agente'], df_agenti_err['Timeouts'], label='Timeouts', color='coral')
    ax3.bar(df_agenti_err['Agente'], df_agenti_err['Illegali'], bottom=df_agenti_err['Timeouts'],
            label='Mosse Illegali', color='firebrick')
    ax3.set_title('Affidabilità: Errori Critici (Meno è meglio)', fontweight='bold')
    ax3.tick_params(axis='x', rotation=30)
    ax3.legend()

    # 4. Durata Media Partite (Turni)
    ax4 = plt.subplot(2, 2, 4)
    scontri_nomi = list(matchups.keys())
    turni_valori = [m['somma_turni'] / m['giocate'] if m['giocate'] > 0 else 0 for m in matchups.values()]
    sns.barplot(x=turni_valori, y=scontri_nomi, palette='Blues_r', ax=ax4)
    ax4.set_title('Durata Media Partite per Matchup (Turni)', fontweight='bold')

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    mostra_statistiche()